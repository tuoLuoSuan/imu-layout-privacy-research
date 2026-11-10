"""Category-quota contact selection: class mix or spatial spread?

selectcount026.py showed that a fixed-size contact subset (k=6) can beat all
fourteen contacts on whole-room hits, but its arms confound two things: which
object classes the kept contacts cover, and where in the room they sit.  This
module holds the class mix fixed instead: every arm draws the same per-class
quota, so the only remaining variable is *which* contacts of each class reach
the refiners and the decoder.

Frozen rules (written before the confirmation batch was run; the module hash is
recorded in every stage file, see protocol.module_sha256):

  k = 6.
  quota(counts, k): largest-remainder apportionment of k over the available
    seated/lying/cabinet contact counts of that room, with at least one slot for
    every class that has at least one contact (e.g. 5/4/5 -> 2/2/2,
    1/0/5 -> 1/0/5).
  base          all contacts (reproduction gate against select026b).
  bal_random    quota-respecting uniform sample per class,
                seeds 500000 + 10*room + (1, 2, 3).
  bal_disperse  quota-respecting greedy farthest point: start from the contact
                farthest from the room centre, then repeatedly take, among the
                classes that still have quota left, the contact farthest from
                every point already chosen.
  bal_oracle    quota-respecting truth-assisted control (upper bound only): each
                class spends its slots on the contacts nearest that class's true
                object centres, one distinct object per slot first.
  plain_random  unconstrained uniform sample of k contacts, selectcount026's
                pick_random with seeds 26000 + 10*room + (1, 2, 3).

Contact selection is fed through selectcount026.arm() unchanged, so the
refiners (contact_loops011 -> wall_refine012) and the decoder
(priorcost014.decode_arm 'base') see exactly the run list selectcount026 would
receive.  Non-contact runs are never dropped.

Gate: dev rooms 11500-11511 with base must reproduce
output/layout-recon/select026b/select026.json (7/12 whole-room hits, mean F1
0.8134920634920634) row by row.

Batches: dev 11500-11511, confirmation 11700-11711 (11400-11411 is already used
by exp_sensor013.py:89, so it cannot serve as a new batch).
"""
import argparse
import concurrent.futures
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from . import multi_instance as M, exp_bias014 as E
from .displacement011 import load
from .selectcount026 import (CONTACT, ORACLE_CLASSES, arm, build, contact_order,
                             contact_positions, front_end, pick_random, seed_of)

K = 6
QUOTA_SEEDS = (1, 2, 3)
QUOTA_SEED_BASE = 500000
TRUTH_CLASS = {'seated': 'chair', 'lying': 'bed', 'cabinet': 'cab'}
ARMS = ('base', 'bal_random', 'bal_disperse', 'bal_oracle', 'plain_random')
DEV_ROOMS = list(range(11500, 11512))
CONFIRM_ROOMS = list(range(11700, 11712))
REFERENCE = Path('output/layout-recon/select026b/select026.json')
RULES = {
    'visits': 14,
    'severity': 0.0,
    'offset': 0,
    'streams': 'prefix',
    'quota': 'largest remainder over available seated/lying/cabinet counts, min 1 per present class',
    'bal_random_seed': '500000 + 10*room + seed, seed in (1, 2, 3)',
    'bal_disperse': 'start farthest from room centre, then farthest from the chosen set among classes with quota left',
    'bal_oracle': 'quota-respecting truth classes chair/bed/cab, nearest contact per object first',
    'plain_random_seed': 'selectcount026 seed_of = 26000 + 10*room + seed, seed in (1, 2, 3)',
    'contact_position': 'unrefined front-end path at the run time midpoint',
    'non_contact_runs': 'never dropped (selectcount026.subset)',
    'arm_chain': 'selectcount026.arm -> contact_loops011 -> wall_refine012 -> priorcost014 base -> score_instances',
}


def module_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def quota(counts, k=K):
    """Largest-remainder split of k over the available contact counts.

    Rounded down first, the leftover units go to the largest fractional shares,
    and any class left at zero is lifted to one at the expense of the largest
    allocation, so a class with contacts is never silently excluded.
    """
    present = [c for c in CONTACT if counts.get(c, 0) > 0]
    alloc = {c: 0 for c in CONTACT}
    if not present:
        return alloc
    if k <= len(present):
        for c in present[:k]:
            alloc[c] = 1
        return alloc
    total = float(sum(counts[c] for c in present))
    share = {c: k * counts[c] / total for c in present}
    for c in present:
        alloc[c] = int(np.floor(share[c]))
    spare = k - sum(alloc[c] for c in present)
    for c in sorted(present, key=lambda c: (-(share[c] - alloc[c]), c))[:spare]:
        alloc[c] += 1
    for c in present:
        while alloc[c] == 0:
            donor = max((x for x in present if x != c), key=lambda x: (alloc[x], x))
            alloc[donor] -= 1
            alloc[c] = 1
    return alloc


