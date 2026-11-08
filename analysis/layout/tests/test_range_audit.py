"""Regression checks for temporal association, door contradictions and range controls."""
import copy
import unittest
import numpy as np
from analysis.layout import door
from analysis.layout.exp_desk_dir import heading_at


class RangeAuditTests(unittest.TestCase):
    def test_heading_is_bound_to_event_not_first_nearest_visit(self):
        path=np.array([[0.,0.],[1.,0.],[1.,1.],[0.,1.],[0.,0.]])
        np.testing.assert_allclose(heading_at(path,[0.,0.],.5,event_distance=4.),[0.,-1.])

    def test_future_path_does_not_change_heading(self):
        past=np.array([[0.,0.],[1.,0.],[1.,1.]])
        future=np.vstack([past,[[8.,9.],[1.,1.],[1.,0.]]])
        np.testing.assert_allclose(heading_at(past,[1.,1.],.5,event_distance=2.),
                                   heading_at(future,[1.,1.],.5,event_distance=2.))

    def test_door_negative_interval_is_conflict_not_zero_width(self):
        iv=door.bed_x_interval('s-59d570ee',1.5,1.0)
        self.assertEqual(iv['status'],'conflict')
        self.assertIsNone(iv['width_m'])
        self.assertLess(iv['signed_width_m'],0.)

    def test_door_override_is_pure_and_keeps_precision(self):
        original=copy.deepcopy(door.DOOR)
        spec=dict(original['s-59d570ee'],centre_x=.9234567)
        iv=door.bed_x_interval('s-59d570ee',2.84,1.525,door_spec=spec)
        self.assertAlmostEqual(iv['lo'],.9234567+.775/2,places=10)
        self.assertEqual(door.DOOR,original)

    def test_nested_walk_coverage_and_events_fixed(self):
        from analysis.layout.exp_walk_range import coverage_route, survey_prefixes
        scene={'W':3.,'L':3.,'S':[.2,.2],
               'gt':{'desk':[1.,1.,2.,2.]}}
        episode=coverage_route(scene)
        rows=survey_prefixes(episode,[0.,.25,.5,1.])
        self.assertTrue(all(a['coverage_room']<=b['coverage_room'] for a,b in zip(rows,rows[1:])))
        for row in rows:
            self.assertFalse(np.any((row['path'][:,0]>1.)&(row['path'][:,0]<2.)&
                                    (row['path'][:,1]>1.)&(row['path'][:,1]<2.)))
        self.assertAlmostEqual(rows[-1]['coverage_reachable'],1.)

    def test_unreached_floor_not_discarded(self):
        from analysis.layout.exp_walk_range import coverage_route, survey_prefixes
        scene={'W':3.,'L':3.,'S':[.2,.2],
               'gt':{'desk':[1.3,0.,1.7,3.]}}
        row=survey_prefixes(coverage_route(scene),[1.])[0]
        self.assertLess(row['coverage_free'],.8)
        self.assertAlmostEqual(row['coverage_reachable'],1.)

    def test_ambiguity_witness_uses_complete_feasible_alternatives(self):
        from analysis.layout.exp_walk_range import ambiguity_witness
        result={'candidates':[{'bed':np.array([0.,0.,1.,1.]),'desk':np.array([3.,3.,4.,4.])}],
                'objects':{'bed':{'support_boxes':np.array([[0.,0.,1.,1.],[2.,0.,3.,1.]])},
                           'desk':{'support_boxes':np.array([[3.,3.,4.,4.]])}}}
        witness=ambiguity_witness(result)
        self.assertTrue(witness['certified_in_declared_geometric_model'])
        self.assertAlmostEqual(witness['minimax_error_lower_m'],1.)
        self.assertEqual(set(witness['layouts'][0]),{'bed','desk'})

    def test_overlapping_box_cannot_create_ambiguity_certificate(self):
        from analysis.layout.exp_walk_range import ambiguity_witness
        result={'candidates':[{'bed':np.array([0.,0.,1.,1.]),'desk':np.array([2.,0.,3.,1.])}],
                'objects':{'bed':{'support_boxes':np.array([[0.,0.,1.,1.],[2.,0.,3.,1.]])},
                           'desk':{'support_boxes':np.array([[2.,0.,3.,1.]])}}}
        self.assertFalse(ambiguity_witness(result)['certified_in_declared_geometric_model'])


if __name__=='__main__':unittest.main()
