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
    def test_catalog_version_keeps_original_version_and_screen_evidence_separate(self):
        r = fixture()
        r['metadata']['metadata']['app_version'] = '0.4.4'
        self.assertEqual(analysis.analyze(r)['screen_policy_verification']['release_status'], 'success')
        self.assertEqual(r['metadata']['metadata']['app_version'], '0.4.4')
        r['metadata']['metadata']['app_version'] = '0.4.10'
        with self.assertRaises(ValueError):
            analysis.analyze(r)
    def test_export_screen_profile_keeps_capture_screen_policy_and_raw_version(self):
        r = fixture()
        r['metadata']['metadata']['app_version'] = '0.4.5'
        self.assertFalse(analysis.analyze(r)['screen_policy_verification']['physical_screen_verified'])
        self.assertEqual(r['metadata']['metadata']['app_version'], '0.4.5')
    def test_file_wait_profile_keeps_sealed_capture_evidence_separate(self):
        r = fixture()
        r['metadata']['metadata']['app_version'] = '0.4.6'
        before = copy.deepcopy(r)
        self.assertFalse(analysis.analyze(r)['screen_policy_verification']['physical_screen_verified'])
        self.assertEqual(r, before)
    def test_clean_ui_profile_keeps_recording_evidence_and_raw_unchanged(self):
        r = fixture()
        r['metadata']['metadata']['app_version'] = '0.4.7'
        before = copy.deepcopy(r)
        self.assertEqual(analysis.analyze(r)['screen_policy_verification']['release_status'], 'success')
        self.assertEqual(r, before)
    def test_long_profile_requires_its_exact_storage_policy_without_claiming_durability(self):
        for duration, flush in [(1800000, 8000), (60000, 2000)]:
            r = fixture()
            r['metadata']['metadata'].update(app_version='0.4.8', requested_duration_ms=duration,
                storage_policy={'schema_version': 1, 'row_trigger': 128, 'timed_flush_ms': flush,
                    'write_timeout_ms': 8000, 'max_buffered_rows': 512,
                    'semantics': 'JS_scheduling_dependent_no_durability_guarantee'})
            before = copy.deepcopy(r)
            result = analysis.analyze(r)
            self.assertEqual(result['storage_policy_verification']['timed_flush_ms'], flush)
            self.assertFalse(result['storage_policy_verification']['durability_verified'])
            self.assertEqual(r, before)
            r['metadata']['metadata']['storage_policy']['timed_flush_ms'] = 1234
            with self.assertRaises(ValueError):
                analysis.analyze(r)
            del r['metadata']['metadata']['storage_policy']
            with self.assertRaises(ValueError):
                analysis.analyze(r)
    def test_progressive_profile_accepts_only_declared_steps_with_matching_flush_policy(self):
        for duration in (300000, 600000, 900000, 1200000, 1800000):
            r = fixture()
            flush = 2000 if duration <= 300000 else 8000
            r['metadata']['metadata'].update(app_version='0.4.9', requested_duration_ms=duration,
                storage_policy={'schema_version': 1, 'row_trigger': 128, 'timed_flush_ms': flush,
                    'write_timeout_ms': 8000, 'max_buffered_rows': 512,
                    'semantics': 'JS_scheduling_dependent_no_durability_guarantee'})
            self.assertEqual(analysis.analyze(r)['storage_policy_verification']['timed_flush_ms'], flush)
            r['metadata']['metadata']['requested_duration_ms'] = 720000
            with self.assertRaises(ValueError):
                analysis.analyze(r)
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