def class_groups(order, runs):
    """Contact indices (positions in order) grouped by contact class."""
    groups = {c: [] for c in CONTACT}
    for j, i in enumerate(order):
        groups[runs[i][0]].append(j)
    return groups


def pick_quota_random(groups, alloc, seed):
    rng = np.random.default_rng(seed)
    picked = []
    for c in CONTACT:
        if alloc[c] <= 0 or not groups[c]:
            continue
        idx = np.asarray(groups[c])
        sel = rng.choice(len(idx), size=min(alloc[c], len(idx)), replace=False)
        picked.extend(int(idx[s]) for s in np.sort(sel))
    return sorted(picked)


def pick_disperse_quota(pos, groups, alloc, centre, k=K):
    """Farthest-point greedy that never exceeds a class quota."""
    pos = np.asarray(pos, float).reshape(-1, 2)
    if not len(pos):
        return []
    cls = np.empty(len(pos), dtype=object)
    for c, idx in groups.items():
        for j in idx:
            cls[j] = c
    left = dict(alloc)
    centre_gap = np.linalg.norm(pos - np.asarray(centre, float), axis=1)
    start = [j for j in range(len(pos)) if left[cls[j]] > 0]
    if not start:
        return []
    first = max(start, key=lambda j: centre_gap[j])
    chosen = [first]
    left[cls[first]] -= 1
    want = min(k, len(pos))
    while len(chosen) < want:
        free = [j for j in range(len(pos)) if j not in chosen and left[cls[j]] > 0]
        if not free:
            break
        gap = np.min(np.linalg.norm(pos[:, None, :] - pos[chosen][None, :, :], axis=2), axis=1)
        pick = max(free, key=lambda j: gap[j])
        chosen.append(pick)
        left[cls[pick]] -= 1
    return sorted(int(j) for j in chosen)


def truth_centres(gt):
    out = {c: [] for c in CONTACT}
    for name, box in gt.items():
        cls = M.category(name)
        for c, tc in TRUTH_CLASS.items():
            if cls == tc:
                b = np.asarray(box, float)
                out[c].append((b[:2] + b[2:]) / 2.)
    return {c: np.asarray(v, float).reshape(-1, 2) for c, v in out.items()}


def pick_oracle_quota(pos, groups, alloc, gt, k=K):
    """Quota-respecting truth-assisted control: nearest contact per true object first."""
    pos = np.asarray(pos, float).reshape(-1, 2)
    centres = truth_centres(gt)
    picked = []
    for c in CONTACT:
        q = min(alloc[c], len(groups[c]))
        if q <= 0:
            continue
        idx = list(groups[c])
        tgt = centres[c]
        if not len(tgt):
            picked.extend(idx[:q])
            continue
        d = np.linalg.norm(pos[idx][:, None, :] - tgt[None, :, :], axis=2)
        chosen = []
        for oi in sorted(range(len(tgt)), key=lambda o: (float(d[:, o].min()), o)):
            free = [p for p in np.argsort(d[:, oi]) if int(p) not in chosen]
            if not free:
                continue
            chosen.append(int(free[0]))
            if len(chosen) >= q:
                break
        while len(chosen) < q:
            free = [p for p in range(len(idx)) if p not in chosen]
            chosen.append(min(free, key=lambda p: (float(d[p].min()), p)))
        picked.extend(int(idx[p]) for p in sorted(chosen))
    return sorted(picked)


