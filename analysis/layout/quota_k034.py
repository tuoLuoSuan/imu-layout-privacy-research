"""Does the contact budget keep its shape once the class mix is pinned?

selectbalanced032.py pinned k=6 with a per-class quota and found that a
quota-respecting dispersed subset beats a quota-respecting random one on a
fresh batch (+0.0899 mean F1, 9/1/2 rooms).  That result leaves the budget
itself open: six contacts were a choice, not a measurement.  This module sweeps
the budget under the same frozen quota rule:

  k in {6, 8, 10, 12, 14}
  arms: base (all contacts, reported once per room), bal_disperse (quota +
        farthest point), bal_random (quota + uniform, seeds 500000+10*room+s),
        plain_random (unconstrained uniform, seeds 26000+10*room+s)

Only k and the resulting quota change between cells of the sweep; record,
front end, refiners, decoder, priors and walk mask are shared inside a room.
At k equal to the number of available contacts the quota arm returns the base
set, which is used as an internal check.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path

import numpy as np

from . import exp_bias014 as E
from .displacement011 import load
from .selectcount026 import CONTACT, arm, contact_order, contact_positions, front_end, pick_random, seed_of
from . import selectbalanced032 as SB

K_VALUES = (6, 8, 10, 12, 14)


def room_rows(room, out, k_values=K_VALUES, arms=('bal_disperse', 'bal_random', 'plain_random')):
    state = SB.build(room, out)
    model = load(E.MODEL)
    t, A, path, Rm, runs, info = front_end(state, model)
    order = contact_order(runs)
    pos = contact_positions(t, path, runs, order)
    groups = SB.class_groups(order, runs)
    counts = {c: len(groups[c]) for c in CONTACT}
    gt = {n: np.asarray(b, float) for n, b in state['scene']['gt'].items()}
    centre = (.5 * float(state['scene']['W']), .5 * float(state['scene']['L']))
    rows = []

    def record(name, seed, picked, alloc, k):
        row = {'room': room, 'k': k, 'arm': name, 'seed': seed, 'k_used': len(picked),
               'quota': dict(alloc) if alloc is not None else None,
               'available_by_class': counts,
               'used_by_class': {c: sum(1 for p in picked if runs[order[p]][0] == c) for c in CONTACT},
               'error': None}
        try:
            res = arm(t, path, Rm, runs, order, picked, state['priors'], state['scene'])
            row.update({key: res[key] for key in ('status', 'all_instances_hit', 'f1', 'tp',
                                                  'n_pred', 'n_events')})
        except Exception as exc:  # noqa: BLE001
            row.update({'status': 'error', 'error': repr(exc), 'all_instances_hit': False,
                        'f1': 0.0, 'tp': 0, 'n_pred': 0, 'n_events': 0})
        rows.append(row)

    if 'base' in arms:
        record('base', None, list(range(len(order))), None, min(len(order), max(k_values)))
    for k in k_values:
        alloc = SB.quota(counts, k)
        if 'bal_random' in arms:
            for s in SB.QUOTA_SEEDS:
                record('bal_random', s, SB.pick_quota_random(groups, alloc, SB.QUOTA_SEED_BASE + 10 * room + s), alloc, k)
        if 'bal_disperse' in arms:
            record('bal_disperse', None, SB.pick_disperse_quota(pos, groups, alloc, centre, k), alloc, k)
        if 'plain_random' in arms:
            for s in SB.QUOTA_SEEDS:
                record('plain_random', s, pick_random(len(order), k, seed_of(room, s)), None, k)
    print(json.dumps({'room': room, 'available': len(order),
                      'hits': {k: sum(1 for r in rows if r['k'] == k and r['arm'] == 'bal_disperse'
                                      and r['all_instances_hit']) for k in k_values}}), flush=True)
    return {'room': room, 'rows': rows, 'available_by_class': counts,
            'n_contacts_available': len(order)}


def worker(task):
    room, out, k_values, arms = task
    out = Path(out)
    cached = out / 'rooms' / f'room-{room:05d}.json'
    if cached.exists():
        try:
            old = json.loads(cached.read_text())
            if old.get('rows'):
                return old
        except Exception:  # noqa: BLE001
            pass
    try:
        res = room_rows(room, out, k_values, arms)
    except Exception as exc:  # noqa: BLE001
        return {'room': room, 'rows': [], 'error': repr(exc)}
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(res, indent=1, default=float))
    return res


def summarise(rows):
    out = {}
    for k in sorted({r['k'] for r in rows}):
        block = {}
        for name in ('base', 'bal_disperse', 'bal_random', 'plain_random'):
            group = [r for r in rows if r['k'] == k and r['arm'] == name and not r.get('error')]
            if not group:
                continue
            block[name] = {'n_rows': sum(1 for r in rows if r['k'] == k and r['arm'] == name),
                           'n_rooms': len({r['room'] for r in group}),
                           'whole_room_hits': int(sum(r['all_instances_hit'] for r in group)),
                           'scored': len(group),
                           'mean_f1': float(np.mean([r['f1'] for r in group])),
                           'mean_k_used': float(np.mean([r['k_used'] for r in group]))}
        out[k] = block
    return out


def paired(rows, name, k):
    by_room = {}
    for r in rows:
        if r['k'] != k or r.get('error'):
            continue
        by_room.setdefault(r['room'], {}).setdefault(r['arm'], []).append(r)
    out = []
    for room in sorted(by_room):
        cell = by_room[room]
        if name not in cell or 'bal_random' not in cell:
            continue
        a = cell[name][0]
        ref = cell['bal_random']
        out.append({'room': room, 'a': a['f1'], 'b': float(np.mean([r['f1'] for r in ref])),
                    'diff': float(a['f1'] - np.mean([r['f1'] for r in ref])),
                    'hit_a': bool(a['all_instances_hit']),
                    'hit_b': float(np.mean([1.0 if r['all_instances_hit'] else 0.0 for r in ref]))})
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--rooms', default='11500-11511,11700-11711')
    ap.add_argument('--k', default=','.join(str(k) for k in K_VALUES))
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--arms', default='bal_disperse,bal_random,plain_random')
    ap.add_argument('--out', default='output/layout-recon/quota_k034')
    a = ap.parse_args()
    ids = []
    for chunk in a.rooms.split(','):
        lo, hi = chunk.split('-')
        ids.extend(range(int(lo), int(hi) + 1))
    k_values = tuple(int(x) for x in a.k.split(','))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        arms = tuple(a.arms.split(','))
        for res in pool.map(worker, [(rid, out, k_values, arms) for rid in ids]):
            results.append(res)
    rows = [r for res in results for r in res['rows']]
    summary = summarise(rows)
    pairs = {k: paired(rows, 'bal_disperse', k) for k in k_values}
    (out / 'quota_k034.json').write_text(json.dumps(
        {'rooms': ids, 'k_values': list(k_values), 'summary': summary,
         'paired_disperse_vs_random': pairs, 'missing': [res['room'] for res in results if 'error' in res]},
        indent=1, default=float))
    for k in k_values:
        blk = summary.get(k, {})
        print(k, {name: (blk[name]['whole_room_hits'], round(blk[name]['mean_f1'], 4), blk[name]['scored'])
                  for name in blk})
