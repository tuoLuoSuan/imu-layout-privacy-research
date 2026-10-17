"""Validate bounded diagnostic structure; no additional capture-acceptance thresholds."""
import json
import math

NAMES = ('callback_body_ms', 'callback_between_ms', 'tick_body_ms', 'tick_entry_gap_ms',
         'tick_between_ms', 'notify_body_ms', 'block_encode_ms', 'write_call_ms', 'write_ack_ms')
BOUNDS = [0, 1, 5, 20, 100, 500, 1000, 2000, None]
POLICY = {'schema_version': 1, 'mode': 'bounded_runtime_observation',
          'clock': 'Date.now_wall_clock_not_monotonic', 'top_limit': 5, 'extra_timers': 0,
          'physical_or_hardware_verified': False}


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def integer(value):
    return type(value) is int and 0 <= value <= 2**53 - 1


def validate(policy, observation):
    if not isinstance(policy, dict) or policy != POLICY or any(
            type(policy[k]) is not type(v) for k, v in POLICY.items()):
        raise ValueError('unknown runtime timing policy')
    o = observation
    if not isinstance(o, dict) or type(o.get('schema_version')) is not int or o['schema_version'] != 1:
        raise ValueError('missing runtime timing observation')
    if o.get('clock') != POLICY['clock'] or o.get('cutoff') != 'tail_construction' or o.get(
            'retention') != 'summary_histogram_and_top5_per_metric' or o.get('histogram_upper_bounds_ms') != BOUNDS:
        raise ValueError('unknown runtime timing interpretation')
    if not integer(o.get('invalid_clock_reads')) or len(json.dumps(o, ensure_ascii=True)) > 16000:
        raise ValueError('runtime observation outside bounded schema')
    metrics = o.get('metrics')
    if not isinstance(metrics, dict) or set(metrics) != set(NAMES):
        raise ValueError('unknown runtime metrics')
    for m in metrics.values():
        if not isinstance(m, dict) or not all(integer(m.get(k)) for k in ('count', 'pending', 'invalid')):
            raise ValueError('invalid runtime counts')
        if not all(number(m.get(k)) for k in ('total_ms', 'max_ms')) or m['max_ms'] > m['total_ms']:
            raise ValueError('invalid runtime durations')
        hist, top = m.get('histogram'), m.get('top')
        if not isinstance(hist, list) or len(hist) != len(BOUNDS) or not all(integer(v) for v in hist) or sum(hist) != m['count']:
            raise ValueError('invalid runtime histogram')
        if not isinstance(top, list) or len(top) != min(5, m['count']):
            raise ValueError('invalid runtime retained spans')
        durations = []
        for span in top:
            if not isinstance(span, dict) or not all(number(span.get(k)) for k in ('start_epoch_ms', 'end_epoch_ms', 'duration_ms')):
                raise ValueError('invalid runtime span')
            if span['end_epoch_ms'] - span['start_epoch_ms'] != span['duration_ms'] or not (
                    span.get('context') is None or number(span.get('context'))):
                raise ValueError('runtime span duration mismatch')
            durations.append(span['duration_ms'])
        if durations != sorted(durations, reverse=True) or (durations and durations[0] != m['max_ms']):
            raise ValueError('runtime maximum mismatch')
        if not m['count'] and (m['total_ms'] != 0 or m['max_ms'] != 0):
            raise ValueError('empty runtime metric with duration')
    return {'schema_version': 1, 'bounded_schema_verified': True,
            'pending_spans': {name: metrics[name]['pending'] for name in NAMES},
            'invalid_clock_reads': o['invalid_clock_reads'], 'watch_cost_or_cause_verified': False,
            'note': 'Same JS loop and wall clock; asynchronous ACK duration is not synchronous blocking; no new capture acceptance gate.'}
