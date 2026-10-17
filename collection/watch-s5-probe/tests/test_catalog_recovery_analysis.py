import copy
import unittest
from test_runtime_timing_analysis import runtime_fixture, analysis
from test_research_ready_analysis import POLICY

class CatalogRecoveryAnalysis(unittest.TestCase):
    def test_0414_requires_same_startup_contract_and_never_rewrites_input(self):
        record=runtime_fixture()
        record['metadata']['row_fields']=list(analysis.decoder.FIELDS)
        record['metadata']['metadata'].update(app_version='0.4.14',
            acquisition_reporting_policy=dict(schema_version=1,mode='lifecycle_only',raw_callback_capture='unchanged',final_report='before_seal'),
            startup_rate_policy=copy.deepcopy(POLICY))
        record['tail']['startup_rate_observation']=dict(schema_version=1,status='not_checked_before_stop',
            evaluated_epoch_ms=None,elapsed_ms=None,count=None,callback_span_ms=None,arrival_per_second=None)
        before=copy.deepcopy(record)
        self.assertEqual(analysis.analyze(record)['startup_rate_verification']['status'],'not_checked_before_stop')
        self.assertEqual(record,before)
        del record['tail']['startup_rate_observation']
        with self.assertRaises(ValueError):analysis.analyze(record)

    def test_unknown_0416_remains_rejected(self):
        record=runtime_fixture();record['metadata']['metadata']['app_version']='0.4.16'
        with self.assertRaises(ValueError):analysis.analyze(record)

if __name__=='__main__':unittest.main()
