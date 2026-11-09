"""Relax the two constraints that make 4 of 32 rooms infeasible.

Section 4.8 shows the candidate pool already contains a candidate within 0.5 m of
every true instance, yet 4 rooms report a conflict.  Two things can block a hard
cover: an event no candidate explains at all, and two near-correct boxes that
overlap each other.  Both are properties of the observation tolerance rather
than of the room, so this module prices neither and filters nothing: it can drop
events that no candidate covers anywhere, and it can allow a small overlap
between estimated boxes.  Everything else (forward checking, value ordering,
node limit) is the frozen search.
"""
import itertools

import numpy as np

from . import multi_instance as M
from . import recovery010 as R
from .oriented_raw011 import decode as oriented_decode
from .priorcost014 import priced_pools

ARMS = {
    'ovl05': {'tol': .05, 'drop': False},
    'ovl10': {'tol': .10, 'drop': False},
    'drop': {'tol': 0., 'drop': True},
    'both05': {'tol': .05, 'drop': True},
    'both10': {'tol': .10, 'drop': True},
}


def search_relaxed(inventory, pools, targets, counts, node_limit=20000, tol=0., drop=False):
    names = [e['id'] for e in inventory]
    compat = {}
    covers = {}
    nodes = 0
    limit_hit = False
    for name, (boxes, masks, energy) in pools.items():
        covers[name] = [sum(1 << j for j, m in enumerate(masks) if int(m) & (1 << t)) for t in range(len(targets))]
    for a, b in itertools.combinations(names, 2):
        if {M.category(a), M.category(b)} == {'desk', 'chair'}:
            continue
        aa = pools[a][0]
        bb = pools[b][0]
        inter = np.maximum(0, np.minimum(aa[:, None, 2:], bb[None, :, 2:]) - np.maximum(aa[:, None, :2], bb[None, :, :2]))
        area = np.minimum(np.prod(aa[:, 2:] - aa[:, :2], axis=1)[:, None], np.prod(bb[:, 2:] - bb[:, :2], axis=1)[None, :])
        valid = np.prod(inter, axis=2) <= 1e-8 * np.maximum(area, 1e-12)
        if tol > 0:
            valid = valid | (inter <= tol).all(axis=2)
        compat[a, b] = [sum(1 << int(j) for j in np.flatnonzero(row)) for row in valid]
        compat[b, a] = [sum(1 << int(j) for j in np.flatnonzero(row)) for row in valid.T]

    def indices(mask):
        while mask:
            bit = mask & -mask
            yield bit.bit_length() - 1
            mask ^= bit

    full = (1 << len(targets)) - 1
    dropped = 0
    if drop:
        for t in range(len(targets)):
            if not any(covers[n][t] for n in names):
                dropped |= 1 << t

    def search(domains, placed, covered):
        nonlocal nodes, limit_hit
        nodes += 1
        if nodes > node_limit:
            limit_hit = True
            return None
        domains = dict(domains)
        changed = True
        while changed:
            changed = False
            for t in indices(full & ~covered):
                providers = [n for n, d in domains.items() if d & covers[n][t]]
                if not providers:
                    return None
                if len(providers) == 1:
                    name = providers[0]
                    new = domains[name] & covers[name][t]
                    if new != domains[name]:
                        domains[name] = new
                        changed = True
        for a, b in itertools.combinations(domains, 2):
            if (a, b) not in compat:
                continue
            if not any(compat[a, b][i] & domains[b] for i in indices(domains[a])):
                return None
        if not domains:
            return placed if covered == full else None
        name = min(domains, key=lambda n: domains[n].bit_count())
        boxes, masks, cost = pools[name]
        order = sorted(indices(domains[name]), key=lambda i: (-(int(masks[i]) & ~covered).bit_count(), float(cost[i])))
        for i in order:
            remaining = {}
            valid = True
            for other, d in domains.items():
                if other == name:
                    continue
                d = d & compat[name, other][i] if (name, other) in compat else d
                if not d:
                    valid = False
                    break
                remaining[other] = d
            if valid:
                result = search(remaining, {**placed, name: i}, covered | int(masks[i]))
                if result is not None:
                    return result
                if limit_hit:
                    return None
        return None

    solution = search({n: (1 << len(pools[n][0])) - 1 for n in names}, {}, dropped)
    if solution is None:
        return {'status': 'search_budget_exhausted' if limit_hit else 'proposal_conflict',
                'boxes': {}, 'candidate_counts': counts, 'search_nodes': nodes,
                'relax': {'tol': tol, 'drop': drop, 'dropped_targets': int(dropped.bit_count())}}
    return {'status': 'ok', 'boxes': {n: pools[n][0][i] for n, i in solution.items()},
            'candidate_counts': counts, 'search_nodes': nodes,
            'relax': {'tol': tol, 'drop': drop, 'dropped_targets': int(dropped.bit_count())},
            'scope': 'Frozen bounded candidate CSP with an overlap tolerance and free dropping of uncoverable events only'}


def decode_arm(priors, t, path, Rm, runs, walk, arm='base', candidate_limit=128):
    if arm == 'base':
        return oriented_decode(priors=priors, t=t, path=path, R=Rm, runs=runs, walk=walk,
                               candidate_limit=candidate_limit, support_cost_weight=.3)
    cfg = ARMS[arm]
    mcs, ocs = R.minimum_cost_search, M._constraint_search

    def relaxed(inv, pools, targets, counts, *a, **k):
        k.setdefault('node_limit', 20000)
        return search_relaxed(inv, pools, targets, counts, tol=cfg['tol'], drop=cfg['drop'], **k)

    R.minimum_cost_search, M._constraint_search = relaxed, relaxed
    try:
        out = oriented_decode(priors=priors, t=t, path=path, R=Rm, runs=runs, walk=walk,
                              candidate_limit=candidate_limit, support_cost_weight=.3)
    finally:
        R.minimum_cost_search, M._constraint_search = mcs, ocs
    out['relax_arm'] = {'arm': arm, **cfg, 'candidate_limit': candidate_limit}
    return out
