"""Sensor-error model for the controlled handset signals (experimental 013).

The generator's own error model is white Gaussian noise plus one constant bias
per stream. Real MEMS handsets add a slowly wandering bias, a scale-factor and
axis-misalignment error, and timestamp jitter. This module layers those terms
on top of an already generated signal so that one severity dial moves only the
sensor side of the chain; geometry, script and decoder stay fixed.

Severity 1.0 reproduces the generator's own noise scale, so the sweep is
relative to the published synthetic chain and is not a calibrated device model.
"""
import numpy as np

BASE = {'acc_white': 0.035, 'gyro_white': 0.003, 'acc_bias_walk': 2e-4, 'gyro_bias_walk': 2e-5,
        'scale': 4e-3, 'misalign': 2e-3, 'ts_jitter_s': 5e-4}


def degrade(gen, severity, seed=0, noise_streams='legacy'):
    if noise_streams not in ('legacy', 'prefix-v1'):
        raise ValueError('noise_streams must be legacy or prefix-v1')
    rng = np.random.default_rng(seed)
    acc_walk_rng, acc_white_rng, gyro_walk_rng, gyro_white_rng, clock_rng = [rng] * 5
    if noise_streams == 'prefix-v1':
        # A versioned diagnostic model. All channel draws are independent of
        # total record length, and drift starts at zero instead of subtracting
        # a future whole-record mean. The frozen legacy model remains default.
        seeds = np.random.SeedSequence(seed).spawn(5)
        acc_walk_rng, acc_white_rng, gyro_walk_rng, gyro_white_rng, clock_rng = [np.random.default_rng(s) for s in seeds]
    s = float(severity)
    if s <= 0.:
        return {**gen, 'sensor_error_model': {'severity': 0., 'terms': {}, 'scope': 'Clean control arm; no term applied'}}
    acc = np.asarray(gen['acc'], float).copy(); gyro = np.asarray(gen['gyro'], float).copy()
    n = len(acc)
    # Slowly wandering bias, one random walk per axis, mean zero over the record.
    def walk(sigma, channel_rng):
        b = np.cumsum(channel_rng.normal(0., sigma, (n, 3)), axis=0)
        return b - (b.mean(axis=0) if noise_streams == 'legacy' else b[0])
    acc += walk(BASE['acc_bias_walk'] * s ** 1.5, acc_walk_rng) + acc_white_rng.normal(0., BASE['acc_white'] * max(0., s - 1.), (n, 3))
    gyro += walk(BASE['gyro_bias_walk'] * s ** 1.5, gyro_walk_rng) + gyro_white_rng.normal(0., BASE['gyro_white'] * max(0., s - 1.), (n, 3))
    # Scale factor and axis misalignment (upper triangular, applied to clean axes).
    k = BASE['scale'] * s
    m = BASE['misalign'] * s
    M = np.array([[1. + k, m, -m], [0., 1. - k, m], [m, 0., 1. + k]])
    acc = acc @ M.T; gyro = gyro @ M.T
    ts = np.rint(np.asarray(gen['ts_ns'], np.int64) + clock_rng.normal(0., BASE['ts_jitter_s'] * s, n) * 1e9).astype(np.int64)
    ts = np.maximum.accumulate(ts)
    metadata = {'severity': s, 'terms': BASE, 'scope': 'Relative MEMS-style error sweep, not a calibrated device model'}
    if noise_streams == 'prefix-v1':
        metadata.update(noise_streams='prefix-v1', bias_reference='initial sample; future record length unused')
    return {**gen, 'acc': acc, 'gyro': gyro, 'ts_ns': ts, 'sensor_error_model': metadata}


def report(clean, noisy):
    d = np.asarray(noisy['acc']) - np.asarray(clean['acc'])
    return {'acc_rms_error': float(np.sqrt((d ** 2).mean())), 'acc_peak_error': float(np.abs(d).max()),
            'gyro_rms_error': float(np.sqrt(((np.asarray(noisy['gyro']) - np.asarray(clean['gyro'])) ** 2).mean()))}
