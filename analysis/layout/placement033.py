"""Does the fixed-budget contact-placement effect survive the device chain?

The geometric layer measures the effect with ideal trajectories: dispersing the
same fourteen contacts over the same route lifts whole-room recovery from
39.78% to 64.70% over 10,000 rooms.  That number is only interesting for this
paper if it is still there when the contacts have to be acquired from noisy
phone and wrist streams, refined, and decoded under declared priors.

Both arms therefore share the room, the walking route, the contact count, the
sensor model, the noise seeds, the front end, both refiners and the decoder.
Only the placement protocol of the same fourteen interactions changes: 'repeat'
returns to one surface per instance, 'dispersed' visits distinct surfaces.
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
from .multi_raw010 import plan, infer
from .displacement011 import load, replay
from .bias_tracker014b import gated_gyro
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .priorcost014 import decode_arm as prior_decode
from . import sensor013 as S

STORE = Path('output/layout-recon/matrix023/off0/v14-s0.0')


def cell(task):
    rid, placement, visits, severity, streams, out = task
    out = Path(out)
    native = E.OLD / 'raw-native800' / 'native' / f'multi-{rid:05d}.json'
    meta = json.loads((E.WRIST / 'metadata.json').read_text())
    scene = M.load_native(native)
    start = json.loads(native.read_text())['agent_placement']['position']
    scene['S'] = np.array([start['x'], start['z']])
    script, prefix = plan(scene, visits=visits, placement=placement)
    phone = generate(scene, 1900000 + rid, script_override=script,
                     noise_streams='independent-v1' if streams == 'prefix' else 'legacy')
    noisy = S.degrade(phone, severity, seed=1910000 + rid,
                      noise_streams='prefix-v1' if streams == 'prefix' else 'legacy')
    watch = mount(generate_watch(noisy, 1900300 + rid), meta['neutral_up_from_development'])
    session = out / 'input'
    write_input(session, noisy)
    write_watch(session, watch)
    priors = {'room': [scene['W'], scene['L']], 'start': scene['S'].tolist(),
              'inventory': [{**e, 'dimensions': np.asarray(e['dimensions']).tolist()}
                            for e in scene['inventory']]}
    (session / 'known-priors.json').write_text(json.dumps(priors))
    model = load(E.MODEL)

    def front(t, A, G):
        _, Gc, info = gated_gyro(t, A, G)
        p, Rm, m = replay(t, A, Gc, model, heading_regularization=True)
        m['gyro_tracker014'] = info
        return p, Rm, m

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
        contacts = [r for r in pred['runs'] if r[0] in ('seated', 'lying', 'cabinet')]
        row = {'room': rid, 'placement': placement, 'visits': visits, 'severity': severity,
               'status': pred['status'], 'all_instances_hit': bool(score['all_instances_hit']),
               'f1': float(score['f1']), 'ok': pred['status'] == 'ok',
               'per_class': score['per_class'], 'n_contacts': len(contacts),
               'distinct_instances': len({c[0] for c in contacts}),
               'duration_s': float(max(r[2] for r in pred['runs'])),
               'coverage_free': float(prefix['coverage_free'])}
    except Exception as e:  # noqa: BLE001
        row = {'room': rid, 'placement': placement, 'visits': visits, 'severity': severity,
               'error': repr(e)}
    (out / 'result.json').write_text(json.dumps(row, indent=1, default=float))
    return row


def run(ids, placements, visits, severity, streams, out, workers):
    out = Path(out)
    tasks = [(rid, p, visits, severity, streams, out / p / f'multi-{rid:05d}')
             for p in placements for rid in ids]
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(cell, tasks):
            rows.append(row)
            print(json.dumps({k: row.get(k) for k in ('room', 'placement', 'status',
                                                      'all_instances_hit', 'f1')}), flush=True)
    return rows


def summarise(rows):
    out = {}
    for p in sorted({r['placement'] for r in rows}):
        mine = [r for r in rows if r['placement'] == p]
        err = [r for r in mine if 'error' in r]
        score = [r for r in mine if 'error' not in r]
        out[p] = {'n': len(mine), 'errors': len(err), 'scored': len(score),
                  'whole': sum(bool(r['all_instances_hit']) for r in score),
                  'mean_f1': float(np.mean([r['f1'] for r in score])) if score else None,
                  'mean_contacts': float(np.mean([r['n_contacts'] for r in score])) if score else None}
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', default='11500-11511')
    ap.add_argument('--arms', default='repeat,dispersed')
    ap.add_argument('--visits', type=int, default=14)
    ap.add_argument('--severity', type=float, default=0.0)
    ap.add_argument('--streams', default='prefix', choices=['legacy', 'prefix'])
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--out', default='output/layout-recon/placement033')
    a = ap.parse_args()
    lo, hi = a.ids.split('-')
    ids = list(range(int(lo), int(hi) + 1))
    rows = run(ids, a.arms.split(','), a.visits, a.severity, a.streams, a.out, a.workers)
    summary = summarise(rows)
    gate = None
    stored = STORE / 'multi-11500' / 'result.json'
    if stored.exists():
        ref = json.loads(stored.read_text())
        mine = next((r for r in rows if r['room'] == 11500 and r['placement'] == 'dispersed'), None)
        gate = {'stored': {'all_instances_hit': ref.get('all_instances_hit'), 'f1': ref.get('f1')},
                'recomputed': None if mine is None else
                {'all_instances_hit': mine.get('all_instances_hit'), 'f1': mine.get('f1')}}
        gate['passed'] = bool(mine and mine.get('all_instances_hit') == ref.get('all_instances_hit')
                              and abs((mine.get('f1') or 0) - ref.get('f1')) <= 1e-9)
    payload = {'protocol': {'ids': [min(ids), max(ids)], 'arms': a.arms.split(','),
                            'visits': a.visits, 'severity': a.severity, 'streams': a.streams,
                            'note': 'same route, contact count, sensor model, seeds, front end, '
                                    'refiners and decoder; only the placement protocol differs'},
               'gate': gate, 'summary': summary, 'rows': rows}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'placement033.json').write_text(json.dumps(payload, indent=1, default=float))
    print(json.dumps({'summary': summary, 'gate': gate}, indent=1))
