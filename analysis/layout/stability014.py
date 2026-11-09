"""Pick a candidate-retention limit by cross-limit agreement, without truth.

Two decodes of the same evidence differ only in how many proposals per instance
survive truncation (64 vs 128).  When both return the same boxes, the answer is
insensitive to that knob and the tighter decode is a safe choice; when they
disagree, the knob matters and the wider decode keeps the room solvable.  The
rule reads no truth and has one threshold, taken from the matching tolerance
(0.5 m) rather than tuned: 0.15 m, the same window used for the declared wall
priors.
"""
import numpy as np

from .priorcost014 import decode_arm as _decode

ARMS = {'stab': ('basec64', 'base'), 'stab128': ('base', 'basec64')}


def _center(box):
    a = np.asarray(box, dtype=float)
    return a[:2].mean(axis=0) if a.ndim == 2 else a[:2]


def box_distance(p, q):
    keys = set(p['boxes']) & set(q['boxes'])
    if not keys:
        return float('inf')
    return max(float(np.linalg.norm(_center(p['boxes'][k]) - _center(q['boxes'][k]))) for k in keys)


def decode_arm(priors, t, path, R, runs, walk, arm='stab', tol=0.15):
    tight, wide = ARMS[arm]
    a = _decode(priors, t, path, R, runs, walk, arm=tight)
    b = _decode(priors, t, path, R, runs, walk, arm=wide)
    d = box_distance(a, b)
    agree = a['status'] == 'ok' and b['status'] == 'ok' and d <= tol
    chosen = a if agree else b
    return {**chosen, 'stability': {'rule': arm, 'tol': tol, 'distance_m': d, 'agree': bool(agree),
                                    'tight': tight, 'wide': wide, 'tight_status': a['status'],
                                    'wide_status': b['status']}}
