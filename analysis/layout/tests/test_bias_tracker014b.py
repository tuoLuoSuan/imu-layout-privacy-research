import unittest
import numpy as np
from analysis.layout.bias_tracker014b import calibrate,gated_gyro


class GatedBiasTests(unittest.TestCase):
    def test_no_drift_evidence_preserves_original_signal_exactly(self):
        t=np.arange(0,20,.02);a=np.tile([0.,0.,9.81],(len(t),1));g=np.tile([.0005,0.,0.],(len(t),1))
        _,out,info=gated_gyro(t,a,g)
        self.assertFalse(info['gyro_correction_applied'])
        np.testing.assert_array_equal(out,g)

    def test_known_initial_hold_does_not_absorb_a_later_yaw_turn(self):
        t=np.arange(0,20,.02);a=np.tile([0.,0.,9.81],(len(t),1));g=np.tile([.002,0.,0.],(len(t),1))
        g[(t>=6)&(t<11),2]+=.08
        _,out,info=calibrate(t,a,g)
        self.assertGreater(np.mean(out[(t>7)&(t<10),2]),.07)


if __name__=='__main__':unittest.main()
