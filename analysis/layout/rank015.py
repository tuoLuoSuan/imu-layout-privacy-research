"""Re-rank near-equal-cost solutions instead of changing the objective.

At severity zero the pool already contains a candidate within 0.5 m of every true
instance, 24 of 32 rooms are exactly right, and 7 of the 8 misses return "ok" a
few boxes away.  Adding a prior as a price moved three rooms in one batch and
nothing in two others, so this module does not price anything: it enumerates the
solutions whose total energy is within a small band of the frozen optimum and
breaks that tie with a truth-free criterion, either the declared near-wall
violation or the number of contact events each chosen box explains.
"""
import itertools

import numpy as np

from . import multi_instance as M
from . import recovery010 as R
from .oriented_raw011 import decode as oriented_decode
from .wall_priors013 import GAP, wall_gap

ARMS = {
    'sw1': {'mode': 'weight', 'weight': 1.},
    'sw3': {'mode': 'weight', 'weight': 3.},
    'eps5p': {'mode': 'prior', 'eps': .005},
    'eps10p': {'mode': 'prior', 'eps': .010},
    'eps5s': {'mode': 'support', 'eps': .005},
    'eps10s': {'mode': 'support', 'eps': .010},
    'eps20s': {'mode': 'support', 'eps': .020},
    'eps20p': {'mode': 'prior', 'eps': .020},
    'minc': {'mode': 'cost', 'eps': 0.},
    'minc64': {'mode': 'cost', 'eps': 0., 'cap': 64},
    'eps10s64': {'mode': 'support', 'eps': .010, 'cap': 64},
    'eps20s64': {'mode': 'support', 'eps': .020, 'cap': 64},
    'eps20p64': {'mode': 'prior', 'eps': .020, 'cap': 64},
}


def _cost(solution, pools):
    return float(sum(pools[n][2][i] for n, i in solution.items()))


def _prior_score(solution, pools, room):
    total = 0.
    for name, i in solution.items():
        bounding = GAP.get(M.category(name))
        if bounding is None:
            continue
        box = np.asarray(pools[name][0][i], float)[None, :]
        gap = float(wall_gap(box, room)[0])
        low, high = bounding
        if high is not None:
            total += max(gap - high, 0.)
        if low is not None:
            total += max(low - gap, 0.)
    return total


def _cost_score(solution, pools):
    return _cost(solution, pools)


def _support_score(solution, pools):
    return -float(sum(int(pools[n][1][i]).bit_count() for n, i in solution.items()))


