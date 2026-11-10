"""Equal-contact selection at one fixed 14-visit, severity-0 recording.

The 3x3 visit-by-severity matrix confounds how many contacts a decoder sees with
how long the recording is: a fourteen-visit cell has both a longer stream and
more contact events than a six-visit cell.  This module holds the recording
fixed (14 visits, severity 0, prefix streams, offset 0 -- exactly the matrix016
cell) and subsamples the *qualified contact runs* down to a fixed count k, so
the only thing that changes between arms is which contacts reach the refiners
and the declared-prior decoder.

The chain is not multi_raw010.infer(), because infer() always hands every run to
the refiners.  The stages are therefore called here in the same order and with
the same arguments as infer(): phone channels -> displacement front end on the
gated-gyro stream -> watch prediction and fusion -> qualified_runs ->
contact_loops011.refine -> wall_refine012.refine -> priorcost014.decode_arm ->
multi_instance.score_instances.  Walk runs are never subsampled, so the walk
mask given to the decoder is built from the same run list that reaches the
refiners.

Strategies (all at the same k, same record, same front end):
  base     every contact (reference; must reproduce the stored 14-visit row),
  prefix   the first k contacts in time order,
  disperse greedy farthest point over the predicted contact position, starting
           from the contact farthest from the room centre,
  random   k contacts sampled uniformly without replacement, three seeds,
  oracle   greedy over true object identity against scene['gt'].
"""
import argparse
import concurrent.futures
import json
from pathlib import Path

import numpy as np

from . import multi_instance as M, exp_bias014 as E, sensor013 as S, action_model as AM
from .sim_handset import generate
from .sim_watch import generate as generate_watch, write as write_watch
from .joint009 import mount
from .synthetic_bridge import write_input
from .displacement011 import load, replay
from .bias_tracker014b import gated_gyro
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .multi_raw010 import plan, qualified_runs
from .priorcost014 import decode_arm as prior_decode
from .watch_cabinet import load as load_watch, fuse
from .wrist_binary import predict

CONTACT = ('seated', 'lying', 'cabinet')
ORACLE_CLASSES = ('chair', 'bed', 'cab')  # categories a contact can actually be about
STORE = Path('output/layout-recon/matrix023/off0/v14-s0.0')
WATCH_ORIGIN_NS = int(1700000000000000000)
SEEDS = (1, 2, 3)


def seed_of(room, index):
    """Fixed, reported sample seed: independent of the drawn values."""
    return 26000 + 10 * room + index


def build(room, root, visits=14, severity=0.0, offset=0):
    """Same scene load, seeds and file writing as matrix016.cell()."""
    native = E.OLD / 'raw-native800' / 'native' / f'multi-{room:05d}.json'
    meta = json.loads((E.WRIST / 'metadata.json').read_text())
    scene = M.load_native(native)
    start = json.loads(native.read_text())['agent_placement']['position']
    scene['S'] = np.array([start['x'], start['z']])
    script, prefix = plan(scene, visits=visits)
    phone = generate(scene, 1900000 + room + offset, script_override=script,
                     noise_streams='independent-v1')
    noisy = S.degrade(phone, severity, seed=1910000 + room + offset, noise_streams='prefix-v1')
    watch = mount(generate_watch(noisy, 1900300 + room), meta['neutral_up_from_development'])
    session = root / f'v{visits}-s{severity}' / f'multi-{room:05d}' / 'input'
    write_input(session, noisy)
    write_watch(session, watch)
    priors = {'room': [scene['W'], scene['L']], 'start': scene['S'].tolist(),
              'inventory': [{**e, 'dimensions': np.asarray(e['dimensions']).tolist()}
                            for e in scene['inventory']]}
    (session / 'known-priors.json').write_text(json.dumps(priors))
    return {'native': native, 'scene': scene, 'session': session, 'priors': priors,
            'prefix': prefix, 'meta': meta}


