"""Synthetic admission/holdout regressions. No physical clock or device result."""
import copy
import unittest
import numpy as np
import evaluation_adapter as e


def mapping():
    return dict(session_id='synthetic-session', source_id='phone', target_id='radar-receive',
                evidence='independent_software_observed', affine_between_anchors_assumed=True,
                max_anchor_gap_s=15., anchors=[dict(source_s=0., target_low_s=9.9, target_high_s=10.1),
                                             dict(source_s=10., target_low_s=19.9, target_high_s=20.1)])


class EvaluationTests(unittest.TestCase):
    def test_unknown_clock_is_not_joined(self):
        self.assertEqual(e.admit_interval(None, 'synthetic-session', 'phone', 'radar-receive', [2., 6.])['status'], 'unknown_clock')

    def test_wrong_session_rejected(self):
        with self.assertRaises(ValueError):
            e.admit_interval(mapping(), 'other-session', 'phone', 'radar-receive', [2., 6.])

    def test_wrong_clock_rejected(self):
        with self.assertRaises(ValueError):
            e.admit_interval(mapping(), 'synthetic-session', 'watch', 'radar-receive', [2., 6.])

    def test_first_frame_alignment_rejected(self):
        m = mapping(); m['evidence'] = 'first_frame_zeroed'
        with self.assertRaises(ValueError):
            e.admit_interval(m, 'synthetic-session', 'phone', 'radar-receive', [2., 6.])

    def test_uncertainty_propagated(self):
        r = e.admit_interval(mapping(), 'synthetic-session', 'phone', 'radar-receive', [2., 6.])
        self.assertTrue(np.allclose(r['common_target_interior_s'], [12.1, 15.9]))
        self.assertFalse(r['physical_clock_validated'])

    def test_no_extrapolation(self):
        r = e.admit_interval(mapping(), 'synthetic-session', 'phone', 'radar-receive', [-1., 6.])
        self.assertEqual(r['status'], 'outside_anchor_support')

    def test_wide_uncertainty_not_shrunk(self):
        m = mapping()
        for a in m['anchors']:
            a['target_low_s'] -= 1.; a['target_high_s'] += 1.
        r = e.admit_interval(m, 'synthetic-session', 'phone', 'radar-receive', [2., 3.])
        self.assertEqual(r['status'], 'insufficient_common_interior')

    def test_anchor_gap_not_hidden(self):
        m = mapping(); m['max_anchor_gap_s'] = 5.
        self.assertEqual(e.admit_interval(m, 'synthetic-session', 'phone', 'radar-receive', [2., 6.])['status'], 'anchor_gap_exceeded')

    def test_nonfinite_gap_cannot_disable_gate(self):
        m = mapping(); m['max_anchor_gap_s'] = float('nan')
        with self.assertRaises(ValueError):
            e.admit_interval(m, 'synthetic-session', 'phone', 'radar-receive', [2., 6.])

    def test_unknown_minimum_is_not_admitted(self):
        with self.assertRaises(ValueError):
            e.admit_interval(mapping(), 'synthetic-session', 'phone', 'radar-receive', [2., 6.], float('nan'))

    def test_empty_session_is_not_an_identity(self):
        m = mapping(); m['session_id'] = ''
        with self.assertRaises(ValueError):
            e.admit_interval(m, '', 'phone', 'radar-receive', [2., 6.])

    def test_causal_clock_interval(self):
        self.assertTrue(np.allclose(e.clock_offset_interval(10., 12., 12.01, 10.04), [1.97, 2.]))
        with self.assertRaises(ValueError):
            e.clock_offset_interval(10., 12., 13., 10.04)

    def test_two_anchor_fit_keeps_c_heldout(self):
        p = np.array([[0., 0.], [1., 0.], [0., 1.], [.1, .2]])
        q = 2*p+np.array([3., 4.]); q[2] += [.3, .4]
        r = e.evaluate_sites(p, q, ['A1', 'B1', 'C1', 'A2'], ['A1', 'B1'])
        self.assertAlmostEqual(r['similarity']['scale'], 2.)
        self.assertAlmostEqual(r['similarity']['heldout'][0]['echo_discrepancy_m'], .5)
        self.assertIsNone(r['physical_phone_position_error_m'])

    def test_missing_holdout_rejected(self):
        with self.assertRaises(ValueError):
            e.evaluate_sites([[0, 0], [1, 0]], [[0, 0], [1, 0]], ['A1', 'B1'], ['A1', 'B1'])

    def test_holdout_cannot_change_fit(self):
        p = np.array([[0., 0.], [1., 0.], [0., 1.]])
        q = p.copy()
        a = e.evaluate_sites(p, q, ['A1', 'B1', 'C1'], ['A1', 'B1'])
        q[2] = [100., 200.]
        b = e.evaluate_sites(p, q, ['A1', 'B1', 'C1'], ['A1', 'B1'])
        self.assertEqual(a['similarity']['transform'], b['similarity']['transform'])

    def test_scale_unit_invariance(self):
        p = np.array([[0., 0.], [1., 0.], [0., 1.]])
        q = 2*p
        a = e.evaluate_sites(p, q, ['A1', 'B1', 'C1'], ['A1', 'B1'])
        b = e.evaluate_sites(1000*p, q, ['A1', 'B1', 'C1'], ['A1', 'B1'])
        self.assertAlmostEqual(a['similarity']['heldout'][0]['echo_discrepancy_m'], b['similarity']['heldout'][0]['echo_discrepancy_m'])
        self.assertNotEqual(a['rigid_nominal_units']['heldout'], b['rigid_nominal_units']['heldout'])

    def test_reflection_is_not_silently_fitted(self):
        p = np.array([[0., 0.], [1., 0.], [0., 1.]])
        q = p*np.array([1., -1.])
        r = e.evaluate_sites(p, q, ['A1', 'B1', 'C1'], ['A1', 'B1'])
        self.assertAlmostEqual(r['similarity']['heldout'][0]['echo_discrepancy_m'], 2.)


if __name__ == '__main__':
    unittest.main()
