import unittest


class MultiInstanceTests(unittest.TestCase):
    def test_duplicate_prediction_does_not_count_as_two_tables(self):
        from analysis.layout.multi_instance import score_instances
        truth={'desk#0':[0,0,1,1],'desk#1':[3,0,4,1]}
        pred={'desk#x':[0,0,1,1],'desk#y':[0,0,1,1]}
        r=score_instances(pred,truth)
        self.assertEqual((r['tp'],r['fp'],r['fn']),(1,1,1))
        self.assertFalse(r['all_instances_hit'])

    def test_instance_names_do_not_supply_the_matching(self):
        from analysis.layout.multi_instance import score_instances
        truth={'desk#0':[0,0,1,1],'desk#1':[3,0,4,1]}
        pred={'desk#0':[3,0,4,1],'desk#1':[0,0,1,1]}
        self.assertTrue(score_instances(pred,truth)['all_instances_hit'])

    def test_decoder_rejects_truth_identity_in_observations(self):
        from analysis.layout.multi_instance import decode_instances
        with self.assertRaises(ValueError):
            decode_instances([4,4],[],[{'object':'cab','pos':[1,1],'instance_id':'cab#1'}],[])

    def test_partial_assignment_patterns_survive_until_second_cabinet(self):
        from analysis.layout.multi_instance import diverse_beam
        states=[(float(i),3,{'a':i}) for i in range(20)]+[(100.,1,{'a':100}),(101.,2,{'a':101})]
        selected=diverse_beam(states,4)
        self.assertEqual({x[1] for x in selected},{1,2,3})

    def test_proposal_cache_preserves_the_selected_layout(self):
        from analysis.layout.multi_instance import decode_instances
        import numpy as np
        inventory=[{'id':'bed#0','category':'bed','dimensions':[1.,2.]},
                   {'id':'chair#0','category':'chair','dimensions':[.4,.4]}]
        events=[{'object':'chair','pos':[3.,3.]}]
        a=decode_instances([4,4],inventory,events,[])
        cache={};b=decode_instances([4,4],inventory,events,[],proposal_cache=cache)
        c=decode_instances([4,4],inventory,events,[],proposal_cache=cache)
        self.assertTrue(cache)
        self.assertEqual(a['status'],b['status'])
        for k in a['boxes']:
            np.testing.assert_array_equal(a['boxes'][k],b['boxes'][k])
            np.testing.assert_array_equal(a['boxes'][k],c['boxes'][k])