def front_end(state, model):
    session = state['session']
    channels = AM.load_phone(session)
    t, A, _ = channels['accelerometer']
    tg, G, _ = channels['gyroscope']
    G = np.c_[*[np.interp(t, tg, G[:, i]) for i in range(3)]]
    _, Gc, gyro_info = gated_gyro(t, A, G)
    path, Rm, info = replay(t, A, Gc, model, heading_regularization=True)
    info['gyro_tracker014'] = gyro_info
    phone = AM.predict_timeline(AM.load_model(), t, A, t, G)
    wt, wa = load_watch(session, WATCH_ORIGIN_NS)
    watch = predict(wt, wa, E.WRIST)
    runs = qualified_runs(t, A, fuse(phone, watch)['runs'])
    return t, A, path, Rm, runs, info


def contact_order(runs):
    """Indices of contact runs, in time order."""
    return sorted([i for i, r in enumerate(runs) if r[0] in CONTACT], key=lambda i: runs[i][1])


def contact_positions(t, path, runs, order):
    """Predicted contact position: the unrefined path at the run's time midpoint."""
    out = []
    for i in order:
        _, a, b = runs[i]
        index = int(np.clip(np.searchsorted(t, .5 * (a + b)), 0, len(t) - 1))
        out.append(np.asarray(path[index], float))
    return np.asarray(out, float).reshape(-1, 2)


def pick_prefix(n, k):
    return list(range(min(k, n)))


def pick_disperse(pos, centre, k):
    if not len(pos):
        return []
    chosen = [int(np.argmax(np.linalg.norm(pos - np.asarray(centre, float), axis=1)))]
    while len(chosen) < min(k, len(pos)):
        gap = np.min(np.linalg.norm(pos[:, None, :] - pos[chosen][None, :, :], axis=2), axis=1)
        gap[chosen] = -1.
        chosen.append(int(np.argmax(gap)))
    return chosen


def pick_random(n, k, seed):
    rng = np.random.default_rng(seed)
    return sorted(int(i) for i in rng.choice(n, size=min(k, n), replace=False))


def pick_oracle(pos, gt, k):
    """Greedy true-identity cover: repeatedly take the (object, contact) pair that
    is globally nearest among still-uncovered objects and still-unpicked contacts."""
    names = [n for n in sorted(gt) if M.category(n) in ORACLE_CLASSES]
    centres = np.asarray([(np.asarray(gt[n])[:2] + np.asarray(gt[n])[2:]) / 2. for n in names], float)
    chosen, covered, free = [], set(), set(range(len(pos)))
    while len(chosen) < min(k, len(pos)) and free and names:
        best = None
        # Prefer an as-yet-uncovered object; once every contact class object is
        # covered the remaining picks go to the unpicked contact nearest any of
        # them, so the oracle still sees exactly k contacts like the other arms.
        pool = [oi for oi in range(len(names)) if oi not in covered] or list(range(len(names)))
        for oi in pool:
            for ci in sorted(free):
                distance = float(np.linalg.norm(pos[ci] - centres[oi]))
                if best is None or distance < best[0] - 1e-12:
                    best = (distance, oi, ci)
        if best is None:
            break
        chosen.append(best[2])
        covered.add(best[1])
        free.discard(best[2])
    return chosen


def subset(runs, order, picked):
    """Runs with only the picked contacts kept; every non-contact run survives."""
    keep = {order[p] for p in picked}
    return [list(r) for i, r in enumerate(runs) if r[0] not in CONTACT or i in keep]


def walk_mask(t, runs):
    mask = np.zeros(len(t), bool)
    for label, a, b in runs:
        if label == 'walk':
            mask |= (t >= a) & (t <= b)
    return mask


