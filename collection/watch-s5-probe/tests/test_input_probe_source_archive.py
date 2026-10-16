import importlib.util
import json
from pathlib import Path
import sys
import unittest

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
import analyze_input_export as analysis
import decode_research_export as decoder

def example():
    probe={'schema_version':1,'api':'@system.sensor.subscribe','requested_interval':'high','requested_duration_ms':2000,
      'result':'completed','hardware_time_semantics':'unverified',
      'callbacks':[{'callback_index':0,'callback_epoch_ms':1010,'performance_now_ms':1.25,'raw_json':'{"ACCELEROMETER":{"x":0.123456789,"y":2,"z":3,"timestamp":555}}','row_sequence':0},
                   {'callback_index':1,'callback_epoch_ms':1010,'performance_now_ms':1.26,'raw_json':'{"x":0.5,"y":4,"z":5}','row_sequence':1}]}
    return {'metadata':{'started_epoch_ms':1000,'metadata':{'record_purpose':'input_probe','acquisition_api':'@system.sensor.subscribe','requested_interval':'high'}},
      'rows':[[0,1010,0.123456789,2,3,'visible'],[1,1010,0.5,4,5,'visible']],
      'tail':{'quality':{'warnings':[]},'input_probe':probe},'report':{'warnings':['zero_callback_intervals'],'hardware_sampling_hz':None}}

class InputAnalysis(unittest.TestCase):
    def test_raw_and_derived_warnings_are_distinct_and_precision_is_observed(self):
        r=analysis.analyze(example())
        self.assertEqual(r['reported_warnings'],[])
        self.assertIn('zero_callback_intervals',r['derived_time_warnings'])
        self.assertTrue(r['input_observation']['fractional_xyz_observed'])
        self.assertFalse(r['input_observation']['hardware_time_verified'])
        self.assertEqual(r['input_observation']['raw_callback_count'],2)
        self.assertIn('ceil',r['statistics_definition']['p95_positive_gap_ms'])
    def test_mutated_row_or_arrival_cannot_pass_raw_mapping(self):
        for field in (1,2):
            r=example();r['rows'][0][field]+=1
            with self.assertRaisesRegex(ValueError,'mapping'):analysis.analyze(r)
    def test_duplicate_sequence_over_budget_and_bad_raw_are_refused(self):
        r=example();r['tail']['input_probe']['callbacks'][1]['row_sequence']=0
        with self.assertRaises(ValueError):analysis.analyze(r)
        r=example();r['tail']['input_probe']['callbacks'][0]['raw_json']='x'*3000
        with self.assertRaises(ValueError):analysis.analyze(r)
    def test_original_record_still_has_distinct_warnings_without_invented_probe(self):
        r=example();r['metadata']['metadata'].pop('record_purpose');r['tail'].pop('input_probe')
        out=analysis.analyze(r);self.assertIsNone(out['input_observation']);self.assertEqual(out['reported_warnings'],[])
    def test_nearest_rank_uses_ceil_not_ds_round(self):
        # 52 positive intervals: round(.95*52)=49 vs ceil(...)=50.
        self.assertEqual(analysis.positive_p95(list(range(1,53))),50)

if __name__=='__main__':unittest.main()