def room_rows(room, out, k=K):
    state = build(room, out)
    model = load(E.MODEL)
    t, A, path, Rm, runs, info = front_end(state, model)
    order = contact_order(runs)
    pos = contact_positions(t, path, runs, order)
    groups = class_groups(order, runs)
    counts = {c: len(groups[c]) for c in CONTACT}
    alloc = quota(counts, k)
    gt = {n: np.asarray(b, float) for n, b in state['scene']['gt'].items()}
    centre = (.5 * float(state['scene']['W']), .5 * float(state['scene']['L']))
    plans = [('base', None, list(range(len(order))), None)]
    for s in QUOTA_SEEDS:
        seed = QUOTA_SEED_BASE + 10 * room + s
        plans.append(('bal_random', s, pick_quota_random(groups, alloc, seed), alloc))
    plans.append(('bal_disperse', None, pick_disperse_quota(pos, groups, alloc, centre, k), alloc))
    plans.append(('bal_oracle', None, pick_oracle_quota(pos, groups, alloc, gt, k), alloc))
    for s in QUOTA_SEEDS:
        plans.append(('plain_random', s, pick_random(len(order), k, seed_of(room, s)), None))
    rows = []
    for name, seed, picked, q in plans:
        row = {'room': room, 'arm': name, 'seed': seed, 'k': k, 'k_used': len(picked),
               'quota': dict(q) if q is not None else None,
               'available_by_class': counts,
               'used_by_class': {c: sum(1 for p in picked if runs[order[p]][0] == c) for c in CONTACT},
               'contacts_kept': [[runs[order[p]][0], round(float(runs[order[p]][1]), 3),
                                  round(float(runs[order[p]][2]), 3)] for p in sorted(picked)],
               'error': None}
        try:
            res = arm(t, path, Rm, runs, order, picked, state['priors'], state['scene'])
            row.update({key: res[key] for key in ('status', 'all_instances_hit', 'f1', 'tp',
                                                  'n_pred', 'n_events')})
        except Exception as exc:  # noqa: BLE001
            row.update({'status': 'error', 'error': repr(exc), 'all_instances_hit': False,
                        'f1': 0.0, 'tp': 0, 'n_pred': 0, 'n_events': 0})
        rows.append(row)
        print(json.dumps({'room': room, 'arm': name, 'seed': seed, 'used': len(picked),
                          'quota': row['quota'], 'hit': row['all_instances_hit'],
                          'f1': round(row['f1'], 4), 'status': row['status'],
                          'error': row['error']}), flush=True)
    return {'room': room, 'rows': rows, 'available_by_class': counts, 'quota': alloc,
            'n_contacts_available': len(order), 'room_centre': list(centre),
            'contact_positions': np.round(pos, 3).tolist()}


def worker(task):
    room, out, k = task
    try:
        return room_rows(room, Path(out), k)
    except Exception as exc:  # noqa: BLE001
        return {'room': room, 'rows': [], 'error': repr(exc)}


def summarise(rows, arms=ARMS):
    out = {}
    for name in arms:
        group = [r for r in rows if r['arm'] == name and not r.get('error')]
        errs = [r for r in rows if r['arm'] == name and r.get('error')]
        out[name] = {'n_rows': sum(1 for r in rows if r['arm'] == name),
                     'n_rooms': len({r['room'] for r in rows if r['arm'] == name}),
                     'n_scored': len(group), 'errors': len(errs),
                     'whole_room_hits': int(sum(r['all_instances_hit'] for r in group)),
                     'mean_f1': float(np.mean([r['f1'] for r in group])) if group else None,
                     'mean_k_used': float(np.mean([r['k_used'] for r in group])) if group else None,
                     'status_counts': {s: sum(1 for r in group if r['status'] == s)
                                       for s in sorted({r['status'] for r in group})},
                     'mean_quota': (None if not group or group[0]['quota'] is None else
                                    {c: float(np.mean([r['quota'][c] for r in group]))
                                     for c in CONTACT}),
                     'error_examples': [r['error'] for r in errs[:3]]}
    out['_rooms'] = {'n_planned': len({r['room'] for r in rows}),
                     'n_rows': len(rows),
                     'n_error_rows': int(sum(1 for r in rows if r.get('error')))}
    return out


