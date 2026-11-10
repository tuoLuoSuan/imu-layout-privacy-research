"""Fixed twenty-visit record, fourteen of twenty contacts: does the choice matter?

026 held one fourteen-visit cell fixed and cut the qualified contacts from 14 to
6, so the stream stayed put and only the count changed.  A count cannot answer
whether the contacts a decoder sees are interchangeable, so this module fixes the
count at 14 and asks the other half of the question.  Every arm reads the same
twenty-visit, severity-0 record (selectcount026.build with visits=20, same seeds,
same streams, offset 0) and every competing arm keeps exactly 14 of its 20
qualified contact runs; every non-contact run, walk runs included, survives in
all arms.  base20 is the all-contact reference on that same record.

The one confound this design does not remove is duration: a twenty-visit record
is longer than the stored fourteen-visit cell, so base20 is comparable to the
14-of-20 arms (same stream) but not to the stored matrix row as if only the
contact count differed.

Selection rules are selectcount026's, unchanged and fixed before the batch:
  base20      every qualified contact (20),
  prefix14    the first 14 contacts in time order,
  disperse14  greedy farthest point over the unrefined contact positions,
              starting from the contact farthest from the room centre,
  random14    14 contacts uniformly without replacement, three seeds from
              selectcount026.seed_of (26000 + 10*room + seed index),
  oracle14    truth-assisted two-stage rule (one nearest contact per contact
              object, spare slots filled by farthest-point), exactly 14.
k, seeds and the 1e-9 gate tolerance are fixed here and are not tuned per room.
"""
import argparse
import concurrent.futures
import json
from collections import Counter
from pathlib import Path

import numpy as np

from . import selectcount026 as C
from . import exp_bias014 as E

VISITS = 20
K = 14
SEEDS = C.SEEDS
ARMS = ('base20', 'prefix14', 'disperse14', 'random14', 'oracle14')


def plans(room, order, pos, centre, gt, k):
    """One plan per arm at the fixed k; base20 keeps every available contact."""
    n = len(order)
    out = [('base20', None, list(range(n))),
           ('prefix14', None, C.pick_prefix(n, k)),
           ('disperse14', None, C.pick_disperse(pos, centre, k))]
    for s in SEEDS:
        out.append(('random14', C.seed_of(room, s), C.pick_random(n, k, C.seed_of(room, s))))
    out.append(('oracle14', None, C.pick_oracle(pos, gt, k)))
    return out


def room_rows(room, out, visits=VISITS, k=K):
    state = C.build(room, Path(out), visits=visits)
    model = C.load(E.MODEL)
    t, A, path, Rm, runs, info = C.front_end(state, model)
    order = C.contact_order(runs)
    pos = C.contact_positions(t, path, runs, order)
    centre = (.5 * float(state['scene']['W']), .5 * float(state['scene']['L']))
    gt = {n: np.asarray(b) for n, b in state['scene']['gt'].items()}
    duration = float(t[-1])
    rows = []
    for name, seed, picked in plans(room, order, pos, centre, gt, k):
        row = {'room': room, 'arm': name, 'seed': seed, 'k': k, 'visits': visits,
               'n_contacts_available': len(order), 'n_contacts_used': len(picked),
               'contacts_kept': [[runs[order[p]][0], round(float(runs[order[p]][1]), 3),
                                  round(float(runs[order[p]][2]), 3)] for p in sorted(picked)],
               'predicted_positions': [np.round(pos[p], 3).tolist() for p in sorted(picked)],
               'stream_duration_s': duration}
        try:
            row.update(C.arm(t, path, Rm, runs, order, picked, state['priors'], state['scene']))
            row['error'] = None
        except Exception as e:  # noqa: BLE001
            row.update({'status': 'error', 'error': repr(e), 'all_instances_hit': False, 'f1': 0.})
        rows.append(row)
        print(json.dumps({'room': room, 'arm': name, 'seed': seed,
                          'contacts': [len(picked), len(order)],
                          'hit': row['all_instances_hit'], 'f1': round(float(row['f1']), 4),
                          'status': row['status'], 'error': row['error']}), flush=True)
    return {'room': room, 'rows': rows, 'n_contacts_available': len(order),
            'contact_class_counts': dict(Counter(runs[i][0] for i in order)),
            'n_contact_objects': len([n for n in state['scene']['gt']
                                      if C.M.category(n) in C.ORACLE_CLASSES]),
            'contact_positions': np.round(pos, 3).tolist(), 'room_centre': list(centre),
            'stream_duration_s': duration,
            'gyro_tracker014': {k2: v for k2, v in info.items() if k2 != 'stationary_mask'}}


def failed_rows(room, visits, k, error):
    """A room that never reaches the arms still contributes its planned rows."""
    rows = []
    for name, seed, _ in plans(room, [], np.empty((0, 2)), (0., 0.), {}, k):
        rows.append({'room': room, 'arm': name, 'seed': seed, 'k': k, 'visits': visits,
                     'n_contacts_available': None, 'n_contacts_used': None,
                     'contacts_kept': [], 'predicted_positions': [], 'stream_duration_s': None,
                     'status': 'error', 'error': error, 'all_instances_hit': False, 'f1': 0.})
    return rows


def worker(task):
    room, out, visits, k = task
    try:
        return room_rows(room, Path(out), visits, k)
    except Exception as e:  # noqa: BLE001
        error = repr(e)
        return {'room': room, 'error': error, 'rows': failed_rows(room, visits, k, error)}


