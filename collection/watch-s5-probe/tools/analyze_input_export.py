"""Extend the unchanged v2 verifier with input-probe provenance and raw-to-row checks."""
import argparse
import json
import math
import statistics
import sys
import decode_research_export as decoder


def positive_p95(values):
    values = sorted(v for v in values if v > 0)
    return values[math.ceil(.95 * len(values)) - 1] if values else None


def ascii_units(text):
    # JS wire encoder emits one \u escape per UTF-16 code unit outside ASCII.
    return sum(1 if ord(c) < 127 else 6 if ord(c) <= 65535 else 12 for c in text)


def analyze(record):
    out = dict(record['report'])
    rows, tail = record['rows'], record['tail']
    gaps = [b[1] - a[1] for a, b in zip(rows, rows[1:])]
    reported = list(tail['quality']['warnings']) if tail else None
    derived = []
    for condition, label in [(not rows, 'no_samples'), (any(g < 0 for g in gaps), 'clock_regression'),
                             (0 in gaps, 'zero_callback_intervals'), (any(g > 1000 for g in gaps), 'callback_gap_over_1s')]:
        if condition:
            derived.append(label)
    out.update(reported_warnings=reported, derived_time_warnings=derived,
               warnings_provenance='warnings is combined; reported_warnings copies tail; derived_time_warnings is computed',
               statistics_definition={'p95_positive_gap_ms': 'sorted strictly-positive gaps[ceil(0.95*N)-1]; nearest rank',
                                      'callback_hz': '(N-1)*1000/(last_callback_ms-first_callback_ms); not hardware Hz'},
               input_observation=None)
    # Additive report; original decoder and originals retain their bytes and classifications.
    if record['metadata']['metadata'].get('record_purpose') != 'input_probe':
        return out
    probe = tail.get('input_probe') if tail else None
    if not isinstance(probe, dict) or probe.get('schema_version') != 1 or probe.get('api') != '@system.sensor.subscribe' or probe.get('requested_interval') != 'high':
        raise ValueError('invalid input probe identity/report')
    callbacks = probe.get('callbacks')
    if not isinstance(callbacks, list) or len(callbacks) > 128:
        raise ValueError('invalid raw callback count')
    if ascii_units(json.dumps(probe, separators=(',', ':'), ensure_ascii=False)) > 49152:
        raise ValueError('input probe report exceeds budget')
    mapped, raw_bytes, mono, shapes = [], 0, [], []
    for i, obs in enumerate(callbacks):
        if not isinstance(obs, dict) or obs.get('callback_index') != i or not decoder.number(obs.get('callback_epoch_ms')):
            raise ValueError('invalid raw callback observation')
        raw = obs.get('raw_json')
        if not isinstance(raw, str) or ascii_units(raw) > 2048:
            raise ValueError('raw callback exceeds budget')
        raw_bytes += ascii_units(raw)
        if raw_bytes > 24576:
            raise ValueError('raw total exceeds budget')
        # The watch generated each string from a JS callback object; retain it, do not rewrite it.
        value = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('non-finite raw value')))
        shapes.append(sorted(value) if isinstance(value, dict) else type(value).__name__)
        if obs.get('performance_now_ms') is not None:
            if not decoder.number(obs['performance_now_ms']):
                raise ValueError('invalid runtime clock read')
            mono.append(obs['performance_now_ms'])
        seq = obs.get('row_sequence')
        if seq is None:
            continue
        if isinstance(seq, bool) or not isinstance(seq, int) or seq != len(mapped) or seq >= len(rows):
            raise ValueError('raw-to-row sequence mapping invalid')
        p = value if isinstance(value, dict) and all(decoder.number(value.get(k)) for k in ('x', 'y', 'z')) else value.get('ACCELEROMETER') if isinstance(value, dict) else None
        if not isinstance(p, dict) or not all(decoder.number(p.get(k)) for k in ('x', 'y', 'z')):
            raise ValueError('raw-to-row XYZ mapping invalid')
        if rows[seq][1] != obs['callback_epoch_ms'] or rows[seq][2:5] != [p[k] for k in ('x', 'y', 'z')]:
            raise ValueError('raw-to-row value/arrival mapping invalid')
        mapped.append(seq)
    if mapped != list(range(len(rows))):
        raise ValueError('raw-to-row mapping is incomplete')
    out['input_observation'] = {
        'result': probe.get('result'), 'raw_callback_count': len(callbacks), 'mapped_rows': len(mapped),
        'raw_json_ascii_bytes': raw_bytes, 'fractional_xyz_observed': any(v != int(v) for r in rows for v in r[2:5]),
        'raw_root_shapes': shapes, 'runtime_clock_reads': len(mono),
        'runtime_clock_regressions': sum(b < a for a, b in zip(mono, mono[1:])),
        'runtime_clock_nonzero_deltas': sum(b > a for a, b in zip(mono, mono[1:])),
        'hardware_time_verified': False, 'hardware_sampling_hz': None,
        'unit_verified': False, 'axis_verified': False, 'cross_device_sync_verified': False,
        'interpretation': 'Observed callback values only. Raw time fields and performance.now require separate semantic validation.'}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        record = decoder.decode_packets(decoder.scan_media([args.input]))
        record['report'] = analyze(record)
        decoder.save_export(record, args.output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(record['report'], ensure_ascii=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
