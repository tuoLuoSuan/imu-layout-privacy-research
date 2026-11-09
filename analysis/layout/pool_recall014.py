"""Pool recall vs selection loss for the 014 raw-input chain (signal-only).

For each room it records the candidate pools the instance search actually
receives (after the 128-candidate truncation) under each global-yaw
hypothesis, then asks two separate questions:

  pool loss      no candidate for that class lies within 0.5 m of the truth
                 centre in any hypothesis  -> the proposer/truncation is at fault
  selection loss a candidate within 0.5 m exists in the winning hypothesis but
                 the decoded box for that instance is elsewhere -> the joint
                 search/assignment is at fault

Inputs are the same session bundle and priors the 014 experiment used; the
evaluation truth file is read only after decoding, for scoring.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path

import numpy as np

from . import multi_instance as M
from . import recovery010 as R
from . import exp_bias014 as E
from .displacement011 import load, replay
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .multi_raw010 import infer as raw_infer
from .oriented_raw011 import decode as oriented_decode

DIST = 0.5


def centres(boxes):
    b = np.asarray(boxes, float).reshape(-1, 4)
    return np.stack([(b[:, 0] + b[:, 2]) / 2, (b[:, 1] + b[:, 3]) / 2], axis=1)


def _nearest(cands, target):
    if not len(cands):
        return float('inf')
    return float(np.min(np.linalg.norm(centres(cands) - np.asarray(target, float)[:2], axis=1)))


def capture_decode(priors, t, path, rotation, runs, walk, *extra):
    calls = []
    mcs, ocs = R.minimum_cost_search, M._constraint_search

    def rec(pools):
        calls.append({k: np.asarray(v[0], float) for k, v in pools.items()})

    def spy_mcs(inv, pools, targets, counts, *a, **k):
        rec(pools)
        return mcs(inv, pools, targets, counts, *a, **k)

    def spy_ocs(inv, pools, targets, counts, *a, **k):
        rec(pools)
        return ocs(inv, pools, targets, counts, *a, **k)

    R.minimum_cost_search = spy_mcs
    M._constraint_search = spy_ocs
    try:
        out = oriented_decode(priors, t, path, rotation, runs, walk, candidate_limit=128, support_cost_weight=.3)
    finally:
        R.minimum_cost_search, M._constraint_search = mcs, ocs
    return out, calls


def audit(folder):
    folder = Path(folder)
    priors = json.loads((folder / 'input' / 'known-priors.json').read_text())
    model = load(E.MODEL)
    cap = {}

    def front(t, A, G):
        p, Rm, info = replay(t, A, G, model, heading_regularization=True)
        return p, Rm, info

    def refine(t, p, Rm, runs, known):
        p, a = loops(t, p, Rm, runs, known)
        p, b = wall(t, p, Rm, runs, known)
        return p, {'point_plane_loops': a, 'cabinet_wall': b}

    def decoder(*a, **k):
        out, calls = capture_decode(*a[:6])
        cap['calls'] = calls
        return out

    pred = raw_infer(folder / 'input', priors, E.WRIST, trajectory_frontend=front, candidate_limit=128,
                     trajectory_refiner=refine, layout_decoder=decoder)
    room = folder.name.rsplit('-s', 1)[0]
    native = E.OLD / 'raw-native800' / 'native' / (room + '.json')
    gt = {k: centres(np.asarray(v, float).reshape(-1, 4))[0] for k, v in M.load_native(native)['gt'].items()}

    calls = cap['calls']
    boxes = {k: np.asarray(v, float).reshape(-1, 4) for k, v in pred['boxes'].items()}
    # which hypothesis produced the answer: most final boxes present in its pools
    match = []
    for pools in calls:
        n = 0
        for k, b in boxes.items():
            found = False
            for arr in pools.values():
                if len(arr) and np.any(np.all(np.abs(arr - b) < 1e-6, axis=1)):
                    found = True
                    break
            n += found
        match.append(n)
    chosen = int(np.argmax(match)) if match else -1

    hyp = [dict(p) for p in calls]
    best = int(np.argmax([sum(_nearest(h.get(c, np.empty((0, 4))), p) <= DIST for c, p in gt.items()) for h in hyp])) if hyp else -1
    rows = {}
    for c, p in gt.items():
        d_pool = _nearest(hyp[chosen].get(c, np.empty((0, 4))), p) if chosen >= 0 else float('inf')
        d_best = _nearest(hyp[best].get(c, np.empty((0, 4))), p) if best >= 0 else float('inf')
        d_final = _nearest(boxes.get(c, np.empty((0, 4))), p) if c in boxes else float('inf')
        rows[c] = {'d_pool_chosen': d_pool, 'd_pool_best': d_best, 'd_final': d_final}
    n_truth = len(gt)
    n_final = sum(v['d_final'] <= DIST for v in rows.values())
    return {'room': room, 'status': pred['status'], 'n_truth': n_truth, 'n_final_hit': n_final,
            'chosen_hyp': chosen, 'best_hyp': best, 'n_hyp': len(calls),
            'pool_loss': sum(v['d_pool_best'] > DIST for v in rows.values()),
            'selection_loss': sum(v['d_pool_best'] <= DIST < v['d_final'] for v in rows.values()),
            'per_class': rows}


def worker(folder):
    try:
        return audit(folder)
    except Exception as e:  # noqa: BLE001 - report, never mask
        return {'room': Path(folder).name, 'error': repr(e)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--rooms', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=6)
    a = ap.parse_args()
    ids = []
    for part in a.rooms.split(','):
        if '-' in part:
            lo, hi = part.split('-')
            ids += list(range(int(lo), int(hi) + 1))
        else:
            ids.append(int(part))
    root = Path(a.root)
    folders = [root / 'records' / f'multi-{i:05d}-s0' for i in ids]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        out = list(pool.map(worker, folders))
    Path(a.out).write_text(json.dumps(out, indent=1))
    for r in out:
        print(json.dumps({k: v for k, v in r.items() if k != 'per_class'}))