import unittest
import numpy as np
from scipy.spatial.transform import Rotation


class Inertial010Tests(unittest.TestCase):
    def test_repeated_stationary_gravity_updates_do_not_lose_the_tail(self):
        from analysis.layout.inertial010 import replay
        fs=60.;t=np.arange(0,600,1/fs)
        # Constant unknown mounting plus many slow, known test rotations.
        angle=.7*np.sin(2*np.pi*t/30)
        pitch=.4*np.sin(2*np.pi*t/45)
        # Rotation only in the first 2 s of each 5 s block, then rest.
        j=(t//5)*5;u=np.clip((t-j)/2,0,1);u=u**3*(10-15*u+6*u*u)
        a0=np.c_[.2*np.sin(j/31),.3*np.sin(j/29),.7*np.sin(j/27)]
        a1=np.c_[.2*np.sin((j+5)/31),.3*np.sin((j+5)/29),.7*np.sin((j+5)/27)]
        R=Rotation.from_euler('xyz',a0+(a1-a0)*u[:,None]).as_matrix()
        dR=np.gradient(R,1/fs,axis=0);B=np.einsum('nji,njk->nik',R,dR)
        G=np.c_[B[:,2,1]-B[:,1,2],B[:,0,2]-B[:,2,0],B[:,1,0]-B[:,0,1]]/2
        rng=np.random.default_rng(8);G+=rng.normal(0,.003,G.shape)+[.0005,-.0004,.0003]
        A=np.einsum('nji,j->ni',R,[0.,0.,9.81])+rng.normal(0,.035,(len(t),3))+[.02,-.01,.03]
        path,att,info=replay(t,A,G)
        self.assertTrue(info['stationary_mask'][-60:].all())
        self.assertLess(np.linalg.norm(path[-1]),.20)
        gravity=np.einsum('nij,nj->ni',att,A-info['accelerometer_bias'])
        self.assertLess(np.linalg.norm(gravity[-60:].mean(axis=0)-[0,0,9.81]),.03)
        self.assertFalse(info['causal'])
        self.assertFalse(info['known_distance_scale'])

    def test_acceleration_variance_alone_does_not_label_walking_as_rest(self):
        from analysis.layout.inertial010 import rest_mask
        t=np.arange(0,20,1/60)
        A=np.tile([0.,0.,9.81],(len(t),1));G=np.zeros_like(A)
        moving=(t>5)&(t<15);A[moving,2]+=1.5*np.sin(2*np.pi*1.4*t[moving])
        mask=rest_mask(t,A,G)
        self.assertLess(mask[(t>6)&(t<14)].mean(),.01)
        self.assertGreater(mask[t<4].mean(),.95)

    def test_slow_handset_rotation_is_not_a_zero_angular_rate_sample(self):
        from analysis.layout.inertial010 import rest_mask
        t=np.arange(0,10,1/60);A=np.tile([0.,0.,9.81],(len(t),1));G=np.tile([0.,0.,.02],(len(t),1))
        self.assertFalse(rest_mask(t,A,G).any())

    def test_declared_closed_loop_uses_only_start_equals_end_constraint(self):
        from analysis.layout.inertial010 import close_loop
        t=np.array([0.,1.,2.]);path=np.array([[0.,0.],[1.3,.1],[.6,.2]])
        np.testing.assert_allclose(close_loop(t,path),[[0.,0.],[1.,0.],[0.,0.]],atol=1e-12)
        np.testing.assert_array_equal(path,[[0.,0.],[1.3,.1],[.6,.2]])


if __name__=='__main__':unittest.main()
