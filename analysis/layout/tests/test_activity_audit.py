import unittest
import numpy as np


class ActivityAuditTests(unittest.TestCase):
    def test_bootstrap_resamples_whole_rooms_together(self):
        from analysis.layout.activity_audit import bootstrap_means
        values=np.array([[0.,0.],[1.,1.],[.25,.25]])
        samples=bootstrap_means(values,draws=100,seed=1)
        np.testing.assert_array_equal(samples[:,0],samples[:,1])
        self.assertTrue(np.all((samples>=0)&(samples<=1)))

    def test_paired_binary_comparison_keeps_discordant_rooms(self):
        from analysis.layout.activity_audit import paired_binary
        result=paired_binary([1,1,0,0],[1,0,1,1])
        self.assertEqual(result['a_only'],1)
        self.assertEqual(result['b_only'],2)
        self.assertEqual(result['both'],1)
        self.assertEqual(result['neither'],0)
        self.assertAlmostEqual(result['b_minus_a'],.25)
        self.assertAlmostEqual(result['mcnemar_exact_two_sided_p'],1.)

    def test_proposal_oracle_cannot_reuse_one_instance(self):
        from analysis.layout.exp_candidate_audit import proposal_bound
        pools={'desk#0':np.array([[0.,0.,1.,1.]])}
        truth={'desk#0':[0.,0.,1.,1.],'desk#1':[0.,0.,1.,1.]}
        result=proposal_bound(pools,truth)
        self.assertEqual(result['desk']['tp'],1)
        self.assertEqual(result['desk']['n_truth'],2)

    def test_witness_requires_separation_and_physical_compatibility(self):
        from analysis.layout.selection_diagnostics import desk_witness
        base={'desk#0':[0,0,1,1],'cab#0':[3,0,4,1]}
        # The only distant alternative overlaps the fixed cabinet.
        self.assertNotIn('separation_m',desk_witness(base,{'desk#0':np.array([[0,0,1,1],[3,0,4,1]])}))
        got=desk_witness(base,{'desk#0':np.array([[0,0,1,1],[0,3,1,4]])})
        self.assertAlmostEqual(got['conditional_minimax_error_lower_m'],1.5)

    def test_joint_selection_improves_on_first_feasible_cost(self):
        from analysis.layout.selection_diagnostics import minimum_cost_search
        from analysis.layout.multi_instance import _constraint_search
        inventory=[{'id':'cab#0'},{'id':'desk#0'}]
        pools={'cab#0':(np.array([[0,0,1,1],[3,0,4,1]]),np.zeros(2,dtype=np.uint64),np.array([0.,1.])),
               'desk#0':(np.array([[0,0,1,1],[0,3,1,4]]),np.zeros(2,dtype=np.uint64),np.array([0.,10.]))}
        first=_constraint_search(inventory,pools,[],{})
        best=minimum_cost_search(inventory,pools,[],{})
        self.assertEqual(first['boxes']['cab#0'][0],0)
        self.assertEqual(best['boxes']['cab#0'][0],3)
        self.assertAlmostEqual(best['objective'],1.)
        self.assertTrue(best['candidate_objective_optimal'])

    def test_repeat_control_keeps_class_counts_but_not_new_locations(self):
        from analysis.layout.multi_instance import event_sequence
        scene={'W':5,'L':5,'gt':{'bed#0':np.array([3,3,4,5]),'cab#0':np.array([0,0,.5,1]),'chair#0':np.array([1,1,1.5,1.5])}}
        path=np.array([(x,y) for x in np.linspace(0,5,40) for y in np.linspace(0,5,40)])
        a=event_sequence(scene,path,14);b=event_sequence(scene,path,14,mode='repeat')
        self.assertEqual([e['object'] for e in a],[e['object'] for e in b])
        unique=lambda es:len({(e['object'],*e['pos']) for e in es})
        self.assertGreater(unique(a),unique(b))
        self.assertEqual(unique(b),3)

    def test_contact_permissions_and_cache_keys_respect_the_observation_model(self):
        from analysis.layout.multi_instance import decode_instances
        inventory=[{'id':'chair#0','category':'chair','dimensions':[.4,.4]}]
        events=[{'object':'chair','pos':[1.,1.]}];cache={}
        strict=decode_instances([2,2],inventory,events,[[1,1]],proposal_cache=cache,contact_padding=0.)
        allowed=decode_instances([2,2],inventory,events,[[1,1]],proposal_cache=cache,contact_padding=0.,walk_excluded_objects=())
        self.assertIn(strict['status'],('no_proposals','proposal_conflict'))
        self.assertEqual(allowed['status'],'ok')


if __name__=='__main__':unittest.main()
