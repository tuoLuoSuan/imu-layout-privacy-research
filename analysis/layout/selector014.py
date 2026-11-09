"""One-knob sweeps of the selection step of the frozen 011 decoder (014).

Pool accounting in `pool_recall014` showed the truncated candidate pools already
contain a box within 0.5 m of every truth instance in the rooms checked, so the
whole-room loss happens when the joint search picks among feasible assignments.
These arms only move selection knobs, never the interface and never truth:

  padding      contact tolerance passed to the support masks (default 0.3 m)
  support_w    weight of the soft contact residual inside the candidate energy
  cap          candidates kept per instance before the search (default 128)

`base` is the frozen setting and must reproduce the published arm.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path

import numpy as np

from . import evidence_space as ES
from . import multi_instance as M
from . import exp_bias014 as E
from . import oriented_raw011 as O
from .displacement011 import load, replay
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .multi_raw010 import infer as raw_infer

ARMS = {
    'base': (0.3, 0.3, 128),
    'p022': (0.22, 0.3, 128),
    'p040': (0.40, 0.3, 128),
    'w00': (0.3, 0.0, 128),
    'w10': (0.3, 1.0, 128),
    'w30': (0.3, 3.0, 128),
    'cap64': (0.3, 0.3, 64),
}


def decode_arm(priors, t, path, Rm, runs, walk, arm='base'):
    pad, scw, cap = ARMS[arm]
    dc, ec = O.directed_contact, ES._contact

    def dc_pad(category, boxes, point, heading, padding=.3):
        return dc(category, boxes, point, heading, pad)

    def ec_pad(boxes, event, padding, reach):
        return ec(boxes, event, pad, reach)

    O.directed_contact, ES._contact = dc_pad, ec_pad
    try:
        return O.decode(priors, t, path, Rm, runs, walk, candidate_limit=cap, support_cost_weight=scw)
    finally:
        O.directed_contact, ES._contact = dc, ec


def run_room(folder, arm):
    folder = Path(folder)
    priors = json.loads((folder / 'input' / 'known-priors.json').read_text())
    model = load(E.MODEL)

    def front(t, A, G):
        p, Rm, info = replay(t, A, G, model, heading_regularization=True)
        return p, Rm, info

    def refine(t, p, Rm, runs, known):
        p, a = loops(t, p, Rm, runs, known)
        p, b = wall(t, p, Rm, runs, known)
        return p, {'point_plane_loops': a, 'cabinet_wall': b}

    def decoder(*a, **kw):
        return decode_arm(a[0], a[1], a[2], a[3], a[4], a[5], arm=arm)

    pred = raw_infer(folder / 'input', priors, E.WRIST, trajectory_frontend=front, candidate_limit=128,
                     trajectory_refiner=refine, layout_decoder=decoder)
    native = E.OLD / 'raw-native800' / 'native' / (folder.name.rsplit('-s', 1)[0] + '.json')
    gt = M.load_native(native)['gt']
    return {'room': folder.name, 'arm': arm, 'status': pred['status'], 'score': M.score_instances(pred['boxes'], gt)}


def worker(task):
    folder, arm = task
    try:
        return run_room(folder, arm)
    except Exception as e:  # noqa: BLE001
        return {'room': Path(folder).name, 'arm': arm, 'error': repr(e)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--rooms', required=True)
    ap.add_argument('--arms', default='base,p022,p040,w00,w10,w30,cap64')
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=10)
    a = ap.parse_args()
    ids = []
    for part in a.rooms.split(','):
        if '-' in part:
            lo, hi = part.split('-')
            ids += list(range(int(lo), int(hi) + 1))
        else:
            ids.append(int(part))
    root = Path(a.root)
    folders = [str(root / 'records' / f'multi-{i:05d}-s0') for i in ids]
    arms = a.arms.split(',')
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        rows = list(pool.map(worker, [(f, arm) for f in folders for arm in arms]))
    Path(a.out).write_text(json.dumps(rows, indent=1))
    for arm in arms:
        rr = [r for r in rows if r.get('arm') == arm and 'score' in r]
        print(arm, 'rooms', len(rr), 'whole', sum(r['score']['all_instances_hit'] for r in rr),
              'f1', round(float(np.mean([r['score']['f1'] for r in rr])), 4),
              'ok', sum(r['status'] == 'ok' for r in rr))
