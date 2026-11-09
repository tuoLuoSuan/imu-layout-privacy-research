import unittest
import numpy as np
from scipy.spatial.transform import Rotation


class GaugeTests(unittest.TestCase):
    def test_identical_motion_in_different_gauges_stays_identical_when_blended(self):
        from analysis.layout.pose_gauge011 import blend
        p=np.array([[0.,0.],[1.,.3],[1.,1.]]);r=Rotation.from_euler('z',np.array([.1,.3,.5])[:,None]).as_matrix();Q=Rotation.from_euler('z',1.1).as_matrix();q=p@Q[:2,:2].T+[4,7];s=Q@r
        path,att=blend(p,r,q,s,.5)
        np.testing.assert_allclose(path,p,atol=1e-10);np.testing.assert_allclose(att,r,atol=1e-10)

    def test_rotation_uses_the_short_arc_across_pi(self):
        from analysis.layout.pose_gauge011 import blend
        p=np.zeros((2,2));a=Rotation.from_euler('z',np.array([0,170])[:,None],degrees=True).as_matrix();b=Rotation.from_euler('z',np.array([0,-170])[:,None],degrees=True).as_matrix();_,r=blend(p,a,p,b,.5)
        self.assertAlmostEqual(abs(Rotation.from_matrix(r[1]).as_euler('xyz',degrees=True)[2]),180.)


if __name__=='__main__':unittest.main()
