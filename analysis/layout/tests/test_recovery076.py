"""Contract and mechanism regressions for the anchor-free decoder."""
import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch


def example(x=1.3):
    return {'schema': 'evidence076-v1', 'frame': 'declared-room',
            'room': [4., 5.], 'inventory': [{'category': 'chair', 'dimensions': [.45, .45]}],
            'events': [{'object': 'chair', 'pos': [x, 2.]}], 'walk': [],
            'desk_relation': False}


class Contract076Tests(unittest.TestCase):
    def test_input_rejects_truth_anchor_and_start(self):
        from analysis.layout.recovery076_data import prepare
        for key in ('truth', 'anchor', 'start', 'room_id'):
            with self.assertRaisesRegex(ValueError, 'Unexpected'):
                prepare({**example(), key: [0, 0]}, grid=12)

    def test_zero_contact_is_finite_and_has_no_learned_location(self):
        from analysis.layout.recovery076_data import prepare, pack
        from analysis.layout.recovery076_model import EvidenceDecoder076
        obs = example(); obs['events'] = []
        model = EvidenceDecoder076(width=32).eval()
        out = model(pack([prepare(obs, grid=12)]))
        self.assertTrue(torch.isfinite(out['log_prob']).all())
        self.assertLess(float(out['log_prob'][0, 0].std().detach()), 1e-6)

    def test_contact_can_move_prediction_more_than_anchor_radius(self):
        from analysis.layout.recovery076_data import prepare, pack
        from analysis.layout.recovery076_model import EvidenceDecoder076, decode
        model = EvidenceDecoder076(width=32).eval()
        centres = []
        for x in (1., 3.):
            b = pack([prepare(example(x), grid=20)])
            pred = decode(model(b), b)[0]
            centres.append(np.mean(np.asarray(pred['chair#0']).reshape(2, 2), axis=0))
        self.assertGreater(np.linalg.norm(centres[0] - centres[1]), 1.5)
        self.assertLess(abs(centres[0][0]-1.), .2)

    def test_contact_permutation_does_not_change_density(self):
        from analysis.layout.recovery076_data import prepare, pack
        from analysis.layout.recovery076_model import EvidenceDecoder076
        a=example(); a['events'] += [{'object':'chair','pos':[2.8,3.]}]
        b=copy.deepcopy(a); b['events'].reverse()
        model=EvidenceDecoder076(width=32).eval()
        x=model(pack([prepare(a, grid=12)]))['log_prob']
        y=model(pack([prepare(b, grid=12)]))['log_prob']
        torch.testing.assert_close(x,y)

    def test_source_tail_cannot_enter_selected_events(self):
        from analysis.layout.recovery076_data import observation_budget
        a=example(); a['events'] += [{'object':'chair','pos':[3.,4.]}]
        b=copy.deepcopy(a); b['events'][1]['pos']=[999.,999.]
        self.assertEqual(observation_budget(a,1),observation_budget(b,1))
        self.assertEqual(len(observation_budget(a,0)['events']),0)

    def test_outside_path_is_reported_not_clamped(self):
        from analysis.layout.recovery076_data import prepare
        a=example(); a['walk']=[[-1.,2.],[1.,2.]]
        p=prepare(a,grid=12)
        self.assertEqual(p['diagnostics']['outside_walk_fraction'], .5)
        self.assertEqual(p['observation']['walk'][0],[-1.,2.])

    def test_same_condition_counterfactuals_change_layout_not_inventory(self):
        from analysis.layout.recovery076_generate import draw_scene
        a,b=draw_scene(47,0),draw_scene(47,1)
        self.assertEqual(a['inventory'],b['inventory'])
        self.assertEqual([a['W'],a['L']],[b['W'],b['L']])
        self.assertFalse(all(np.allclose(a['gt'][k],b['gt'][k]) for k in a['gt']))
        self.assertTrue(all(len(a['gt'])==len(s['inventory']) for s in (a,b)))

    def test_manifest_rejects_group_and_fingerprint_leakage(self):
        from analysis.layout.recovery076_data import validate_manifest
        rows=[{'id':'a','group':'g','fingerprint':'f','split':'train'},
              {'id':'b','group':'g','fingerprint':'q','split':'test'}]
        with self.assertRaisesRegex(ValueError,'group'):
            validate_manifest({'schema':'manifest076-v1','rows':rows})
        rows[1].update(group='h',fingerprint='f')
        with self.assertRaisesRegex(ValueError,'fingerprint'):
            validate_manifest({'schema':'manifest076-v1','rows':rows})

    def test_loss_is_connected_to_learnable_evidence_not_truth_at_forward(self):
        from analysis.layout.recovery076_data import prepare, pack
        from analysis.layout.recovery076_model import EvidenceDecoder076, objective
        p=prepare(example(),grid=12); b=pack([p]); model=EvidenceDecoder076(width=32)
        out=model(b)
        loss=objective(out,b,[{'chair#0':[1.275,1.875,1.725,2.325]}])
        loss.backward()
        self.assertGreater(sum(float(v.grad.abs().sum()) for v in model.parameters() if v.grad is not None),0.)
        with self.assertRaisesRegex(ValueError,'Unexpected'):
            model({**b,'target':torch.zeros(1,1,2)})

    def test_static_prediction_is_serializable(self):
        import json
        from analysis.layout.recovery076_eval import static_decode
        json.dumps(static_decode(example(),unrestricted=True)['boxes'])

    def test_training_loader_does_not_open_test_files(self):
        from analysis.layout.recovery076_data import dump,sha,load_rows
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dump(root/'obs.json',example())
            dump(root/'target.json',{'boxes':{'chair#0':[1,1.7,1.45,2.15]}})
            train={'id':'a','group':'g','fingerprint':'f','split':'train','status':'ok',
                   'input':'obs.json','target':'target.json',
                   'input_sha256':sha(root/'obs.json'),'target_sha256':sha(root/'target.json')}
            test={**train,'id':'b','group':'h','fingerprint':'q','split':'test',
                  'input':'MUST_NOT_BE_OPENED.json','target':'MUST_NOT_BE_OPENED.json'}
            dump(root/'manifest.json',{'schema':'manifest076-v1','rows':[train,test]})
            rows=load_rows(root/'manifest.json',{'train'},grid=12)
            self.assertEqual([r['row']['id'] for r in rows],['a'])

    def test_joint_decode_does_not_collapse_two_chairs(self):
        from analysis.layout.recovery076_data import prepare,pack
        from analysis.layout.recovery076_model import EvidenceDecoder076,decode
        obs=example(1.);obs['inventory']*=2;obs['events']+=[{'object':'chair','pos':[3.,2.]}]
        batch=pack([prepare(obs,grid=20)]);model=EvidenceDecoder076(width=32).eval()
        boxes=decode(model(batch),batch)[0]
        centres=[np.asarray(b).reshape(2,2).mean(0) for b in boxes.values()]
        self.assertGreater(np.linalg.norm(centres[0]-centres[1]),1.5)

    def test_group_bootstrap_counts_conditions_not_budget_rows(self):
        from analysis.layout.recovery076_eval import surfaces
        rows=[]
        for group in ('g','h'):
            for copy in (0,1):
                for arm in ('learned','outline'):
                    rows.append({'id':group+str(copy),'group':group,'arm':arm,'coverage_target':.5,
                                 'contacts_requested':6,'usable':True,'whole_room':int(arm=='learned'),
                                 'whole_footprint':0,'f1':0.,'footprint_f1':0.})
        result=surfaces(rows,draws=100)['paired'][0]
        self.assertEqual(result['independent_condition_groups'],2)
        self.assertEqual(result['paired_rows'],4)
        self.assertEqual(surfaces(rows,draws=100)['overall_paired'][0]['condition_groups'],2)

    def test_new_confirmation_rejects_reused_geometry(self):
        from analysis.layout.recovery076_data import check_confirmation
        manifest={'schema':'manifest076-v1','rows':[{'id':'new','group':'new','fingerprint':'old','split':'confirmation'}]}
        with self.assertRaisesRegex(ValueError,'overlaps'):
            check_confirmation(manifest,[],['old'])

    def test_joint_rotation_transforms_targets_and_candidates_consistently(self):
        from analysis.layout.recovery076_data import prepare,pack
        from analysis.layout.recovery076_model import EvidenceDecoder076,objective
        from analysis.layout.recovery076_augment import rotate_batch
        batch=pack([prepare(example(),grid=12)])
        truth=[{'chair#0':[1.075,1.775,1.525,2.225]}]
        model=EvidenceDecoder076(width=32).eval()
        a=objective(model(batch),batch,truth)
        b,t=rotate_batch(batch,truth,1)
        torch.testing.assert_close(a,objective(model(b),b,t))

    def test_same_condition_contact_swap_moves_prediction_and_keeps_recipient_truth(self):
        from analysis.layout.recovery076_data import prepare,pack
        from analysis.layout.recovery076_model import EvidenceDecoder076,decode
        from analysis.layout.recovery076_eval import score,contact_swap_diagnostic
        model=EvidenceDecoder076(width=32).eval();entries=[];original=[]
        for i,x in enumerate((1.,3.)):
            sample=prepare(example(x),grid=20);truth={'chair#0':[x-.225,1.775,x+.225,2.225]}
            meta={'id':str(i),'group':'g','fingerprint':str(i),'coverage_target':.5,'contacts_requested':1}
            entries.append({'row':meta,'sample':sample,'truth':truth})
            b=pack([sample]);s=score(decode(model(b),b)[0],truth)
            original.append({**meta,**s,'boxes':decode(model(b),b)[0],'usable':True,'arm':'learned'})
        result=contact_swap_diagnostic(model,entries,original)
        swapped=[r for r in result['rows'] if r['arm']=='paired_contact_swap']
        self.assertEqual(result['paired_recipients'],2)
        self.assertEqual(sum(r['whole_room'] for r in original),2)
        self.assertEqual(sum(r['whole_room'] for r in swapped),0)
        first=next(r for r in swapped if r['id']=='0')
        self.assertGreater(np.asarray(first['boxes']['chair#0']).reshape(2,2).mean(0)[0],2.7)

if __name__=='__main__':unittest.main()
