import unittest
import numpy as np
import torch

from analysis.layout.recovery076_data import prepare,pack
from analysis.layout.recovery076_model import EvidenceDecoder076


def observation():
    return {'schema':'evidence076-v1','frame':'declared-room','room':[4.,5.],
            'inventory':[{'category':'chair','dimensions':[.45,.45]}],
            'events':[{'object':'chair','pos':[1.,2.]},{'object':'chair','pos':[1.1,2.1]}],
            'walk':[],'desk_relation':False}


class Recovery077Tests(unittest.TestCase):
    def test_initial_scores_match_fixed_kernel(self):
        from analysis.layout.recovery077_model import CandidateScorer077
        b=pack([prepare(observation(),12)])
        torch.testing.assert_close(CandidateScorer077()(b)['energy'],EvidenceDecoder076()(b)['energy'])

    def test_truth_and_anchor_are_rejected(self):
        from analysis.layout.recovery077_model import CandidateScorer077
        b=pack([prepare(observation(),12)])
        for key in ('truth','target','anchor','room_id'):
            with self.assertRaisesRegex(ValueError,'Unexpected'):
                CandidateScorer077()({**b,key:torch.zeros(1)})

    def test_features_compare_candidates_and_ignore_event_order(self):
        from analysis.layout.recovery077_model import candidate_features
        a=observation();b=observation();b['events'].reverse()
        x=candidate_features(pack([prepare(a,12)]))['features']
        y=candidate_features(pack([prepare(b,12)]))['features']
        torch.testing.assert_close(x,y)
        self.assertGreater(float(x.var(dim=2).sum()),.1)

    def test_zero_contact_cannot_activate_learned_spatial_prior(self):
        from analysis.layout.recovery077_model import CandidateScorer077
        obs=observation();obs['events']=[];b=pack([prepare(obs,12)])
        model=CandidateScorer077()
        with torch.no_grad():
            for p in model.scorer.parameters():p.uniform_(-.2,.2)
        torch.testing.assert_close(model(b)['energy'],EvidenceDecoder076()(b)['energy'])

    def test_zero_residual_strength_is_fixed_even_after_training(self):
        from analysis.layout.recovery077_model import CandidateScorer077
        b=pack([prepare(observation(),12)]);model=CandidateScorer077()
        with torch.no_grad():
            for p in model.scorer.parameters():p.uniform_(-.2,.2)
        torch.testing.assert_close(model(b,strength=0.)['energy'],EvidenceDecoder076()(b)['energy'])

    def test_rotation_preserves_relative_candidate_features(self):
        from analysis.layout.recovery077_model import candidate_features
        from analysis.layout.recovery076_augment import rotate_batch
        b=pack([prepare(observation(),12)])
        r,_=rotate_batch(b,[{}],1)
        torch.testing.assert_close(candidate_features(b)['features'],candidate_features(r)['features'],atol=1e-5,rtol=1e-5)

    def test_candidate_scorer_receives_nonzero_gradient_and_changes_ranking(self):
        from analysis.layout.recovery077_model import CandidateScorer077,training_loss
        b=pack([prepare(observation(),12)]);model=CandidateScorer077(width=32)
        truth=[{'chair#0':[.775,1.775,1.225,2.225]}]
        before=model(b)['energy'].detach().clone();opt=torch.optim.Adam(model.scorer.parameters(),lr=.01)
        for _ in range(5):
            opt.zero_grad();loss,stats=training_loss(model(b),b,truth);loss.backward();opt.step()
        after=model(b)['energy'].detach()
        self.assertGreater(float((after-before).abs().max()),.01)
        self.assertEqual(stats['supervised_slots'],1)
        self.assertTrue(all(p.grad is None for p in model.fixed.parameters()))

    def test_unobserved_slots_do_not_train_guessed_locations(self):
        from analysis.layout.recovery077_model import CandidateScorer077,training_loss
        obs=observation();obs['events']=[];b=pack([prepare(obs,12)]);model=CandidateScorer077(width=32)
        loss,stats=training_loss(model(b),b,[{'chair#0':[.775,1.775,1.225,2.225]}])
        loss.backward()
        self.assertEqual(stats['supervised_slots'],0)
        self.assertLess(sum(float(p.grad.abs().sum()) for p in model.scorer.parameters() if p.grad is not None),1e-8)

    def test_fast_common_search_matches_original_search(self):
        from analysis.layout.recovery077_runtime import decode_fast
        from analysis.layout.recovery076_model import decode
        obs=observation();obs['inventory']*=2
        obs['events']=[{'object':'chair','pos':[1.,2.]},{'object':'chair','pos':[3.,2.]}]
        b=pack([prepare(obs,12)]);out=EvidenceDecoder076()(b)
        self.assertEqual(decode_fast(out,b,18,24),decode(out,b,18,24))

if __name__=='__main__':unittest.main()
