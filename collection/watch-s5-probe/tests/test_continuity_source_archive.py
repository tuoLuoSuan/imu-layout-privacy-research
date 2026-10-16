from pathlib import Path
import copy
import importlib.util
import json
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import analyze_precise_export as previous
candidate=Path(__file__).resolve().parents[1]/'tools/analyze_continuity_export.py'
if candidate.exists():
    spec=importlib.util.spec_from_file_location('continuity_analysis',candidate)
    analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)
else:analysis=previous
from test_precise_source_archive import fixture as original

def fixture():
    r=original();r['metadata']['started_epoch_ms']=1000;r['tail']['stopped_epoch_ms']=2000;r['tail']['stop_reason']='duration'
    r['metadata']['metadata'].update(app_version='0.4.2',sensor_path='generic',continuity_policy={
        'schema_version':1,'heartbeat_period_ms':1000,'tick_delay_warning_ms':1500,'silence_limit_ms':3000,
        'time_basis':'JS_callback_wall_clock','external_liveness_reference':False})
    r['tail']['continuity_observation']={'schema_version':1,'semantics':'JS_wall_clock_observations_only','accepted_rows':2,
        'first_accepted_epoch_ms':1000,'last_accepted_epoch_ms':1060,'started_epoch_ms':1000,'stopped_epoch_ms':2000,
        'start_gap_ms':0,'terminal_gap_ms':940,'max_no_accepted_gap_ms':940,
        'tick_count':1,'heartbeat_count':1,'last_tick_epoch_ms':2000,'max_tick_gap_ms':1000,
        'terminal_tick_gap_ms':0,'late_tick_count':0,'silence_observed':False,'external_liveness_reference':False}
    r['events']=[{'callback_epoch_ms':2000,'type':'capture_heartbeat','detail':json.dumps({'i':1,'n':2,'a':1060,'g':940})}]
    return r

class ContinuityAnalysis(unittest.TestCase):
    def test_verified_evidence_does_not_claim_external_liveness(self):
        r=analysis.analyze(fixture());self.assertIn('continuity_verification',r)
        self.assertFalse(r['continuity_verification']['external_liveness_reference'])
        self.assertIsNone(r['hardware_sampling_hz'])
    def test_mode_or_summary_tampering_is_rejected(self):
        for key,value in [('accepted_rows',3),('terminal_gap_ms',0),('first_accepted_epoch_ms',1001),('max_no_accepted_gap_ms',1000)]:
            r=fixture();r['tail']['continuity_observation'][key]=value
            with self.assertRaises(ValueError):analysis.analyze(r)
        r=fixture();r['metadata']['metadata']['sensor_path']='legacy'
        with self.assertRaises(ValueError):analysis.analyze(r)
    def test_missing_heartbeat_or_invented_sample_count_is_rejected(self):
        r=fixture();r['events']=[]
        with self.assertRaises(ValueError):analysis.analyze(r)
        r=fixture();r['events'][0]['detail']=json.dumps({'i':1,'n':9,'a':1060,'g':940})
        with self.assertRaises(ValueError):analysis.analyze(r)
    def test_unflagged_terminal_silence_cannot_remain_plain_sealed(self):
        r=fixture();c=r['tail']['continuity_observation'];r['tail']['stopped_epoch_ms']=6000
        c.update(stopped_epoch_ms=6000,terminal_gap_ms=4940,max_no_accepted_gap_ms=4940,terminal_tick_gap_ms=4000,silence_observed=True)
        out=analysis.analyze(r);self.assertIn('duration_with_terminal_silence',out['warnings'])
        self.assertEqual(out['session_status'],'sealed_with_warnings')
    def test_probe_or_old_formal_record_requires_its_own_analyzer(self):
        r=fixture();r['metadata']['metadata']['record_purpose']='input_probe'
        with self.assertRaises(ValueError):analysis.analyze(r)
        r=fixture();del r['metadata']['metadata']['continuity_policy']
        with self.assertRaises(ValueError):analysis.analyze(r)

if __name__=='__main__':unittest.main()