def search_band(inventory, pools, targets, counts, node_limit=60000, eps=0., criterion='prior', room=None):
    names = [e['id'] for e in inventory]
    compat = {}
    covers = {}
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
        compat[a, b] = [sum(1 << int(j) for j in np.flatnonzero(row)) for row in valid]
        compat[b, a] = [sum(1 << int(j) for j in np.flatnonzero(row)) for row in valid.T]

    def indices(mask):
        while mask:
            bit = mask & -mask
            yield bit.bit_length() - 1
            mask ^= bit

    full = (1 << len(targets)) - 1
    state = {'nodes': 0, 'limit': False, 'best': None}

    def search(domains, placed, covered, cost):
        state['nodes'] += 1
        if state['nodes'] > node_limit:
            state['limit'] = True
            return None
        if state['best'] is not None and cost > state['best'] + eps + 1e-12:
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
            if covered == full:
                if state['best'] is None or cost < state['best']:
                    state['best'] = cost
            return placed
        name = min(domains, key=lambda n: domains[n].bit_count())
        boxes, masks, energy = pools[name]
        order = sorted(indices(domains[name]), key=lambda i: (-(int(masks[i]) & ~covered).bit_count(), float(energy[i])))
        found = None
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
                out = search(remaining, {**placed, name: i}, covered | int(masks[i]), cost + float(energy[i]))
                if out is not None and found is None:
                    found = out
                if state['limit']:
                    return found
        return found

    best = search({n: (1 << len(pools[n][0])) - 1 for n in names}, {}, 0, 0.)
    if best is None:
        return {'status': 'search_budget_exhausted' if state['limit'] else 'proposal_conflict',
                'boxes': {}, 'candidate_counts': counts, 'search_nodes': state['nodes'],
                'band': {'eps': eps, 'criterion': criterion}}
    limit = state['best'] + eps + 1e-12
    chosen = None
    chosen_score = None
    pool = [best]
    seen = {tuple(sorted(best.items()))}
    state2 = {'nodes': 0, 'limit': False}

    def enumerate_all(domains, placed, covered, cost, out):
        state2['nodes'] += 1
        if state2['nodes'] > node_limit:
            state2['limit'] = True
            return
        if cost > limit:
            return
        domains = dict(domains)
        changed = True
        while changed:
            changed = False
            for t in indices(full & ~covered):
                providers = [n for n, d in domains.items() if d & covers[n][t]]
                if not providers:
                    return
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
                return
        if not domains:
            if covered == full:
                key = tuple(sorted(placed.items()))
                if key not in seen:
                    seen.add(key)
                    out.append(dict(placed))
            return
        name = min(domains, key=lambda n: domains[n].bit_count())
        boxes, masks, energy = pools[name]
        for i in sorted(indices(domains[name]), key=lambda j: (-(int(masks[j]) & ~covered).bit_count(), float(energy[j]))):
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
                enumerate_all(remaining, {**placed, name: i}, covered | int(masks[i]), cost + float(energy[i]), out)
            if state2['limit']:
                return

    sols = []
    enumerate_all({n: (1 << len(pools[n][0])) - 1 for n in names}, {}, 0, 0., sols)
    pool = list(seen)
    for key in pool:
        sol = dict(key)
        if criterion == 'prior':
            score = _prior_score(sol, pools, room)
        elif criterion == 'cost':
            score = _cost_score(sol, pools)
        else:
            score = _support_score(sol, pools)
        if chosen_score is None or score < chosen_score:
            chosen, chosen_score = sol, score
    if chosen is None:
        chosen = best
    return {'status': 'ok', 'boxes': {n: pools[n][0][i] for n, i in chosen.items()},
            'candidate_counts': counts, 'search_nodes': state['nodes'] + state2['nodes'],
            'band': {'eps': eps, 'criterion': criterion, 'n_within_band': len(pool), 'score': float(chosen_score or 0.)},
            'scope': 'Frozen objective, solutions within eps of the optimum, tie broken by a declared prior or by explained-event count'}


def decode_arm(priors, t, path, Rm, runs, walk, arm='base', candidate_limit=128):
    if arm == 'base':
        return oriented_decode(priors=priors, t=t, path=path, R=Rm, runs=runs, walk=walk,
                               candidate_limit=candidate_limit, support_cost_weight=.3)
    cfg = ARMS[arm]
    candidate_limit = cfg.get('cap', candidate_limit)
    if cfg['mode'] == 'weight':
        return oriented_decode(priors=priors, t=t, path=path, R=Rm, runs=runs, walk=walk,
                               candidate_limit=candidate_limit, support_cost_weight=cfg['weight'])
    room = np.asarray(priors['room'], float)
    mcs, ocs = R.minimum_cost_search, M._constraint_search

    def band_search(inv, pools, targets, counts, *a, **k):
        k.pop('node_limit', None)
        return search_band(inv, pools, targets, counts, eps=cfg['eps'], criterion=cfg['mode'], room=room)

    R.minimum_cost_search, M._constraint_search = band_search, band_search
    try:
        out = oriented_decode(priors=priors, t=t, path=path, R=Rm, runs=runs, walk=walk,
                              candidate_limit=candidate_limit, support_cost_weight=.3)
    finally:
        R.minimum_cost_search, M._constraint_search = mcs, ocs
    out['rank_arm'] = {'arm': arm, **cfg}
    return out
