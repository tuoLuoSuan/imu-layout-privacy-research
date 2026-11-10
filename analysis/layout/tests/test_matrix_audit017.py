import unittest

import numpy as np

from analysis.layout import matrix016, reportmatrix016, sensor013
from analysis.layout.sim_handset import generate


def result(room, visits, severity, hit=True):
    return dict(room=room, visits=visits, severity=severity,
                all_instances_hit=hit, f1=float(hit), ok=True,
                n_events=10, coverage_free=1.)


class MatrixAuditTests(unittest.TestCase):
    def test_exception_keeps_f1_denominator(self):
        rows = [result(1, 6, 0.), dict(room=2, visits=6, severity=0., error='failed')]
        summary = matrix016.summarise(rows)['v6-s0.0']
        self.assertEqual(summary['n'], 2)
        self.assertEqual(summary['f1'], .5)

    def test_exception_is_failure_in_paired_test(self):
        rows = [result(1, 6, 0.), dict(room=1, visits=6, severity=1., error='failed')]
        comparison = reportmatrix016.paired(rows, 'v6-s0.0', 'v6-s1.0')
        self.assertEqual(comparison['n'], 1)
        self.assertEqual(comparison['a_only'], 1)

    def test_missing_pair_is_explicit(self):
        with self.assertRaises(ValueError):
            reportmatrix016.paired([result(1, 6, 0.)], 'v6-s0.0', 'v6-s1.0')

    def test_duplicate_outcome_is_rejected(self):
        rows = [result(1, 6, 0.), result(1, 6, 0.), result(1, 6, 1.)]
        with self.assertRaises(ValueError):
            reportmatrix016.paired(rows, 'v6-s0.0', 'v6-s1.0')

    def test_repeated_contrasts_do_not_multiply_independent_rooms(self):
        rows = [result(room, v, s, hit=(s == 0.))
                for room in range(1, 4) for v in (6, 10, 14) for s in (0., 1.)]
        pairs = [(f'v{v}-s0.0', f'v{v}-s1.0') for v in (6, 10, 14)]
        report = reportmatrix016.clustered_axis(rows, pairs, bootstrap_samples=100)
        self.assertEqual(report['n_rooms'], 3)
        self.assertEqual(report['n_contrasts_per_room'], 3)
        self.assertEqual(report['p_sign_flip'], .25)


class HandsetNoiseStreamsTests(unittest.TestCase):
    def generate_still(self, seconds, **kwargs):
        segment = dict(start=0., end=seconds, label='other',
                       a=np.array([1., 1.]), b=np.array([1., 1.]), heading=np.array([0., 1.]))
        return generate(dict(W=4., L=4.), seed=7, fs=20., script_override=[segment], **kwargs)

    def test_independent_streams_preserve_both_axes_on_common_prefix(self):
        short = self.generate_still(2., noise_streams='independent-v1')
        long = self.generate_still(4., noise_streams='independent-v1')
        for channel in ('acc', 'gyro'):
            # Numerical derivative boundary stencils differ at machine precision.
            np.testing.assert_allclose(short[channel], long[channel][:len(short['t'])], atol=1e-13, rtol=0)

    def test_default_preserves_legacy_noise_sequence(self):
        output = self.generate_still(2.)
        rng = np.random.default_rng(7)
        np.testing.assert_array_equal(output['acc'], output['clean_acc'] +
                                      rng.normal(0, .035, output['acc'].shape) + [.02, -.01, .03])
        np.testing.assert_array_equal(output['gyro'], output['clean_gyro'] +
                                      rng.normal(0, .003, output['gyro'].shape) + [.0005, -.0004, .0003])

    def test_perturbations_can_preserve_common_prefix(self):
        short = self.generate_still(2., noise_streams='independent-v1')
        long = self.generate_still(4., noise_streams='independent-v1')
        short = sensor013.degrade(short, .5, seed=17, noise_streams='prefix-v1')
        long = sensor013.degrade(long, .5, seed=17, noise_streams='prefix-v1')
        for channel in ('acc', 'gyro', 'ts_ns'):
            np.testing.assert_allclose(short[channel], long[channel][:len(short['t'])], atol=1e-13, rtol=0)


if __name__ == '__main__':
    unittest.main()