def gate_room(out, room=11500):
    """Rebuild the stored fourteen-visit cell once and compare its base arm."""
    state = C.build(room, Path(out), visits=14, severity=0.0, offset=0)
    model = C.load(E.MODEL)
    t, A, path, Rm, runs, info = C.front_end(state, model)
    order = C.contact_order(runs)
    row = C.arm(t, path, Rm, runs, order, list(range(len(order))),
                state['priors'], state['scene'])
    reference = C.stored(room)
    if reference is None:
        return {'room': room, 'visits': 14, 'checked': False,
                'reason': 'stored row missing', 'stored': None, 'recomputed': None}
    passed = (bool(row['all_instances_hit']) == reference['all_instances_hit']
              and abs(float(row['f1']) - reference['f1']) <= 1e-9)
    return {'room': room, 'visits': 14, 'checked': True, 'passed': bool(passed),
            'stored': reference,
            'recomputed': {'all_instances_hit': bool(row['all_instances_hit']),
                           'f1': float(row['f1']), 'status': row['status'],
                           'n_contacts_available': len(order)},
            'criterion': 'same all_instances_hit and |f1 difference| <= 1e-9'}


def summarise(rows, rooms):
    """Every planned row stays in the denominator, error and conflict rows included."""
    out = {}
    for name in ARMS:
        group = [r for r in rows if r['arm'] == name]
        n = len(group)
        known = [r for r in group if r.get('n_contacts_used') is not None]
        out[name] = {
            'n': n, 'n_rooms': len({r['room'] for r in group}),
            'n_rows_with_contact_count': len(known),
            'whole_room_hits': int(sum(bool(r['all_instances_hit']) for r in group)),
            'whole_room_rate': float(np.mean([bool(r['all_instances_hit']) for r in group])) if n else 0.,
            'mean_f1': float(np.mean([float(r['f1']) for r in group])) if n else 0.,
            'mean_contacts_used': float(np.mean([r['n_contacts_used'] for r in known])) if known else 0.,
            'status_counts': dict(Counter(str(r.get('status')) for r in group)),
            'n_error_rows': int(sum(1 for r in group if r.get('error'))),
            'denominator': 'all planned rows, proposal_conflict and error rows included'}
    out['_rooms'] = {'n_planned': len(rooms), 'n_reported': len({r['room'] for r in rows}),
                     'n_rows': len(rows),
                     'n_error_rows': int(sum(1 for r in rows if r.get('error')))}
    return out


def protocol(rooms, visits, k):
    return {'visits': visits, 'k': k, 'severity': 0.0, 'offset': 0, 'streams': 'prefix',
            'rooms': [min(rooms), max(rooms)], 'ids': list(rooms),
            'generation': 'selectcount026.build(room, out, visits=%d, severity=0.0, offset=0)'
                          % visits,
            'arms': {'base20': 'every qualified contact',
                     'prefix14': 'first 14 contacts in time order',
                     'disperse14': 'greedy farthest point from the room centre',
                     'random14': 'uniform without replacement, three fixed seeds',
                     'oracle14': 'truth-assisted object coverage, farthest-point fill to 14'},
            'seed_base': 26000, 'random_seeds': list(SEEDS),
            'random_seed_rule': '26000 + 10*room + seed index',
            'oracle_scope': list(C.ORACLE_CLASSES),
            'contact_position': 'unrefined front-end path at the run time midpoint',
            'disperse_origin': 'room centre',
            'denominator': 'all planned rows, proposal_conflict and error rows included',
            'gate': 'rebuild room 11500 at visits=14 and compare its base arm with the stored '
                    'matrix023/off0/v14-s0.0 row',
            'gate_tolerance': 1e-9,
            'fixed_before_batch': 'k=14, seeds 1/2/3 and the 1e-9 gate tolerance are fixed here; '
                                  'no per-room tuning',
            'duration_confound': 'the twenty-visit record is longer than the stored fourteen-visit '
                                 'cell; base20 is comparable to the 14-of-20 arms on the same '
                                 'stream, not to the stored row as a pure count change',
            'stored_reference': str(C.STORE).replace('\\', '/')}


def run(rooms, out, visits=VISITS, k=K, jobs=6, gate_only=False):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    gate = gate_room(out)
    payload = {'protocol': protocol(rooms, visits, k), 'gate': gate, 'summary': {},
               'rows': [], 'rooms': [], 'batch_run': False}
    if gate_only or not gate.get('passed'):
        (out / 'select027.json').write_text(json.dumps(payload, indent=1, default=float))
        print(json.dumps({'gate': gate}, indent=1, default=float))
        if gate_only:
            return payload
        raise SystemExit('Reproduction gate failed for room %d' % gate['room'])
    tasks = [(room, str(out), visits, k) for room in rooms]
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(worker, tasks))
    rows = [r for result in results for r in result['rows']]
    payload = {'protocol': payload['protocol'], 'gate': gate,
               'summary': summarise(rows, rooms), 'rows': rows,
               'rooms': [{k2: v for k2, v in result.items() if k2 != 'rows'}
                         for result in results],
               'batch_run': True}
    (out / 'select027.json').write_text(json.dumps(payload, indent=1, default=float))
    print(json.dumps({'gate': payload['gate'],
                      'summary': {name: {m: payload['summary'][name][m] for m in
                                         ('n', 'whole_room_hits', 'mean_f1', 'mean_contacts_used',
                                          'status_counts')}
                                  for name in payload['summary'] if not name.startswith('_')},
                      'rows': payload['summary']['_rooms']}, indent=1, default=float))
    return payload


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--rooms', default='11500-11511')
    p.add_argument('--visits', type=int, default=VISITS)
    p.add_argument('--k', type=int, default=K)
    p.add_argument('--jobs', type=int, default=6)
    p.add_argument('--out', required=True)
    p.add_argument('--gate_only', action='store_true')
    a = p.parse_args()
    lo, hi = a.rooms.split('-')
    ids = list(range(int(lo), int(hi) + 1))
    run(ids, a.out, a.visits, a.k, a.jobs, a.gate_only)
