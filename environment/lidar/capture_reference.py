"""Bounded reference capture. Default is a write-free plan, never hardware execution.

Ubuntu hardware path requires --execute, normal user, sourced ROS, explicit driver,
config and NEW output directory. This new path still requires VM/device acceptance.
"""
import argparse
import gc
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from bag_check import TOPICS, digest, inspect_bag


class WindowGate:
    topics=tuple(TOPICS)

    def __init__(self,start_ns,duration_s=15,ready_timeout_s=10,max_silence_s=1):
        self.start_ns=start_ns;self.duration_ns=int(duration_s*1e9)
        self.ready_timeout_ns=int(ready_timeout_s*1e9);self.max_silence_ns=int(max_silence_s*1e9)
        self.first={};self.last={};self.counts={t:0 for t in self.topics};self.ready_ns=None;self.failure=None

    def observe(self,topic,now_ns):
        if topic not in self.topics:raise ValueError('Unexpected topic')
        if self.ready_ns is None and now_ns-self.start_ns>self.ready_timeout_ns:self.failure='ready_timeout'
        if topic in self.last and now_ns<self.last[topic]:self.failure='observer_clock_reversed'
        if topic in self.last and self.ready_ns is not None and now_ns-self.last[topic]>self.max_silence_ns:
            self.failure='topic_silence'
        self.first.setdefault(topic,now_ns);self.last[topic]=now_ns;self.counts[topic]+=1
        if self.ready_ns is None and len(self.first)==len(self.topics):self.ready_ns=now_ns

    def state(self,now_ns):
        if self.failure:return 'failed'
        if self.ready_ns is None:
            if now_ns-self.start_ns>self.ready_timeout_ns:self.failure='ready_timeout';return 'failed'
            return 'waiting'
        if any(now_ns-v>self.max_silence_ns for v in self.last.values()):
            self.failure='topic_silence';return 'failed'
        return 'complete' if now_ns-self.ready_ns>=self.duration_ns else 'recording'


def exit_status(returncode):
    return {'returncode':returncode,'signal':-returncode if returncode is not None and returncode<0 else None,
            'graceful':returncode==0,'interpretation':'direct POSIX child status; positive wrapper codes are not decoded'}


def stop_owned(child):
    actions=[]
    for sig,timeout in [(signal.SIGINT,10),(signal.SIGTERM,4),(signal.SIGKILL,2)]:
        if child.poll() is not None:break
        actions.append(sig.name);os.killpg(child.pid,sig)
        try:child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:continue
    try:os.killpg(child.pid,0);group_remains=True
    except ProcessLookupError:group_remains=False
    return {**exit_status(child.poll()),'stop_actions':actions,'owned_group_remains':group_remains}


