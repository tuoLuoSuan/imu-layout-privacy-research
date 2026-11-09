"""Run every same-RMS shape on the same rooms, one trajectory front end each."""
import argparse
import concurrent.futures
import json
from pathlib import Path

import numpy as np

from . import multi_instance as M
from . import exp_bias014 as E
from .displacement011 import load, replay
from .bias_tracker014b import replay as gated_replay, gated_gyro
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .multi_raw010 import infer as raw_infer
from .priorcost014 import decode_arm
from .sensorshape014 import perturb, conditions, TARGET as DEFAULT_TARGET

CASE_ROOT = {
    'confirm32': Path('output/research-sync/2026-11-09-bias-aware-input-014/confirm32'),
    'fresh32': Path('output/research-sync/2026-11-09-paper-and-raw-input-012/wall-fresh32'),
}


def _plain(obj):
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if hasattr(obj, 'item'):
        return obj.item()
    return obj


def _path_len(p):
    p = np.asarray(p, dtype=float)
    return float(np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1).sum())


def run_room(folder, seed=0, target=None, tracker='none', only=None):
    target = dict(DEFAULT_TARGET if target is None else target)
    folder = Path(folder)
    priors = json.loads((folder / 'input' / 'known-priors.json').read_text())
    model = load(E.MODEL)
    truth = np.load(folder / 'evaluation-truth.npz')
    pos_true = np.asarray(truth['position'], dtype=float)
    len_true = _path_len(pos_true)
    disp_true = float(np.linalg.norm(pos_true[-1, :2] - pos_true[0, :2]))
    native = E.OLD / 'raw-native800' / 'native' / (folder.name.rsplit('-s', 1)[0] + '.json')
    gt = M.load_native(native)['gt']

    state = {}

    def refine(t, p, Rm, runs, known):
        p, a = loops(t, p, Rm, runs, known)
        p, b = wall(t, p, Rm, runs, known)
        state['path'] = np.asarray(p, dtype=float)
        return p, {'loops': a, 'wall': b}

    def make_front(shape, channels):
        def run(t, A, G):
            if tracker == 'b':
                return gated_replay(t, A, G, model)
            if tracker == 'gg':
                _, Gc, _ = gated_gyro(t, A, G)
                return replay(t, A, Gc, model, heading_regularization=True)
            return replay(t, A, G, model, heading_regularization=True)

        def front(t, A, G):
            if shape is None:
                return run(t, A, G)
            A2, G2 = perturb(A, G, shape, channels, seed, target)
            return run(t, A2, G2)
        return front

    rows = []
    for name, shape, channels in conditions():
        if only and name not in only:
            continue
        chans = ('gyro', 'acc') if channels == 'both' else (channels,) if channels else ()

        def decoder(*a, **k):
            return decode_arm(*a[:6], arm='base')

        try:
            pred = raw_infer(folder / 'input', priors, E.WRIST, trajectory_frontend=make_front(shape, chans),
                             candidate_limit=128, trajectory_refiner=refine, layout_decoder=decoder)
        except Exception as exc:  # noqa: BLE001
            rows.append({'room': folder.name, 'condition': name, 'status': 'frontend_error',
                         'error': repr(exc)[:300], 'score': None, 'path_ratio': None, 'disp_ratio': None})
            print(json.dumps({'room': folder.name, 'cond': name, 'status': 'frontend_error'}), flush=True)
            continue
        path = state.get('path')
        rows.append({'room': folder.name, 'condition': name, 'status': pred['status'],
                     'score': M.score_instances(pred['boxes'], gt),
                     'path_ratio': None if path is None else _path_len(path) / len_true,
                     'disp_ratio': None if path is None else float(np.linalg.norm(path[-1, :2] - path[0, :2])) / disp_true})
        print(json.dumps({'room': folder.name, 'cond': name, 'status': pred['status'],
                          'tp': rows[-1]['score']['tp']}), flush=True)
    return rows


def worker(task):
    folder, seed, target, tracker, only = task
    try:
        return run_room(folder, seed, target, tracker, only)
    except Exception as e:  # noqa: BLE001
        return [{'room': Path(folder).name, 'condition': 'error', 'error': repr(e)}]


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', choices=sorted(CASE_ROOT), required=True)
    ap.add_argument('--rooms', required=True)
    ap.add_argument('--pattern', default='multi-{i:05d}-s0')
    ap.add_argument('--seed', type=int, default=7000)
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--tracker', choices=['none', 'b', 'gg'], default='none')
    ap.add_argument('--only', default='')
    ap.add_argument('--acc-rms', type=float, default=DEFAULT_TARGET['acc'])
    ap.add_argument('--gyro-rms', type=float, default=DEFAULT_TARGET['gyro'])
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    target = {'acc': a.acc_rms, 'gyro': a.gyro_rms}
    ids = []
    for part in a.rooms.split(','):
        if '-' in part:
            lo, hi = part.split('-')
            ids += list(range(int(lo), int(hi) + 1))
        else:
            ids.append(int(part))
    root = CASE_ROOT[a.case]
    only = set(filter(None, a.only.split(',')))
    tasks = [(str(root / 'records' / a.pattern.format(i=i)), a.seed + i, target, a.tracker, only) for i in ids]
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for part in pool.map(worker, tasks):
            rows += part
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(_plain(rows), indent=1, default=str))
    for name, _, _ in conditions():
        rr = [r for r in rows if r.get('condition') == name and isinstance(r.get('score'), dict)]
        if not rr:
            continue
        pr = [r['path_ratio'] for r in rr if r.get('path_ratio')]
        print(name, 'n', len(rr), 'whole', sum(r['score']['all_instances_hit'] for r in rr),
              'f1', round(float(np.mean([r['score']['f1'] for r in rr])), 4),
              'ok', sum(r['status'] == 'ok' for r in rr),
              'path_ratio', round(float(np.median(pr)), 4) if pr else None)
