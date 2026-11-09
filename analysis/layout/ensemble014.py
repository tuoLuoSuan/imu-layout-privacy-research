"""Truth-free decoders that try to convert pool atoms into whole-room hits.

The 014 pools already contain a candidate within 0.5 m of every truth instance
in the rooms checked, so the loss sits in the joint assignment/selection step.
Two cheap interventions are compared against the single-solution decoder:

  cap256  keep twice as many candidates per instance before the search
  ens10   10 stochastic re-solves (multiplicative log-normal noise on the
          candidate energies) and return the solution that agrees most with the
          per-instance marginal modes of all returned solutions

Both only re-arrange candidate-level evidence; no truth, no labels.
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
from .wall_priors013 import decode as wall_decode, GAP as WALL_GAP

ARMS = ['base', 'cap256', 'ens10']


def _centres(b):
    b = np.asarray(b, float).reshape(-1, 4)
    return np.stack([(b[:, 0] + b[:, 2]) / 2, (b[:, 1] + b[:, 3]) / 2], axis=1)


def _decode_with(rng, noise, **kw):
    """Run one oriented decode, optionally perturbing candidate energies."""
    mcs, ocs = R.minimum_cost_search, M._constraint_search

    def jitter(pools):
        if noise <= 0:
            return pools
        out = {}
        for k, (b, m, e) in pools.items():
            e = np.asarray(e, float)
            out[k] = (b, m, e * np.exp(noise * rng.standard_normal(len(e))))
        return out

    def spy_mcs(inv, pools, targets, counts, *a, **k):
        return mcs(inv, jitter(pools), targets, counts, *a, **k)

    def spy_ocs(inv, pools, targets, counts, *a, **k):
        return ocs(inv, jitter(pools), targets, counts, *a, **k)

    R.minimum_cost_search, M._constraint_search = spy_mcs, spy_ocs
    try:
        return oriented_decode(**kw)
    finally:
        R.minimum_cost_search, M._constraint_search = mcs, ocs


def _consensus(sols, tol=.15):
    """Pick the returned solution that best matches per-instance marginal modes."""
    ids = sorted({k for s in sols for k in s})
    clusters = {}
    for k in ids:
        pts = []
        for s in sols:
            if k in s:
                pts.append(np.asarray(s[k], float))
        cs = []
        for p in pts:
            c = _centres(p)[0]
            for cl in cs:
                if np.linalg.norm(cl['centre'] - c) <= tol:
                    cl['n'] += 1
                    break
            else:
                cs.append({'centre': c, 'n': 1})
        clusters[k] = cs
    best, best_score = None, -1.0
    for s in sols:
        score = 0.0
        for k in ids:
            if k not in s or not clusters[k]:
                continue
            c = _centres(s[k])[0]
            score += max(cl['n'] for cl in clusters[k] if np.linalg.norm(cl['centre'] - c) <= tol) if any(
                np.linalg.norm(cl['centre'] - c) <= tol for cl in clusters[k]) else 0
        if score > best_score:
            best, best_score = s, score
    return best, best_score / max(1, len(ids) * len(sols))


def decode_arm(priors, t, path, Rm, runs, walk, arm='base', k=10, noise=.02, seed=0):
    cap = 256 if arm == 'cap256' else (64 if arm.endswith('c64') else 128)
    kw = dict(priors=priors, t=t, path=path, R=Rm, runs=runs, walk=walk,
              candidate_limit=cap, support_cost_weight=.3)
    if arm in ('w013off', 'cab015', 'bed012', 'cab015bed012'):
        gaps = {'cab015': {'cab': (None, .15)},
                'bed012': {'bed': (None, .12)},
                'cab015bed012': {'cab': (None, .15), 'bed': (None, .12)}}.get(arm)
        return wall_decode(priors, t, path, Rm, runs, walk, candidate_limit=128, support_cost_weight=.3,
                           wall=arm != 'w013off', gaps=gaps)
    if arm in ('cap256', 'base'):
        return oriented_decode(**kw)
    rng = np.random.default_rng(seed)
    sols = [_decode_with(rng, noise, **kw) for _ in range(k)]
    boxes = [s['boxes'] for s in sols if s.get('status') == 'ok']
    if not boxes:
        return sols[0]
    chosen, agree = _consensus(boxes)
    out = {k: v for k, v in sols[0].items()}
    for s in sols:
        if s['boxes'] is chosen:
            out = {**s}
            break
    out['ensemble'] = {'k': k, 'noise': noise, 'n_ok': len(boxes), 'agreement': agree}
    return out


def run_room(folder, arm, k, noise, seed):
    folder = Path(folder)
    priors = json.loads((folder / 'input' / 'known-priors.json').read_text())
    model = load(E.MODEL)

    def front(t, A, G):
        p, Rm, info = replay(t, A, G, model, heading_regularization=True)
        return p, Rm, info

    def refine(t, p, Rm, runs, known):
        p, a = loops(t, p, Rm, runs, known)
        p, b = wall(t, p, Rm, runs, known)
        return p, {'point_plane_loops': a, 'cabinet_wall': b}

    def decoder(*a, **kw):
        return decode_arm(a[0], a[1], a[2], a[3], a[4], a[5], arm=arm, k=k, noise=noise, seed=seed)

    pred = raw_infer(folder / 'input', priors, E.WRIST, trajectory_frontend=front, candidate_limit=128,
                     trajectory_refiner=refine, layout_decoder=decoder)
    native = E.OLD / 'raw-native800' / 'native' / (folder.name.rsplit('-s', 1)[0] + '.json')
    gt = M.load_native(native)['gt']
    score = M.score_instances(pred['boxes'], gt)
    return {'room': folder.name, 'arm': arm, 'status': pred['status'], 'score': score,
            'ensemble': pred.get('ensemble'), 'boxes': {k: np.asarray(v).tolist() for k, v in pred['boxes'].items()}}


def worker(task):
    folder, arm, k, noise, seed = task
    try:
        return run_room(folder, arm, k, noise, seed)
    except Exception as e:  # noqa: BLE001
        return {'room': Path(folder).name, 'arm': arm, 'error': repr(e)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--rooms', required=True)
    ap.add_argument('--arms', default='base,cap256,ens10')
    ap.add_argument('--k', type=int, default=10)
    ap.add_argument('--noise', type=float, default=.02)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=10)
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
    arms = a.arms.split(',')
    tasks = [(str(f), arm, a.k, a.noise, a.seed) for f in folders for arm in arms]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        rows = list(pool.map(worker, tasks))
    Path(a.out).write_text(json.dumps(rows, indent=1))
    for arm in arms:
        rr = [r for r in rows if r.get('arm') == arm and 'score' in r]
        print(arm, 'rooms', len(rr), 'whole', sum(r['score']['all_instances_hit'] for r in rr),
              'f1', round(float(np.mean([r['score']['f1'] for r in rr])), 4),
              'ok', sum(r['status'] == 'ok' for r in rr))
