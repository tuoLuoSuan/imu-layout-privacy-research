import unittest
import numpy as np
import torch

from analysis.layout.recovery076_data import prepare,pack
from analysis.layout.recovery077_model import CandidateScorer077
from analysis.layout.recovery077_runtime import decode_fast


def example():
    return {'schema':'evidence076-v1','frame':'declared-room','room':[4.,5.],
            'inventory':[{'category':'chair','dimensions':[.45,.45]}]*2,
            'events':[{'object':'chair','pos':[1.,2.]},{'object':'chair','pos':[3.,2.]}],
            'walk':[[.5,.5],[.5,1.]],'desk_relation':False}


class Recovery078Tests(unittest.TestCase):
    def test_f1_fallback_preserves_partial_hits_when_all_candidates_fail(self):
        from analysis.layout.train078 import ranking_loss_f1
        scores=torch.zeros(1,2,requires_grad=True)
        output={'scores':scores,'residual':scores};batch={'hyp_valid':torch.ones(1,2,dtype=torch.bool)}
        labels={'whole':torch.zeros(1,2),'footprint':torch.zeros(1,2),'f1':torch.tensor([[.9,.5]]),
            'dmax':torch.tensor([[4.,.6]]),'mean_error':torch.tensor([[1.,.4]]),'mean_iou':torch.tensor([[.5,.4]])}
        ranking_loss_f1(output,batch,labels).backward()
        self.assertLess(float(scores.grad[0,0]),float(scores.grad[0,1]))

    def test_validation_guard_rejects_f1_regression(self):
        from analysis.layout.train078 import choose_strength
        metrics={s:{'whole_count':10,'footprint_count':3,'f1':.5,'footprint_rate':.3} for s in (0.,.25,.5,.75,1.)}
        metrics[1.].update(whole_count=12,f1=.49)
        metrics[.5].update(whole_count=11,f1=.51)
        self.assertEqual(choose_strength(metrics,max_f1_drop=0.,max_footprint_drop=0.),.5)
    def test_specialist_routes_by_observed_contact_count_with_exact_fallback(self):
        from analysis.layout.recovery078_runtime import predict
        from analysis.layout.recovery078_model import LayoutRanker078
        teacher=CandidateScorer077();obs=example();obs['events']=obs['events'][:1]
        b=pack([prepare(obs,12)]);saved={'strength':1.,'protocol':{'candidate_protocol':{'args':{
            'candidates':16,'beam':8,'max_layouts':24,'analytic':True,'only_cell':'1,2'}}}}
        result=predict(obs,LayoutRanker078(width=32),saved,teacher,{'grid':12,'score_strength':1.})
        self.assertEqual(result['route'],'frozen077_other_contact_count')
        self.assertEqual(result['boxes'],decode_fast(teacher(b),b,16,8)[0])
        config=saved['protocol']['candidate_protocol']['args'];config.pop('only_cell');config['only_contacts']=2
        again=predict(obs,LayoutRanker078(width=32),saved,teacher,{'grid':12,'score_strength':1.})
        self.assertEqual(again['boxes'],result['boxes'])
        self.assertEqual(again['contact_specialization'],2)
    def test_observation_only_runtime_keeps_baseline_at_zero_strength(self):
        from analysis.layout.recovery078_runtime import predict
        from analysis.layout.recovery078_model import LayoutRanker078
        teacher=CandidateScorer077();obs=example();b=pack([prepare(obs,12)])
        saved={'strength':0.,'protocol':{'candidate_protocol':{'args':{
            'candidates':16,'beam':8,'max_layouts':24,'analytic':True}}}}
        result=predict(obs,LayoutRanker078(width=32),saved,teacher,{'grid':12,'score_strength':1.})
        self.assertEqual(result['boxes'],decode_fast(teacher(b),b,16,8)[0])
        with self.assertRaisesRegex(ValueError,'Unexpected'):
            predict({**obs,'target':{}},LayoutRanker078(width=32),saved,teacher,{'grid':12})
    def test_analytic_proposals_project_to_declared_grid_without_targets(self):
        from analysis.layout.recovery078_candidates import hypotheses,with_analytic_proposals,as_boxes
        obs=example();b=pack([prepare(obs,12)]);o=CandidateScorer077()(b);h=hypotheses(o,b,16,8)
        raw={'chair#0':[.75,1.75,1.2,2.2],'chair#1':[2.75,1.75,3.2,2.2]}
        a=with_analytic_proposals(h,b,o,raw,max_layouts=32)
        self.assertEqual(as_boxes(a,0),as_boxes(h,0))
        for slot,j in enumerate(a['slots']):
            np.testing.assert_allclose(a['boxes'][:,slot,:2],
                b['centres'][0,j,a['indices'][:,slot]].numpy()-b['sizes'][0,j,a['indices'][:,slot]].numpy()/2)
        with self.assertRaisesRegex(ValueError,'complete'):
            with_analytic_proposals(h,b,o,{'chair#0':raw['chair#0']})
    def test_sampled_search_is_deterministic_and_preserves_fallback(self):
        from analysis.layout.recovery078_candidates import sampled_hypotheses,as_boxes
        obs=example();obs['inventory'].append({'category':'desk','dimensions':[1.2,.6]})
        b=pack([prepare(obs,12)]);o=CandidateScorer077()(b)
        a=sampled_hypotheses(o,b,16,8,max_layouts=32,draws=4)
        c=sampled_hypotheses(o,b,16,8,max_layouts=32,draws=4)
        np.testing.assert_array_equal(a['boxes'],c['boxes'])
        self.assertEqual(as_boxes(a,0),decode_fast(o,b,16,8)[0])
        self.assertGreater(len(a['boxes']),8)
    def test_diverse_search_keeps_original_and_contains_distinct_orders(self):
        from analysis.layout.recovery078_candidates import diverse_hypotheses,as_boxes,unique_hypotheses
        obs=example();obs['inventory'][1]={'category':'cab','dimensions':[.65,.40]}
        b=pack([prepare(obs,12)]);o=CandidateScorer077()(b)
        h=diverse_hypotheses(o,b,16,8,max_layouts=24)
        self.assertEqual(as_boxes(h,0),decode_fast(o,b,16,8)[0])
        self.assertLessEqual(len(h['boxes']),24)
        self.assertGreater(len(h['boxes']),8)
        self.assertEqual(len(unique_hypotheses(h)['boxes']),len(h['boxes']))

    def test_first_hypothesis_matches_same_search077(self):
        from analysis.layout.recovery078_candidates import hypotheses,as_boxes
        b=pack([prepare(example(),12)]);o=CandidateScorer077()(b)
        h=hypotheses(o,b,candidates=16,beam=8)
        self.assertEqual(as_boxes(h,0),decode_fast(o,b,16,8)[0])
        self.assertGreater(len(h['boxes']),1)

    def test_truth_fields_cannot_enter_graph_features(self):
        from analysis.layout.recovery078_candidates import graph_features,hypotheses
        obs=example();b=pack([prepare(obs,12)]);o=CandidateScorer077()(b);h=hypotheses(o,b,16,8)
        with self.assertRaisesRegex(ValueError,'Unexpected'):
            graph_features({**obs,'truth':[]},b,h)

    def test_zero_initialization_keeps_base_ranking(self):
        from analysis.layout.recovery078_model import LayoutRanker078
        b={'nodes':torch.rand(2,8,3,41),'edges':torch.rand(2,8,3,3,8),
           'node_valid':torch.ones(2,3,dtype=torch.bool),'hyp_valid':torch.ones(2,8,dtype=torch.bool),
           'base_score':torch.randn(2,8),'has_events':torch.ones(2,dtype=torch.bool)}
        torch.testing.assert_close(LayoutRanker078(width=32)(b)['scores'],b['base_score'])

    def test_zero_contact_diverse_search_has_exact077_fallback(self):
        from analysis.layout.recovery078_candidates import diverse_hypotheses,as_boxes,graph_features
        from analysis.layout.recovery078_model import LayoutRanker078,pack_graph
        obs=example();obs['events']=[]
        b=pack([prepare(obs,12)]);o=CandidateScorer077()(b)
        h=diverse_hypotheses(o,b,16,8,max_layouts=24)
        g,_=pack_graph([{'features':graph_features(obs,b,h)}]);m=LayoutRanker078(width=32)
        with torch.no_grad():m.head[-1].weight.normal_()
        index=int(m(g)['scores'].argmax())
        self.assertEqual(as_boxes(h,index),decode_fast(o,b,16,8)[0])

    def test_backbone_receives_gradient_after_output_head_unfreezes(self):
        from analysis.layout.recovery078_model import LayoutRanker078,ranking_loss
        b={'nodes':torch.rand(1,4,2,41),'edges':torch.rand(1,4,2,2,8),
           'node_valid':torch.ones(1,2,dtype=torch.bool),'hyp_valid':torch.ones(1,4,dtype=torch.bool),
           'base_score':torch.zeros(1,4),'has_events':torch.ones(1,dtype=torch.bool)}
        labels={'whole':torch.tensor([[1.,0,0,0]]),'dmax':torch.tensor([[.1,.6,.7,.8]]),
                'mean_error':torch.tensor([[.1,.4,.5,.6]]),'mean_iou':torch.tensor([[.8,.5,.3,.2]])}
        m=LayoutRanker078(width=32);optim=torch.optim.AdamW(m.parameters(),lr=.001)
        for _ in range(2):
            optim.zero_grad();ranking_loss(m(b),b,labels).backward();optim.step()
        self.assertGreater(float(m.node[0].weight.grad.abs().sum()),0)

    def test_graph_node_permutation_is_invariant(self):
        from analysis.layout.recovery078_model import LayoutRanker078
        b={'nodes':torch.rand(2,8,3,41),'edges':torch.rand(2,8,3,3,8),
           'node_valid':torch.ones(2,3,dtype=torch.bool),'hyp_valid':torch.ones(2,8,dtype=torch.bool),
           'base_score':torch.randn(2,8),'has_events':torch.ones(2,dtype=torch.bool)}
        model=LayoutRanker078(width=32).eval()
        with torch.no_grad():model.head[-1].weight.normal_(0,.1)
        p=torch.tensor([2,0,1]);c={**b,'nodes':b['nodes'][:,:,p],
            'edges':b['edges'][:,:,p][:,:,:,p],'node_valid':b['node_valid'][:,p]}
        torch.testing.assert_close(model(b)['scores'],model(c)['scores'])

    def test_ranker_rejects_targets_and_preserves_zero_event_baseline(self):
        from analysis.layout.recovery078_model import LayoutRanker078
        b={'nodes':torch.rand(1,4,2,41),'edges':torch.rand(1,4,2,2,8),
           'node_valid':torch.ones(1,2,dtype=torch.bool),'hyp_valid':torch.ones(1,4,dtype=torch.bool),
           'base_score':torch.randn(1,4),'has_events':torch.zeros(1,dtype=torch.bool)}
        m=LayoutRanker078(width=32)
        with self.assertRaisesRegex(ValueError,'Unexpected'):m({**b,'whole':torch.ones(1,4)})
        with torch.no_grad():m.head[-1].weight.normal_()
        torch.testing.assert_close(m(b)['scores'],b['base_score'])

    def test_candidate_labeling_is_separate_from_generation(self):
        from analysis.layout.recovery078_candidates import hypotheses,label_hypotheses
        b=pack([prepare(example(),12)]);o=CandidateScorer077()(b);h=hypotheses(o,b,16,8)
        original=h['boxes'].copy()
        labels=label_hypotheses(h,{'chair#0':[.775,1.775,1.225,2.225],
                                    'chair#1':[2.775,1.775,3.225,2.225]})
        self.assertTrue(np.array_equal(original,h['boxes']))
        self.assertEqual(len(labels['whole']),len(h['boxes']))

    def test_listwise_loss_sends_gradient_to_joint_score(self):
        from analysis.layout.recovery078_model import LayoutRanker078,ranking_loss
        b={'nodes':torch.rand(1,4,2,41),'edges':torch.rand(1,4,2,2,8),
           'node_valid':torch.ones(1,2,dtype=torch.bool),'hyp_valid':torch.ones(1,4,dtype=torch.bool),
           'base_score':torch.zeros(1,4),'has_events':torch.ones(1,dtype=torch.bool)}
        target={'whole':torch.tensor([[1.,0.,0.,0.]]),'dmax':torch.tensor([[.2,.7,1.,2.]]),
                'mean_error':torch.tensor([[.1,.5,.8,1.]]),'mean_iou':torch.tensor([[.8,.4,.2,.1]])}
        m=LayoutRanker078(width=32);loss=ranking_loss(m(b),b,target);loss.backward()
        self.assertGreater(float(m.head[-1].weight.grad.abs().sum()),0.)

if __name__=='__main__':unittest.main()
