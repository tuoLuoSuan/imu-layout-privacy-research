"""Shared-contract rawIMU bridge with separate calibration and oracle arms.

Twenty one-instance scenes are fixed before generation, four development and
sixteen confirmation. This is an additional phone-only controlled protocol;
it neither replaces the legacy real replay nor modifies10000-room geometry.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks
from scipy.spatial.transform import Rotation
from . import multi_instance as M,action_model as AM,paths
from .contact_contract import CONTRACT,body_axis,contacts_from_runs,decode,distance_scale
from .sim_handset import generate
from .simulation_validation import physical_report
from .synthetic_bridge import write_input,frozen_inference
from analysis.phone_pdr.carry_diagnostic import orientation_trace
from .inertial_replay import estimate as zupt_estimate,rest_attitude
from .sim_watch import generate as generate_watch,write as write_watch
from .watch_cabinet import detect as detect_watch,fuse as fuse_watch
from analysis.phone_ronin.adapter import make_windows,predict,integrate_centers


def estimated_attitude(session):
    ch=AM.load_phone(session);ta,A,_=ch['accelerometer'];tg,G,_=ch['gyroscope']
    trace=orientation_trace([(float(t),*map(float,x)) for t,x in zip(ta,A)],[(float(t),*map(float,x)) for t,x in zip(tg,G)])
    q=np.array([r['quaternion'] for r in trace]);R=Rotation.from_quat(np.c_[q[:,1:],q[:,0]]).as_matrix()
    return tg,R,A,G


def rotations_at(t,source_time,R):
    # Interpolate headings through rotations rather than averaging Euler yaw.
    from scipy.spatial.transform import Slerp
    return Slerp(source_time,Rotation.from_matrix(R))(np.clip(t,source_time[0],source_time[-1])).as_matrix()


def step_path(t,A,R,stride):
    world=np.einsum('nij,nj->ni',R,A);vertical=world[:,2]
    # No action labels/true motion passed into this detector.
    peaks,_=find_peaks(vertical,prominence=.5,distance=max(1,int(.30/np.median(np.diff(t)))))
    headings=body_axis(R,'walk');pos=np.zeros((len(t),2));delta=np.zeros_like(pos)
    for index in peaks:
        near=peaks[(peaks!=index)&(abs(t[peaks]-t[index])<2.)]
        if not len(near):continue
        delta[index]=headings[index]*stride
    pos=np.cumsum(delta,axis=0)
    return pos,peaks


def rest_ronin(t,A,G,R):
    grid=t[0]+np.arange(int(np.floor((t[-1]-t[0])*200))+1)/200
    world=np.concatenate([np.einsum('nij,nj->ni',R,G),np.einsum('nij,nj->ni',R,A)],axis=1)
    features=np.c_[*[np.interp(grid,t,world[:,j]) for j in range(6)]].astype(np.float32)
    windows,wt=make_windows(grid,features);v,_=predict(windows,paths.RONIN_ARCH,paths.RONIN_CKPT,hashlib.sha256(Path(paths.RONIN_CKPT).read_bytes()).hexdigest())
    return wt[:,2],integrate_centers(wt[:,2],v)


def action_metrics(gen,actions):
    truth=[];pred=[]
    for w in actions['windows']:
        i=min(int(round(w['center_s']*gen['fs'])),len(gen['t'])-1);truth.append(str(gen['truth']['label'][i]));pred.append(w['label'])
    return {c:{'n_true':sum(k==c for k in truth),'n_pred':sum(k==c for k in pred),
       'recall':sum(a==b==c for a,b in zip(truth,pred))/max(1,sum(a==c for a in truth))} for c in ['walk','seated','lying','cabinet','other']}


def run_case(scene,out,seed,calibration):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);session=out/'input';gen=generate(scene,seed);write_input(session,gen)
    truth=gen['truth'];wrist=generate_watch(gen,seed+300);write_watch(session,wrist)
    np.savez_compressed(out/'evaluation-truth.npz',time=gen['t'],position=truth['pos'],rotation=truth['R'],labels=truth['label'],watch_time=wrist['t'],watch_position=wrist['truth']['pos'],watch_rotation=wrist['truth']['R'])
    time,xy,actions,legacy,info=frozen_inference(session);native_time,R,A,G=estimated_attitude(session);estR=rotations_at(time,native_time,R)
    true_xy=np.c_[np.interp(time,gen['t'],truth['pos'][:,0]),np.interp(time,gen['t'],truth['pos'][:,1])];trueR=rotations_at(time,gen['t'],truth['R'])
    oracle_runs=[[label,a,b] for a,b,label in truth['segments']];truth_boxes={k.split('#')[0]:b for k,b in scene['gt'].items()}
    sizes={k:sorted(b[2:]-b[:2]) for k,b in truth_boxes.items()};actual_length=float(np.linalg.norm(np.diff(true_xy,axis=0),axis=1).sum());pred_length=float(np.linalg.norm(np.diff(xy,axis=0),axis=1).sum())
    pdr_native,peaks=step_path(native_time,A,R,calibration['pdr_stride_m']);pdr=np.c_[np.interp(time,native_time,pdr_native[:,0]),np.interp(time,native_time,pdr_native[:,1])]
    zupt_native,zupt_info=zupt_estimate(native_time,A,G,R);zupt=np.c_[np.interp(time,native_time,zupt_native[:,0]),np.interp(time,native_time,zupt_native[:,1])]
    restR=rest_attitude(native_time,A,G);restRt=rotations_at(time,native_time,restR)
    rt,rx=rest_ronin(native_time,A,G,restR);rest_model_path=np.c_[np.interp(time,rt,rx[:,0]),np.interp(time,rt,rx[:,1])]
    calibrated_native,calibrated_info=zupt_estimate(native_time,A,G,restR);calibrated_path=np.c_[np.interp(time,native_time,calibrated_native[:,0]),np.interp(time,native_time,calibrated_native[:,1])]
    watch_detection=detect_watch(wrist['t'],wrist['acc'],phone=(native_time,A,G));joint=fuse_watch(actions,watch_detection)
    (session/'watch-actions.json').write_text(json.dumps(watch_detection,indent=1),encoding='utf-8')
    arms=[('truth_pose_truth_actions',true_xy,trueR,oracle_runs),('ronin_truth_actions',xy,estR,oracle_runs),
          ('oracle_scaled_ronin_truth_actions',xy*(actual_length/pred_length),estR,oracle_runs),
          ('independent_scaled_ronin_truth_actions',xy*calibration['ronin_scale'],estR,oracle_runs),
          ('independent_scaled_ronin_predicted_actions',xy*calibration['ronin_scale'],estR,actions['runs']),
          ('pdr_truth_actions',pdr,estR,oracle_runs),('pdr_predicted_actions',pdr,estR,actions['runs']),
          ('zupt_truth_actions',zupt,estR,oracle_runs),('zupt_predicted_actions',zupt,estR,actions['runs']),
          ('rest_zupt_truth_actions',calibrated_path,restRt,oracle_runs),('rest_zupt_predicted_actions',calibrated_path,restRt,actions['runs']),
          ('rest_zupt_joint_actions',calibrated_path,restRt,joint['runs']),
          ('independent_scaled_ronin_joint_actions',xy*calibration['ronin_scale'],estR,joint['runs']),
          ('rest_ronin_truth_actions',rest_model_path,restRt,oracle_runs),
          ('calibrated_rest_ronin_truth_actions',rest_model_path*calibration['rest_ronin_scale'],restRt,oracle_runs),
          ('calibrated_rest_ronin_joint_actions',rest_model_path*calibration['rest_ronin_scale'],restRt,joint['runs'])]
    result=[]
    for name,path,attitude,runs in arms:
        contacts=contacts_from_runs(time,path,attitude,runs);walk=np.zeros(len(time),bool)
        for label,a,b in runs:
            if label=='walk':walk|=(time>=a)&(time<=b)
        prediction=decode([scene['W'],scene['L']],scene['S'],path,contacts,sizes,walk)
        score=M.score_instances(prediction['boxes'],truth_boxes)
        result.append({'arm':name,'oracle_assisted':'truth' in name or name.startswith('oracle'),'prediction':prediction,'score':score})
    record={'scene':scene['scene'],'seed':seed,'duration_s':float(gen['t'][-1]),'physics':physical_report(gen),
       'frontend':{'path_ratio':pred_length/actual_length,'path_m':pred_length,'truth_device_path_m':actual_length,'pdr_path_m':float(np.linalg.norm(np.diff(pdr,axis=0),axis=1).sum()),'detected_steps':len(peaks)},
       'actions':action_metrics(gen,actions),'predicted_runs':actions['runs'],'watch_runs':watch_detection['runs'],'watch_sample_rate_hz':wrist['fs'],'cabinet_source_in_joint':'watch_accelerometer_with_phone_quiet_gate','legacy_unadapted_status':legacy['status'],'zupt':zupt_info,'rest_zupt':calibrated_info,'rows':result}
    (out/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8');print(json.dumps({'scene':scene['scene'],'physical':record['physics']['passed'],'path_ratio':record['frontend']['path_ratio'],'tp':{r['arm']:r['score']['tp'] for r in result},'action_recall':{k:v['recall'] for k,v in record['actions'].items()}}),flush=True)
    return record


def calibrate(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);session=out/'input';gen=generate(None,seed=901,calibration=True);write_input(session,gen)
    time,xy,actions,_,_=frozen_inference(session);start,end,_=gen['truth']['segments'][1];selected=(time>=start+.5)&(time<=end-.5)
    # The endpoints and10m distance are marked in this separate calibration
    # episode. No room-truth distance or per-room fitted scale is used here.
    scale=distance_scale(xy[selected],10.);t,R,A,G=estimated_attitude(session);pdr,peaks=step_path(t,A,R,1.)
    mask=(t>=start)&(t<=end);step_length=float(np.linalg.norm(np.diff(pdr[mask],axis=0),axis=1).sum());stride=10/step_length
    rt,rx=rest_ronin(t,A,G,rest_attitude(t,A,G));selected=(rt>=start+.5)&(rt<=end-.5);rs=distance_scale(rx[selected],10.)
    record={'reference_distance_m':10.,'ronin_scale':scale,'rest_ronin_scale':rs,'pdr_stride_m':stride,'calibration_seed':901,'independent_layout_episode':True,'window':[start,end],'motion_contract':CONTRACT,'physics':physical_report(gen),'scope':'Known-distance instrument calibration, not a no-aid attack or per-room oracle fit'}
    (out/'calibration.json').write_text(json.dumps(record,indent=1),encoding='utf-8');print(json.dumps(record),flush=True);return record


def run(native,out,phase='dev'):
    native,out=map(Path,(native,out));out.mkdir(parents=True,exist_ok=True);ids=[f'multi-{i:05d}' for i in range(0,160,8)]
    freeze=out/'protocol.json'
    if not freeze.exists():
        protocol={'ids':ids,'development':ids[:4],'confirmation':ids[4:],'contract':CONTRACT,'models_frozen':True,'phone_only':False,'watch':'three-axis acceleration16.7Hz, no gyro; cabinet ONLY from wrist with raw-phone stillness gate','gate':'truth pose and truth actions first; all4 centres within0.5m','inputs':'Raw phone6axis and watch3axis CSV; evaluation truth separate; common simulated clock','source_sha256':{n:hashlib.sha256(Path(__file__).with_name(n+'.py').read_bytes()).hexdigest() for n in ['sim_handset','sim_watch','watch_cabinet','contact_contract','inertial_replay','bridge009']}}
        freeze.write_text(json.dumps(protocol,indent=1),encoding='utf-8')
    calibration_file=out/'calibration/calibration.json';cal=calibrate(out/'calibration') if not calibration_file.exists() else json.loads(calibration_file.read_text())
    selected=ids[:4] if phase=='dev' else ids[4:];rows=[]
    for i,name in enumerate(selected):
        target=out/name;f=target/'results.json'
        rows.append(json.loads(f.read_text(encoding='utf-8')) if f.exists() else run_case(M.load_native(native/(name+'.json')),target,seed=9001+ids.index(name),calibration=cal))
    result={'phase':phase,'n_rooms':len(rows),'calibration':cal,'summary':{arm:{'all_centres_hit':sum(r['score']['all_instances_hit'] for q in rows for r in q['rows'] if r['arm']==arm),'f1':float(np.mean([r['score']['f1'] for q in rows for r in q['rows'] if r['arm']==arm]))} for arm in [r['arm'] for r in rows[0]['rows']]},'rows':rows}
    (out/(phase+'-summary.json')).write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--phase',choices=['dev','confirm'],default='dev');a=p.parse_args();run(a.native,a.out,a.phase)
