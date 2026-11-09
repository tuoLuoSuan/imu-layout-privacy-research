"""Class-wise measured wall adjacency as a candidate-pool prior (experimental 013).

Every desk, bed and cabinet in the 1,000-room native sample sits within a
measured gap of a wall: desk max 0.150 m, bed max 0.100 m, cab max 0.159 m
(median 0.104/0.100/0.101). Chairs never do: min gap 0.497 m, median 0.851.
These are measured placement properties of the controlled generator, declared
side information like the rectangular room and the known inventory -- not an
interaction measurement and not truth for any evaluated room.

Frozen 011 stays untouched: this module re-implements the 011 decoder with one
composed pool filter so the arms differ in exactly one variable.
"""
import numpy as np
from . import evidence_space as ES
from .contact_contract import body_axis
from .multi_raw010 import interaction_events, OPTIONS
from .oriented_raw011 import bed_orientation_mask, directed_contact
from .recovery010 import solve
from .selection_diagnostics import outline_cost

# (low, high) admissible gap to the nearest wall; None means unbounded.
GAP = {'bed': (None, 0.12), 'desk': (None, 0.16), 'cab': (None, 0.16), 'chair': (0.45, None)}
SOURCE = 'output/layout-recon/wall-gap-measure013.json (1,000 native rooms)'


def wall_gap(boxes, room):
    b = np.asarray(boxes, float).reshape(-1, 4)
    w, l = float(room[0]), float(room[1])
    return np.minimum(np.minimum(b[:, 0], w - b[:, 2]), np.minimum(b[:, 1], l - b[:, 3]))


def pool_mask(entry, boxes, room, gaps=GAP):
    """Boolean mask over an untruncated candidate pool; never empties the pool."""
    bounds = gaps.get(entry['category'])
    keep = np.ones(len(boxes), bool)
    if bounds is None or not len(boxes):
        return keep
    gap = wall_gap(boxes, room)
    low, high = bounds
    if low is not None:
        keep &= gap >= low
    if high is not None:
        keep &= gap <= high
    return keep if keep.any() else np.ones(len(boxes), np.bool_)


def decode(priors, t, path, R, runs, walk, candidate_limit=128, support_cost_weight=0., wall=True):
    t = np.asarray(t); path = np.asarray(path); R = np.asarray(R)
    events = interaction_events(t, path, runs); directions = []
    for label, a, b in runs:
        if label not in ['seated', 'lying', 'cabinet'] or b - a < 2.:
            continue
        ids = np.flatnonzero((t >= a + .25 * (b - a)) & (t <= a + .75 * (b - a)))
        if len(ids) < 3:
            continue
        h = body_axis(R[ids], label).mean(axis=0); h /= max(1e-9, np.linalg.norm(h)); directions.append(h)
    if len(directions) != len(events):
        raise AssertionError('Every contact must keep its own measured heading')
    cab = [h for e, h in zip(events, directions) if e['object'] == 'cab']
    axis_source = cab or [h for e, h in zip(events, directions) if e['object'] == 'bed'] or directions
    offset = np.degrees(np.arctan2(axis_source[0][1], axis_source[0][0])) if axis_source else 0.
    angles = [a - offset for a in [0, 90, 180, 270]]; candidates = []
    for degrees in angles:
        a = np.radians(degrees); Q = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        q = (path - path[0]) @ Q.T + priors['start']
        ev = [{'object': e['object'], 'pos': ((np.asarray(e['pos']) - path[0]) @ Q.T + priors['start']).tolist()} for e in events]
        heads = [h @ Q.T for h in directions]
        lookup = {(e['object'], *e['pos']): h for e, h in zip(ev, heads)}
        lying = [h for e, h in zip(ev, heads) if e['object'] == 'bed']
        def filtering(entry, boxes, room):
            keep = bed_orientation_mask(boxes, np.mean(lying, axis=0)) if entry['category'] == 'bed' and lying else np.ones(len(boxes), bool)
            if not wall:
                return keep
            composed = keep & pool_mask(entry, boxes, room)
            return composed if composed.any() else keep
        def support(entry, boxes, e):
            c = 'chair' if e['object'] == 'desk_relation' else e['object']; h = lookup[c, *e['pos']]
            return directed_contact(e['object'], boxes, e['pos'], h, .3) if e['object'] in ['cab', 'desk_relation'] else ES._contact(boxes, e, .3, .6)
        obs = np.unique(np.round(q[np.asarray(walk, bool)][::12] / .1) * .1, axis=0) if np.any(walk) else np.empty((0, 2))
        opts = {**OPTIONS, 'candidate_limit': candidate_limit, 'proposal_filter': filtering, 'event_support': support,
                'known_desk_protocol': True, 'support_cost_weight': support_cost_weight}
        result = solve(priors['room'], priors['inventory'], ev, obs, 'depth_portfolio', decoder_options=opts)
        outside = np.maximum(-q, q - np.array(priors['room'])).clip(min=0)
        cost = 100 * float(outside.mean()) + 10 * float(outside.max())
        cost += 1000 if result['status'] != 'ok' else float(np.mean(outline_cost(np.array(list(result['boxes'].values())), priors['room'], obs)))
        candidates.append({**result, 'yaw_deg': float(degrees), 'registration_cost': cost, 'events': ev,
                           'measured_heading': np.asarray(heads).tolist(), 'n_walk_points': len(obs)})
    best = min(candidates, key=lambda r: r['registration_cost'])
    return {**best, 'boxes': {k: np.asarray(v).tolist() for k, v in best['boxes'].items()},
            'orientation_source': 'Signal-estimated phone attitude under fixed pose-to-body protocol; absolute yaw unknown',
            'table_relation': 'A seated person faces some table within0.9m, unknown partner and along-edge offset',
            'wall_prior': {'applied': bool(wall), 'gaps_m': GAP if wall else None, 'source': SOURCE if wall else None},
            'frame_hypotheses': [{k: r[k] for k in ['yaw_deg', 'registration_cost', 'status']} for r in candidates]}
