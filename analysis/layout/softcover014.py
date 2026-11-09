"""Soft event coverage: turn the hard 100% contact mask into a priced objective.

The 014 oracle probe showed every instance owns a within-0.5 m candidate, yet
four rooms stay infeasible even when the search is restricted to those
candidates: two carry contact events that no truth-near box can cover, two are
blocked by non-overlap among the near-truth boxes.  A hard coverage CSP turns
either case into a total room failure.  This module prices each uncovered event
at lambda and lets the search return the cheapest nearly-covering assignment,
which is the same "feasible but wrong" distinction SUMMON reports for contact
losses.  No truth is read.
"""
import argparse
import concurrent.futures
import itertools
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

LAMBDAS = {'soft002': .02, 'soft010': .1, 'soft050': .5, 'soft100': 1., 'soft300': 3., 'soft1000': 10.}


def soft_search(inventory, pools, targets, counts, node_limit=20000, lam=.1):
    """Branch and bound over the same finite candidate CSP, events priced."""
    names = [e['id'] for e in inventory]
    compat, covers = {}, {}
    nodes, limit_hit = 0, False
    best, best_cost, best_miss = None, np.inf, 0
    full = (1 << len(targets)) - 1
    for name, (boxes, masks, energy) in pools.items():
        covers[name] = [sum(1 << j for j, m in enumerate(masks) if int(m) & (1 << t))
                        for t in range(len(targets))]
    for a, b in itertools.combinations(names, 2):
        if {M.category(a), M.category(b)} == {'desk', 'chair'}:
            continue
        aa, bb = pools[a][0], pools[b][0]
        inter = np.maximum(0, np.minimum(aa[:, None, 2:], bb[None, :, 2:]) - np.maximum(aa[:, None, :2], bb[None, :, :2]))
        area = np.minimum(np.prod(aa[:, 2:] - aa[:, :2], axis=1)[:, None],
                          np.prod(bb[:, 2:] - bb[:, :2], axis=1)[None, :])
        valid = np.prod(inter, axis=2) <= 1e-8 * np.maximum(area, 1e-12)
        compat[a, b] = [sum(1 << int(j) for j in np.flatnonzero(row)) for row in valid]
        compat[b, a] = [sum(1 << int(j) for j in np.flatnonzero(row)) for row in valid.T]

    def bits(mask):
        while mask:
            bit = mask & -mask
            yield bit.bit_length() - 1
            mask ^= bit

    def search(domains, placed, covered, dropped, cost):
        nonlocal nodes, limit_hit, best, best_cost, best_miss
        nodes += 1
        if nodes > node_limit:
            limit_hit = True
            return
        domains = dict(domains)
        while True:
            changed = False
            for t in bits(full & ~(covered | dropped)):
                providers = [n for n, d in domains.items() if d & covers[n][t]]
                if not providers:
                    dropped |= 1 << t
                    changed = True
                    continue
                if len(providers) == 1:
                    name = providers[0]
                    new = domains[name] & covers[name][t]
                    if new != domains[name]:
                        domains[name] = new
                        changed = True
            if not changed:
                break
        lower = cost + sum(min(float(pools[n][2][i]) for i in bits(d)) for n, d in domains.items()) \
            + lam * dropped.bit_count()
        if lower >= best_cost - 1e-12:
            return
        if not domains:
            miss = full & ~covered
            total = cost + lam * miss.bit_count()
            if total < best_cost - 1e-12:
                best, best_cost, best_miss = dict(placed), total, miss.bit_count()
            return
        for a, b in itertools.combinations(domains, 2):
            if (a, b) in compat and not any(compat[a, b][i] & domains[b] for i in bits(domains[a])):
                return
        name = min(domains, key=lambda n: domains[n].bit_count())
        boxes, masks, energy = pools[name]
        for i in sorted(bits(domains[name]), key=lambda j: (float(energy[j]), -(int(masks[j]) & ~covered).bit_count())):
            remaining, ok = {}, True
            for other, d in domains.items():
                if other == name:
                    continue
                d = d & compat[name, other][i] if (name, other) in compat else d
                if not d:
                    ok = False
                    break
                remaining[other] = d
            if ok:
                search(remaining, {**placed, name: i}, covered | int(masks[i]), dropped,
                       cost + float(energy[i]))
            if limit_hit:
                return

    search({n: (1 << len(pools[n][0])) - 1 for n in names}, {}, 0, 0, 0.)
    if best is None:
        return {'status': 'search_budget_exhausted' if limit_hit else 'proposal_conflict',
                'boxes': {}, 'search_nodes': nodes, 'candidate_counts': counts}
    return {'status': 'ok', 'boxes': {n: pools[n][0][i] for n, i in best.items()},
            'candidate_counts': counts, 'search_nodes': nodes, 'objective': float(best_cost),
            'dropped_events': int(best_miss), 'lambda': float(lam),
            'candidate_objective_optimal': not limit_hit,
            'search_budget_exhausted_with_incumbent': limit_hit}


