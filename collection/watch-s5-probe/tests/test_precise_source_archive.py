from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import analyze_precise_export as analysis

def fixture():
    return {'metadata':{'metadata':{'record_purpose':'recording','acquisition_api':'@system.sensor.subscribe','requested_interval':'high'}},
      'rows':[[0,1000,0.125,2.5,9.8,'visible'],[1,1060,0.25,2.6,9.7,'visible']],
      'tail':{'quality':{'warnings':[]},'acquisition_observation':{'schema_version':1,'status':'stopped','sensor_path':'generic',
        'api':'@system.sensor.subscribe','requested_interval':'high','accepted_rows':2,'valid_xyz_callbacks':2,'callback_count':2,
        'fractional_xyz_scalars':6,'first_callback_json':'{"ACCELEROMETER":{"x":0.125,"y":2.5,"z":9.8}}',
        'last_callback_json':'{"ACCELEROMETER":{"x":0.25,"y":2.6,"z":9.7}}',
        'first_accepted_callback_epoch_ms':1000,'last_accepted_callback_epoch_ms':1060,
        'cleanup':{'status':'unsubscribe_returned','handle':129}}},'report':{'warnings':[],'session_status':'sealed','hardware_sampling_hz':None}}

class PreciseAnalysis(unittest.TestCase):
    def test_fractional_observation_and_counters_match_without_hardware_rate_claim(self):
        r=analysis.analyze(fixture());self.assertEqual(r['recording_observation']['fractional_xyz_scalars'],6)
        self.assertEqual(r['recording_observation']['accepted_rows'],2);self.assertIsNone(r['hardware_sampling_hz'])
        self.assertFalse(r['recording_observation']['unit_verified'])
    def test_metadata_mode_counters_and_snapshot_tampering_are_refused(self):
        for mutation in ('interval','counter','snapshot'):
            r=fixture()
            if mutation=='interval':r['metadata']['metadata']['requested_interval']='game'
            if mutation=='counter':r['tail']['acquisition_observation']['accepted_rows']=3
            if mutation=='snapshot':r['rows'][0][2]=1.25
            with self.assertRaises(ValueError):analysis.analyze(r)
    def test_no_probe_report_is_silently_treated_as_formal_capture(self):
        r=fixture();r['metadata']['metadata']['record_purpose']='input_probe'
        with self.assertRaises(ValueError):analysis.analyze(r)
    def test_cleanup_failure_remains_explicit(self):
        r=fixture();r['tail']['acquisition_observation']['cleanup']['status']='unsubscribe_exception'
        out=analysis.analyze(r);self.assertFalse(out['recording_observation']['unsubscribe_return_observed'])
        self.assertIn('acquisition_cleanup_not_confirmed',out['warnings'])
        self.assertEqual(out['session_status'],'sealed_with_warnings')

if __name__=='__main__':unittest.main()
