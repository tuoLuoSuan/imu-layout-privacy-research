import unittest
import numpy as np
from analysis.layout.bias_tracker014 import calibrate


class BiasTrackerTests(unittest.TestCase):
    def test_zero_rate_bias_does_not_hide_a_stable_initial_hold(self):
        t=np.arange(0,20,.02);a=np.tile([0.,0.,9.81],(len(t),1));g=np.tile([.025,-.02,.01],(len(t),1))
        aa,gg,info=calibrate(t,a,g)
        self.assertGreater(info['rest_samples'],len(t)*.8)
        self.assertLess(np.max(abs(gg)),1e-6)
        np.testing.assert_allclose(aa,a,atol=1e-6)

    def test_recurrent_stable_pose_tracks_accelerometer_drift(self):
        t=np.arange(0,80,.02);a=np.tile([0.,0.,9.81],(len(t),1));a[:,0]+=.002*t
        g=np.c_[.0003*t,np.zeros((len(t),2))]
        aa,gg,info=calibrate(t,a,g)
        self.assertLess(np.ptp(aa[100:-100,0]),.025)
        self.assertLess(np.max(abs(gg[100:-100])),.001)

    def test_nonincreasing_sensor_clock_is_rejected(self):
        with self.assertRaises(ValueError):calibrate([0.,0.,1.],np.zeros((3,3)),np.zeros((3,3)))


if __name__=='__main__':unittest.main()
