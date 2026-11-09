import unittest
import numpy as np


class ContactLoopsTests(unittest.TestCase):
    def test_repeated_unknown_seat_is_a_loop_constraint_not_a_given_position(self):
        from analysis.layout.contact_loops011 import optimize
        t=np.arange(0,31.);q=np.c_[t*.03,np.zeros(len(t))]
        obs=[{'class':'chair','time':10.,'point':[.3,0.]},{'class':'chair','time':20.,'point':[.6,0.]}]
        corrected,info=optimize(t,q,obs,{'chair':1,'cab':0})
        self.assertLess(abs(corrected[20,0]-corrected[10,0]),.15)
        np.testing.assert_array_equal(corrected[0],q[0]);self.assertFalse(info['given_furniture_position'])

    def test_cabinet_plane_closure_does_not_collapse_tangent_motion(self):
        from analysis.layout.contact_loops011 import optimize
        t=np.arange(0,31.);q=np.c_[t*.03,t*.2]
        obs=[{'class':'cab','time':10.,'point':[.3,2.],'normal':[1.,0.]},{'class':'cab','time':20.,'point':[.6,4.],'normal':[1.,0.]}]
        corrected,_=optimize(t,q,obs,{'chair':0,'cab':1})
        self.assertLess(abs(corrected[20,0]-corrected[10,0]),.25)
        self.assertAlmostEqual(corrected[20,1]-corrected[10,1],2.,places=6)


if __name__=='__main__':unittest.main()
