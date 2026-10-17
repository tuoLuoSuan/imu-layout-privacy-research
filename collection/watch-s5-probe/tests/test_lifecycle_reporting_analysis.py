import copy
import unittest
from test_runtime_timing_analysis import runtime_fixture, analysis

POLICY = dict(schema_version=1, mode='lifecycle_only', raw_callback_capture='unchanged', final_report='before_seal')


class LifecycleReportingAnalysis(unittest.TestCase):
    def record(self):
        r = runtime_fixture()
        r['metadata']['metadata'].update(app_version='0.4.12', acquisition_reporting_policy=POLICY.copy())
        return r

    def test_explicit_policy_is_required_and_input_remains_unchanged(self):
        r = self.record()
        before = copy.deepcopy(r)
        result = analysis.analyze(r)
        self.assertEqual(result['acquisition_reporting_verification']['policy'], POLICY)
        self.assertFalse(result['acquisition_reporting_verification']['native_rate_or_root_cause_verified'])
        self.assertEqual(r, before)

    def test_unknown_policy_or_future_version_rejected(self):
        for alteration in ('missing', 'mode', 'bool', 'extra', 'future'):
            r = self.record()
            m = r['metadata']['metadata']
            if alteration == 'missing':
                del m['acquisition_reporting_policy']
            elif alteration == 'mode':
                m['acquisition_reporting_policy']['mode'] = 'silent'
            elif alteration == 'bool':
                m['acquisition_reporting_policy']['schema_version'] = True
            elif alteration == 'extra':
                m['acquisition_reporting_policy']['rate_fixed'] = True
            else:
                m['app_version'] = '0.4.13'
            with self.assertRaises(ValueError):
                analysis.analyze(r)
