import unittest
import numpy as np


class Analytic077Tests(unittest.TestCase):
    def test_two_beds_do_not_each_need_to_cover_both_far_contacts(self):
        from analysis.layout.multi_instance import decode_instances
        from analysis.layout.analytic077 import corrected_static
        obs={'schema':'evidence076-v1','frame':'declared-room','room':[6.,4.],
             'inventory':[{'category':'bed','dimensions':[1.,1.]}]*2,
             'events':[{'object':'bed','pos':[1.,1.]},{'object':'bed','pos':[5.,3.]}],
             'walk':[],'desk_relation':False}
        inv=[{'id':f'bed#{i}','category':'bed','dimensions':[1.,1.]} for i in range(2)]
        old=decode_instances(obs['room'],inv,obs['events'],np.empty((0,2)),known_desk_protocol=False)
        self.assertEqual(old['status'],'no_proposals')
        new=corrected_static(obs)
        self.assertEqual(new['status'],'ok')
        self.assertEqual(len(new['boxes']),2)
        for e in obs['events']:
            p=np.asarray(e['pos'])
            self.assertTrue(any(np.all(p>=np.asarray(b)[:2]-.2000001) and np.all(p<=np.asarray(b)[2:]+.2000001) for b in new['boxes'].values()))

    def test_legacy_module_is_not_modified_by_corrected_baseline(self):
        from analysis.layout import multi_instance as m
        from analysis.layout.analytic077 import corrected_static
        original=m._proposals
        obs={'schema':'evidence076-v1','frame':'declared-room','room':[3.,4.],
             'inventory':[{'category':'chair','dimensions':[.4,.4]}],
             'events':[{'object':'chair','pos':[1.,2.]}],'walk':[],'desk_relation':False}
        corrected_static(obs)
        self.assertIs(m._proposals,original)

if __name__=='__main__':unittest.main()
