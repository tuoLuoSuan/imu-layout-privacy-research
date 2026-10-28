"""Behavioral guards for an independent, read-only reference implementation."""
import unittest
import numpy as np
try:
    import reference_core as core
except ModuleNotFoundError:
    core = None


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(core, 'Independent reference core has not been implemented')

    def test_negative_voxels_and_phase_do_not_alias(self):
        p = np.array([[-.001, -.051, .049], [-.001, -.051, .049], [.051, .001, .101]], dtype=np.float32)
        q = core.voxel_coords(p)
        np.testing.assert_array_equal(q, [[-1, -2, 0], [1, 0, 2]])
        q2 = core.voxel_coords(np.array([[.025, .025, .025]], dtype=np.float32), phase=[.025, .025, .025])
        np.testing.assert_array_equal(q2, [[0, 0, 0]])

    def test_chebyshev_distance_matches_brute_force(self):
        ref = np.array([[0, 0, 0], [-5, 7, -3], [10, -10, 5]])
        q = np.array([[1, 0, 0], [-1, -1, 1], [-7, 7, -3], [10, -8, 6]])
        expected = np.max(np.abs(q[:, None, :] - ref[None, :, :]), axis=2).min(axis=1)
        np.testing.assert_array_equal(core.neighbor_distances(q, ref), expected)

    def test_empty_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            core.neighbor_distances(np.array([[0, 0, 0]]), np.empty((0, 3)))

    def test_all_eighty_connected_voxels_count_toward_centroid(self):
        p = np.array([[x, y, .025 + .05*z] for x in [.025, .075] for y in [.025, .075] for z in range(20)])
        candidates = core.candidates(p)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['n'], 80)
        np.testing.assert_allclose(candidates[0]['c'], p.mean(axis=0), atol=1e-14)

    def test_two_person_sized_blobs_are_both_returned(self):
        a = np.array([[0., 0., .05*k] for k in range(24)])
        b = np.array([[2., 2., .05*k] for k in range(30)])
        candidates = core.candidates(np.vstack([a, b]))
        self.assertEqual(sorted(c['n'] for c in candidates), [24, 30])

    def test_half_open_time_windows_keep_boundary_unambiguous(self):
        t = np.array([1.999999999, 2., 5.999999999, 6.])
        np.testing.assert_array_equal(core.window_indices(t, (2., 6.)), [1, 2])

    def test_multisolution_invalidates_primary_even_with_high_coverage(self):
        frames = []
        for t in np.arange(0., 60., .1):
            n = 1 if 0 <= t < 8 or 40 <= t < 60 else 0
            candidates = [{'n': 40, 'c': [1., 2., 1.], 'zspan': 1.}] if n else []
            if abs(t-3.) < 1e-8:
                candidates.append({'n': 41, 'c': [2., 2., 1.], 'zspan': 1.})
            frames.append({'t': float(t), 'struct_valid': True, 'novel': .02 if n else 0., 'occ': bool(n), 'ncand': len(candidates), 'cands': candidates})
        result = core.summarize(frames)
        self.assertTrue(result['V2']['pass'])
        self.assertTrue(result['V3']['ambiguous'])
        self.assertIsNone(result['primary_revisit_diff'])

    def test_known_rotation_scale_alignment_and_holdout(self):
        p = np.array([[0., 0.], [1., 0.], [.2, .7]])
        R = np.array([[0., -1.], [1., 0.]])
        q = 2.3*(p @ R.T)+[3., -4.]
        transform = core.fit_similarity(p[:2], q[:2])
        self.assertAlmostEqual(transform['scale'], 2.3)
        np.testing.assert_allclose(core.apply_similarity(p, transform), q, atol=1e-12)

    def test_reflection_cannot_be_hidden_as_rotation(self):
        p = np.array([[0., 0.], [1., 0.], [.2, .7]])
        q = p*np.array([-1., 1.])
        transform = core.fit_similarity(p, q)
        self.assertGreater(np.linalg.det(transform['rotation']), .99)
        self.assertGreater(np.linalg.norm(core.apply_similarity(p, transform)-q), .1)

    def test_collapsed_anchor_baseline_is_not_fitted(self):
        with self.assertRaises(ValueError):
            core.fit_similarity(np.zeros((2, 2)), np.array([[0., 0.], [1., 1.]]))


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(core, 'Independent reference core has not been implemented')

    def test_empty_predictions_never_become_observations(self):
        tracker = core.ConservativeTracker()
        tracker.step(0., [{'c': [0., 0., 1.]}])
        row = tracker.step(.1, [])
        self.assertIsNone(row['observed_xy'])
        self.assertEqual(row['state'], 'missing')

    def test_split_candidates_are_not_silently_merged_or_selected(self):
        tracker = core.ConservativeTracker()
        tracker.step(0., [{'c': [0., 0., 1.]}])
        row = tracker.step(.1, [{'c': [.01, 0., 1.]}, {'c': [.02, 0., 1.]}])
        self.assertEqual(row['state'], 'ambiguous')
        self.assertIsNone(row['observed_xy'])

    def test_impossible_jump_is_rejected(self):
        tracker = core.ConservativeTracker()
        tracker.step(0., [{'c': [0., 0., 1.]}])
        row = tracker.step(.1, [{'c': [10., 0., 1.]}])
        self.assertEqual(row['state'], 'rejected_jump')
        self.assertIsNone(row['observed_xy'])

    def test_long_gap_starts_new_track_without_claiming_identity(self):
        tracker = core.ConservativeTracker()
        first = tracker.step(0., [{'c': [0., 0., 1.]}])
        second = tracker.step(2., [{'c': [2., 0., 1.]}])
        self.assertNotEqual(first['track_id'], second['track_id'])
        self.assertEqual(second['state'], 'acquired')

    def test_nominal_unit_invariance_of_gate(self):
        a = core.ConservativeTracker(max_speed=3., base_gate=.15)
        b = core.ConservativeTracker(max_speed=3000., base_gate=150.)
        for t, xy in [(0., [0., 0.]), (.1, [.2, 0.]), (.2, [.4, .1])]:
            aa = a.step(t, [{'c': [*xy, 1.]}])
            bb = b.step(t, [{'c': [*(1000*np.array(xy)), 1000.]}])
            self.assertEqual(aa['state'], bb['state'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
