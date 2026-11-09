"""Diagnostic: does the declared wall prior hurt when the trajectory is correct?

Same rooms, same predicted actions, same decoder family; only the front end is
replaced by the truth pose. If the pool filter is harmless at truth pose, the
harm measured on estimated poses comes from drift, not from the prior.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path
import numpy as np
from . import multi_instance as M
from . import multi_raw010 as X
from .oriented_raw011 import decode as baseline
from .wall_priors013 import decode as wall_decode
from .expansion_report import footprint_all
from .exp_wall013 import case_for

OLD = Path('output/research-sync/2026-11-09-joint-input-and-recovery-010')
ARMS = ['truth_frozen011', 'truth_wall013']


def worker(task):
    i, out = task
    out = Path(out); case = case_for('development8', out, i)
    target = out / ('truthpose-' + case.name + '.json')
    if target.exists():
        return json.loads(target.read_text())
    priors = json.loads((case / 'input/known-priors.json').read_text())
    truth = np.load(case / 'evaluation-truth.npz')
    rows = []

    def oracle(t, A, G):
        return truth['position'][:, :2], truth['rotation'], {'oracle_assisted': True,
                                                            'stationary_mask': np.zeros(len(t), bool), 'causal': False}

    def pairup(*args):
        priors_, t, path, R, runs, mask, cap = args
        rows.append({'arm': 'truth_frozen011', 'prediction': baseline(*args, support_cost_weight=.3)})
        rows.append({'arm': 'truth_wall013', 'prediction': wall_decode(priors_, t, path, R, runs, mask, cap,
                                                                     support_cost_weight=.3, wall=True)})
        return rows[0]['prediction']

    X.infer(case / 'input', priors, OLD / 'wrist-ensemble-final', trajectory_frontend=oracle,
            candidate_limit=128, layout_decoder=pairup)
    scene = M.load_native(OLD / 'raw-native800/native' / (case.name + '.json'))
    for row in rows:
        row['score'] = M.score_instances(row['prediction']['boxes'], scene['gt'])
        row['whole_iou0_5'] = footprint_all(row['prediction']['boxes'], scene['gt'])
    result = {'scene': case.name, 'role': 'development8', 'rows': rows}
    target.write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps({'scene': i, 'arms': [(r['arm'], r['prediction']['status'], r['score']['tp']) for r in rows]}), flush=True)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', default='11000-11007')
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=2)
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.ids.split('-'))
    ids = list(range(lo, hi + 1))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    records = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for res in pool.map(worker, [(i, a.out) for i in ids]):
            records.append(res)
    summary = {}
    for arm in ARMS:
        rows = [r for q in records for r in q['rows'] if r['arm'] == arm]
        summary[arm] = {'n': len(rows), 'whole': sum(r['score']['all_instances_hit'] for r in rows),
                        'f1': float(np.mean([r['score']['f1'] for r in rows])),
                        'ok': sum(r['prediction']['status'] == 'ok' for r in rows),
                        'iou': sum(r['whole_iou0_5'] for r in rows),
                        'per_class': {c: [sum(r['score']['per_class'].get(c, {}).get('tp', 0) for r in rows),
                                          sum(r['score']['per_class'].get(c, {}).get('n_truth', 0) for r in rows)]
                                      for c in ['bed', 'desk', 'cab', 'chair']}}
    (Path(a.out) / 'truthpose-summary.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
