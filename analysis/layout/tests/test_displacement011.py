import unittest
import numpy as np
from scipy.spatial.transform import Rotation


class Displacement011Tests(unittest.TestCase):
    def test_features_have_no_absolute_yaw_or_room_coordinate(self):
        from analysis.layout.displacement011 import segment_features
        from analysis.layout.sim_motion import basis_from_up,U_UP
        t=np.arange(0,3,1/120);A=np.tile([6.7,-6.8,-.6],(len(t),1));G=np.zeros_like(A)
        R=np.tile(basis_from_up(U_UP['stand']),(len(t),1,1));path=np.c_[t,t*.1];bias=np.zeros(3)
        a=segment_features(t,A,G,R,path,bias,0,len(t)-1)
        Q=Rotation.from_euler('z',1.2).as_matrix();RR=Q@R;qq=path@Q[:2,:2].T+[15.,-7.]
        b=segment_features(t,A,G,RR,qq,bias,0,len(t)-1)
        self.assertEqual(set(a),set(b));np.testing.assert_allclose(list(a.values()),list(b.values()),atol=1e-9)
        self.assertFalse(any(s in k for k in a for s in ['scene','label','truth','instance']))

    def test_static_cores_retain_each_detected_short_stop(self):
        from analysis.layout.displacement011 import cores
        t=np.arange(0,10,.01);mask=((t<2)|((t>4)&(t<5))|(t>7))
        out=cores(t,mask)
        self.assertTrue(out[450]);self.assertFalse(out[410]);self.assertTrue(out[100]);self.assertTrue(out[850])

    def test_dominant_heading_regularizer_is_yaw_equivariant_and_preserves_length(self):
        from analysis.layout.displacement011 import dominant_headings
        angle=np.radians([.3,-.4,90.2,89.8,180.1,179.7,45.]);d=np.c_[np.cos(angle),np.sin(angle)]
        a=dominant_headings(d);phi=.8;Q=np.array([[np.cos(phi),-np.sin(phi)],[np.sin(phi),np.cos(phi)]])
        np.testing.assert_allclose(dominant_headings(d@Q.T),a@Q.T,atol=1e-10)
        np.testing.assert_allclose(np.linalg.norm(a,axis=1),1.,atol=1e-10)
        np.testing.assert_allclose(a[-1],d[-1])


if __name__=='__main__':unittest.main()
