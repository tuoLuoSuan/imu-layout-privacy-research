"""Activity budget x evidence quality: one paired 3x3 matrix, not a fitted surface.

Earlier layers varied one axis at a time: the simulation line varied the interaction
budget with clean geometry, and the device line varied sensor severity at a fixed
budget.  The claim that leakage is set jointly by how much activity there is and how
well it is measured needs the two axes on the same rooms and the same chain.  Each
cell therefore regenerates the same scene with a different visit budget, applies the
same sensor model at a different severity, and runs the frozen front end, the gated
gyro tracker, the two refiners and the declared-prior decoder.  Cells are reported
separately; nothing here is interpolated into a curve.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path

import numpy as np

from . import multi_instance as M, exp_bias014 as E
from .sim_handset import generate
from .sim_watch import generate as generate_watch, write as write_watch
from .joint009 import mount
from .synthetic_bridge import write_input
from .displacement011 import load, replay
from .bias_tracker014b import gated_gyro
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .multi_raw010 import plan, infer
from .priorcost014 import decode_arm as prior_decode
from . import sensor013 as S


def cell(task):
    rid, visits, severity, out = task
    out = Path(out)
    native = E.OLD / 'raw-native800' / 'native' / f'multi-{rid:05d}.json'
    meta = json.loads((E.WRIST / 'metadata.json').read_text())
    scene = M.load_native(native)
    start = json.loads(native.read_text())['agent_placement']['position']
    scene['S'] = np.array([start['x'], start['z']])
    script, prefix = plan(scene, visits=visits)
    phone = generate(scene, 1900000 + rid, script_override=script)
    noisy = S.degrade(phone, severity, seed=1910000 + rid)
    watch = mount(generate_watch(noisy, 1900300 + rid), meta['neutral_up_from_development'])
    session = out / 'input'
    write_input(session, noisy)
    write_watch(session, watch)
    priors = {'room': [scene['W'], scene['L']], 'start': scene['S'].tolist(),
              'inventory': [{**e, 'dimensions': np.asarray(e['dimensions']).tolist()} for e in scene['inventory']]}
    (session / 'known-priors.json').write_text(json.dumps(priors))
    model = load(E.MODEL)

    def front(t, A, G):
        _, Gc, info = gated_gyro(t, A, G)
        p, Rm, meta_f = replay(t, A, Gc, model, heading_regularization=True)
        meta_f['gyro_tracker014'] = info
        return p, Rm, meta_f

    def refine(t, p, Rm, runs, known):
        p, a = loops(t, p, Rm, runs, known)
        p, b = wall(t, p, Rm, runs, known)
        return p, {'point_plane_loops': a, 'cabinet_wall': b}

    def decoder(*a, **k):
        return prior_decode(*a[:6], arm='base')

    try:
        pred = infer(session, priors, E.WRIST, trajectory_frontend=front, candidate_limit=128,
                     trajectory_refiner=refine, layout_decoder=decoder)
        score = M.score_instances(pred['boxes'], scene['gt'])
        row = {'room': rid, 'visits': visits, 'severity': severity, 'status': pred['status'],
               'all_instances_hit': bool(score['all_instances_hit']), 'f1': float(score['f1']),
               'ok': pred['status'] == 'ok', 'per_class': score['per_class'],
               'n_events': len(pred['runs']), 'duration_s': float(max(r[2] for r in pred['runs'])),
               'coverage_free': float(prefix['coverage_free']),
               'sensor': S.report(phone, noisy)}
    except Exception as e:  # noqa: BLE001
        row = {'room': rid, 'visits': visits, 'severity': severity, 'error': repr(e)}
    (out / 'result.json').write_text(json.dumps(row, indent=1, default=float))
    return row


def worker(task):
    try:
        return cell(task)
    except Exception as e:  # noqa: BLE001
        rid, visits, severity, _ = task
        return {'room': rid, 'visits': visits, 'severity': severity, 'error': repr(e)}


def summarise(rows):
    cells = {}
    for r in rows:
        key = f"v{r['visits']}-s{r['severity']}"
        c = cells.setdefault(key, {'visits': r['visits'], 'severity': r['severity'], 'n': 0, 'whole': 0, 'ok': 0,
                                   'f1': 0., 'errors': 0, 'events': [], 'coverage': []})
        c['n'] += 1
        if 'error' in r:
            c['errors'] += 1
            continue
        c['whole'] += int(r['all_instances_hit'])
        c['ok'] += int(r['ok'])
        c['f1_sum'] = c.get('f1_sum', 0.) + r['f1']
        c['scored'] = c.get('scored', 0) + 1
        c['events'].append(r['n_events'])
        c['coverage'].append(r['coverage_free'])
    for c in cells.values():
        c['f1'] = c.pop('f1_sum', 0.) / max(1, c.get('scored', 0))
        c['events_median'] = float(np.median(c.pop('events'))) if c['events'] else None
        c['coverage_median'] = float(np.median(c.pop('coverage'))) if c['coverage'] else None
    return cells


def run(ids, visits, severities, out, workers=6):
    out = Path(out)
    tasks = []
    for v in visits:
        for s in severities:
            for i in ids:
                d = out / f'v{v}-s{s}' / f'multi-{i:05d}'
                d.mkdir(parents=True, exist_ok=True)
                tasks.append((i, v, s, str(d)))
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(worker, tasks):
            rows.append(r)
            print(json.dumps({k: r.get(k) for k in ('room', 'visits', 'severity', 'error', 'status')}), flush=True)
    cells = summarise(rows)
    payload = {'cells': cells, 'rows': rows}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'matrix.json').write_text(json.dumps(payload, indent=1, default=float))
    print(json.dumps({k: {m: v[m] for m in ('whole', 'ok', 'f1', 'errors')} for k, v in cells.items()}, indent=1))
    return payload


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--ids', default='11500-11511')
    p.add_argument('--visits', default='6,10,14')
    p.add_argument('--severities', default='0,0.5,1')
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    lo, hi = a.ids.split('-')
    run(list(range(int(lo), int(hi) + 1)), [int(x) for x in a.visits.split(',')],
        [float(x) for x in a.severities.split(',')], a.out, a.workers)