def run(args,plan):
    if os.name!='posix':raise ValueError('Hardware execution requires Ubuntu/POSIX.')
    if os.geteuid()==0:raise ValueError('Run as the normal research user, not root.')
    driver=Path(args.driver_executable).resolve(strict=True);config=Path(args.config).resolve(strict=True)
    output=Path(args.output).absolute()
    if output.exists():raise ValueError('Output must be a new directory.')
    if not driver.is_file() or not os.access(driver,os.X_OK):raise ValueError('Driver must be an executable file.')
    config_bytes=config.read_bytes();json.loads(config_bytes)
    # Importing this module and printing a plan never imports or initializes ROS.
    import rclpy
    from rclpy.signals import SignalHandlerOptions
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.serialization import serialize_message
    from sensor_msgs.msg import PointCloud2,Imu
    import rosbag2_py

    existing=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            if (proc/'exe').resolve().name==driver.name:existing.append(int(proc.name))
        except (OSError,RuntimeError):pass
    if existing:raise ValueError(f'Existing driver processes left untouched: {existing}')
    output.mkdir(parents=True,exist_ok=False)
    (output/'driver-config-snapshot.json').write_bytes(config_bytes)
    report={**plan,'executed':True,'execution_verified_on_device':False,'geometry_quality':'not_assessed',
            'config_sha256_before':digest(config),'capture_window':'incomplete','errors':[]}
    child=node=writer=None;initialized=False;gate=None
    try:
        os.environ['ROS_DOMAIN_ID']='91';os.environ['ROS_LOCALHOST_ONLY']='1'
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO);initialized=True
        node=rclpy.create_node('imu_reference_recorder',enable_rosout=False)
        writer=rosbag2_py.SequentialWriter()
        writer.open(rosbag2_py.StorageOptions(uri=str(output/'bag'),storage_id='sqlite3'),
                    rosbag2_py.ConverterOptions('',''))
        for name,kind in TOPICS.items():
            writer.create_topic(rosbag2_py.TopicMetadata(name=name,type=kind,serialization_format='cdr'))
        gate=WindowGate(time.monotonic_ns(),args.seconds)

        def callback(topic,msg):
            try:
                gate.observe(topic,time.monotonic_ns())
                writer.write(topic,serialize_message(msg),time.time_ns())
            except Exception as e:
                gate.failure='callback_or_write_failure';report['errors'].append(repr(e))

        subscriptions=[]
        for topic,kind in [('/livox/lidar',PointCloud2),('/livox/imu',Imu)]:
            subscriptions.append(node.create_subscription(kind,topic,lambda msg,t=topic:callback(t,msg),qos_profile_sensor_data))
        command=[str(driver),'--ros-args','-p','xfer_format:=0','-p','multi_topic:=0',
                 '-p','data_src:=0','-p','publish_freq:=10.0','-p','output_data_type:=0',
                 '-p','frame_id:=livox_frame','-p','user_config_path:='+str(config)]
        report['driver_command']=command;report['driver_executable_sha256']=digest(driver)
        with (output/'driver.log').open('xb') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            while gate.state(time.monotonic_ns()) not in ('complete','failed'):
                if child.poll() is not None:gate.failure='driver_exited_before_window_end';break
                rclpy.spin_once(node,timeout_sec=0.05)
            report['capture_window']='complete' if gate.state(time.monotonic_ns())=='complete' else 'fail'
    except BaseException as e:
        report['errors'].append(repr(e))
    finally:
        # Destroy callbacks, then the writer (Humble closes on destruction), before stopping the driver.
        if node is not None:
            try:node.destroy_node()
            except Exception as e:report['errors'].append('destroy_node: '+repr(e))
        writer=None;gc.collect();report['writer_release_monotonic_ns']=time.monotonic_ns()
        if initialized:
            try:rclpy.shutdown()
            except Exception as e:report['errors'].append('shutdown: '+repr(e))
        if child is not None:
            try:report['driver_exit']=stop_owned(child)
            except Exception as e:report['errors'].append('stop_owned: '+repr(e))
        if gate:
            report['observer']={'first_ns':gate.first,'last_ns':gate.last,'counts':gate.counts,
                'ready_ns':gate.ready_ns,'deadline_ns':None if gate.ready_ns is None else gate.ready_ns+gate.duration_ns,
                'failure':gate.failure,'max_silence_s':1,'ready_timeout_s':10}
        report['config_unchanged']=digest(config)==report['config_sha256_before']
        try:report['bag_check']=inspect_bag(output/'bag')
        except Exception as e:report['errors'].append('bag_check: '+repr(e))
        report['driver_shutdown']='pass' if report.get('driver_exit',{}).get('graceful') and not report['driver_exit']['owned_group_remains'] else 'fail'
        report['artifact_sha256']={p.relative_to(output).as_posix():digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
        (output/'capture-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if (report['capture_window']=='complete' and report.get('bag_check',{}).get('record_structure')=='pass'
                 and report['driver_shutdown']=='pass' and report['config_unchanged'] and not report['errors']) else 2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver-executable',required=True);parser.add_argument('--config',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--seconds',type=int,choices=range(5,61),default=15)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    plan={'schema_version':1,'executed':False,'requested_window_s':args.seconds,'driver_executable':args.driver_executable,
          'config':args.config,'output':args.output,'ros_domain_id':91,'localhost_only':True,
          'time_semantics':'host realtime record timestamps; original ROS headers preserved, device clock unvalidated',
          'readiness':'both topics received, max startup 10s, observed silence >1s fails',
          'storage':'CDR messages including readiness warmup and possible final spin tail; no interpolation or trimming',
          'qos':'ROS sensor_data best effort; no claim of lossless UDP or complete sensor delivery',
          'hardware_acceptance':'not_run'}
    if not args.execute:print(json.dumps(plan,indent=2));return 0
    return run(args,plan)


if __name__=='__main__':raise SystemExit(main())
