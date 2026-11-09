"""Same record-level RMS, three temporal structures, identical rooms.

The severity knob in exp_sensor013 couples four mechanisms at once, so a fall in
the whole-room rate cannot be attributed to amplitude or to spectral shape.  This
module holds the amplitude fixed: each perturbation series is rescaled to the same
per-axis RMS, and only the shape changes -- white (flat spectrum), const (all power
at DC), walk (red, integrated white noise).  Applied to the gyro channels, the
accelerometer channels, or both.
"""
import numpy as np

SHAPES = ('white', 'const', 'walk')
CHANNELS = ('gyro', 'acc', 'both')
TARGET = {'gyro': 0.01, 'acc': 0.05}  # per-axis RMS, rad/s and m/s^2


def _white(rng, n, sigma):
    return rng.normal(0.0, sigma, n)


def _const(rng, n, sigma):
    return np.full(n, sigma * float(rng.choice([-1.0, 1.0])))


def _walk(rng, n, sigma):
    w = np.cumsum(rng.normal(0.0, 1.0, n))
    w -= w.mean()
    sd = float(w.std())
    return w * (sigma / sd) if sd > 0 else np.zeros(n)


_GEN = {'white': _white, 'const': _const, 'walk': _walk}


def perturb(A, G, shape, channels=('gyro', 'acc'), seed=0, target=TARGET):
    rng = np.random.default_rng(seed)
    A = np.array(A, dtype=float, copy=True)
    G = np.array(G, dtype=float, copy=True)
    gen = _GEN[shape]
    if 'acc' in channels:
        for k in range(3):
            A[:, k] += gen(rng, len(A), target['acc'])
    if 'gyro' in channels:
        for k in range(3):
            G[:, k] += gen(rng, len(G), target['gyro'])
    return A, G


def conditions():
    return [('clean', None, None)] + [(f'{s}-{c}', s, c) for s in SHAPES for c in CHANNELS]
