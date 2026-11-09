"""Experimental cabinet-wall side-information arm; not part of frozen 011."""
import numpy as np
from scipy.optimize import least_squares
from .contact_contract import body_axis
from .heading_consensus012 import axis_consensus


def fit_room_drift(time, path, observations, room, depths):
    t, p = np.asarray(time, float), np.asarray(path, float)
    if not observations or not len(depths):
        return p.copy(), {'used': False, 'objective': 0.}
    knots = np.unique(np.r_[t[0], [e['time'] for e in observations], t[-1]])
    targets = []
    for e in observations:
        axis = int(np.argmax(abs(np.asarray(e['normal']))))
        positive = e['normal'][axis] > 0
        intervals = []
        for depth in depths:
            lo, hi = depth + .6, depth + .6 + .15
            if positive:
                lo, hi = room[axis] - hi, room[axis] - lo
            intervals.append((lo, hi))
        value = e['point'][axis]
        lo, hi = min(intervals, key=lambda r: max(r[0] - value, value - r[1], 0.))
        targets.append((int(np.searchsorted(knots, e['time'])), axis, value, lo, hi))
    sample = np.arange(0, len(t), max(1, int(round(1. / np.median(np.diff(t))))))
    def residual(flat):
        delta = np.vstack([np.zeros(2), flat.reshape(-1, 2)])
        scale = .02 + .005 * np.maximum(.1, np.diff(knots))
        regularizer = (np.diff(delta, axis=0) / scale[:, None]).ravel()
        contacts = []
        for j, axis, value, lo, hi in targets:
            v = value + delta[j, axis]
            contacts.append((max(lo - v, 0.) - max(v - hi, 0.)) / .08)
        d = np.c_[*[np.interp(t[sample], knots, delta[:, a]) for a in [0, 1]]]
        q = p[sample] + d
        outside = np.maximum(-q, q - np.asarray(room)).clip(min=0).ravel() / .2
        return np.r_[regularizer, contacts, outside]
    fit = least_squares(residual, np.zeros(2 * (len(knots) - 1)), max_nfev=100)
    delta = np.vstack([np.zeros(2), fit.x.reshape(-1, 2)])
    d = np.c_[*[np.interp(t, knots, delta[:, a]) for a in [0, 1]]]
    return p + d, {'used': True, 'objective': float(np.sum(residual(fit.x)**2)), 'success': bool(fit.success),
                   'max_correction_m': float(np.linalg.norm(d, axis=1).max()), 'knots_s': knots.tolist(),
                   'corrections_m': delta.tolist(), 'assigned_phone_intervals': [[a, lo, hi] for _, a, _, lo, hi in targets],
                   'extra_side_information': 'Storage depth normal faces away from a wall, gap in [0,0.15]m; reach0.6m. Not IMU observations.'}


def refine(time, path, rotation, runs, priors):
    t, p, R = np.asarray(time), np.asarray(path), np.asarray(rotation)
    obs = []
    for label, a, b in runs:
        if label != 'cabinet' or b - a < 2.:
            continue
        ids = np.flatnonzero((t >= a + .25 * (b - a)) & (t <= a + .75 * (b - a)))
        if len(ids) < 3:
            continue
        h = body_axis(R[ids], label).mean(axis=0)
        h /= max(1e-9, np.linalg.norm(h))
        obs.append({'time': float(np.median(t[ids])), 'point': np.median(p[ids], axis=0), 'normal': h})
    if not obs:
        return p.copy(), {'used': False}
    offset, _ = axis_consensus([e['normal'] for e in obs])
    depths = [min(e['dimensions']) for e in priors['inventory'] if e['category'] == 'cab']
    candidates = []
    for degrees in [a - offset for a in [0, 90, 180, 270]]:
        a = np.radians(degrees)
        Q = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        q = (p - p[0]) @ Q.T + priors['start']
        ev = [{**e, 'point': (e['point'] - p[0]) @ Q.T + priors['start'], 'normal': e['normal'] @ Q.T} for e in obs]
        fixed, meta = fit_room_drift(t, q, ev, priors['room'], depths)
        candidates.append(((fixed - priors['start']) @ Q + p[0], {**meta, 'yaw_deg': degrees}))
    result, meta = min(candidates, key=lambda pair: pair[1].get('objective', 0.))
    return result, meta
