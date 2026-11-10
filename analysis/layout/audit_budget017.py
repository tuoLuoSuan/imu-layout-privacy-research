"""Read-only audit of the frozen 016 matrix and common motion prefixes.

The optional handset noise streams are a new diagnostic version. No frozen
record, input CSV, trajectory or score is regenerated or overwritten here.
"""
import argparse
import hashlib
import json
import subprocess
import types
from pathlib import Path

import numpy as np

from . import exp_bias014 as E, multi_instance as M, sensor013
from .multi_raw010 import plan
from .reportmatrix016 import main as report_matrix
from .sim_handset import generate


def rms_difference(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def prefix_audit(room, seconds=100.):
    native = E.OLD / 'raw-native800' / 'native' / f'multi-{room:05d}.json'
    scene = M.load_native(native)
    start = json.loads(native.read_text(encoding='utf-8'))['agent_placement']['position']
    scene['S'] = np.array([start['x'], start['z']])
    rows = []
    for mode in ('legacy', 'independent-v1'):
        reference = None
        reference_degraded = None
        reference_prefix_v1 = None
        for visits in (6, 10, 14):
            script, _ = plan(scene, visits=visits)
            phone = generate(scene, 1900000 + room, script_override=script, noise_streams=mode)
            degraded = sensor013.degrade(phone, .5, seed=1910000 + room)
            prefix_v1 = sensor013.degrade(phone, .5, seed=1910000 + room, noise_streams='prefix-v1')
            n = int(seconds * phone['fs'])
            if len(phone['t']) < n:
                raise ValueError('Requested prefix exceeds a generated record')
            if reference is None:
                reference, reference_degraded = phone, degraded
                reference_prefix_v1 = prefix_v1
                continue
            rows.append({'room': room, 'noise_streams': mode, 'visits_a': 6, 'visits_b': visits,
                         'prefix_seconds': seconds, 'n_prefix_samples': n,
                         'duration_a_s': float(reference['t'][-1]), 'duration_b_s': float(phone['t'][-1]),
                         'position_max_difference_m': float(np.abs(reference['truth']['pos'][:n] - phone['truth']['pos'][:n]).max()),
                         'rotation_max_difference': float(np.abs(reference['truth']['R'][:n] - phone['truth']['R'][:n]).max()),
                         'clean_acc_rms_difference': rms_difference(reference['clean_acc'][:n], phone['clean_acc'][:n]),
                         'clean_gyro_rms_difference': rms_difference(reference['clean_gyro'][:n], phone['clean_gyro'][:n]),
                         'measured_acc_rms_difference': rms_difference(reference['acc'][:n], phone['acc'][:n]),
                         'measured_gyro_rms_difference': rms_difference(reference['gyro'][:n], phone['gyro'][:n]),
                         's05_acc_rms_difference': rms_difference(reference_degraded['acc'][:n], degraded['acc'][:n]),
                         's05_gyro_rms_difference': rms_difference(reference_degraded['gyro'][:n], degraded['gyro'][:n]),
                         'prefix_v1_acc_rms_difference': rms_difference(reference_prefix_v1['acc'][:n], prefix_v1['acc'][:n]),
                         'prefix_v1_gyro_rms_difference': rms_difference(reference_prefix_v1['gyro'][:n], prefix_v1['gyro'][:n]),
                         'prefix_v1_timestamp_max_difference_ns': int(np.abs(reference_prefix_v1['ts_ns'][:n] - prefix_v1['ts_ns'][:n]).max())})
    return rows


def main(matrix, output, rooms):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    matrix = Path(matrix)
    report = report_matrix(matrix, output / 'clustered-report.json')
    payload = {'source_matrix': str(matrix), 'source_matrix_sha256': hashlib.sha256(matrix.read_bytes()).hexdigest(),
               'n_rows': len(json.loads(matrix.read_text())['rows']), 'report': report,
               'common_prefix': [row for room in rooms for row in prefix_audit(room)],
               'scope': 'statistical recalculation and generator audit only; no inference, retraining or score changes',
               'noise_streams_default': 'legacy',
               'remaining_prefix_issue': 'Frozen default uses length-dependent draws and record-centred drift. Both opt-in versions are required for prefix consistency. No end-to-end scores were recomputed.'}
    old_source = subprocess.run(['git', 'show', '342dcdb:analysis/layout/sensor013.py'], check=True,
                                capture_output=True, text=True, encoding='utf-8').stdout
    old = types.ModuleType('frozen_sensor013')
    exec(compile(old_source, '342dcdb/sensor013.py', 'exec'), old.__dict__)
    synthetic = {'acc': np.ones((100, 3)), 'gyro': np.ones((100, 3)) * .01,
                 'ts_ns': np.arange(100, dtype=np.int64) * 10000000}
    compatibility = []
    for severity in (0., .5, 1., 2.):
        before = old.degrade(synthetic, severity, seed=17)
        after = sensor013.degrade(synthetic, severity, seed=17)
        equal = all(np.array_equal(before[k], after[k]) for k in ('acc', 'gyro', 'ts_ns'))
        if not equal:
            raise AssertionError('Default sensor model differs from frozen revision')
        compatibility.append({'severity': severity, 'default_arrays_equal_to_342dcdb': equal})
    payload['sensor_legacy_compatibility'] = compatibility
    (output / 'audit.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--matrix', default='output/layout-recon/matrix-11500/matrix.json')
    parser.add_argument('--out', default='output/research-sync/2026-11-10-budget-audit-017')
    parser.add_argument('--rooms', default='11500')
    args = parser.parse_args()
    main(args.matrix, args.out, [int(room) for room in args.rooms.split(',')])