def arm(t, path, Rm, runs, order, picked, priors, scene):
    runs_sub = subset(runs, order, picked)
    p, detail = loops(t, path, Rm, runs_sub, priors)
    p, wall_detail = wall(t, p, Rm, runs_sub, priors)
    pred = prior_decode(priors, t, p, Rm, runs_sub, walk_mask(t, runs_sub), 'base')
    score = M.score_instances(pred['boxes'], scene['gt'])
    return {'status': pred['status'], 'all_instances_hit': bool(score['all_instances_hit']),
            'f1': float(score['f1']), 'tp': int(score['tp']), 'n_pred': len(pred['boxes']),
            'n_events': len(pred['events']), 'refinement': {'point_plane_loops': detail,
                                                            'cabinet_wall': wall_detail},
            'picked_runs': [runs[i] for i in sorted(order[p] for p in picked)]}


def room_rows(room, k, out, strategies=('base', 'prefix', 'disperse', 'oracle', 'random')):
    state = build(room, out)
    model = load(E.MODEL)
    t, A, path, Rm, runs, info = front_end(state, model)
    order = contact_order(runs)
    pos = contact_positions(t, path, runs, order)
    centre = (.5 * float(state['scene']['W']), .5 * float(state['scene']['L']))
    plans = []
    if 'base' in strategies:
        plans.append(('base', None, list(range(len(order)))))
    if 'prefix' in strategies:
        plans.append(('prefix', None, pick_prefix(len(order), k)))
    if 'disperse' in strategies:
        plans.append(('disperse', None, pick_disperse(pos, centre, k)))
    if 'oracle' in strategies:
        plans.append(('oracle', None, pick_oracle(pos, {n: np.asarray(b) for n, b in state['scene']['gt'].items()}, k)))
    if 'random' in strategies:
        for s in SEEDS:
            plans.append(('random', seed_of(room, s), pick_random(len(order), k, seed_of(room, s))))
    rows = []
    for name, seed, picked in plans:
        row = {'room': room, 'strategy': name, 'seed': seed, 'k': k,
               'n_contacts_available': len(order), 'n_contacts_used': len(picked),
               'contacts_kept': [[runs[order[p]][0], round(float(runs[order[p]][1]), 3),
                                  round(float(runs[order[p]][2]), 3)] for p in sorted(picked)],
               'predicted_positions': [np.round(pos[p], 3).tolist() for p in sorted(picked)]}
        try:
            row.update(arm(t, path, Rm, runs, order, picked, state['priors'], state['scene']))
            row['error'] = None
        except Exception as e:  # noqa: BLE001
            row.update({'status': 'error', 'error': repr(e), 'all_instances_hit': False, 'f1': 0.})
        rows.append(row)
        print(json.dumps({'room': room, 'strategy': name, 'seed': seed,
                          'contacts': [len(picked), len(order)],
                          'hit': row['all_instances_hit'], 'f1': round(row['f1'], 4),
                          'status': row['status'], 'error': row['error']}), flush=True)
    return {'room': room, 'rows': rows, 'n_contacts_available': len(order),
            'n_contact_objects': len([n for n in state['scene']['gt'] if M.category(n) in ORACLE_CLASSES]),
            'contact_positions': np.round(pos, 3).tolist(), 'room_centre': list(centre),
            'gyro_tracker014': {k2: v for k2, v in info.items() if k2 != 'stationary_mask'}}


def worker(task):
    room, k, out, strategies = task
    try:
        return room_rows(room, k, Path(out), strategies)
    except Exception as e:  # noqa: BLE001
        return {'room': room, 'error': repr(e), 'rows': []}


def stored(room):
    path = STORE / f'multi-{room:05d}' / 'result.json'
    if not path.exists():
        return None
    row = json.loads(path.read_text())
    return {'path': str(path).replace('\\', '/'), 'status': row.get('status'),
            'all_instances_hit': bool(row['all_instances_hit']), 'f1': float(row['f1'])}


