import importlib.util
from pathlib import Path
import unittest
import numpy as np

SCRIPT = Path(__file__).resolve().parents[2] / 'tools' / 'export-defence-evidence.py'
SPEC = importlib.util.spec_from_file_location('defence_export', SCRIPT)
export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export)


class DefenceEvidenceTest(unittest.TestCase):
    def test_common_translation_cannot_distort_pair_distances(self):
        p = np.array([[0., 0.], [1., 0.], [0., 2.]])
        self.assertLess(export.distance_distortion(p, p + [30., -12.]), 1e-12)
        self.assertGreater(export.distance_distortion(p, p * 2), 0.5)

    def test_house_bootstrap_keeps_routes_together(self):
        # Two independent houses; four perfectly dependent routes per house.
        values = np.array([[[0.]] * 4, [[1.]] * 4])
        ci = export.house_intervals(values, ['dorm', 'dorm'], seed=12)
        np.testing.assert_array_equal(ci, [[0., 1.]])

    def test_rate_preserves_fractional_tie_credit(self):
        r = export.rate(np.array([1/3, 1/3, 0., 1.]))
        self.assertEqual(r['denominator'], 4)
        self.assertAlmostEqual(r['numerator'], 5/3)
        self.assertEqual(r['value'], r['numerator']/r['denominator'])


if __name__ == '__main__':
    unittest.main()
