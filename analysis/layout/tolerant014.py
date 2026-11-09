"""Interval-valued contact residuals instead of point targets (014).

The frozen support model scores a cabinet contact by |distance - 0.60| and a
seated contact by distance-to-centre, both divided by the padding. Those are
point targets: a box whose surface sits 0.52 m from the phone is penalised as
much as one at 0.68 m, even though the phone-to-surface distance varies with
posture inside a band. Under 0.12-0.18 m pose error this term can prefer a box
that is farther from the trajectory but sits exactly at the nominal reach.

This module keeps the same accept/reject masks and only replaces the residual
with a hinge that is zero inside a tolerance band. Masks unchanged means the
feasible set is identical; only the selection objective moves, so the base arm
must reproduce the frozen arm exactly.

Arms:
  base       frozen residuals
  cabtol     cabinet residual zero while |d-0.60| <= tol
  chairtol   seated residual zero while centre distance <= tol
  band       both
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

TOL = .10
ARMS = {'base': (False, False), 'cabtol': (True, False), 'chairtol': (False, True), 'band': (True, True)}


def _directed(cab_tol, tol):
    base = O.directed_contact

    def call(category, boxes, point, heading, padding=.3):
        if category != 'cab' or not cab_tol:
            return base(category, boxes, point, heading, padding)
        boxes = np.asarray(boxes); p = np.asarray(point)
        axis = int(np.argmax(abs(np.asarray(heading)))); other = 1 - axis
        sign = 1 if heading[axis] >= 0 else -1
        face = boxes[:, axis] if sign > 0 else boxes[:, axis + 2]
        distance = (face - p[axis]) * sign
        along = (p[other] >= boxes[:, other] - padding) & (p[other] <= boxes[:, other + 2] + padding)
        keep = along & (abs(distance - .6) <= padding + 1e-8) & (np.argmin(boxes[:, 2:] - boxes[:, :2], axis=1) == axis)
        res = np.maximum(abs(distance - .6) - tol, 0.)
        return keep, res / max(padding, 1e-9)

    return call


def _contact(chair_tol, tol):
    base = ES._contact

    def call(boxes, event, padding, reach):
        if not chair_tol or event['object'] != 'chair':
            return base(boxes, event, padding, reach)
        keep, _ = base(boxes, event, padding, reach)
        d = np.linalg.norm(ES.centres(np.asarray(boxes, float)) - np.asarray(event['pos'], float), axis=1)
        return keep, np.maximum(d - tol, 0.) / max(padding, 1e-9)

    return call


def decode_arm(priors, t, path, Rm, runs, walk, arm='base'):
    cab_tol, chair_tol = ARMS[arm]
    dc, ec = O.directed_contact, ES._contact
    O.directed_contact, ES._contact = _directed(cab_tol, TOL), _contact(chair_tol, TOL)
    try:
        return O.decode(priors, t, path, Rm, runs, walk, candidate_limit=128, support_cost_weight=.3)
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
    ap.add_argument('--arms', default='base,cabtol,chairtol,band')
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
              'ok', sum(r['status'] == 'ok' for r in rr),
              'cab_tp', sum(r['score']['per_class']['cab']['tp'] for r in rr))
