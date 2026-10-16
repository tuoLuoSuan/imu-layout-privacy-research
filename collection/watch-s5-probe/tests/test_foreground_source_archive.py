from pathlib import Path
import copy
import importlib.util
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_continuity_source_archive import fixture as prior
import analyze_continuity_export as previous
candidate = Path(__file__).resolve().parents[1] / 'tools/analyze_foreground_export.py'
if candidate.exists():
    spec = importlib.util.spec_from_file_location('foreground_analysis', candidate)
    analysis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analysis)
else:
    analysis = previous

def fixture():
    r = prior()
    r['metadata']['metadata'].update(app_version='0.4.3', screen_policy={
        'schema_version': 1, 'mode': 'foreground_keep_awake',
        'api': '@system.brightness.setKeepScreenOn', 'physical_screen_verified': False})
    r['tail']['screen_observation'] = {'schema_version': 1, 'mode': 'foreground_keep_awake',
        'api': '@system.brightness.setKeepScreenOn', 'physical_screen_verified': False,
        'acquire': {'status': 'success', 'requested_epoch_ms': 900, 'completed_epoch_ms': 950},
        'release': {'status': 'success', 'requested_epoch_ms': 2000, 'completed_epoch_ms': 2100},
        'late_release_attempts': 0}
    return r

class ForegroundAnalysis(unittest.TestCase):
    def test_screen_report_is_required_and_not_physical_screen_proof(self):
        r = analysis.analyze(fixture())
        self.assertIn('screen_policy_verification', r)
        self.assertFalse(r['screen_policy_verification']['physical_screen_verified'])
    def test_missing_or_fake_acquisition_is_rejected(self):
        for alteration in ('missing', 'failed', 'future_acquire'):
            r = fixture()
            if alteration == 'missing':
                del r['tail']['screen_observation']
            elif alteration == 'failed':
                r['tail']['screen_observation']['acquire']['status'] = 'failed'
            else:
                r['tail']['screen_observation']['acquire']['completed_epoch_ms'] = 1100
            with self.assertRaises(ValueError):
                analysis.analyze(r)
    def test_release_failure_remains_warning_even_if_tail_omits_it(self):
        r = fixture()
        r['tail']['screen_observation']['release'].update(status='timeout', error={'message': 'timeout', 'code': None})
        out = analysis.analyze(r)
        self.assertIn('screen_release_unconfirmed', out['warnings'])
        self.assertEqual(out['session_status'], 'sealed_with_warnings')
    def test_pending_or_invented_physical_confirmation_is_rejected(self):
        for key in ('pending', 'physical'):
            r = fixture()
            if key == 'pending':
                r['tail']['screen_observation']['release']['status'] = 'pending'
            else:
                r['tail']['screen_observation']['physical_screen_verified'] = True
            with self.assertRaises(ValueError):
                analysis.analyze(r)

if __name__ == '__main__':
    unittest.main()
