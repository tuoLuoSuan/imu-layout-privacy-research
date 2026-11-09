"""Same declared near-wall prior, third placement: a priced cost, not a filter.

Section 4.6 compares two placements of the near-wall knowledge and finds that
putting it in the candidate set deletes near-correct boxes.  A cost placement is
strictly weaker than a filter: every candidate survives and a violation only has
to be paid for in metres.  With the measured gaps (bed 0.10, desk 0.15, storage
0.159, chair >= 0.497 m) a wrong box usually violates by several times the
0.12-0.18 m pose error, so a price can separate candidates even when the contact
residual is nearly flat.

No truth and no room reference furniture are read: the prior is the same
declared generator property used in section 4.6, and the only new quantity is
the weight lambda, in metres of violation per unit of candidate energy.
"""
import numpy as np

from . import multi_instance as M
from . import recovery010 as R
from .wall_priors013 import GAP, wall_gap
from .oriented_raw011 import decode as oriented_decode

LAMBDAS = {'p05': .5, 'p10': 1., 'p30': 3.}


def priced_pools(inventory, pools, room, lam):
    """Add lambda times the declared-gap violation to every candidate energy."""
    if lam <= 0:
        return pools
    room = np.asarray(room, float)
    out = {}
    for name, (boxes, masks, energy) in pools.items():
        bounding = GAP.get(M.category(name))
        energy = np.asarray(energy, float)
        if bounding is None or not len(np.asarray(boxes)):
            out[name] = (boxes, masks, energy)
            continue
        gap = wall_gap(boxes, room)
        violation = np.zeros(len(boxes), float)
        low, high = bounding
        if high is not None:
            violation += np.maximum(gap - high, 0.)
        if low is not None:
            violation += np.maximum(low - gap, 0.)
        out[name] = (boxes, masks, energy + lam * violation)
    return out


def decode_arm(priors, t, path, Rm, runs, walk, arm='base'):
    cap = 64 if arm.endswith('c64') else 128
    kw = dict(priors=priors, t=t, path=path, R=Rm, runs=runs, walk=walk,
              candidate_limit=cap, support_cost_weight=.3)
    if arm.startswith('base'):
        return oriented_decode(**kw)
    lam = LAMBDAS[arm.replace('c64', '')]
    room = np.asarray(priors['room'], float)
    mcs, ocs = R.minimum_cost_search, M._constraint_search

    def spy(inv, pools, targets, counts, *a, **k):
        return None

    def priced_mcs(inv, pools, targets, counts, *a, **k):
        return mcs(inv, priced_pools(inv, pools, room, lam), targets, counts, *a, **k)

    def priced_ocs(inv, pools, targets, counts, *a, **k):
        return ocs(inv, priced_pools(inv, pools, room, lam), targets, counts, *a, **k)

    R.minimum_cost_search, M._constraint_search = priced_mcs, priced_ocs
    try:
        out = oriented_decode(**kw)
    finally:
        R.minimum_cost_search, M._constraint_search = mcs, ocs
    out['prior_cost'] = {'arm': arm, 'lambda': lam, 'candidate_limit': cap}
    return out
