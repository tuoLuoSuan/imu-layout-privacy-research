"""Relax the startup still gate instead of trusting its absolute thresholds.

The frozen front end (analysis/layout/inertial010.py:21-35) decides "handset at
rest" with absolute thresholds (0.085 m/s^2 on the acceleration spread,
0.009 rad/s on the window gyro magnitude) and inertial010.py:56 then refuses the
record unless such a block starts within 4 s. A slow gyro error of a few
0.001 rad/s already keeps the window magnitude above 0.009 rad/s even though the
handset really is still, so the record dies before any layout work.

This module keeps the frozen thresholds as a floor and adds the record's own
noise scale, so a record whose still segments are detectable *relative to its
own noise* still yields a startup bias. Nothing else changes: the corrected
signal is handed back to the frozen replay, which re-estimates the bias and
therefore stays consistent with the published pipeline.
"""
import numpy as np
from scipy.ndimage import uniform_filter1d

from .inertial010 import intervals, rest_mask

GYRO_FLOOR = .009
ACC_FLOOR = .085
GRAVITY_TOL = .15


def statistics(time, acceleration, gyro):
    t = np.asarray(time, float)
    A = np.asarray(acceleration, float)
    G = np.asarray(gyro, float)
    w = max(3, int(.4 / np.median(np.diff(t))))
    mean = uniform_filter1d(A, w, axis=0, mode='nearest')
    var = np.maximum(uniform_filter1d(A * A, w, axis=0, mode='nearest') - mean * mean, 0)
    acc = np.sqrt(var.sum(axis=1))
    gyr = np.sqrt(uniform_filter1d((G * G).sum(axis=1), w, mode='nearest'))
    grav = np.abs(np.linalg.norm(mean, axis=1) - 9.81)
    return acc, gyr, grav


def adaptive_mask(time, acceleration, gyro, quantile=.10, k=1.5):
    acc, gyr, grav = statistics(time, acceleration, gyro)
    quiet = (grav < GRAVITY_TOL) & (acc < np.quantile(acc, .5))
    if not np.any(quiet):
        quiet = grav < GRAVITY_TOL
    gyro_scale = float(np.quantile(gyr[quiet], quantile))
    acc_scale = float(np.quantile(acc[quiet], quantile))
    gyro_thr = max(GYRO_FLOOR, k * gyro_scale)
    acc_thr = max(ACC_FLOOR, k * acc_scale)
    stable = (acc < acc_thr) & (gyr < gyro_thr) & (grav < GRAVITY_TOL)
    out = np.zeros(len(acc), bool)
    for a, b in intervals(stable):
        if np.asarray(time)[b - 1] - np.asarray(time)[a] >= .8:
            out[a:b] = True
    return out, {'gyro_threshold': gyro_thr, 'acc_threshold': acc_thr,
                 'gyro_quantile_rad_s': gyro_scale, 'acc_quantile_m_s2': acc_scale,
                 'quantile': quantile, 'k': k}


def startup_bias(time, acceleration, gyro):
    """Return (bias, route, info). route is 'frozen' when the frozen gate already works."""
    t = np.asarray(time, float)
    G = np.asarray(gyro, float)
    dt = float(np.median(np.diff(t)))
    frozen = rest_mask(t, acceleration, G)
    blocks = intervals(frozen)
    if blocks and blocks[0][0] <= int(4. / dt):
        return G[frozen].mean(axis=0), 'frozen', {'frozen_rest_samples': int(frozen.sum())}
    mask, info = adaptive_mask(t, acceleration, G)
    blocks = intervals(mask)
    if not blocks:
        raise ValueError('No still segment even relative to this record')
    a, b = blocks[0]
    if t[b - 1] - t[a] < .8:
        raise ValueError('First relative still segment shorter than 0.8 s')
    bias = np.median(G[a:b], axis=0)
    info.update(route='relative', first_block_start_s=float(t[a]),
                first_block_len_s=float(t[b - 1] - t[a]),
                frozen_first_block_s=None if not intervals(frozen) else float(t[intervals(frozen)[0][0]]))
    return bias, 'relative', info


def correct(time, acceleration, gyro):
    bias, route, info = startup_bias(time, acceleration, gyro)
    G = np.asarray(gyro, float)
    if route == 'frozen':
        return np.asarray(acceleration, float), G, {'route': route, **info}
    return np.asarray(acceleration, float), G - bias, {'route': route,
                                                       'startup_bias_norm_rad_s': float(np.linalg.norm(bias)), **info}

def protocol_bias(time, acceleration, gyro, hold_s=2.):
    """Anchor the rate bias on the documented startup hold.

    The capture protocol already opens with a still hold, so the first
    `hold_s` seconds are the most trustworthy zero-rate sample even when the
    absolute gate rejects them: what pushes the window magnitude over 0.009
    rad/s is precisely the error we want to subtract.
    """
    t = np.asarray(time, float)
    A = np.asarray(acceleration, float)
    G = np.asarray(gyro, float)
    head = t - t[0] <= hold_s
    if head.sum() < 8:
        raise ValueError('Startup hold shorter than 8 samples')
    acc, gyr, grav = statistics(t, A, G)
    if float(np.median(grav[head])) > GRAVITY_TOL:
        raise ValueError('Startup hold does not look like gravity')
    if float(np.median(acc[head])) > 3 * ACC_FLOOR:
        raise ValueError('Startup hold is not quiet enough for a bias sample')
    bias = G[head].mean(axis=0)
    return bias, {'route': 'protocol', 'startup_bias_norm_rad_s': float(np.linalg.norm(bias)),
                  'startup_hold_s': float(t[head][-1] - t[head][0]),
                  'startup_gyro_rms_rad_s': float(np.sqrt((G[head] ** 2).sum(axis=1).mean()))}


def correct_protocol(time, acceleration, gyro):
    bias, info = protocol_bias(time, acceleration, gyro)
    return np.asarray(acceleration, float), np.asarray(gyro, float) - bias, info
