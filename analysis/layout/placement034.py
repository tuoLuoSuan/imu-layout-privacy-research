"""Does the placement effect depend on the decoder?

placement033.py shows that dispersing the same fourteen contacts lifts whole-room
recovery on the device chain (64 unseen rooms: 48/64 against 30/64).  That
statement was conditional on one decoder: priorcost014.decode_arm('base'), the
directional decoder with candidate cap 128 and no pricing.  This module repeats
the same record twice per room, once per placement protocol, and decodes the
same runs with three decoders that differ in the candidate cap and in whether a
wall/support price reshuffles the candidate order:

  base      cap 128, direct directional decode (reproduces placement033)
  c64       cap 64, the truncation arm used in the earlier batches
  p10c64    cap 64 with the priced pool (lambda 10), the arm that gained on the
            11200/11600 batches

Only the decoder changes between arms; record, front end, refiners, priors and
walk mask are shared, so the placement effect is measured under three different
selections of the same candidate set.
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
DECODERS = ('base', 'basec64', 'p10c64')


def cell(task):
    rid, placement, visits, severity, streams, out, decoders = task
    out = Path(out)
    cached = out / 'result.json'
    if cached.exists():
        try:
            old = json.loads(cached.read_text())
            if not old.get('error'):
                return old
        except Exception:  # noqa: BLE001
            pass
    decoders = tuple(decoders)
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

    scores = {}

    def decoder(priors_, t, path, Rm, runs, walk, candidate_limit=128):
        boxes = None
        for arm in decoders:
            try:
                b = prior_decode(priors_, t, path, Rm, runs, walk, arm=arm)
                s = M.score_instances(b['boxes'], scene['gt'])
                scores[arm] = {'all_instances_hit': bool(s['all_instances_hit']),
                               'f1': float(s['f1']), 'tp': int(s['tp']),
                               'n_pred': int(s['fp'] + s['tp'])}
                if arm == 'base':
                    boxes = b
            except Exception as exc:  # noqa: BLE001
                scores[arm] = {'error': repr(exc)}
                if arm == 'base':
                    raise
        return boxes

    try:
        pred = infer(session, priors, E.WRIST, trajectory_frontend=front, candidate_limit=128,
                     trajectory_refiner=refine, layout_decoder=decoder)
        contacts = [r for r in pred['runs'] if r[0] in ('seated', 'lying', 'cabinet')]
        row = {'room': rid, 'placement': placement, 'visits': visits, 'severity': severity,
               'status': pred['status'], 'decoders': scores,
               'n_contacts': len(contacts),
               'duration_s': float(max(r[2] for r in pred['runs'])),
               'coverage_free': float(prefix['coverage_free'])}
    except Exception as e:  # noqa: BLE001
        row = {'room': rid, 'placement': placement, 'visits': visits, 'severity': severity,
               'error': repr(e), 'decoders': scores}
    (out / 'result.json').write_text(json.dumps(row, indent=1, default=float))
    return row


def run(ids, placements, visits, severity, streams, out, workers, decoders=DECODERS):
    out = Path(out)
    tasks = [(rid, p, visits, severity, streams, out / p / f'multi-{rid:05d}', decoders)
             for p in placements for rid in ids]
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(cell, tasks):
            rows.append(row)
            print(json.dumps({'room': row.get('room'), 'placement': row.get('placement'),
                              'status': row.get('status'),
                              'scores': {k: {kk: row['decoders'][k].get(kk)
                                             for kk in ('all_instances_hit', 'f1')}
                                         for k in row.get('decoders', {})},
                              'error': row.get('error')}), flush=True)
    return rows


def summarise(rows, decoders=DECODERS):
    out = {}
    for arm in decoders:
        for p in sorted({r['placement'] for r in rows}):
            mine = [r for r in rows if r['placement'] == p and arm in r.get('decoders', {})]
            scored = [r for r in mine if 'error' not in r['decoders'][arm]]
            errors = [r for r in mine if 'error' in r['decoders'][arm]]
            out.setdefault(arm, {})[p] = {
                'n': len(mine), 'scored': len(scored), 'errors': len(errors),
                'whole': sum(bool(r['decoders'][arm]['all_instances_hit']) for r in scored),
                'mean_f1': float(np.mean([r['decoders'][arm]['f1'] for r in scored])) if scored else None,
                'error_examples': [r['decoders'][arm]['error'] for r in errors[:3]]}
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', default='11500-11511')
    ap.add_argument('--arms', default='repeat,dispersed')
    ap.add_argument('--visits', type=int, default=14)
    ap.add_argument('--severity', type=float, default=0.0)
    ap.add_argument('--streams', default='prefix', choices=['legacy', 'prefix'])
    ap.add_argument('--decoders', default=','.join(DECODERS))
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--out', default='output/layout-recon/placement034')
    a = ap.parse_args()
    ids = []
    for chunk in a.ids.split(','):
        lo, hi = chunk.split('-')
        ids.extend(range(int(lo), int(hi) + 1))
    rows = run(ids, a.arms.split(','), a.visits, a.severity, a.streams, a.out, a.workers,
               a.decoders.split(','))
    summary = summarise(rows, tuple(a.decoders.split(',')))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'placement034.json').write_text(json.dumps(
        {'ids': ids, 'summary': summary, 'rows': rows}, indent=1, default=float))
    print(json.dumps(summary, indent=1))
