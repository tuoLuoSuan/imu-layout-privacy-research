"""Validate explicit foreground screen requests, not physical screen power or background support."""
import argparse
import json
import sys
import analyze_continuity_export as previous
import decode_research_export as decoder
import runtime_timing_contract
import startup_rate_contract

POLICY = {'schema_version': 1, 'mode': 'foreground_keep_awake',
          'api': '@system.brightness.setKeepScreenOn', 'physical_screen_verified': False}

def analyze(record):
    out = previous.analyze(record)
    head, tail = record['metadata'], record['tail']
    meta = head['metadata']
    report = tail.get('screen_observation')
    if meta.get('app_version') not in ('0.4.3', '0.4.4', '0.4.5', '0.4.6', '0.4.7', '0.4.8', '0.4.9', '0.4.10', '0.4.11', '0.4.12', '0.4.13', '0.4.14', '0.4.15') or meta.get('screen_policy') != POLICY or meta['screen_policy'].get('physical_screen_verified') is not False:
        raise ValueError('unknown foreground screen policy')
    if meta.get('app_version') in ('0.4.8', '0.4.9', '0.4.10', '0.4.11', '0.4.12', '0.4.13', '0.4.14', '0.4.15'):
        duration = meta.get('requested_duration_ms')
        durations = (2000, 10000, 30000, 60000, 180000, 300000, 1800000)
        if meta['app_version'] in ('0.4.9', '0.4.10', '0.4.11', '0.4.12', '0.4.13', '0.4.14', '0.4.15'):
            durations += (600000, 900000, 1200000)
        if isinstance(duration, bool) or duration not in durations:
            raise ValueError('unknown long-profile duration')
        storage = {'schema_version': 1, 'row_trigger': 128,
                   'timed_flush_ms': 8000 if duration >= 600000 else 2000,
                   'write_timeout_ms': 8000, 'max_buffered_rows': 512,
                   'semantics': 'JS_scheduling_dependent_no_durability_guarantee'}
        observed = meta.get('storage_policy')
        if not isinstance(observed, dict) or observed != storage or any(
                isinstance(observed.get(k), bool) for k in storage if k != 'semantics'):
            raise ValueError('missing or unknown storage policy')
        out['storage_policy_verification'] = dict(storage, durability_verified=False)
    if not isinstance(report, dict) or any(report.get(k) != v for k, v in POLICY.items()) or report.get('physical_screen_verified') is not False:
        raise ValueError('missing or invalid screen observation')
    acquire, release = report.get('acquire'), report.get('release')
    if not isinstance(acquire, dict) or not isinstance(release, dict) or report.get('late_release_attempts') != 0:
        raise ValueError('invalid foreground request lifecycle')
    if acquire.get('status') != 'success' or release.get('status') not in ('success', 'failed', 'exception', 'timeout'):
        raise ValueError('capture without successful acquire or terminal release observation')
    for operation in (acquire, release):
        values = [operation.get(k) for k in ('requested_epoch_ms', 'completed_epoch_ms')]
        if not all(decoder.number(v) and v >= 0 for v in values) or values[1] < values[0]:
            raise ValueError('invalid screen request timing')
    if acquire['completed_epoch_ms'] > head['started_epoch_ms'] or release['requested_epoch_ms'] < head['started_epoch_ms']:
        raise ValueError('screen request / capture order mismatch')
    if release['status'] != 'success':
        out['warnings'] = sorted(set(out['warnings'] + ['screen_release_unconfirmed']))
        if out.get('session_status') == 'sealed':
            out['session_status'] = 'sealed_with_warnings'
    out['screen_policy_verification'] = {
        'head_tail_policy_matches': True, 'acquire_status': acquire['status'],
        'release_status': release['status'], 'physical_screen_verified': False,
        'background_continuity_verified': False,
        'note': 'Ordinary API results only; physical screen state still needs an independent report.'}
    if meta.get('app_version') in ('0.4.10', '0.4.11', '0.4.12', '0.4.13', '0.4.14', '0.4.15'):
        out['runtime_timing_verification'] = runtime_timing_contract.validate(
            meta.get('runtime_timing_policy'), tail.get('runtime_timing_observation'))
    if meta.get('app_version') in ('0.4.12', '0.4.13', '0.4.14', '0.4.15'):
        policy = {'schema_version': 1, 'mode': 'lifecycle_only',
                  'raw_callback_capture': 'unchanged', 'final_report': 'before_seal'}
        reported = meta.get('acquisition_reporting_policy')
        if reported != policy or type(reported.get('schema_version')) is not int:
            raise ValueError('unknown acquisition reporting policy')
        out['acquisition_reporting_verification'] = {
            'policy': policy, 'native_rate_or_root_cause_verified': False}
    if meta.get('app_version') in ('0.4.13', '0.4.14', '0.4.15'):
        if head.get('row_fields') != decoder.FIELDS:
            raise ValueError('missing or unknown startup row fields')
        out['startup_rate_verification'] = startup_rate_contract.validate(
            meta.get('startup_rate_policy'), tail.get('startup_rate_observation'), head, tail,
            [dict(zip(head['row_fields'], row, strict=True)) for row in record['rows']])
    return out

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    try:
        record = decoder.decode_packets(decoder.scan_media([args.input]))
        record['report'] = analyze(record)
        decoder.save_export(record, args.output)
    except (ValueError, OSError, KeyError, TypeError) as e:
        print(str(e), file=sys.stderr)
        return 2
    print(json.dumps(record['report'], ensure_ascii=True))
    return 0

if __name__ == '__main__':
    sys.exit(main())
