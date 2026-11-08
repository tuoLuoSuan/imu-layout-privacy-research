"""Soundness and physical-protocol checks for continuous position envelopes."""
import unittest
import numpy as np


class ContinuousRegionTests(unittest.TestCase):
    def test_no_anchor_is_continuous_room_not_a_finite_bank(self):
        from analysis.layout.continuous_regions import object_region
        r=object_region([4.,3.],[1.,.5],'desk',[],[])
        np.testing.assert_allclose(r['center_bounds_m'],[.25,.25,3.75,2.75])

    def test_repeated_point_chair_never_conflicts_when_exact(self):
        from analysis.layout.continuous_regions import object_region
        e=[{'object':'chair','pos':[1.7,1.2]}]*3
        r=object_region([4.,3.],[.4,.4],'chair',e,[],padding=.2)
        self.assertTrue(r['bounds_sound_if_model_conditions_hold'])
        self.assertLessEqual(r['radius_upper_m'],np.sqrt(2)*.2+1e-7)

    def test_floor_avoidance_retains_zero_width_boundary(self):
        from analysis.layout.continuous_regions import subtract_open
        r=subtract_open(np.array([[0.,0.,1.,1.]]),[-1.,-1.,1.,2.])
        self.assertTrue(any(np.allclose(b,[1.,0.,1.,1.]) for b in r))

    def test_no_unsound_small_radius_when_region_budget_exhausted(self):
        from analysis.layout.continuous_regions import object_region
        r=object_region([4.,4.],[1.,1.],'bed',[],[[2.,2.]],max_regions=1)
        self.assertTrue(r['relaxed_by_budget'])
        self.assertGreater(r['radius_upper_m'],1.)

    def test_exact_truth_survives_random_valid_contact_and_walk_constraints(self):
        from analysis.layout.continuous_regions import object_region,contains_box
        box=np.array([1.031,1.267,2.431,2.067])
        events=[{'object':'bed','pos':[1.1,1.3]},{'object':'bed','pos':[2.3,2.0]}]
        path=np.array([[.2,.2],[.4,1.8],[2.8,1.2],[3.1,3.1]])
        r=object_region([4.,4.],box[2:]-box[:2],'bed',events,path)
        self.assertTrue(contains_box(r,box))
        c=(box[:2]+box[2:])/2
        self.assertLessEqual(np.linalg.norm(c-r['point_m']),r['radius_upper_m']+1e-8)

    def test_cabinet_union_allows_different_operation_faces(self):
        from analysis.layout.continuous_regions import object_region,contains_box
        box=np.array([1.,1.,2.,1.5])
        events=[{'object':'cab','pos':[.4,1.2]},{'object':'cab','pos':[1.5,2.1]}]
        r=object_region([4.,4.],[1.,.5],'cab',events,[])
        self.assertTrue(contains_box(r,box))

    def test_valid_spreading_stays_inside_bed_and_on_same_cabinet_face(self):
        from analysis.layout.exp_contact_spread import spread_events
        from analysis.layout.evidence_space import _contact
        examples=[('bed',[1.,1.,3.,2.],[1.1,1.1]),
                  ('cab',[1.,1.,3.,1.5],[1.5,.4])]
        for obj,box,anchor in examples:
            for frac in [0.,.25,.5,.75,1.]:
                e,_=spread_events([{'object':obj,'pos':anchor}],obj,box,frac)
                self.assertTrue(all(_contact(np.array([box]),v,.2,.6)[0][0] for v in e),(obj,frac,e))
                if obj=='bed':
                    self.assertTrue(all(np.all(np.array(v['pos'])>=box[:2]) and np.all(np.array(v['pos'])<=box[2:]) for v in e))

    def test_valid_chair_protocol_does_not_move_exact_center(self):
        from analysis.layout.exp_contact_spread import spread_events
        events=[{'object':'chair','pos':[1.,1.]}]
        e,span=spread_events(events,'chair',[.8,.8,1.2,1.2],1.)
        self.assertEqual(span,0.)
        self.assertTrue(all(v['pos']==[1.,1.] for v in e))

    def test_activity_events_are_causal_nested_and_physically_compatible(self):
        from analysis.layout.activity_surface import event_sequence
        from analysis.layout.evidence_space import _contact
        scene={'W':4.,'L':4.,'gt':{'bed':[2.,2.,3.8,3.8],
              'cab':[.2,.2,.8,1.2],'chair':[1.,1.,1.4,1.4],'desk':[.2,2.,.8,3.]}}
        path=np.array([[1.4,.7],[1.8,1.8],[1.7,2.5],[1.2,.7]])
        first=event_sequence(scene,path,3,'dispersed')
        later=event_sequence(scene,path,9,'dispersed')
        self.assertEqual(first,later[:3])
        for e in later:self.assertTrue(_contact(np.array([scene['gt'][e['object']]]),e,.2,.6)[0][0])

    def test_surface_threshold_requires_confirmation_in_both_axes(self):
        from analysis.layout.activity_surface import threshold_frontier
        self.assertEqual(threshold_frontier(np.ones((2,2)),[0.,1.],[0,1]),[])
        self.assertEqual(threshold_frontier(np.ones((3,3)),[0.,.5,1.],[0,3,6]),[{'coverage_target':0.,'visits':0}])

    def test_face_inverse_uses_endpoints_normal_and_sizes(self):
        from analysis.layout.oracle_upper_check import face_box
        for n,ends in [([1.,0.],[[3.6,1.],[3.6,3.]]),([-1.,0.],[[1.4,1.],[1.4,3.]])]:
            np.testing.assert_allclose(face_box(ends,n,[1.,2.]),[2.,1.,3.,3.])

    def test_face_inverse_rejects_inconsistent_observations(self):
        from analysis.layout.oracle_upper_check import face_box
        with self.assertRaises(ValueError):face_box([[1.,1.],[2.,2.]],[1.,0.],[1.,2.])

    def test_joint_selection_keeps_a_bed_that_leaves_room_for_desk(self):
        from analysis.layout.continuous_decode import decode
        regions={'bed':{'point_m':np.array([2.,.5]),'modes':[{'dimensions':[1.,1.],
            'q_regions':np.array([[0.,0.,0.,0.],[3.,0.,3.,0.]])}]},
            'desk':{'point_m':np.array([.5,.5]),'modes':[{'dimensions':[1.,1.],
            'q_regions':np.array([[0.,0.,0.,0.]])}]}}
        r=decode([5.,5.],regions,[],[])
        self.assertEqual(r['status'],'ok')
        self.assertAlmostEqual(r['boxes']['bed'][0],3.)


if __name__=='__main__':unittest.main()