def decode_arm(priors, t, path, Rm, runs, walk, arm='base', node_limit=20000):
    cap = 64 if arm.endswith('c64') else 128
    kw = dict(priors=priors, t=t, path=path, R=Rm, runs=runs, walk=walk,
              candidate_limit=cap, support_cost_weight=.3)
    if arm in ('base', 'basec64'):
        return oriented_decode(**kw)
    lam = LAMBDAS[arm.replace('c64', '')]
    mcs, ocs = R.minimum_cost_search, M._constraint_search

    def soft(inv, pools, targets, counts, *a, **k):
        return soft_search(inv, pools, targets, counts, node_limit=node_limit, lam=lam)

    R.minimum_cost_search, M._constraint_search = soft, soft
    try:
        out = oriented_decode(**kw)
    finally:
        R.minimum_cost_search, M._constraint_search = mcs, ocs
    out['decoder'] = {'arm': arm, 'lambda': lam, 'node_limit': node_limit}
    return out


def run_room(folder, arm, node_limit=20000):
    folder = Path(folder)
    priors = json.loads((folder / 'input' / 'known-priors.json').read_text())
    model = load(E.MODEL)

    def front(t, A, G):
        return replay(t, A, G, model, heading_regularization=True)

    def refine(t, p, Rm, runs, known):
        p, a = loops(t, p, Rm, runs, known)
        p, b = wall(t, p, Rm, runs, known)
        return p, {'point_plane_loops': a, 'cabinet_wall': b}

    def decoder(*a, **k):
        return decode_arm(a[0], a[1], a[2], a[3], a[4], a[5], arm=arm, node_limit=node_limit)

    pred = raw_infer(folder / 'input', priors, E.WRIST, trajectory_frontend=front, candidate_limit=128,
                     trajectory_refiner=refine, layout_decoder=decoder)
    native = E.OLD / 'raw-native800' / 'native' / (folder.name.rsplit('-s', 1)[0] + '.json')
    gt = M.load_native(native)['gt']
    score = M.score_instances(pred['boxes'], gt)
    return {'room': folder.name, 'arm': arm, 'status': pred['status'], 'score': score,
            'decoder': pred.get('decoder'), 'boxes': {k: np.asarray(v).tolist() for k, v in pred['boxes'].items()}}


def worker(task):
    folder, arm, node_limit = task
    try:
        return run_room(folder, arm, node_limit)
    except Exception as e:  # noqa: BLE001
        return {'room': Path(folder).name, 'arm': arm, 'error': repr(e)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--rooms', required=True)
    ap.add_argument('--arms', default='base,soft010')
    ap.add_argument('--node-limit', type=int, default=20000)
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
    arms = a.arms.split(',')
    tasks = [(str(root / 'records' / f'multi-{i:05d}-s0'), arm, a.node_limit) for i in ids for arm in arms]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        rows = list(pool.map(worker, tasks))
    Path(a.out).write_text(json.dumps(rows, indent=1, default=str))
    for arm in arms:
        rr = [r for r in rows if r.get('arm') == arm and 'score' in r]
        drop = [r['decoder'].get('dropped_events') for r in rr if r.get('decoder')]
        print(arm, 'rooms', len(rr), 'whole', sum(r['score']['all_instances_hit'] for r in rr),
              'f1', round(float(np.mean([r['score']['f1'] for r in rr])), 4),
              'ok', sum(r['status'] == 'ok' for r in rr), 'dropped', drop)
