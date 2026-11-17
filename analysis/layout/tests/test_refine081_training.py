import unittest
import numpy as np
import torch


class Refine081TrainingTests(unittest.TestCase):
    def test_k6_view_loader_keeps_failures_out_of_training(self):
        from tools.train_refine081 import load_k6_views
        import json, tempfile
        from pathlib import Path
        metas={'ok':{'id':'ok','contacts_requested':6,'split':'train','status':'ok'},
               'failed':{'id':'failed','contacts_requested':6,'split':'validation','status':'failed'}}
        rows=[{'id':'ok','split':'train','boxes':{'chair#0':[0,0,1,1]}},
              {'id':'failed','split':'validation','boxes':{}}]
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'views.jsonl';p.write_text('\n'.join(map(json.dumps,rows)),encoding='utf-8')
            views,failures=load_k6_views(p,metas)
        self.assertEqual(set(views),{'ok'});self.assertEqual(failures,['failed'])

    def test_same_category_targets_are_matched_not_named(self):
        from tools.train_refine081 import match_targets
        coarse={'chair#0':[2.,0.,2.4,.4],'chair#1':[0.,0.,.4,.4]}
        truth={'chair#0':[0.,0.,.4,.4],'chair#1':[2.,0.,2.4,.4]}
        keys,target=match_targets(coarse,truth)
        np.testing.assert_allclose(target[0],truth['chair#1'])
        self.assertEqual(keys,['chair#0','chair#1'])

    def test_actual_degenerate_targets_fail_loudly(self):
        from tools.train_refine081 import match_targets
        with self.assertRaises(ValueError):
            match_targets({'chair#0':[0.,0.,.4,.4]}, {'chair#0':[0.,0.,0.,0.]})

    def test_padding_cannot_create_nan_or_change_loss(self):
        from tools.train_refine081 import refinement_loss
        box=torch.tensor([[[.5,.5,1.,1.]]]);target=box+.03;room=torch.tensor([[4.,5.]])
        delta=torch.zeros(1,1,2,requires_grad=True);valid=torch.ones(1,1,dtype=torch.bool)
        a=refinement_loss(delta,box,target,valid,room)
        padded=lambda x:torch.cat([x,torch.zeros_like(x)],1)
        d=padded(delta);b=refinement_loss(d,padded(box),padded(target),torch.tensor([[True,False]]),room)
        torch.testing.assert_close(a,b)
        b.backward();self.assertTrue(torch.isfinite(delta.grad).all())


if __name__=='__main__':unittest.main()
