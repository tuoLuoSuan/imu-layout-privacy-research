import unittest
import numpy as np
import torch


class Spatial088Tests(unittest.TestCase):
    def test_route_reads_actual_events_only(self):
        from analysis.layout.recovery088_spatial_runtime import use_spatial_zero
        self.assertTrue(use_spatial_zero({'events':[],'coverage_target':.25,'family':'free'}))
        self.assertTrue(use_spatial_zero({'events':[],'coverage_target':1.,'family':'wall'}))
        self.assertFalse(use_spatial_zero({'events':[{}]}))

    def test_cached_field_residual_matches_original_model(self):
        from analysis.layout.recovery083_fields import fields,scalar_features
        from analysis.layout.recovery083_model import SpatialResidual083
        from analysis.layout.recovery076_data import prepare,pack
        from analysis.layout.recovery088_spatial_runtime import residual_field
        torch.set_num_threads(2);torch.manual_seed(8812)
        obs={'schema':'evidence076-v1','frame':'declared-room','room':[4.,5.],
             'inventory':[{'category':'chair','dimensions':[.4,.5]}],
             'events':[],'walk':[[.1,.2],[1.,2.]],'desk_relation':False}
        batch=pack([prepare(obs)]);model=SpatialResidual083();model.eval()
        with torch.no_grad():model.head.weight.normal_(0,.02);model.scalar[-1].weight.normal_(0,.02)
        got=residual_field(obs,batch,model)[0,0];c=batch['centres'][0,0];size=batch['sizes'][0,0]
        cell=(c[:,1]/5*24).long().clamp(0,23)*24+(c[:,0]/4*24).long().clamp(0,23)
        scal=torch.from_numpy(np.stack([scalar_features(obs,3,s.numpy()) for s in size]))
        with torch.inference_mode():expected=model.residual(torch.from_numpy(fields(obs))[None],scal,torch.full((len(c),),3,dtype=torch.long),cell)
        torch.testing.assert_close(got,expected,atol=1e-6,rtol=1e-5)


if __name__=='__main__':unittest.main()
