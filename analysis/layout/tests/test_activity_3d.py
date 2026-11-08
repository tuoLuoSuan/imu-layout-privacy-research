import unittest
from analysis.layout import fig_main_activity3d as F


def row(scene,f1,whole):
    return {'scene':scene,'split':'train','counts':{'bed':1,'desk':1,'cab':1,'chair':1},
            'coverage':.5,'visits':2,'method':'generic','executable':True,'status':'ok',
            'events':[],'score':{'f1':f1,'all_instances_hit':whole,
            'per_class':{c:{'tp':1,'fp':0,'fn':0} for c in ['bed','desk','cab','chair']}}}


class ActivityFigureTests(unittest.TestCase):
    def test_recovery_degree_and_whole_room_success_are_distinct(self):
        records=[{'scene':'a','rows':[row('a',.8,False)]},{'scene':'b','rows':[row('b',1.,True)]}]
        d=F.prepare(records,{'n_rooms':2,'cells':[(.5,2)],'methods':['generic']})
        self.assertAlmostEqual(d['views']['all|all|generic|f1']['z'][0][0],90.)
        self.assertAlmostEqual(d['views']['all|all|generic|layout']['z'][0][0],50.)

    def test_duplicate_condition_cannot_inflate_the_result(self):
        a=row('a',1.,True)
        with self.assertRaises(ValueError):F.prepare([{'scene':'a','rows':[a,a]}],{'n_rooms':1,'cells':[(.5,2)],'methods':['generic']})

    def test_boundary_works_at_grid_edge_and_does_not_assume_monotonicity(self):
        p=F.pareto([[10,80],[81,70]],[90,95],[2,5],80)
        self.assertEqual({(v['coverage'],v['visits']) for v in p},{(95,2),(90,5)})


if __name__=='__main__':unittest.main()