def paired(rows, a='bal_disperse', b='bal_random'):
    """Per-room paired difference F1(a) - mean F1(b over its seeds)."""
    by_room = {}
    for r in rows:
        if r.get('error'):
            continue
        if r['arm'] == a:
            by_room.setdefault(r['room'], {})[a] = r
        if r['arm'] == b:
            by_room.setdefault(r['room'], {}).setdefault(b, []).append(r)
    per = []
    for room in sorted(by_room):
        cell = by_room[room]
        if a not in cell or b not in cell:
            per.append({'room': room, 'complete': False})
            continue
        base = float(np.mean([r['f1'] for r in cell[b]]))
        hit_b = float(np.mean([1.0 if r['all_instances_hit'] else 0.0 for r in cell[b]]))
        diff = float(cell[a]['f1']) - base
        per.append({'room': room, 'complete': True,
                    'f1_a': float(cell[a]['f1']), 'f1_b_mean': base, 'diff': diff,
                    'sign': 1 if diff > 1e-12 else (-1 if diff < -1e-12 else 0),
                    'hit_a': bool(cell[a]['all_instances_hit']), 'hit_b_mean': hit_b,
                    'hit_diff': (1.0 if cell[a]['all_instances_hit'] else 0.0) - hit_b})
    done = [p for p in per if p['complete']]
    return {'a': a, 'b': b, 'n_rooms': len(done), 'incomplete': len(per) - len(done),
            'mean_diff': float(np.mean([p['diff'] for p in done])) if done else None,
            'better': sum(1 for p in done if p['sign'] > 0),
            'worse': sum(1 for p in done if p['sign'] < 0),
            'equal': sum(1 for p in done if p['sign'] == 0),
            'mean_hit_diff': float(np.mean([p['hit_diff'] for p in done])) if done else None,
            'hit_better': sum(1 for p in done if p['hit_diff'] > 1e-12),
            'hit_worse': sum(1 for p in done if p['hit_diff'] < -1e-12),
            'hit_equal': sum(1 for p in done if abs(p['hit_diff']) <= 1e-12),
            'per_room': per}


def gate(dev_rows):
    """The dev base arm must reproduce the stored select026b fourteen-visit row set."""
    ref = json.loads(REFERENCE.read_text(encoding='utf-8'))
    ref_rows = {r['room']: r for r in ref['rows'] if r['strategy'] == 'base'}
    rows = sorted([r for r in dev_rows if r['arm'] == 'base'], key=lambda r: r['room'])
    per, ok = [], len(rows) == len(ref_rows) and all(r['room'] in ref_rows for r in rows)
    for r in rows:
        stored = ref_rows.get(r['room'])
        same = (stored is not None
                and bool(r['all_instances_hit']) == bool(stored['all_instances_hit'])
                and abs(float(r['f1']) - float(stored['f1'])) <= 1e-9)
        per.append({'room': r['room'], 'recomputed_hit': bool(r['all_instances_hit']),
                    'reference_hit': None if stored is None else bool(stored['all_instances_hit']),
                    'recomputed_f1': float(r['f1']),
                    'reference_f1': None if stored is None else float(stored['f1']),
                    'match': bool(same)})
        ok = ok and same
    hits = int(sum(1 for r in rows if r['all_instances_hit']))
    mean = float(np.mean([r['f1'] for r in rows])) if rows else 0.
    ref_hits = int(sum(1 for r in ref_rows.values() if r['all_instances_hit']))
    ref_mean = float(np.mean([r['f1'] for r in ref_rows.values()]))
    return {'passed': bool(ok and hits == ref_hits and abs(mean - ref_mean) <= 1e-9),
            'reference': REFERENCE.as_posix(),
            'criterion': 'per-room all_instances_hit and |f1 difference| <= 1e-9 against select026b',
            'recomputed': {'whole_room_hits': hits, 'mean_f1': mean, 'n_rooms': len(rows)},
            'reference_totals': {'whole_room_hits': ref_hits, 'mean_f1': ref_mean,
                                 'n_rooms': len(ref_rows)},
            'per_room': per}


def protocol(rooms, k=K, stage=None):
    return {**RULES, 'k': k, 'ids': list(rooms), 'rooms': [min(rooms), max(rooms)],
            'stage': stage, 'module_sha256': module_sha256(),
            'reference': REFERENCE.as_posix()}


def same_rules(a, b):
    keys = list(RULES) + ['k', 'module_sha256']
    return all(a.get(key) == b.get(key) for key in keys)


