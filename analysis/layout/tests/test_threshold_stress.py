"""Fault-budget and activity-range counterexamples, independent of learned models."""
import unittest
import numpy as np
from analysis.layout import evidence_space as ES


class ThresholdStressTests(unittest.TestCase):
    def test_zero_fault_budget_is_the_existing_model(self):
        a=[[1.,1.],[2.,2.],[3.,2.]]
        expected=ES.bed_position_envelope([5.,4.],[2.,1.],a,.2)
        got=ES.bed_outlier_envelope([5.,4.],[2.,1.],a,.2,0)
        self.assertEqual(got['bounds'],expected['bounds'])

    def test_one_wrong_event_keeps_the_good_model_in_the_union(self):
        got=ES.bed_outlier_envelope([6.,5.],[2.,1.],[[1.,1.],[2.,1.5],[3.,2.],[5.8,4.8]],.2,1)
        b=np.array(got['bounds']);true=np.array([2.,1.5])
        self.assertTrue(np.all(true>=b[:2]) and np.all(true<=b[2:]))

    def test_all_events_suspect_means_no_contact_information(self):
        got=ES.bed_outlier_envelope([5.,4.],[2.,1.],[[3.,3.]],.2,1)
        expected=ES.bed_position_envelope([5.,4.],[2.,1.],[],.2)
        self.assertEqual(got['bounds'],expected['bounds'])

    def test_unknown_bad_event_is_not_selected_using_truth(self):
        # Two far-apart observations can each be the single good event.
        got=ES.bed_outlier_envelope([8.,5.],[2.,1.],[[1.,1.],[7.,4.]],.2,1)
        self.assertGreater(got['bounds'][2]-got['bounds'][0],3.)
        self.assertFalse(ES.envelope_certificate(got['bounds'],[4.,2.5],.5)['allow'])

    def test_invalid_fault_budget_is_rejected(self):
        with self.assertRaises(ValueError):ES.bed_outlier_envelope([5.,4.],[2.,1.],[],.2,-1)

    def test_repeated_endpoints_protect_against_an_added_false_event(self):
        a=[[1.,1.],[1.,1.],[3.,2.],[3.,2.]]
        expected=ES.bed_position_envelope([6.,5.],[2.,1.],a,.2)
        got=ES.bed_outlier_envelope([6.,5.],[2.,1.],a+[[5.8,4.8]],.2,1)
        np.testing.assert_allclose(got['bounds'],expected['bounds'])


if __name__=='__main__':unittest.main()
