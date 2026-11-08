"""Scientific reporting regressions: fixed cohorts and sampled boundaries."""
import unittest
import numpy as np
from analysis.layout import activity_surface as AS, exp_threshold_fine as fine


class ReportingTests(unittest.TestCase):
    def test_final_grid_cell_can_be_a_pareto_boundary(self):
        self.assertEqual(AS.threshold_frontier([[0, 0], [0, 1]], [.9, 1.], [2, 5]),
                         [{'coverage_target': 1., 'visits': 5}])

    def test_empty_objects_are_not_four_centre_success(self):
        self.assertFalse(fine._hit({'executable': True, 'objects': {}}))

    def test_missing_room_cannot_shrink_the_denominator(self):
        row = {'scene': 'a', 'policy': 'repeat', 'visits': 2,
               'coverage_target': .85, 'executable': True,
               'objects': {k: {'joint_error_m': 0.} for k in ['bed','desk','cab','chair']}}
        cell = fine.summarise([row], ['a', 'b'])['repeat|0.85|2']
        self.assertEqual((cell['hits'], cell['rooms'], cell['missing']), (1, 2, 1))

    def test_duplicate_room_is_rejected(self):
        row = {'scene':'a', 'policy':'repeat', 'visits':2, 'coverage_target':.85,
               'executable':False, 'objects':{}}
        with self.assertRaises(ValueError): fine.summarise([row,row], ['a'])

    def test_unknown_or_nonfinite_error_is_not_success(self):
        objects = {k:{'joint_error_m':0.} for k in ['bed','desk','cab','chair']}
        objects['cab']['joint_error_m'] = np.nan
        self.assertFalse(fine._hit({'executable':True,'objects':objects}))


class ExternalGeometryTests(unittest.TestCase):
    def test_exported_box_uses_bbox_center_not_object_pivot(self):
        from analysis.layout.procthor_scale import engine_box
        obj={'position':{'x':99,'z':99},'axisAlignedBoundingBox':
             {'center':{'x':2,'z':3},'size':{'x':1,'z':2}}}
        self.assertEqual(engine_box(obj),[1.5,2.,2.5,4.])

    def test_polygon_rectangle_test_allows_collinear_vertices(self):
        from analysis.layout.procthor_scale import is_rectangle
        self.assertTrue(is_rectangle([[0,0],[0,1],[0,2],[3,2],[3,0]]))
        self.assertFalse(is_rectangle([[0,0],[0,2],[1,2],[1,1],[3,1],[3,0]]))

    def test_room_membership_is_parsed_without_surface_children(self):
        from analysis.layout.procthor_scale import object_room
        self.assertEqual(object_room('Chair|4|2|1'),'4')
        self.assertEqual(object_room('Mug|surface|4|1'),'4')


if __name__ == '__main__': unittest.main()
