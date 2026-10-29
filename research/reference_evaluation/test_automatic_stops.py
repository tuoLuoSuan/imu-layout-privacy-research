import unittest
import numpy as np
import automatic_stops as c


class StopTests(unittest.TestCase):
    def test_no_stop_has_no_fallback(self):
        self.assertEqual(c.segment_mask(np.arange(50) * .1, np.zeros(50, bool)), [])

    def test_two_second_half_open_segment_is_kept(self):
        t = np.arange(40) * .1
        mask = (t >= 1) & (t < 3)
        self.assertEqual(c.segment_mask(t, mask), [{'start_s': 1., 'end_s': 3., 'samples': 20}])

    def test_short_stop_not_stretched(self):
        t = np.arange(40) * .1
        self.assertEqual(c.segment_mask(t, (t >= 1) & (t < 2.9)), [])

    def test_merge_gap_does_not_use_reference(self):
        t = np.arange(50) * .1
        mask = np.ones(50, bool); mask[20:22] = False
        self.assertEqual(len(c.segment_mask(t, mask)), 1)
        mask[22] = False
        self.assertEqual(len(c.segment_mask(t, mask)), 2)

    def test_missing_time_cannot_be_bridged(self):
        t = np.r_[np.arange(25) * .1, 10 + np.arange(25) * .1]
        result = c.segment_mask(t, np.ones(50, bool))
        self.assertEqual(len(result), 2)
        self.assertLess(result[0]['end_s'], result[1]['start_s'])

    def test_bad_clocks_rejected(self):
        with self.assertRaises(ValueError): c.segment_mask([0, 1, 1], [True] * 3)

    def test_imu_constant_gravity_is_still_after_warmup(self):
        t = np.arange(600) / 200
        f = np.zeros((600, 6)); f[:, 5] = 9.81
        mask, _ = c.imu_mask(t, f)
        self.assertFalse(mask[:199].any())
        self.assertTrue(mask[199:].all())

    def test_large_gyro_is_not_still(self):
        t = np.arange(600) / 200
        f = np.zeros((600, 6)); f[:, 0] = 1.; f[:, 5] = 9.81
        self.assertFalse(c.imu_mask(t, f)[0].any())

    def test_merged_stop_cannot_answer_two_reference_visits(self):
        detected = [{'start_s': 0., 'end_s': 20.}]
        reference = [[2., 6.], [12., 16.]]
        result = c.associate(detected, reference)
        self.assertEqual(sum(x is not None for x in result['reference_to_detected']), 1)
        self.assertEqual(result['detected_covering_multiple_references'], [0])

    def test_missing_queries_keep_denominator_four(self):
        result = c.score_queries([], [None] * 7, [0, 1, 2, 0, 2, 1, 0])
        self.assertEqual(result['queries'], 4)
        self.assertEqual(result['correct_lower'], 0)
        self.assertEqual(result['correct_upper'], 0)
        self.assertEqual(result['missing_targets'], 4)

    def test_unlabelled_previous_detection_is_not_discarded(self):
        # Reference visits map to indices 0 and 2; nearest prior is unlabelled index 1.
        result = c.score_queries([[0, 0], [9, 0], [10, 0]], [0, 2], [0, 0])
        self.assertEqual(result['correct_lower'], 0)
        self.assertEqual(result['correct_upper'], 1)
        self.assertEqual(result['details'][0]['predicted_detected_indices'], [1])

    def test_detected_position_uses_whole_segment(self):
        t = np.arange(10, dtype=float)
        result = c.segment_positions([{'start_s': 0., 'end_s': 10.}], t, np.c_[t, t])
        self.assertEqual(result[0]['xy'], [4.5, 4.5])

    def test_finite_random_ranking_ap_differs_from_constant_score(self):
        result = c.expected_random_ap(4, 2)
        self.assertAlmostEqual(result['analytic'], result['enumerated'])
        self.assertGreater(result['analytic'], .5)


if __name__ == '__main__': unittest.main()
