"""Inference adapter contracts, independent of walking labels or trained accuracy."""
import importlib.util, math, tempfile, unittest
from pathlib import Path
import numpy as np

AVAILABLE=importlib.util.find_spec('analysis.phone_ronin.adapter') is not None
if AVAILABLE:
    from analysis.phone_ronin.adapter import (prepare_features, make_windows,
        integrate_centers, rotate_batch, write_result, checked_file)

class Availability(unittest.TestCase):
    def test_inference_adapter_exists(self):
        self.assertTrue(AVAILABLE, 'Independent pretrained inference adapter is missing')

@unittest.skipUnless(AVAILABLE, 'adapter not implemented')
class Contracts(unittest.TestCase):
    def test_quaternion_rotation_and_norm(self):
        q=np.array([[math.sqrt(.5),0,0,math.sqrt(.5)]])
        r=rotate_batch(q,np.array([[1.,0,2.]]))
        np.testing.assert_allclose(r,[[0,1,2]],atol=1e-12)
        self.assertAlmostEqual(float(np.linalg.norm(r)),math.sqrt(5))

    def test_channel_order_and_gravity_retained(self):
        a=[(i*.01,0,0,9.80665) for i in range(251)]
        g=[(i*.01,0,0,.2) for i in range(251)]
        t,f,info=prepare_features(a,g)
        np.testing.assert_allclose(f[:,0:2],0,atol=1e-9)
        np.testing.assert_allclose(f[:,2],.2,atol=1e-7)
        np.testing.assert_allclose(f[:,3:5],0,atol=1e-9)
        np.testing.assert_allclose(f[:,5],9.80665,atol=1e-6)
        self.assertEqual(info['features'],['gyro_x','gyro_y','gyro_z','accel_x','accel_y','accel_z'])
        np.testing.assert_allclose(np.diff(t),.005,atol=1e-14)

    def test_overlap_no_extrapolation(self):
        a=[(i*.01,0,0,9.80665) for i in range(401)]
        g=[(.003+i*.01,0,0,0) for i in range(401)]
        t,_,_=prepare_features(a,g)
        self.assertGreaterEqual(t[0],.003)
        self.assertLessEqual(t[-1],4.)

    def test_gap_rejected(self):
        bad=[(0,0,0,9.80665),(2,0,0,9.80665)]
        with self.assertRaisesRegex(ValueError,'gap'):
            prepare_features(bad,bad)

    def test_no_overlap_rejected(self):
        a=[(0,0,0,9.80665),(.1,0,0,9.80665)]
        g=[(2,0,0,0),(2.1,0,0,0)]
        with self.assertRaisesRegex(ValueError,'overlap'):
            prepare_features(a,g)

    def test_strided_windows_match_author_start_indices(self):
        t=np.arange(421)/200; f=np.arange(421*6).reshape(421,6).astype(float)
        windows,timing=make_windows(t,f)
        self.assertEqual(windows.shape,(23,6,200))
        np.testing.assert_array_equal(windows[1],f[10:210].T)
        np.testing.assert_allclose(timing[0],[0,1,.5])
        np.testing.assert_allclose(timing[-1],[1.1,2.1,1.6])

    def test_short_or_irregular_grid_rejected(self):
        with self.assertRaises(ValueError):make_windows(np.arange(200)/200,np.zeros((200,6)))
        with self.assertRaises(ValueError):make_windows(np.arange(401)/100,np.zeros((401,6)))

    def test_center_integration_constant_velocity_and_turn(self):
        times=np.array([.5,.55,.6])
        positions=integrate_centers(times,np.array([[2.,0],[2.,0],[0,2.]]))
        np.testing.assert_allclose(positions,[[0,0],[.1,0],[.15,.05]],atol=1e-14)
        with self.assertRaises(ValueError):integrate_centers(times,np.full((3,2),np.nan))

    def test_output_exclusive_and_guarded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); out=root/'fresh'
            t=np.arange(4)/20+.5; vel=np.ones((4,2));pos=integrate_centers(t,vel)
            report={'status':'adapted_inference_only','accuracy_validated':False}
            write_result(out,report,t,vel,pos,allowed_root=root)
            before={p.name:p.read_bytes() for p in out.iterdir()}
            with self.assertRaises(FileExistsError):write_result(out,report,t,vel,pos,allowed_root=root)
            self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir()})
            with self.assertRaises(ValueError):write_result(root.parent/'escape',report,t,vel,pos,allowed_root=root)

    def test_identity_mismatch_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'invalid.pt';p.write_bytes(b'not a checkpoint')
            with self.assertRaisesRegex(ValueError,'SHA256'):checked_file(p,'0'*64)

if __name__=='__main__':unittest.main()
