import copy
import unittest
from test_runtime_timing_analysis import runtime_fixture,analysis
from test_research_ready_analysis import POLICY

def daily_record():
    r=runtime_fixture();r['metadata']['row_fields']=list(analysis.decoder.FIELDS)
    r['metadata']['metadata'].update(app_version='0.4.15',
        acquisition_reporting_policy=dict(schema_version=1,mode='lifecycle_only',raw_callback_capture='unchanged',final_report='before_seal'),startup_rate_policy=copy.deepcopy(POLICY))
    r['tail']['startup_rate_observation']=dict(schema_version=1,status='not_checked_before_stop',evaluated_epoch_ms=None,elapsed_ms=None,count=None,callback_span_ms=None,arrival_per_second=None)
    return r

class DailyFinishAnalysis(unittest.TestCase):
    def test_daily_version_keeps_existing_policy_and_source_bytes(self):
        r=daily_record();before=copy.deepcopy(r)
        self.assertEqual(analysis.analyze(r)['startup_rate_verification']['status'],'not_checked_before_stop')
        self.assertEqual(r,before)
    def test_complete_future_fixture_still_refused(self):
        r=daily_record();r['metadata']['metadata']['app_version']='0.4.16'
        with self.assertRaisesRegex(ValueError,'unknown foreground screen policy'):analysis.analyze(r)

if __name__=='__main__':unittest.main()
