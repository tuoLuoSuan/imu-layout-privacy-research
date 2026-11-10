"""Incremental-contact diagnostic: what extra events exclude, and what we deploy.

Fixed the trajectory front end (no contact-driven refine), then hand the decoder
the first k contact events of a record and ask three things at each k:

  compatible   how many candidates per instance still satisfy every event bit
               (this is V(E_k) inside a finite, truncated candidate pool)
  retained     is a candidate within 0.5 m of the truth centre among them
  deployed     does the production decode hit every instance

The first two must be non-increasing in k, because the masks are bitfields over
events.  The third is a decode result and need not be.  Truth is read only for
scoring, after decoding.
"""
import argparse
import concurrent.futures
import json
import re
from pathlib import Path

import numpy as np

from . import multi_instance as M
from . import recovery010 as R
from . import exp_bias014 as E
from .displacement011 import load, replay
from .wall_refine012 import refine as wall
from .multi_raw010 import infer as raw_infer
from .priorcost014 import decode_arm as prior_decode

DIST = 0.5
KS = (2, 4, 6, 8, 12, 16, 24, 32)


def centres(boxes):
    b = np.asarray(boxes, float).reshape(-1, 4)
    return np.stack([(b[:, 0] + b[:, 2]) / 2, (b[:, 1] + b[:, 3]) / 2], axis=1)


def _capture(args, runs):
    """Decode with runs, recording the pools the search actually receives."""
    prior, t, path, Rm, _runs, walk = args
    calls = []
    mcs, ocs = R.minimum_cost_search, M._constraint_search

    def rec(pools):
        calls.append({k: (np.asarray(v[0], float).reshape(-1, 4), np.asarray(v[1], np.uint64))
                      for k, v in pools.items()})

    def spy_mcs(inv, pools, targets, counts, *a, **k):
        rec(pools)
        return mcs(inv, pools, targets, counts, *a, **k)

    def spy_ocs(inv, pools, targets, counts, *a, **k):
        rec(pools)
        return ocs(inv, pools, targets, counts, *a, **k)

    R.minimum_cost_search, M._constraint_search = spy_mcs, spy_ocs
    try:
        out = prior_decode(prior, t, path, Rm, runs, walk, arm='base')
    finally:
        R.minimum_cost_search, M._constraint_search = mcs, ocs
    return out, calls


def room(folder, ks=KS):
    folder = Path(folder)
    priors = json.loads((folder / 'input' / 'known-priors.json').read_text())
    name = re.search(r'multi-(\d+)', folder.name).group(0)
    native = E.OLD / 'raw-native800' / 'native' / (name + '.json')
    scene = M.load_native(native)
    gt = {k: centres(np.asarray(v, float).reshape(-1, 4))[0] for k, v in scene['gt'].items()}
    gt_boxes = {k: np.asarray(v, float).reshape(-1, 4)[0] for k, v in scene['gt'].items()}
    model = load(E.MODEL)
    sweep = {}

    def front(t, A, G):
        p, Rm, info = replay(t, A, G, model, heading_regularization=True)
        return p, Rm, info

    def refine(t, p, Rm, runs, known):
        p, b = wall(t, p, Rm, runs, known)
        return p, {'cabinet_wall': b}

    def decoder(*a):
        args = a[:6]
        n = len(args[4])
        for k in ks:
            if k > n:
                continue
            out, calls = _capture(args, args[4][:k])
            per = []
            for inst, target in gt.items():
                near, best, size = 0, np.inf, 0
                for pools in calls:
                    if inst not in pools:
                        continue
                    boxes = pools[inst][0]
                    size = max(size, int(len(boxes)))
                    if len(boxes):
                        d = np.min(np.linalg.norm(centres(boxes) - target, axis=1))
                        best = min(best, float(d))
                per.append((inst, size, int(best <= DIST), best))
            score = M.score_instances(out['boxes'], gt_boxes) if out.get('status') == 'ok' else None
            sweep[str(k)] = {
                'used': int(k), 'status': out.get('status'),
                'whole': bool(score['all_instances_hit']) if score else False,
                'f1': float(score['f1']) if score else 0.,
                'pool_size_median': float(np.median([c for _, c, _, _ in per])) if per else None,
                'pool_size_max': int(max(c for _, c, _, _ in per)) if per else None,
                'retained': sum(kp for _, _, kp, _ in per), 'n_truth': len(per),
                'dmin_median': float(np.median([d for _, _, _, d in per])) if per else None,
                'dmin_max': float(max(d for _, _, _, d in per)) if per else None,
                'n_hyp': len(calls)}
        out, _ = _capture(args, args[4])
        return out

    pred = raw_infer(folder / 'input', priors, E.WRIST, trajectory_frontend=front, candidate_limit=128,
                     trajectory_refiner=refine, layout_decoder=decoder)
    score = M.score_instances(pred['boxes'], gt_boxes) if pred['status'] == 'ok' else None
    return {'room': name, 'n_events': None, 'sweep': sweep, 'status': pred['status'],
            'whole_full': bool(score['all_instances_hit']) if score else False,
            'f1_full': float(score['f1']) if score else 0.}


def worker(folder):
    try:
        return room(folder)
    except Exception as e:  # noqa: BLE001 - report, never mask
        return {'room': Path(folder).name, 'error': repr(e)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--rooms', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--ks', default=','.join(str(k) for k in KS))
    a = ap.parse_args()
    ids = []
    for part in a.rooms.split(','):
        if '-' in part:
            lo, hi = part.split('-')
            ids += list(range(int(lo), int(hi) + 1))
        else:
            ids.append(int(part))
    ks = tuple(int(x) for x in a.ks.split(','))
    folder = [Path(a.root) / f'multi-{i:05d}' for i in ids]
    folder = [f if f.exists() else Path(a.root) / f'multi-{i:05d}-s0' for f, i in zip(folder, ids)]
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for r in pool.map(worker, [str(f) for f in folder]):
            rows.append(r)
            print(json.dumps({k: r.get(k) for k in ('room', 'status', 'whole_full', 'error')}), flush=True)
    Path(a.out).write_text(json.dumps({'rooms': rows, 'ks': list(ks)}, indent=1, default=float))
    print('wrote', a.out)
