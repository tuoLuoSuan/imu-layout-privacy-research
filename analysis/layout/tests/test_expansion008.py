import json,tempfile,unittest
from pathlib import Path


class Expansion008Tests(unittest.TestCase):
    def test_ambiguity_distance_ignores_label_swaps_and_uses_bottleneck_matching(self):
        from analysis.layout.permutation_witness import bottleneck_layout_distance,witness
        a={'desk#0':[0,0,.1,.1],'desk#1':[.6,0,.7,.1]}
        swapped={'desk#1':a['desk#0'],'desk#0':a['desk#1']}
        b={'desk#0':[1.2,0,1.3,.1],'desk#1':[.6,0,.7,.1]}
        self.assertEqual(bottleneck_layout_distance(a,swapped),0.)
        self.assertAlmostEqual(bottleneck_layout_distance(a,b),.6)
        self.assertFalse(witness(a,b,.5)['certified'])

    def test_stored_desk_witness_does_not_use_named_slot_distance_as_a_bound(self):
        import numpy as np
        from analysis.layout.selection_diagnostics import desk_witness
        layout={'desk#0':[0,0,.1,.1],'desk#1':[.6,0,.7,.1]}
        result=desk_witness(layout,{'desk#0':np.array([[0,0,.1,.1],[1.2,0,1.3,.1]])})
        self.assertNotIn('separation_m',result)

    def test_known_family_sampler_needs_no_target_coordinates(self):
        from analysis.layout.known_family_prior import sample_family
        import numpy as np
        inventory=[{'id':c+'#'+str(i),'category':c,'dimensions':d} for c,n,d in [('bed',1,[1.2,2.]),('desk',2,[.6,1.5]),('cab',2,[.5,1.]),('chair',2,[.44,.44])] for i in range(n)]
        samples=sample_family([4.,7.],inventory,seed=1)
        self.assertTrue(samples)
        for sample in samples:
            self.assertEqual(len(sample),7)
            self.assertTrue(all(np.all(b[:2]>=0) and np.all(b[2:]<=[4.,7.]) for b in sample.values()))

    def test_execution_failure_accounting_keeps_successful_rooms(self):
        from analysis.layout.expansion_report import ledger_label,footprint_all
        self.assertEqual(ledger_label({'executable':True,'status':'ok','score':{'all_instances_hit':True}}),'all_centres_hit')
        self.assertEqual(ledger_label({'executable':True,'status':'proposal_conflict'}),'retained_proposals_joint_conflict')
        self.assertTrue(footprint_all({'desk#0':[3,0,4,1],'desk#1':[0,0,1,1]},{'desk#0':[0,0,1,1],'desk#1':[3,0,4,1]}))

    def test_direction_channel_does_not_grant_true_instance_identity(self):
        import numpy as np
        from analysis.layout.desk_channel_audit import add_bearings
        pools={'desk#0':(np.array([[1.,0.,2.,1.],[-2.,0.,-1.,1.]]),np.zeros(2,dtype=np.uint64),np.zeros(2))}
        out,targets=add_bearings(pools,[],[{'pos':[0.,.5],'bearing':[1.,0.]}],max_distance=2.)
        self.assertEqual(out['desk#0'][1].tolist(),[1,0])
        with self.assertRaises(ValueError):add_bearings(pools,[],[{'pos':[0.,.5],'bearing':[1.,0.],'instance_id':'desk#0'}])

    def test_regression_deltas_name_their_baseline(self):
        from analysis.layout.exp_real_regression import baseline_comparison
        current={'rot_deg':170.,'boxes':{'bed':[1.,2.,3.,4.]}}
        legacy={'rot_deg':171.,'boxes':{'bed':[1.07,2.,3.,4.]}}
        result=baseline_comparison(current,current,'verified_replay')
        older=baseline_comparison(current,legacy,'historical_snapshot')
        self.assertEqual(result['max_coordinate_delta_m']['bed'],0.)
        self.assertAlmostEqual(older['max_coordinate_delta_m']['bed'],.07)
        self.assertNotEqual(result['baseline_id'],older['baseline_id'])

    def test_oracle_uses_the_same_classwise_permutation_as_scoring(self):
        import numpy as np
        from analysis.layout.exp_candidate_audit import matched_oracle_search
        inventory=[{'id':'cab#0'},{'id':'cab#1'}]
        truth={'cab#0':[0,0,1,1],'cab#1':[3,0,4,1]}
        pools={'cab#0':(np.array([[3.,0.,4.,1.]]),np.zeros(1,dtype=np.uint64),np.zeros(1)),
               'cab#1':(np.array([[0.,0.,1.,1.]]),np.zeros(1,dtype=np.uint64),np.zeros(1))}
        result=matched_oracle_search(inventory,pools,[],{},truth)
        self.assertTrue(result['all_hit'])
        self.assertEqual(result['matching']['cab#0'],'cab#1')

    def test_additional_seeds_keep_new_ids_and_balanced_inventory(self):
        from analysis.layout.simple_rooms import prepare_multi
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            sizes={'Bed':(1.2,.6,2.),'Desk':(.6,.7,1.65),'Dresser':(.5,1.2,1.),'Chair':(.45,.8,.45)}
            assets={k:[{'assetId':k+'-test','boundingBox':dict(zip(['x','y','z'],v))}] for k,v in sizes.items()}
            (p/'assets.json').write_text(json.dumps(assets))
            (p/'template.json').write_text(json.dumps({'rooms':[{'floorMaterial':{'name':'Wood'}}],'proceduralParameters':{}}))
            result=prepare_multi(p/'assets.json',p/'template.json',p/'out',n=8,seed=61110000,start_index=1000,split_override='confirmation')
            self.assertEqual(result['rows'][0]['house_id'],'multi-01000')
            self.assertEqual({r['source_split'] for r in result['rows']},{'confirmation'})
            self.assertEqual(set(result['inventory_patterns_bed_desk_storage_chair'].values()),{1})
            self.assertEqual([r['seed'] for r in result['rows']],list(range(61110000,61110008)))


if __name__=='__main__':unittest.main()
