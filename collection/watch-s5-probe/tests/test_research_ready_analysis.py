from pathlib import Path
import copy
import importlib.util
import unittest
import sys

tools = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0,str(tools))
candidate = tools / 'startup_rate_contract.py'
if candidate.exists():
    spec = importlib.util.spec_from_file_location('startup_contract', candidate)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validate = module.validate
else:
    validate = lambda *args: {'status': 'not_implemented'}

POLICY = dict(schema_version=1, mode='stop_and_preserve_slow_high_start', check_after_ms=5000,
    minimum_callback_span_ms=2500, minimum_arrival_per_second=10,
    applies_to='generic_high_duration_at_least_10s',
    rate_semantics='JS_callback_arrival_not_hardware_or_research_gate', retry='none')

def fixture(gap=60):
    rows = [dict(callback_epoch_ms=t, sequence=i) for i,t in enumerate(range(0,5001,gap))]
    span=rows[-1]['callback_epoch_ms']-rows[0]['callback_epoch_ms']
    rate=(len(rows)-1)*1000/span
    status='stopped_slow' if rate<10 else 'passed'
    head=dict(started_epoch_ms=0,metadata=dict(sensor_path='generic',requested_interval='high',requested_duration_ms=600000))
    tail=dict(stopped_epoch_ms=5000,stop_reason='startup_rate_low' if rate<10 else 'manual',quality=dict(warnings=['startup_rate_low'] if rate<10 else []))
    observation=dict(schema_version=1,status=status,evaluated_epoch_ms=5000,elapsed_ms=5000,
        count=len(rows),callback_span_ms=span,arrival_per_second=rate)
    return [copy.deepcopy(POLICY),observation,head,tail,rows]

class StartupRateAnalysis(unittest.TestCase):
    def test_normal_and_slow_are_recomputed_without_changing_rows(self):
        for gap,status in [(60,'passed'),(200,'stopped_slow')]:
            args=fixture(gap);before=copy.deepcopy(args)
            self.assertEqual(validate(*args)['status'],status)
            self.assertEqual(args,before)
    def test_policy_changes_and_booleans_are_rejected(self):
        for key,value in [('check_after_ms',1),('minimum_arrival_per_second',True),('retry','automatic')]:
            args=fixture();args[0][key]=value
            with self.assertRaises(ValueError):validate(*args)
    def test_fabricated_check_counts_times_and_rate_are_rejected(self):
        for key,value in [('count',2),('evaluated_epoch_ms',100),('callback_span_ms',9999),('arrival_per_second',50),('schema_version',True)]:
            args=fixture();args[1][key]=value
            with self.assertRaises(ValueError):validate(*args)
    def test_stop_and_warning_must_preserve_failed_startup(self):
        for key in ['stop','warning','status']:
            args=fixture(200)
            if key=='stop':args[3]['stop_reason']='duration'
            elif key=='warning':args[3]['quality']['warnings']=[]
            else:args[1]['status']='passed'
            with self.assertRaises(ValueError):validate(*args)
    def test_mid_is_not_a_pass_or_a_high_failure(self):
        args=fixture(200);args[2]['metadata']['requested_interval']='mid'
        args[1]=dict(schema_version=1,status='not_applicable',evaluated_epoch_ms=None,elapsed_ms=None,count=None,callback_span_ms=None,arrival_per_second=None)
        args[3].update(stop_reason='manual',quality=dict(warnings=[]))
        self.assertEqual(validate(*args)['status'],'not_applicable')
        args[1]['status']='passed'
        with self.assertRaises(ValueError):validate(*args)
    def test_manual_before_the_check_is_explicitly_not_validated(self):
        args=fixture();args[1]=dict(schema_version=1,status='not_checked_before_stop',evaluated_epoch_ms=None,elapsed_ms=None,count=None,callback_span_ms=None,arrival_per_second=None)
        self.assertEqual(validate(*args)['status'],'not_checked_before_stop')
        args[1]['count']=len(args[-1])
        with self.assertRaises(ValueError):validate(*args)
    def test_unknown_status_or_pending_tail_is_rejected(self):
        for status in ['pending','native_fixed','']:
            args=fixture();args[1]['status']=status
            with self.assertRaises(ValueError):validate(*args)
    def test_insufficient_span_remains_a_visible_failure(self):
        args=fixture();args[-1][:]=[dict(callback_epoch_ms=4500,sequence=0)]
        args[1].update(status='insufficient',count=1,callback_span_ms=0,arrival_per_second=None)
        args[3].update(stop_reason='startup_rate_unconfirmed',quality=dict(warnings=['startup_rate_unconfirmed']))
        self.assertEqual(validate(*args)['status'],'insufficient')
    def test_unimplemented_future_version_is_still_rejected(self):
        from test_runtime_timing_analysis import runtime_fixture, analysis
        record=runtime_fixture()
        record['metadata']['metadata']['app_version']='0.4.16'
        with self.assertRaises(ValueError):analysis.analyze(record)

if __name__=='__main__':unittest.main()
