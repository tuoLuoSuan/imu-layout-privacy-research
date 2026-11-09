import unittest
import numpy as np


class GaitFitTests(unittest.TestCase):
    def test_template_is_stationary_outside_the_motion_interval(self):
        from analysis.layout.gait_fit011 import template
        from analysis.layout.sim_motion import U_UP
        t=np.array([-1.,-.5,3.5,4.]);a,g=template(t,1.,3.,.4,.5,1.)
        up=np.asarray(U_UP['walk']);up=up/np.linalg.norm(up)
        np.testing.assert_allclose(a,np.tile(9.81*up,(len(t),1)),atol=1e-10);np.testing.assert_allclose(g,0.,atol=1e-10)

    def test_raw_template_distance_is_recovered_without_a_position_input(self):
        from analysis.layout.gait_fit011 import template,fit
        t=np.arange(-.3,4.4,1/120);a,g=template(t,1.25,4.,.7,.5,1.);rng=np.random.default_rng(12);a+=rng.normal(0,.035,a.shape)+[.02,-.01,.03];g+=rng.normal(0,.003,g.shape)+[.0005,-.0004,.0003]
        result=fit(t,a,g,1.15)
        self.assertLess(abs(result['distance_m']-1.25),.06)


if __name__=='__main__':unittest.main()
