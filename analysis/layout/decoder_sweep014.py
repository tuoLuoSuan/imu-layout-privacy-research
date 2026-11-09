"""Cache one trajectory reconstruction per room, then apply every decoder offline.

The front end plus wrist action model costs about 13 s per room, the layout
decode about 3 s.  Sweeping ten decoder variants by re-reading passive IMU would
therefore spend 95 % of the budget on identical work, so the six arguments the
decoder receives are captured once and each arm is scored against the same
cached evidence.  Only the decoder under test sees them; no truth is read here.
"""
import argparse
import concurrent.futures
import importlib
import json
from pathlib import Path

import numpy as np

from . import multi_instance as M
from . import exp_bias014 as E
from .displacement011 import load, replay
from .bias_tracker014b import replay as gated_replay
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .multi_raw010 import infer as raw_infer
from .priorcost014 import decode_arm as prior_decode
from .ensemble014 import decode_arm as ensemble_decode
from .softcover014 import decode_arm as soft_decode

ARMS = {
    'base': lambda *a: prior_decode(*a, arm='base'),
    'c64': lambda *a: prior_decode(*a, arm='basec64'),
    'p05': lambda *a: prior_decode(*a, arm='p05'),
    'p10': lambda *a: prior_decode(*a, arm='p10'),
    'p30': lambda *a: prior_decode(*a, arm='p30'),
    'p10c64': lambda *a: prior_decode(*a, arm='p10c64'),
    'p05c64': lambda *a: prior_decode(*a, arm='p05c64'),
    'p30c64': lambda *a: prior_decode(*a, arm='p30c64'),
    'soft010': lambda *a: soft_decode(*a, arm='soft010', node_limit=60000),
    'soft100': lambda *a: soft_decode(*a, arm='soft100', node_limit=60000),
    'soft300': lambda *a: soft_decode(*a, arm='soft300', node_limit=60000),
    'soft1000': lambda *a: soft_decode(*a, arm='soft1000', node_limit=60000),
    'ens10': lambda *a: ensemble_decode(*a, arm='ens10'),
    'ens10c64': lambda *a: ensemble_decode(*a, arm='ens10c64'),
}

DECODERS = {}


def build(arm):
    if arm in DECODERS:
        return DECODERS[arm]
    if arm not in ARMS:
        raise KeyError(arm)
    DECODERS[arm] = ARMS[arm]
    return DECODERS[arm]


def room_sweep(folder, arms, tracker='none'):
    folder = Path(folder)
    priors = json.loads((folder / 'input' / 'known-priors.json').read_text())
    model = load(E.MODEL)
    cache = {}

    def front(t, A, G):
        if tracker == 'b':
            return gated_replay(t, A, G, model)
        if tracker == 'gg':
            from .bias_tracker014b import gated_gyro
            _, Gc, meta = gated_gyro(t, A, G)
            p, Rm, info = replay(t, A, Gc, model, heading_regularization=True)
            info['gyro_tracker014'] = meta
            return p, Rm, info
        return replay(t, A, G, model, heading_regularization=True)

    def refine(t, p, Rm, runs, known):
        p, a = loops(t, p, Rm, runs, known)
        p, b = wall(t, p, Rm, runs, known)
        return p, {'point_plane_loops': a, 'cabinet_wall': b}

    def decoder(*a, **k):
        cache['args'] = a[:6]
        return build('base')(*a[:6])

    pred = raw_infer(folder / 'input', priors, E.WRIST, trajectory_frontend=front, candidate_limit=128,
                     trajectory_refiner=refine, layout_decoder=decoder)
    native = E.OLD / 'raw-native800' / 'native' / (folder.name.rsplit('-s', 1)[0] + '.json')
    gt = M.load_native(native)['gt']
    rows = [{'room': folder.name, 'arm': 'base', 'status': pred['status'],
             'boxes': {k: np.asarray(v).tolist() for k, v in pred['boxes'].items()},
             'score': M.score_instances(pred['boxes'], gt)}]
    args = cache['args']
    for arm in arms:
        if arm == 'base':
            continue
        try:
            out = build(arm)(*args)
            rows.append({'room': folder.name, 'arm': arm, 'status': out['status'],
                         'boxes': {k: np.asarray(v).tolist() for k, v in out['boxes'].items()},
                         'score': M.score_instances(out['boxes'], gt),
                         'yaw_deg': out.get('yaw_deg'), 'prior_cost': out.get('prior_cost'),
                         'ensemble': out.get('ensemble')})
        except Exception as e:  # noqa: BLE001
            rows.append({'room': folder.name, 'arm': arm, 'error': repr(e)})
    return rows


def worker(task):
    folder, arms, tracker = task
    try:
        return room_sweep(folder, arms, tracker)
    except Exception as e:  # noqa: BLE001
        return [{'room': Path(folder).name, 'arm': 'error', 'error': repr(e)}]


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--rooms', required=True)
    ap.add_argument('--arms', default='base,c64,p05,p10,p30')
    ap.add_argument('--out', required=True)
    ap.add_argument('--pattern', default='multi-{i:05d}-s0')
    ap.add_argument('--tracker', choices=['none', 'b', 'gg'], default='none')
    ap.add_argument('--jobs', type=int, default=10)
    a = ap.parse_args()
    arms = a.arms.split(',')
    ids = []
    for part in a.rooms.split(','):
        if '-' in part:
            lo, hi = part.split('-')
            ids += list(range(int(lo), int(hi) + 1))
        else:
            ids.append(int(part))
    root = Path(a.root)
    tasks = [(str(root / 'records' / a.pattern.format(i=i)), arms, a.tracker) for i in ids]
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for part in pool.map(worker, tasks):
            rows += part
    Path(a.out).write_text(json.dumps(rows, indent=1, default=str))
    for arm in ['base'] + arms:
        rr = [r for r in rows if r.get('arm') == arm and 'score' in r]
        if not rr:
            continue
        print(arm, 'rooms', len(rr), 'whole', sum(r['score']['all_instances_hit'] for r in rr),
              'f1', round(float(np.mean([r['score']['f1'] for r in rr])), 4),
              'ok', sum(r['status'] == 'ok' for r in rr))
