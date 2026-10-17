import copy
import unittest
from test_runtime_timing_analysis import runtime_fixture, analysis


class CatalogPerformanceAnalysis(unittest.TestCase):
    def test_new_version_preserves_timing_validation_and_input(self):
        r = runtime_fixture()
        r['metadata']['metadata']['app_version'] = '0.4.11'
        before = copy.deepcopy(r)
        result = analysis.analyze(r)
        self.assertFalse(result['runtime_timing_verification']['watch_cost_or_cause_verified'])
        self.assertEqual(r, before)

    def test_future_and_missing_observation_rejected(self):
        for mode in ('future', 'missing'):
            r = runtime_fixture()
            r['metadata']['metadata']['app_version'] = '0.4.13' if mode == 'future' else '0.4.11'
            if mode == 'missing':
                del r['tail']['runtime_timing_observation']
            with self.assertRaises(ValueError):
                analysis.analyze(r)
