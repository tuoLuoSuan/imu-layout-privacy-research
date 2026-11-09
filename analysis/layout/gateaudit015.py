"""Print the startup still-gate diagnostics behind the shape experiment.

The frozen front end refuses a record unless an absolute still block starts
within 4 s (analysis/layout/inertial010.py:56) and it judges "still" with fixed
thresholds (inertial010.py:21-35). This CLI reports, per signal condition, where
that block lands, how much of the opening 6 s passes the gyro gate, what the
adaptive quantile mask would choose, and what the gated tracker concludes. It is
the recomputation path for the mechanism table in
docs/research/2026-11-09-device-loss-placement-014.md.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from . import action_model as AM
from .bias_tracker014b import calibrate
from .inertial010 import intervals, rest_mask
from .restgate015 import adaptive_mask, correct_protocol, statistics
from .sensorshape014 import conditions, perturb

ACC_RMS = 0.02
GYRO_RMS = 0.003

CASE_ROOT = {
    'confirm32': Path('output/research-sync/2026-11-09-bias-aware-input-014/confirm32'),
    'fresh32': Path('output/research-sync/2026-11-09-paper-and-raw-input-012/wall-fresh32'),
}


def audit(time, acceleration, gyro):
    t = np.asarray(time, float)
    A = np.asarray(acceleration, float)
    G = np.asarray(gyro, float)
    mask = rest_mask(t, A, G)
    blocks = intervals(mask)
    long = [(a, b) for a, b in blocks if t[b - 1] - t[a] >= .8]
    head = t - t[0] <= 6.
    _, gyr, _ = statistics(t, A, G)
    row = {
        'frozen_rest_samples': int(mask.sum()),
        'frozen_first_block_s': None if not blocks else round(float(t[blocks[0][0]]), 2),
        'frozen_first_long_block_s': None if not long else round(float(t[long[0][0]]), 2),
        'head6s_samples': int(head.sum()),
        'head6s_gyro_pass_fraction': round(float(mask[head].mean()), 3),
        'head6s_gyro_median_rad_s': round(float(np.median(gyr[head])), 4),
    }
    amask, info = adaptive_mask(t, A, G)
    ablk = [(a, b) for a, b in intervals(amask) if t[b - 1] - t[a] >= .8]
    row.update({
        'adaptive_gyro_threshold_rad_s': round(info['gyro_threshold'], 4),
        'adaptive_gyro_quantile_rad_s': round(info['gyro_quantile_rad_s'], 5),
        'adaptive_first_long_block_s': None if not ablk else round(float(t[ablk[0][0]]), 2),
    })
    try:
        _, _, meta = calibrate(t, A, G)
        row.update({
            'tracker_status': 'ok',
            'gyro_drift_rms_rad_s': round(meta['gyro_drift_rms_rad_s'], 5),
            'gyro_mean_se_rad_s': round(meta['gyro_mean_se_rad_s'], 5),
            'initial_gyro_bias_norm_rad_s': round(meta['initial_gyro_bias_norm_rad_s'], 5),
            'gyro_correction_applied': bool(meta['gyro_drift_rms_rad_s'] > 1.5 * meta['gyro_mean_se_rad_s'] + 1e-8
                                            or meta['initial_gyro_bias_norm_rad_s'] > .006),
        })
    except Exception as exc:  # noqa: BLE001
        row.update({'tracker_status': 'error', 'tracker_error': repr(exc)[:200]})
    return row


def path_len(p):
    p = np.asarray(p, float)
    return float(np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1).sum())


def replay_probe(folder, t, A, G, model):
    """Path-length ratio of the frozen player vs a first-2 s bias correction."""
    from .displacement011 import replay
    truth = np.load(Path(folder) / 'evaluation-truth.npz')
    reference = path_len(np.asarray(truth['position'], float))
    out = {}
    for name in ('raw', 'protocol_bias'):
        if name == 'raw':
            A2, G2 = A, G
        else:
            try:
                A2, G2, _ = correct_protocol(t, A, G)
            except Exception as exc:  # noqa: BLE001
                out[name] = repr(exc)[:120]
                continue
        try:
            path, _, _ = replay(t, A2, G2, model, heading_regularization=True)
            out[name] = round(path_len(path) / reference, 3)
        except Exception as exc:  # noqa: BLE001
            out[name] = repr(exc)[:120]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', choices=sorted(CASE_ROOT), default='confirm32')
    ap.add_argument('--room', default='multi-11500-s0')
    ap.add_argument('--conditions', default='clean,walk-gyro')
    ap.add_argument('--seed', type=int, default=None)
    # The shape experiment ran at acc .02 m/s^2 and gyro .003 rad/s; the module
    # default (.05/.01) is a much stronger perturbation and must not be assumed.
    ap.add_argument('--acc-rms', type=float, default=ACC_RMS)
    ap.add_argument('--gyro-rms', type=float, default=GYRO_RMS)
    ap.add_argument('--out', default='')
    ap.add_argument('--probe', choices=['stats', 'replay'], default='stats')
    a = ap.parse_args()
    folder = CASE_ROOT[a.case] / 'records' / a.room
    ch = AM.load_phone(folder / 'input')
    t, A, _ = ch['accelerometer']
    tg, G, _ = ch['gyroscope']
    G = np.c_[*[np.interp(t, tg, G[:, i]) for i in range(3)]]
    target = {'acc': a.acc_rms, 'gyro': a.gyro_rms}
    index = {name: (shape, channels) for name, shape, channels in conditions()}
    seed = a.seed if a.seed is not None else 7000 + int(a.room.rsplit('-', 2)[-2])
    rows = []
    for name in filter(None, a.conditions.split(',')):
        if name == 'clean':
            A2, G2 = A, G
        else:
            shape, channels = index[name]
            chans = ('gyro', 'acc') if channels == 'both' else (channels,)
            A2, G2 = perturb(A, G, shape, chans, seed, target)
        if a.probe == 'replay':
            from .exp_bias014 import MODEL
            rows.append({'room': a.room, 'condition': name, **replay_probe(folder, t, A2, G2, MODEL)})
        else:
            rows.append({'room': a.room, 'condition': name, **audit(t, A2, G2)})
        print(json.dumps(rows[-1]), flush=True)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(rows, indent=1))


if __name__ == '__main__':
    main()