def summarise(rows, rooms):
    out = {}
    for name in sorted({r['strategy'] for r in rows}):
        group = [r for r in rows if r['strategy'] == name]
        scored = [r for r in group if not r.get('error')]
        out[name] = {'n_rows': len(group), 'n_rooms': len({r['room'] for r in group}),
                     'n_scored': len(scored), 'errors': len(group) - len(scored),
                     'whole_room_hits': int(sum(r['all_instances_hit'] for r in scored)),
                     'whole_room_rate': float(np.mean([r['all_instances_hit'] for r in scored])) if scored else 0.,
                     'mean_f1': float(np.mean([r['f1'] for r in scored])) if scored else 0.,
                     'mean_contacts_used': float(np.mean([r['n_contacts_used'] for r in scored])) if scored else 0.,
                     'mean_contacts_available': float(np.mean([r['n_contacts_available'] for r in scored])) if scored else 0.}
    out['_rooms'] = {'n_planned': len(rooms), 'n_reported': len({r['room'] for r in rows}),
                     'n_error_rows': int(sum(1 for r in rows if r.get('error')))}
    return out


def gate(rows, room=11500):
    """The base arm must reproduce the stored fourteen-visit severity-0 row."""
    reference = stored(room)
    base = next((r for r in rows if r['room'] == room and r['strategy'] == 'base'), None)
    if reference is None or base is None:
        return {'room': room, 'checked': False, 'reason': 'stored row or base row missing',
                'stored': reference, 'recomputed': None}
    passed = (bool(base['all_instances_hit']) == reference['all_instances_hit']
              and abs(float(base['f1']) - reference['f1']) <= 1e-9)
    return {'room': room, 'checked': True, 'passed': bool(passed), 'stored': reference,
            'recomputed': {'all_instances_hit': bool(base['all_instances_hit']),
                           'f1': float(base['f1']), 'status': base['status'],
                           'n_contacts_available': base['n_contacts_available']},
            'criterion': 'same all_instances_hit and |f1 difference| <= 1e-9'}


def run(rooms, k, out, jobs=4, strategies=('base', 'prefix', 'disperse', 'oracle', 'random')):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [(room, k, str(out), strategies) for room in rooms]
    results = []
    if jobs <= 1:
        results = [worker(task) for task in tasks]
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(worker, tasks))
    rows = [r for result in results for r in result['rows']]
    payload = {'protocol': {'rooms': [min(rooms), max(rooms)], 'ids': list(rooms), 'k': k,
                            'visits': 14, 'severity': 0.0, 'streams': 'prefix', 'offset': 0,
                            'seed_base': 26000, 'random_seeds': list(SEEDS),
                            'oracle_scope': list(ORACLE_CLASSES),
                            'contact_position': 'unrefined front-end path at the run time midpoint',
                            'disperse_origin': 'room centre',
                            'stored_reference': str(STORE).replace('\\', '/')},
               'gate': gate(rows, rooms[0] if rooms else 11500),
               'summary': summarise(rows, rooms), 'rows': rows,
               'rooms': [{k2: v for k2, v in result.items() if k2 != 'rows'} for result in results]}
    (out / 'select026.json').write_text(json.dumps(payload, indent=1, default=float))
    summary = {name: {m: payload['summary'][name][m] for m in
                      ('n_scored', 'errors', 'whole_room_hits', 'mean_f1', 'mean_contacts_available')}
               for name in payload['summary'] if not name.startswith('_')}
    print(json.dumps({'gate': payload['gate'], 'summary': summary,
                      'rows': payload['summary']['_rooms']}, indent=1, default=float))
    return payload


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--rooms', default='11500-11511')
    p.add_argument('--k', type=int, default=6)
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--out', required=True)
    p.add_argument('--strategies', default='base,prefix,disperse,oracle,random')
    p.add_argument('--gate_only', action='store_true')
    a = p.parse_args()
    parts = a.rooms.split('-')
    ids = list(range(int(parts[0]), int(parts[-1]) + 1))
    names = tuple(x.strip() for x in a.strategies.split(',') if x.strip())
    if a.gate_only:
        ids, names = [ids[0]], ('base',)
    payload = run(ids, a.k, a.out, a.jobs, names)
    if a.gate_only and not payload['gate'].get('passed'):
        raise SystemExit('Reproduction gate failed for room %d' % ids[0])
