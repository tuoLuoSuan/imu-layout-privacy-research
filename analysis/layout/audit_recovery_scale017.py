"""Post-hoc recovery-at-scale audit of frozen predictions, with no new inference.

The pre-existing primary tolerance stays at 0.5 m. Each tolerance independently
repeats same-category one-to-one matching, including failed/empty predictions.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from . import multi_instance as M
from .reportmatrix016 import wilson


def main(root, native, output):
    root, native, output = Path(root), Path(native), Path(output)
    rows = []
    hashes = []
    expected_arms = {'new_raw', 'old_raw_matched', 'watch_absent', 'watch_clock10s',
                     'truth_pose_same_predicted_actions'}
    for room in range(11100, 11132):
        source = root / f'multi-{room:05d}' / 'results.json'
        result = json.loads(source.read_text(encoding='utf-8'))
        truth_path = native / f'multi-{room:05d}.json'
        truth = M.load_native(truth_path)['gt']
        if {row['arm'] for row in result['rows']} != expected_arms:
            raise ValueError(f'Arm mismatch in {source}')
        if hashlib.sha256(truth_path.read_bytes()).hexdigest() != result['native_sha256']:
            raise ValueError(f'Native geometry differs from frozen record {room}')
        hashes.append({'room': room, 'result_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
        for arm in result['rows']:
            for tolerance in (.10, .20, .25, .30, .40, .50, .75, 1.00):
                score = M.score_instances(arm['prediction']['boxes'], truth, tolerance=tolerance)
                if tolerance == .50:
                    if score['all_instances_hit'] != arm['score']['all_instances_hit'] or abs(score['f1'] - arm['score']['f1']) > 1e-12:
                        raise AssertionError(f'Frozen primary score mismatch in {room}/{arm["arm"]}')
                rows.append({'room': room, 'arm': arm['arm'], 'tolerance_m': tolerance,
                             'whole': score['all_instances_hit'], 'f1': score['f1'],
                             'tp': score['tp'], 'fp': score['fp'], 'fn': score['fn']})
    cells = []
    for arm in sorted(expected_arms):
        for tolerance in sorted({r['tolerance_m'] for r in rows}):
            selected = [r for r in rows if r['arm'] == arm and r['tolerance_m'] == tolerance]
            k = sum(r['whole'] for r in selected)
            cells.append({'arm': arm, 'tolerance_m': tolerance, 'n': len(selected), 'whole': k,
                          'rate': k / len(selected), 'wilson95': wilson(k, len(selected)),
                          'mean_room_f1': float(np.mean([r['f1'] for r in selected]))})
    payload = {'scope': 'Post-hoc evaluation-only sensitivity. Primary tolerance remains0.5m. Not an activity-budget or information-theoretic threshold.',
               'n_rooms': 32, 'primary_scores_verified': 160, 'source_records': hashes,
               'matching': 'Recomputed at each tolerance; same-category one-to-one; no excluded failures',
               'cells': cells, 'rows': rows}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'recovery-scale.json').write_text(json.dumps(payload, indent=1), encoding='utf-8')
    with (output / 'recovery-scale.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cells[0]))
        writer.writeheader()
        writer.writerows(cells)
    for cell in cells:
        if cell['tolerance_m'] in (.25, .5, .75, 1.):
            print(cell['arm'], cell['tolerance_m'], f"{cell['whole']}/{cell['n']}", round(cell['mean_room_f1'], 4))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='output/research-sync/2026-11-09-raw-input-repair-011/confirm32')
    parser.add_argument('--native', default='output/research-sync/2026-11-09-joint-input-and-recovery-010/raw-native800/native')
    parser.add_argument('--out', default='output/research-sync/2026-11-10-budget-audit-017')
    args = parser.parse_args()
    main(args.root, args.native, args.out)
