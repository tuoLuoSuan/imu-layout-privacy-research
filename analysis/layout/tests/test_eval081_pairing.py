"""Prevent dropping failed requests or treating repeated cells as new groups."""
import unittest


class Eval081PairingTests(unittest.TestCase):
    def test_pairing_keeps_failed_requests_and_group_sizes(self):
        from tools.eval082_locked import paired
        rows=[]
        cases=[('a','g1',1,0),('b','g1',1,0),('c','g1',1,0),
               ('d','g2',0,1),('failed','g3',0,0)]
        for rid,group,new,old in cases:
            for arm,value in [('new',new),('old',old)]:
                rows.append({'id':rid,'group':group,'arm':arm,'whole_room':value,
                             'whole_footprint':value,'f1':float(value)})
        result=paired(rows,'new','old',100)
        self.assertEqual(result['n_requested_pairs'],5)
        self.assertEqual(result['independent_condition_groups'],3)
        self.assertEqual(result['centre_repaired'],3)
        self.assertEqual(result['centre_broken'],1)
        self.assertAlmostEqual(result['delta_centre_footprint_f1'][0],.4)

    def test_pairing_rejects_different_requested_ids(self):
        from tools.eval082_locked import paired
        with self.assertRaises(ValueError):
            paired([{'id':'a','arm':'new'}],'new','old',100)


if __name__=='__main__':
    unittest.main()
