"""Recompute the declared engineering startup check, not research eligibility or native Hz."""
import math

POLICY = dict(schema_version=1, mode='stop_and_preserve_slow_high_start', check_after_ms=5000,
    minimum_callback_span_ms=2500, minimum_arrival_per_second=10,
    applies_to='generic_high_duration_at_least_10s',
    rate_semantics='JS_callback_arrival_not_hardware_or_research_gate', retry='none')
FIELDS = {'schema_version','status','evaluated_epoch_ms','elapsed_ms','count','callback_span_ms','arrival_per_second'}

def natural(v):
    return type(v) is int and 0 <= v <= 2**53-1

def validate(policy, observation, head, tail, rows):
    if not isinstance(policy,dict) or policy != POLICY or any(type(policy[k]) is not type(v) for k,v in POLICY.items()):
        raise ValueError('unknown startup engineering policy')
    o = observation
    if not isinstance(o,dict) or set(o) != FIELDS or type(o['schema_version']) is not int or o['schema_version'] != 1:
        raise ValueError('missing or invalid startup observation')
    meta=head['metadata']
    enabled=meta['sensor_path']=='generic' and meta['requested_interval']=='high' and meta['requested_duration_ms']>=10000
    evaluated=o['status'] in ('passed','stopped_slow','insufficient')
    if not evaluated:
        expected='not_checked_before_stop' if enabled else 'not_applicable'
        if o['status']!=expected or any(o[k] is not None for k in FIELDS-{'schema_version','status'}):
            raise ValueError('unknown or fabricated unchecked startup result')
        if tail['stop_reason'] in ('startup_rate_low','startup_rate_unconfirmed'):
            raise ValueError('startup failure missing its observation')
    else:
        if not enabled or not all(natural(o[k]) for k in ('evaluated_epoch_ms','elapsed_ms','count')):
            raise ValueError('startup observation outside applicable capture')
        if not head['started_epoch_ms']+5000 <= o['evaluated_epoch_ms'] <= tail['stopped_epoch_ms'] or o['elapsed_ms'] != o['evaluated_epoch_ms']-head['started_epoch_ms']:
            raise ValueError('startup check time mismatch')
        n=o['count']
        if n>len(rows):raise ValueError('startup count exceeds rows')
        if n and rows[n-1]['callback_epoch_ms']>o['evaluated_epoch_ms']:
            raise ValueError('startup check counts future rows')
        if n<len(rows) and rows[n]['callback_epoch_ms']<o['evaluated_epoch_ms']:
            raise ValueError('startup check omits earlier rows')
        span=rows[n-1]['callback_epoch_ms']-rows[0]['callback_epoch_ms'] if n else None
        rate=(n-1)*1000/span if span is not None and span>0 else None
        if o['callback_span_ms']!=span or (span is not None and not natural(o['callback_span_ms'])):
            raise ValueError('startup span mismatch')
        if rate is None:
            if o['arrival_per_second'] is not None:raise ValueError('invented startup rate')
        elif type(o['arrival_per_second']) not in (int,float) or not math.isfinite(o['arrival_per_second']) or not math.isclose(rate,o['arrival_per_second'],rel_tol=1e-12):
            raise ValueError('startup arrival rate mismatch')
        sufficient=n>=2 and span is not None and span>=2500
        expected='insufficient' if not sufficient else 'stopped_slow' if rate<10 else 'passed'
        if o['status']!=expected:raise ValueError('startup decision mismatch')
        reason={'stopped_slow':'startup_rate_low','insufficient':'startup_rate_unconfirmed'}.get(expected)
        if reason:
            if tail['stop_reason']!=reason or reason not in tail['quality']['warnings'] or n!=len(rows):
                raise ValueError('startup failure hidden or rows changed after stopping')
        elif tail['stop_reason'] in ('startup_rate_low','startup_rate_unconfirmed'):
            raise ValueError('passing startup contradicts failure reason')
    return dict(status=o['status'],declared_policy=policy,observation_recomputed=True,
                native_rate_or_root_cause_verified=False,research_acceptance_verified=False)