def run(rooms, out, jobs=2, k=K, stage='dev'):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [(room, str(out), k) for room in rooms]
    started = time.time()
    if jobs <= 1:
        results = [worker(task) for task in tasks]
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(worker, tasks))
    rows = [r for result in results for r in result['rows']]
    payload = {'protocol': protocol(rooms, k, stage),
               'elapsed_s': round(time.time() - started, 1),
               'finished_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
               'summary': summarise(rows), 'rows': rows,
               'rooms': [{key: v for key, v in result.items() if key != 'rows'}
                         for result in results]}
    if stage == 'dev':
        payload['gate'] = gate(rows)
    target = out / ('stage-%s.json' % stage)
    target.write_text(json.dumps(payload, indent=1, default=float), encoding='utf-8')
    print(json.dumps({'stage': stage, 'file': target.as_posix(), 'elapsed_s': payload['elapsed_s'],
                      'gate': payload.get('gate', {}).get('passed'),
                      'summary': {name: [payload['summary'][name]['whole_room_hits'],
                                         round(payload['summary'][name]['mean_f1'], 4),
                                         payload['summary'][name]['n_scored']]
                                  for name in ARMS}}, indent=1, default=float))
    if stage == 'dev' and not payload['gate']['passed']:
        raise SystemExit('reproduction gate failed')
    return payload


def combine(out):
    out = Path(out)
    dev = json.loads((out / 'stage-dev.json').read_text(encoding='utf-8'))
    conf = json.loads((out / 'stage-confirm.json').read_text(encoding='utf-8'))
    if not same_rules(dev['protocol'], conf['protocol']):
        raise SystemExit('frozen rules differ between dev and confirmation batches')
    payload = {
        'protocol': {**{key: v for key, v in dev['protocol'].items() if key != 'stage'},
                     'dev_rooms': dev['protocol']['ids'],
                     'confirm_rooms': conf['protocol']['ids'],
                     'confirm_ran_after_dev': conf['finished_at'] >= dev['finished_at'],
                     'module_sha256_dev': dev['protocol']['module_sha256'],
                     'module_sha256_confirm': conf['protocol']['module_sha256'],
                     'dev_finished_at': dev['finished_at'],
                     'confirm_finished_at': conf['finished_at']},
        'gate': dev['gate'],
        'dev': {'summary': dev['summary'], 'paired_disperse_minus_random': paired(dev['rows']),
                'paired_oracle_minus_random': paired(dev['rows'], 'bal_oracle', 'bal_random'),
                'paired_bal_vs_plain': paired(dev['rows'], 'bal_random', 'plain_random'),
                'rows': dev['rows']},
        'confirm': {'summary': conf['summary'], 'paired_disperse_minus_random': paired(conf['rows']),
                    'paired_oracle_minus_random': paired(conf['rows'], 'bal_oracle', 'bal_random'),
                    'paired_bal_vs_plain': paired(conf['rows'], 'bal_random', 'plain_random'),
                    'rows': conf['rows']},
    }
    crit = payload['confirm']['paired_disperse_minus_random']
    payload['verdict'] = {
        'primary_endpoint': 'per-room paired F1 difference bal_disperse - mean(bal_random 3 seeds)',
        'confirm_mean_diff': crit['mean_diff'],
        'confirm_better_worse_equal': [crit['better'], crit['worse'], crit['equal']],
        'confirm_secondary_hit_diff': payload['confirm']['summary']['bal_disperse']['whole_room_hits']
                                      - payload['confirm']['summary']['bal_random']['whole_room_hits'] / 3.0,
        'positive': bool(crit['mean_diff'] is not None and crit['mean_diff'] > 0
                         and crit['better'] > crit['worse']),
    }
    target = out / 'select032.json'
    target.write_text(json.dumps(payload, indent=1, default=float), encoding='utf-8')
    print(json.dumps({'file': target.as_posix(), 'gate': payload['gate']['passed'],
                      'dev': {name: [payload['dev']['summary'][name]['whole_room_hits'],
                                     round(payload['dev']['summary'][name]['mean_f1'], 4)]
                              for name in ARMS},
                      'confirm': {name: [payload['confirm']['summary'][name]['whole_room_hits'],
                                         round(payload['confirm']['summary'][name]['mean_f1'], 4)]
                                  for name in ARMS},
                      'confirm_diff': {key: payload['verdict'][key] for key in
                                       ('confirm_mean_diff', 'confirm_better_worse_equal',
                                        'confirm_secondary_hit_diff', 'positive')}},
                     indent=1, default=float))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rooms', default='11500-11511')
    parser.add_argument('--k', type=int, default=K)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--out', default='output/layout-recon/select032')
    parser.add_argument('--stage', default='dev')
    parser.add_argument('--combine', action='store_true')
    args = parser.parse_args()
    if args.combine:
        combine(args.out)
    else:
        lo, hi = args.rooms.split('-')
        run(list(range(int(lo), int(hi) + 1)), args.out, args.jobs, args.k, args.stage)
