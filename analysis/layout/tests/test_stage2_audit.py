"""Counterexamples to envelope guarantees and allegedly matched ablations."""
import unittest
import numpy as np
from analysis.layout import evidence_space as ES, exp_span, exp_budget


class StageTwoTests(unittest.TestCase):
    def test_two_small_axis_widths_do_not_bound_euclidean_error(self):
        c=ES.envelope_certificate([0.,0.,.8,.8],[.4,.4],.5)
        self.assertGreater(c['radius_upper_m'],.5)
        self.assertFalse(c['allow'])

    def test_radius_is_relative_to_actual_output_not_just_midpoint(self):
        c=ES.envelope_certificate([0.,0.,.9,0.],[0.,0.],.5)
        self.assertAlmostEqual(c['radius_upper_m'],.9)
        self.assertFalse(c['allow'])
        self.assertTrue(ES.envelope_certificate([0.,0.,.9,0.],[.45,0.],.5)['allow'])

    def test_empty_or_invalid_envelope_never_certifies(self):
        self.assertFalse(ES.envelope_certificate(None,None,.5)['allow'])
        self.assertFalse(ES.envelope_certificate([1.,0.,0.,1.],[0.,0.],.5)['allow'])

    def test_single_anchor_keeps_all_other_classes(self):
        events=[{'object':'bed','pos':[0,0]},{'object':'chair','pos':[1,1]},
                {'object':'bed','pos':[2,0]},{'object':'cab','pos':[3,1]}]
        edits=exp_span._edits(events)
        self.assertEqual([e['object'] for e in edits['single:bed']],['chair','cab','bed'])

    def test_collapse_preserves_actual_event_count(self):
        events=[{'object':'bed','pos':[0,0],'available_distance_m':1},
                {'object':'bed','pos':[2,0],'available_distance_m':2}]
        self.assertEqual(len(exp_span._edits(events)['collapse:bed']),2)

    def test_missing_output_counts_as_failure_in_budget_cell(self):
        def row(error):
            return {'scene':str(error),'arm':'TA-U','policy':'dispersed','budget_m':8.,'coverage':.2,
                    'scores':{'0.5':{'center_error_m':{o:error for o in exp_budget.OBJECTS},
                                    'center_diameter_upper_m':{o:.2 for o in exp_budget.OBJECTS}}}}
        r=exp_budget.cell([row(.1),row(None)],'TA-U','dispersed',8.)
        self.assertEqual(r['hit']['bed'],.5)

    def test_prefix_never_includes_future_contact_or_route(self):
        from analysis.layout.activity_experiment import prefix_episode
        e={'points':np.array([[0,0],[1,0],[2,0]]),'arc':np.array([0,1,2]),
           'events':[{'object':'bed','available_distance_m':2,'pos':[2,0]}]}
        p,events=prefix_episode(e,1.)
        self.assertEqual(len(p),2);self.assertEqual(events,[])

    def test_span_formula_is_not_applied_to_a_fixed_chair_center(self):
        r=exp_span.span_requirement('chair',[2.,2.],[0.,0.],.2,.5)
        self.assertEqual(r['status'],'not_applicable')

    def test_only_scanned_axis_loses_width(self):
        r=exp_span.span_requirement('bed',[2.,1.],[1.,0.],.2,.5)
        np.testing.assert_allclose(r['event_width_m'],[1.4,1.4])

    def test_direction_alone_keeps_distance_ambiguity(self):
        from analysis.layout.exp_desk import forward_support
        boxes=np.array([[1.,-.1,1.2,.1],[2.,-.1,2.2,.1],[-.1,1.,.1,1.2]])
        np.testing.assert_array_equal(forward_support(boxes,[0,0],[1,0],.2),[True,True,False])

    def test_semantic_cycles_keep_anchor_coordinates_and_no_class_fixed(self):
        from analysis.layout.exp_semantics import cycle_labels
        e=[{'object':x,'pos':[i,2],'available_distance_m':i} for i,x in enumerate(['bed','chair','cab'])]
        r=cycle_labels(e,1)
        self.assertTrue(all(a['object']!=b['object'] for a,b in zip(e,r)))
        self.assertEqual([a['pos'] for a in e],[a['pos'] for a in r])

    def test_offset_span_scan_stays_in_contact_extent_and_is_nested(self):
        from analysis.layout.exp_span import span_positions
        box=np.array([0.,0.,2.,1.]);old=None
        for span in [0.,.5,1.,2.]:
            p=span_positions(box,0,span,[.8,.2])
            self.assertTrue(np.all(p>=box[:2]) and np.all(p<=box[2:]))
            lo,hi=p[:,0].min(),p[:,0].max()
            if old is not None:self.assertTrue(lo<=old[0] and hi>=old[1])
            old=(lo,hi)

    def test_continuous_bed_envelope_does_not_depend_on_grid_samples(self):
        r=ES.bed_position_envelope([4.,4.],[2.,1.],[[1.,1.],[3.,2.]],.2)
        b=np.asarray(r['bounds']);truth=np.array([2.,1.5])
        self.assertTrue(np.all(truth>=b[:2]) and np.all(truth<=b[2:]))
        self.assertLess(ES.envelope_certificate(b,(b[:2]+b[2:])/2)['radius_upper_m'],.5)

    def test_continuous_bed_envelope_marks_inconsistent_contacts(self):
        r=ES.bed_position_envelope([4.,4.],[2.,1.],[[0.,0.],[4.,4.]],.1)
        self.assertEqual(r['status'],'conflict')


if __name__=='__main__':unittest.main()
