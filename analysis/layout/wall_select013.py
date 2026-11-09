"""Conditional wall prior: decode with and without the pool filter, then pick by data fit (013).

wall013p showed the pool filter deletes correct boxes once the trajectory drifts
(dev 4/8, fresh 22/32 vs 23/32 unfiltered). Filtering changes the candidate set,
so the failure is invisible in the filtered solution itself. This arm keeps both
solutions and lets the data decide, with the declared wall adjacency used only as
a penalty on solutions that violate it.
"""
import numpy as np
from .wall_priors013 import decode as wall_decode, GAP, wall_gap


def _violation(result, priors):
    cat = {e['id']: e['category'] for e in priors['inventory']}
    total = 0.
    for name, box in result['boxes'].items():
        bounds = GAP.get(cat.get(name))
        if bounds is None or bounds[1] is None:
            continue
        total += max(0., float(wall_gap(np.asarray(box, float).reshape(1, 4), priors['room'])[0]) - bounds[1])
    return total


def decode_select(priors, t, path, R, runs, walk, candidate_limit=128, support_cost_weight=0., lam=20.):
    filtered = wall_decode(priors, t, path, R, runs, walk, candidate_limit, support_cost_weight, wall=True)
    plain = wall_decode(priors, t, path, R, runs, walk, candidate_limit, support_cost_weight, wall=False)
    scored = []
    for tag, res in [('filtered', filtered), ('unfiltered', plain)]:
        cost = float(res['registration_cost']) + lam * _violation(res, priors)
        scored.append((0 if res['status'] == 'ok' else 1, cost, tag, res))
    _, cost, tag, best = min(scored, key=lambda s: (s[0], s[1]))
    return {**best, 'wall_selection': {'chosen': tag, 'score': cost, 'lambda': lam,
                                       'filtered_cost': float(filtered['registration_cost']),
                                       'unfiltered_cost': float(plain['registration_cost']),
                                       'filtered_violation_m': _violation(filtered, priors),
                                       'unfiltered_violation_m': _violation(plain, priors)}}
