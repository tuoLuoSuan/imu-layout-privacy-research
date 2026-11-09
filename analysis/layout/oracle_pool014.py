"""Is the truth-near part of the pool jointly feasible? (014)

pool_recall014 showed that for the rooms checked every truth instance has a
candidate within 0.5 m somewhere in the truncated pools, yet whole-room hits
stop at 24/32. Two very different causes remain:

  objective   the truth-near candidates are jointly admissible, but the search
              returns another feasible set whose energy is lower
  mask/matching  some contact event is only covered by a wrong candidate, so no
              combination of truth-near boxes can cover all events

This module records the exact (inventory, pools, targets, counts) the search
received, then re-runs the same search restricted to the truth-near candidates
of each instance. Truth is read only after decoding, for the restriction and
for scoring. A feasible restricted search means no mask is blocking; an
infeasible one localises the blocking event.
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


def capture_decode(priors, t, path, rotation, runs, walk, *extra):
    calls = []
    mcs, ocs = R.minimum_cost_search, M._constraint_search

    def rec(inv, pools, targets, counts):
        calls.append({'inv': inv, 'targets': targets, 'counts': dict(counts),
                      'pools': {k: (np.asarray(v[0], float), np.asarray(v[1]),
                                    np.asarray(v[2], float)) for k, v in pools.items()}})

    def spy_mcs(inv, pools, targets, counts, *a, **k):
        rec(inv, pools, targets, counts)
        return mcs(inv, pools, targets, counts, *a, **k)

    def spy_ocs(inv, pools, targets, counts, *a, **k):
        rec(inv, pools, targets, counts)
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
    gt = {k: centres(np.asarray(v, float).reshape(-1, 4))[0]
          for k, v in M.load_native(E.OLD / 'raw-native800' / 'native' / (room + '.json'))['gt'].items()}
    calls = cap.get('calls', [])
    rows = []
    for h in calls:
        near, counts, cover = {}, {}, {}
        for name, (boxes, masks, energy) in h['pools'].items():
            target = gt.get(name)
            if target is None:
                continue
            d = np.linalg.norm(centres(boxes) - target, axis=1) if len(boxes) else np.empty(0)
            sel = np.flatnonzero(d <= DIST)
            counts[name] = int(len(sel))
            if len(sel):
                near[name] = (boxes[sel], masks[sel], energy[sel])
                cover[name] = int(np.unique(np.concatenate(
                    [[j for j in range(len(h['targets'])) if int(m) & (1 << j)] for m in masks[sel]])).size)
        if len(near) < len(h['pools']):
            rows.append({'hyp': len(rows), 'verdict': 'incomplete_pool', 'n_near': int(len(near)),
                         'n_instances': len(h['pools']), 'per_instance_near': {k: int(v) for k, v in counts.items()}})
            continue
        full = (1 << len(h['targets'])) - 1
        union = 0
        for b, m, e in near.values():
            for bit in m:
                union |= int(bit)
        res = M._constraint_search(h['inv'], near, h['targets'], h['counts'])
        solved = {k: np.asarray(v, float).reshape(-1, 4) for k, v in res['boxes'].items()}
        hit = sum(np.linalg.norm(centres(solved[k])[0] - gt[k]) <= DIST for k in solved if k in gt)
        rows.append({'hyp': len(rows), 'verdict': res['status'], 'n_near': int(len(near)),
                     'n_instances': len(h['pools']), 'n_targets': len(h['targets']),
                     'restricted_hits': int(hit), 'per_instance_near': {k: int(v) for k, v in counts.items()},
                     'event_cover': {k: int(v) for k, v in cover.items()},
                     'search_nodes': int(res.get('search_nodes') or 0),
                     'n_uncoverable_events': int(bin(full & ~union).count('1'))})
    return {'room': room, 'status': pred['status'], 'n_truth': len(gt),
            'n_hyp': len(calls), 'hypotheses': rows}


def worker(folder):
    try:
        return audit(folder)
    except Exception as e:  # noqa: BLE001
        return {'room': Path(folder).name, 'error': repr(e)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--rooms', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=8)
    a = ap.parse_args()
    ids = []
    for part in a.rooms.split(','):
        if '-' in part:
            lo, hi = part.split('-')
            ids += list(range(int(lo), int(hi) + 1))
        else:
            ids.append(int(part))
    root = Path(a.root)
    folders = [str(root / 'records' / f'multi-{i:05d}-s0') for i in ids]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        rows = list(pool.map(worker, folders))
    Path(a.out).write_text(json.dumps(rows, indent=1, default=int))
    for r in rows:
        if 'error' in r:
            print(r['room'], 'ERROR', r['error'])
            continue
        best = max(r['hypotheses'], key=lambda h: h.get('n_near', 0)) if r['hypotheses'] else {}
        print(r['room'], r['status'], 'n_hyp', r['n_hyp'], '|', best.get('verdict'),
              'near', best.get('n_near'), '/', best.get('n_instances'),
              'restricted_hits', best.get('restricted_hits'))
