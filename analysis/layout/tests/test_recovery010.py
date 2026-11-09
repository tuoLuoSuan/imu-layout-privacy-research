import unittest
from unittest.mock import patch
import numpy as np
from analysis.layout import multi_instance as M


class Recovery010Tests(unittest.TestCase):
    def test_prior_is_applied_before_candidate_limit(self):
        # A valid wall candidate must survive even when an interior cluster
        # would consume the complete finite proposal budget.
        xy=np.c_[np.linspace(2,7,129),np.full(129,4.)]
        boxes=np.vstack([np.c_[xy,xy+[.6,1.2]],[.1,4.,.7,5.2]])
        seen=[]
        def keep(entry,bank,room):seen.append(len(bank));return bank[:,0]<.2
        with patch.object(M,'_proposals',return_value=(boxes,{'point_m':np.array([5.,5.])})):
            r=M.decode_instances([10.,10.],[{'id':'desk#0','category':'desk','dimensions':[.6,1.2]}],[],np.empty((0,2)),candidate_limit=4,proposal_filter=keep)
        self.assertEqual(seen,[130]);self.assertEqual(r['status'],'ok')
        np.testing.assert_allclose(r['boxes']['desk#0'],[.1,4.,.7,5.2])

    def test_empty_strict_prior_never_silently_relaxes(self):
        with patch.object(M,'_proposals',return_value=(np.array([[2.,2.,2.6,3.2]]),{'point_m':np.array([2.,2.])})):
            r=M.decode_instances([5.,5.],[{'id':'desk#0','category':'desk','dimensions':[.6,1.2]}],[],np.empty((0,2)),proposal_filter=lambda *_:np.array([False]))
        self.assertEqual(r['status'],'no_proposals');self.assertEqual(r['boxes'],{})

    def test_depth_wall_prior_does_not_accept_a_desk_touching_only_its_short_end(self):
        from analysis.layout.recovery010 import wall_mask
        boxes=np.array([[.1,1.,.7,2.2],[2.,.1,2.6,1.3]])
        np.testing.assert_array_equal(wall_mask(boxes,[5.,5.],.15,False),[True,True])
        np.testing.assert_array_equal(wall_mask(boxes,[5.,5.],.15,True),[True,False])

    def test_continuous_prior_is_intersected_before_sampling_points(self):
        # Filtering sampled points cannot invent the missing0.10..0.15 band.
        # Intersecting the continuous domain first must sample that band.
        entry={'id':'desk#0','category':'desk','dimensions':[.6,1.2]}
        bank,_=M._proposals([5.,5.],entry,[],np.empty((0,2)),.2,
                           region_prior=lambda *_:np.array([[.10,1.,.15,1.2]]))
        self.assertGreater(len(bank),0)
        self.assertTrue(np.all(bank[:,0]>=.10-1e-10))
        self.assertTrue(np.all(bank[:,0]<=.15+1e-10))
        self.assertTrue(np.any(np.isclose(bank[:,0],.125)))

    def test_portfolio_falls_back_on_solver_failure_without_target_positions(self):
        from analysis.layout.recovery010 import solve
        bank=np.array([[2.,.1,2.6,1.3]])
        with patch.object(M,'_proposals',return_value=(bank,{'point_m':np.array([2.,1.])})):
            r=solve([5.,5.],[{'id':'desk#0','category':'desk','dimensions':[.6,1.2]}],[],np.empty((0,2)),policy='depth_portfolio')
        self.assertEqual(r['status'],'ok');self.assertTrue(r['fallback_used'])
        self.assertEqual(r['attempts'][0]['status'],'no_proposals')

    def test_declared_contact_bound_is_used_in_continuous_proposals(self):
        inv=[{'id':'bed#0','category':'bed','dimensions':[2.,1.]}]
        ev=[{'object':'bed','pos':[1.,2.]},{'object':'bed','pos':[3.5,2.]}]
        r=M.decode_instances([6.,6.],inv,ev,np.empty((0,2)),contact_padding=.3,walk_excluded_objects=())
        self.assertEqual(r['status'],'ok')


if __name__=='__main__':unittest.main()
