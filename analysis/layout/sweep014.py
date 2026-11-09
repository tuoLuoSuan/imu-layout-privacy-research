"""One trajectory reconstruction per room, many decoders: sweep the retention cap.

Candidate truncation is not only a cost knob: keeping 128 per instance was worse
than keeping 64 in the 014 pools (22/32 at 256, 24/32 at 128, 25/32 at 64), which
suggests distractors dominate the near-flat contact objective.  Re-running the
whole front end for every cap would hide that signal behind 13 s of unrelated
work, so this module caches the six decoder arguments once per room and then
applies each arm offline.  No truth is read by any decoder.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path

import numpy as np

from . import multi_instance as M
from . import exp_bias014 as E
from .displacement011 import load, replay
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .multi_raw010 import infer as raw_infer
from .oriented_raw011 import decode as oriented_decode

CAPS = [32, 48, 64, 80, 96, 128]


def room_sweep(folder, caps):
    folder = Path(folder)
    priors = json.loads((folder / 'input' / 'known-priors.json').read_text())
    model = load(E.MODEL)
    cache = {}

    def front(t, A, G):
        return replay(t, A, G, model, heading_regularization=True)

    def refine(t, p, Rm, runs, known):
        p, a = loops(t, p, Rm, runs, known)
        p, b = wall(t, p, Rm, runs, known)
        return p, {'point_plane_loops': a, 'cabinet_wall': b}

    def decoder(*a, **k):
        cache['args'] = a[:6]
        return oriented_decode(a[0], a[1], a[2], a[3], a[4], a[5], candidate_limit=128,
                               support_cost_weight=.3)

    p = raw_infer(folder / 'input', priors, E.WRIST, trajectory_frontend=front, candidate_limit=128,
                  trajectory_refiner=refine, layout_decoder=decoder)
    native = E.OLD / 'raw-native800' / 'native' / (folder.name.rsplit('-s', 1)[0] + '.json')
    gt = M.load_native(native)['gt']
    rows = [{'room': folder.name, 'cap': 128, 'status': p['status'], 'boxes': {k: np.asarray(v).tolist() for k, v in p['boxes'].items()},
             'score': M.score_instances(p['boxes'], gt)}]
    args = cache['args']
    for cap in caps:
        if cap == 128:
            continue
        try:
            out = oriented_decode(*args, candidate_limit=cap, support_cost_weight=.3)
            rows.append({'room': folder.name, 'cap': cap, 'status': out['status'],
                         'boxes': {k: np.asarray(v).tolist() for k, v in out['boxes'].items()},
                         'score': M.score_instances(out['boxes'], gt),
                         'yaw_deg': out.get('yaw_deg'), 'search_nodes': out.get('search_nodes')})
        except Exception as e:  # noqa: BLE001
            rows.append({'room': folder.name, 'cap': cap, 'error': repr(e)})
    return rows


def worker(task):
    folder, caps = task
    try:
        return room_sweep(folder, caps)
    except Exception as e:  # noqa: BLE001
        return [{'room': Path(folder).name, 'cap': None, 'error': repr(e)}]


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--rooms', required=True)
    ap.add_argument('--caps', default='32,48,64,80,96,128')
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=10)
    a = ap.parse_args()
    caps = [int(c) for c in a.caps.split(',')]
    ids = []
    for part in a.rooms.split(','):
        if '-' in part:
            lo, hi = part.split('-')
            ids += list(range(int(lo), int(hi) + 1))
        else:
            ids.append(int(part))
    root = Path(a.root)
    tasks = [(str(root / 'records' / f'multi-{i:05d}-s0'), caps) for i in ids]
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for part in pool.map(worker, tasks):
            rows += part
    Path(a.out).write_text(json.dumps(rows, indent=1, default=str))
    for cap in caps:
        rr = [r for r in rows if r.get('cap') == cap and 'score' in r]
        print('cap', cap, 'rooms', len(rr), 'whole', sum(r['score']['all_instances_hit'] for r in rr),
              'f1', round(float(np.mean([r['score']['f1'] for r in rr])), 4),
              'ok', sum(r['status'] == 'ok' for r in rr))
