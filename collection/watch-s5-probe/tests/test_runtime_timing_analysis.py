import copy
import unittest
from test_foreground_source_archive import fixture, analysis

NAMES = ('callback_body_ms', 'callback_between_ms', 'tick_body_ms', 'tick_entry_gap_ms',
         'tick_between_ms', 'notify_body_ms', 'block_encode_ms', 'write_call_ms', 'write_ack_ms')


def runtime_fixture():
    r = fixture()
    r['metadata']['metadata'].update(app_version='0.4.10', requested_duration_ms=600000,
        storage_policy={'schema_version': 1, 'row_trigger': 128, 'timed_flush_ms': 8000,
                        'write_timeout_ms': 8000, 'max_buffered_rows': 512,
                        'semantics': 'JS_scheduling_dependent_no_durability_guarantee'},
        runtime_timing_policy={'schema_version': 1, 'mode': 'bounded_runtime_observation',
            'clock': 'Date.now_wall_clock_not_monotonic', 'top_limit': 5, 'extra_timers': 0,
            'physical_or_hardware_verified': False})
    r['tail']['runtime_timing_observation'] = {'schema_version': 1,
        'clock': 'Date.now_wall_clock_not_monotonic', 'cutoff': 'tail_construction',
        'retention': 'summary_histogram_and_top5_per_metric',
        'histogram_upper_bounds_ms': [0, 1, 5, 20, 100, 500, 1000, 2000, None],
        'invalid_clock_reads': 0, 'metrics': {name: {'count': 0, 'total_ms': 0,
            'max_ms': 0, 'pending': int(name == 'tick_body_ms'), 'invalid': 0,
            'histogram': [0] * 9, 'top': []} for name in NAMES}}
    return r


class RuntimeTimingAnalysis(unittest.TestCase):
    def test_valid_diagnostic_retains_raw_and_pending_without_claiming_a_cause(self):
        r = runtime_fixture()
        before = copy.deepcopy(r)
        try:
            result = analysis.analyze(r)
        except ValueError as error:
            self.fail('valid runtime profile is not implemented: ' + str(error))
        self.assertFalse(result['runtime_timing_verification']['watch_cost_or_cause_verified'])
        self.assertEqual(result['runtime_timing_verification']['pending_spans']['tick_body_ms'], 1)
        self.assertEqual(r, before)

    def test_declared_observation_is_required_and_future_version_refused(self):
        for key in ('missing', 'policy', 'future'):
            r = runtime_fixture()
            if key == 'missing':
                del r['tail']['runtime_timing_observation']
            elif key == 'policy':
                r['metadata']['metadata']['runtime_timing_policy']['extra_timers'] = 1
            else:
                r['metadata']['metadata']['app_version'] = '0.4.13'
            with self.assertRaises(ValueError):
                analysis.analyze(r)

    def test_observation_limits_are_schema_checks_not_new_capture_gates(self):
        for bad in ('bool', 'top', 'histogram', 'negative', 'metric'):
            r = runtime_fixture()
            obs = r['tail']['runtime_timing_observation']
            metric = obs['metrics']['callback_body_ms']
            if bad == 'bool': metric['pending'] = True
            elif bad == 'top': metric['top'] = [None] * 6
            elif bad == 'histogram': metric['histogram'][0] = 1
            elif bad == 'negative': metric['max_ms'] = -1
            else: obs['metrics']['invented'] = metric.copy()
            with self.assertRaises(ValueError):
                analysis.analyze(r)


if __name__ == '__main__':
    unittest.main()
