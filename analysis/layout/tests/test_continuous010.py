import unittest
import numpy as np


class Continuous010Tests(unittest.TestCase):
    def test_continuous_contact_band_and_latent_repeated_chair_assignment(self):
        from analysis.layout.continuous_solver010 import solve
        inv=[{'id':'chair#0','category':'chair','dimensions':[.4,.4]},
             {'id':'chair#1','category':'chair','dimensions':[.4,.4]}]
        events=[{'object':'chair','pos':[1.,1.]},{'object':'chair','pos':[3.,3.]},{'object':'chair','pos':[1.05,1.]}]
        result=solve([4,4],inv,events,[],padding=.1)
        self.assertEqual(result['status'],'ok')
        boxes=np.array(list(result['boxes'].values()));centres=(boxes[:,:2]+boxes[:,2:])/2
        for e in events:self.assertLessEqual(abs(centres-e['pos']).max(axis=1).min(),.10001)

    def test_impossible_single_bed_contacts_are_reported_as_infeasible(self):
        from analysis.layout.continuous_solver010 import solve
        inv=[{'id':'bed#0','category':'bed','dimensions':[1.,1.]}]
        result=solve([5,5],inv,[{'object':'bed','pos':[.1,.1]},{'object':'bed','pos':[4.,4.]}],[],padding=.1)
        self.assertEqual(result['status'],'continuous_domain_empty')

    def test_resource_limit_without_an_incumbent_does_not_become_a_layout(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from analysis.layout.continuous_solver010 import solve,Program
        with patch.object(Program,'run',return_value=SimpleNamespace(status=1,x=None,mip_gap=None,mip_node_count=None)):
            result=solve([5,5],[{'id':'chair#0','category':'chair','dimensions':[.4,.4]}],[],[])
        self.assertEqual(result['status'],'continuous_budget');self.assertEqual(result['boxes'],{})


if __name__=='__main__':unittest.main()
