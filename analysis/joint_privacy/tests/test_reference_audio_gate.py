"""Reference-only fail-closed guard; synthetic positives do not validate detection."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np

READY = importlib.util.find_spec('analysis.joint_privacy.reference_audio_gate') is not None
if READY:
    from analysis.joint_privacy.reference_audio_gate import validate_cue_candidates, load_cue_support

SHA = 'a' * 64
def candidate():
    return {'global_audio_offset_s': 1., 'matches': [
        {'role': 'M1', 'video_pts_s': 1., 'tone_end_video_pts_s': 1.5, 'correlation': .9},
        {'role': 'task', 'video_pts_s': 3., 'tone_end_video_pts_s': 3.5, 'correlation': .95}]}
def voiced():
    return .1 * np.sin(2 * np.pi * 880 * np.arange(80000) / 16000)
def check(pcm=None, c=None):
    return validate_cue_candidates(voiced() if pcm is None else pcm,
        candidate() if c is None else c, expected_roles=['M1', 'task'],
        source_sha256=SHA, support_s=[0., 5.])

class Entry(unittest.TestCase):
    def test_fail_closed_reference_entry_exists(self):
        self.assertTrue(READY, 'missing explicit audio-candidate acceptance gate')

@unittest.skipUnless(READY, 'gate not yet implemented')
class Gate(unittest.TestCase):
    def assert_rejected(self, r):
        self.assertFalse(r['accepted'])
        self.assertIsNone(r['global_audio_offset_s'])
        self.assertEqual(r['matches'], [])
        self.assertFalse(r['clock_accepted'])

    def test_digital_silence_never_gets_a_plausible_offset(self):
        self.assert_rejected(check(pcm=np.zeros(80000)))

    def test_ds076_quantized_near_zero_counterexample_is_rejected(self):
        pcm = np.zeros(2097835)
        pcm[:261] = np.resize(np.array([-3., 4.]) / 32768, 261)
        c = candidate()
        for m in c['matches']:
            m['correlation'] = 1e-149
        r = check(pcm=pcm, c=c)
        self.assert_rejected(r)
        self.assertIn('insufficient_audio_energy', r['reasons'])

    def test_high_energy_without_candidates_does_not_prove_cues(self):
        r = validate_cue_candidates(voiced(), None, expected_roles=['M1', 'task'],
            source_sha256=SHA, support_s=[0., 5.])
        self.assert_rejected(r)
        self.assertTrue(r['audio_quality']['energy_gate_pass'])

    def test_near_zero_correlations_reject_even_when_energy_is_high(self):
        c = candidate()
        c['matches'][0]['correlation'] = 1e-149
        self.assert_rejected(check(c=c))

    def test_missing_out_of_order_and_duplicate_roles_reject(self):
        for matches in [candidate()['matches'][:1], list(reversed(candidate()['matches'])),
                        [candidate()['matches'][0]] * 2]:
            self.assert_rejected(check(c={'global_audio_offset_s': 1., 'matches': matches}))

    def test_bad_numeric_or_out_of_support_candidate_rejects(self):
        for field, value in [('video_pts_s', -1.), ('tone_end_video_pts_s', 6.),
                             ('correlation', float('nan')), ('correlation', True)]:
            c = candidate()
            c['matches'][0][field] = value
            self.assert_rejected(check(c=c))
        c = candidate()
        c['global_audio_offset_s'] = float('inf')
        self.assert_rejected(check(c=c))

    def test_nonfinite_pcm_is_rejected(self):
        pcm = voiced()
        pcm[5] = np.nan
        self.assert_rejected(check(pcm=pcm))

    def test_qualified_synthetic_candidates_remain_candidates_only(self):
        c = candidate()
        original = copy.deepcopy(c)
        r = check(c=c)
        self.assertTrue(r['accepted'])
        self.assertEqual(r['matches'], c['matches'])
        self.assertEqual(c, original)
        self.assertFalse(r['clock_accepted'])
        self.assertFalse(r['action_reference_created'])
        self.assertFalse(r['physical_av_sync_verified'])

    def test_loader_rejects_legacy_failed_and_wrong_source_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'support.json'
            for result in [candidate(), check(pcm=np.zeros(80000))]:
                p.write_text(json.dumps(result), encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_cue_support(p, source_sha256=SHA)
            p.write_text(json.dumps(check()), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_cue_support(p, source_sha256='b' * 64)
            self.assertTrue(load_cue_support(p, source_sha256=SHA)['accepted'])

if __name__ == '__main__':
    unittest.main()
