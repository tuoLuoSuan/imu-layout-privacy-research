"""Synthetic files and clocks only; never contacts ROS, a VM or a device."""
import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bag_check import inspect_bag
from capture_reference import WindowGate, exit_status


class BagTests(unittest.TestCase):
    def fixture(self, root, imu_times=(100, 200, 300), imu_type='sensor_msgs/msg/Imu'):
        (root/'metadata.yaml').write_text('synthetic_only: true\n')
        with closing(sqlite3.connect(root/'bag_0.db3')) as db, db:
            db.executescript('CREATE TABLE topics(id INTEGER,name TEXT,type TEXT);'
                             'CREATE TABLE messages(id INTEGER PRIMARY KEY,topic_id INTEGER,timestamp INTEGER,data BLOB);')
            db.executemany('INSERT INTO topics VALUES(?,?,?)',[(1,'/livox/lidar','sensor_msgs/msg/PointCloud2'),(2,'/livox/imu',imu_type)])
            for topic, times in [(1,(1_000_000_000,1_100_000_000,1_200_000_000)),(2,imu_times)]:
                db.executemany('INSERT INTO messages(topic_id,timestamp,data) VALUES(?,?,?)',[(topic,t,b'SYNTHETIC') for t in times])

    def test_topic_rates_use_own_intervals_and_preserve_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.fixture(root)
            before=(root/'bag_0.db3').read_bytes();r=inspect_bag(root)
            self.assertEqual(r['record_structure'],'pass')
            self.assertEqual(r['topics']['/livox/lidar']['mean_interarrival_rate_hz'],10)
            self.assertEqual(r['topics']['/livox/imu']['mean_interarrival_rate_hz'],10_000_000)
            self.assertEqual(r['geometry_quality'],'not_assessed')
            self.assertEqual(before,(root/'bag_0.db3').read_bytes())

    def test_empty_imu_is_not_success(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.fixture(root,imu_times=())
            self.assertEqual(inspect_bag(root)['record_structure'],'fail')

    def test_wrong_type_and_reversed_clock_are_not_success(self):
        for times,kind in [((300,200,100),'sensor_msgs/msg/Imu'),((100,200),'wrong/Type')]:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as t:
                root=Path(t);self.fixture(root,times,kind)
                self.assertEqual(inspect_bag(root)['record_structure'],'fail')

    def test_missing_input_is_not_created_and_unsealed_is_not_pass(self):
        with tempfile.TemporaryDirectory() as t:
            missing=Path(t)/'absent'
            with self.assertRaises(ValueError):inspect_bag(missing)
            self.assertFalse(missing.exists())
            self.fixture(Path(t));(Path(t)/'metadata.yaml').unlink()
            self.assertEqual(inspect_bag(Path(t))['record_structure'],'fail')


class WindowTests(unittest.TestCase):
    def test_both_topics_are_required_and_readiness_starts_new_clock(self):
        g=WindowGate(0,duration_s=2,ready_timeout_s=10,max_silence_s=1)
        g.observe('/livox/lidar',3_000_000_000)
        self.assertEqual(g.state(4_000_000_000),'waiting')
        g.observe('/livox/imu',4_000_000_000)
        self.assertEqual(g.ready_ns,4_000_000_000)
        self.assertEqual(g.state(4_000_000_000),'recording')
        for n in range(4,7):
            for topic in g.topics:g.observe(topic,n*1_000_000_000)
        self.assertEqual(g.state(6_000_000_000),'complete')

    def test_silence_and_startup_timeout_fail(self):
        g=WindowGate(0,ready_timeout_s=3)
        self.assertEqual(g.state(3_000_000_001),'failed')
        self.assertEqual(g.failure,'ready_timeout')
        g=WindowGate(0,duration_s=2,max_silence_s=1)
        for topic in g.topics:g.observe(topic,1)
        self.assertEqual(g.state(2_000_000_002),'failed')
        self.assertEqual(g.failure,'topic_silence')

    def test_positive_wrapper_code_does_not_invent_signal(self):
        self.assertEqual(exit_status(-11)['signal'],11)
        self.assertIsNone(exit_status(245)['signal'])
        self.assertFalse(exit_status(245)['graceful'])

    def test_late_ready_callback_cannot_erase_startup_timeout(self):
        g=WindowGate(0,ready_timeout_s=3)
        for topic in g.topics:g.observe(topic,3_000_000_001)
        self.assertEqual(g.state(3_000_000_001),'failed')
        self.assertEqual(g.failure,'ready_timeout')

    def test_resumed_callbacks_do_not_hide_a_delivery_gap(self):
        g=WindowGate(0)
        for topic in g.topics:g.observe(topic,1)
        for topic in g.topics:g.observe(topic,2_000_000_002)
        self.assertEqual(g.state(2_000_000_002),'failed')

    def test_default_plan_has_no_writes_or_ros_import_requirement(self):
        with tempfile.TemporaryDirectory() as t:
            target=Path(t)/'not-created'
            p=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'capture_reference.py'),
                              '--driver-executable','missing-driver','--config','missing-config',
                              '--output',str(target)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertFalse(json.loads(p.stdout)['executed'])
            self.assertFalse(target.exists())


if __name__=='__main__':unittest.main()
