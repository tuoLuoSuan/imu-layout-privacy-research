"""Experimental measured-heading consensus. Frozen 011 stays unchanged."""
import numpy as np
from . import evidence_space as ES
from .contact_contract import body_axis
from .multi_raw010 import interaction_events, OPTIONS
from .oriented_raw011 import bed_orientation_mask, directed_contact
from .recovery010 import solve
from .selection_diagnostics import outline_cost


def axis_consensus(headings):
    h = np.asarray(headings, float).reshape(-1, 2)
    if not len(h):
        return 0., {'accepted': False, 'inliers': 0}
    angle = np.arctan2(h[:, 1], h[:, 0])
    distance = abs(np.angle(np.exp(4j * (angle[:, None] - angle[None, :])))) / 4
    neighbours = distance <= np.radians(5.)
    winner = int(np.argmax(neighbours.sum(axis=1)))
    keep = neighbours[winner]
    if keep.sum() < max(2, .5 * len(h)):
        return float(np.degrees(angle[0])), {'accepted': False, 'inliers': int(keep.sum())}
    mode = np.angle(np.exp(4j * angle[keep]).sum()) / 4
    return float(np.degrees(mode)), {'accepted': True, 'inliers': int(keep.sum()), 'total': len(h)}


def decode(priors, t, path, R, runs, walk, candidate_limit=128, support_cost_weight=.3):
    """Same finite decoder and evidence as 011; only frame-axis estimate changes.

    Contact axes are observations under the declared Manhattan/phone protocol.
    No reference positions, labels, instance IDs or true orientations are read.
    """
    t, path, R = np.asarray(t), np.asarray(path), np.asarray(R)
    events, directions = interaction_events(t, path, runs), []
    for label, a, b in runs:
        if label not in ['seated', 'lying', 'cabinet'] or b - a < 2.:
            continue
        ids = np.flatnonzero((t >= a + .25 * (b - a)) & (t <= a + .75 * (b - a)))
        if len(ids) < 3:
            continue
        h = body_axis(R[ids], label).mean(axis=0)
        directions.append(h / max(1e-9, np.linalg.norm(h)))
    if len(events) != len(directions):
        raise AssertionError('One measured direction per contact')
    structural = [h for e, h in zip(events, directions) if e['object'] in ['cab', 'bed']]
    offset, meta = axis_consensus(structural or directions)
    candidates = []
    for degrees in [a - offset for a in [0, 90, 180, 270]]:
        a = np.radians(degrees)
        Q = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        q = (path - path[0]) @ Q.T + priors['start']
        ev = [{'object': e['object'], 'pos': ((np.asarray(e['pos']) - path[0]) @ Q.T + priors['start']).tolist()} for e in events]
        heads = [h @ Q.T for h in directions]
        lookup = {(e['object'], *e['pos']): h for e, h in zip(ev, heads)}
        lying = [h for e, h in zip(ev, heads) if e['object'] == 'bed']

        def filtering(entry, boxes, room):
            return bed_orientation_mask(boxes, np.mean(lying, axis=0)) if entry['category'] == 'bed' and lying else np.ones(len(boxes), bool)

        def support(entry, boxes, e):
            c = 'chair' if e['object'] == 'desk_relation' else e['object']
            h = lookup[c, *e['pos']]
            return directed_contact(e['object'], boxes, e['pos'], h, .3) if e['object'] in ['cab', 'desk_relation'] else ES._contact(boxes, e, .3, .6)

        obs = np.unique(np.round(q[np.asarray(walk, bool)][::12] / .1) * .1, axis=0) if np.any(walk) else np.empty((0, 2))
        opts = {**OPTIONS, 'candidate_limit': candidate_limit, 'proposal_filter': filtering, 'event_support': support, 'known_desk_protocol': True, 'support_cost_weight': support_cost_weight}
        result = solve(priors['room'], priors['inventory'], ev, obs, 'depth_portfolio', decoder_options=opts)
        outside = np.maximum(-q, q - np.array(priors['room'])).clip(min=0)
        cost = 100 * float(outside.mean()) + 10 * float(outside.max())
        cost += 1000 if result['status'] != 'ok' else float(np.mean(outline_cost(np.array(list(result['boxes'].values())), priors['room'], obs)))
        candidates.append({**result, 'yaw_deg': float(degrees), 'registration_cost': cost, 'events': ev, 'measured_heading': np.asarray(heads).tolist(), 'n_walk_points': len(obs)})
    best = min(candidates, key=lambda r: r['registration_cost'])
    return {**best, 'boxes': {k: np.asarray(b).tolist() for k, b in best['boxes'].items()}, 'axis_consensus': meta,
            'frame_hypotheses': [{k: r[k] for k in ['yaw_deg', 'registration_cost', 'status']} for r in candidates]}
