"""Contact confidence by event duration, with same-count random controls.

IMU-HOI's point: not every predicted contact deserves to be treated as a hard
fact.  Here the only per-contact quality signal the frozen chain exposes without
new sensing is how long the event lasted, so a contact's duration is the
confidence score.  Arms keep the recording, the front end, the refiners, the
decoder and the count fixed; only which contacts are kept changes.

Reference points already on disk for the same record (selectcount026.py):
  all 14 contacts        7/12 rooms, F1 0.8135
  first 6 contacts       4/12 rooms, F1 0.7274
  random 6 (3 seeds)     8/36 rooms, F1 0.6435
"""
import argparse
import concurrent.futures
import json
from pathlib import Path

from . import multi_instance as M, exp_bias014 as E
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .displacement011 import load
from .priorcost014 import decode_arm as prior_decode
from .selectcount026 import build, front_end, contact_order, walk_mask

CONTACT = ('seated', 'lying', 'cabinet')
SEEDS = (1, 2, 3)


def durations(runs, order):
    return {i: float(runs[i][2] - runs[i][1]) for i in order}


def pick_longest(runs, order, k):
    return sorted(sorted(order, key=lambda i: (-durations(runs, order)[i], runs[i][1]))[:k])


def arm(t, path, Rm, runs, priors, keep):
    # Every non-contact run survives: walk and other runs are never subsampled,
    # so the walk mask handed to the decoder comes from the same list as the
    # refiners see.  Dropping them here reproduces nothing (it moved base from
    # 7/12 to 3/12 when this module was first written).
    keep = set(keep)
    sub = [list(r) for i, r in enumerate(runs) if r[0] not in CONTACT or i in keep]
    p, d1 = loops(t, path, Rm, sub, priors)
    p, d2 = wall(t, p, Rm, sub, priors)
    pred = prior_decode(priors, t, p, Rm, sub, walk_mask(t, sub), 'base')
    return pred, {'point_plane_loops': d1, 'cabinet_wall': d2}


def room_rows(room, out):
    state = build(room, out)
    model = load(E.MODEL)
    t, A, path, Rm, runs, _info = front_end(state, model)
    order = contact_order(runs)
    priors = state['priors']
    rows = []
    arms = [('base', None)]
    for k in (6, 9, 11):
        arms.append((f'dur{k}', k))
        for seed in SEEDS:
            arms.append((f'rand{k}-s{seed}', (k, seed)))
    for name, spec in arms:
        import random as _random
        if spec is None:
            keep = order
        elif isinstance(spec, int):
            keep = pick_longest(runs, order, spec)
        else:
            k, seed = spec
            rng = _random.Random(700000 + 10 * room + seed)
            keep = sorted(rng.sample(order, k))
        pred, detail = arm(t, path, Rm, runs, priors, keep)
        score = M.score_instances(pred['boxes'], state['scene']['gt'])
        rows.append({'room': room, 'arm': name, 'k': len(keep), 'status': pred['status'],
                     'all_instances_hit': bool(score['all_instances_hit']), 'f1': float(score['f1']),
                     'mean_contact_duration_s': float(sum(runs[i][2] - runs[i][1] for i in keep) / len(keep)),
                     'labels': {l: sum(1 for i in keep if runs[i][0] == l) for l in CONTACT},
                     'refinement': detail})
    return rows


def worker(task):
    room, out = task
    try:
        return room_rows(room, Path(out))
    except Exception as exc:
        return [{'room': room, 'arm': 'error', 'error': repr(exc)}]


def summarise(rows):
    out = {}
    names = [r['arm'] for r in rows if r.get('arm') != 'error']
    for name in sorted(set(names)):
        sub = [r for r in rows if r.get('arm') == name]
        good = [r for r in sub if 'f1' in r]
        out[name] = {'n': len(sub), 'whole_room_hits': sum(1 for r in good if r['all_instances_hit']),
                     'mean_f1': float(sum(r['f1'] for r in good) / len(good)) if good else None,
                     'mean_k': float(sum(r['k'] for r in good) / len(good)) if good else None,
                     'mean_contact_duration_s': float(sum(r['mean_contact_duration_s'] for r in good) / len(good)) if good else None,
                     'status_counts': {s: sum(1 for r in good if r['status'] == s) for s in sorted({r['status'] for r in good})}}
    return out


def run(rooms, out, jobs=4):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        for chunk in pool.map(worker, [(r, out) for r in rooms]):
            rows.extend(chunk)
            print(json.dumps({'room': chunk[0].get('room'), 'arms': len(chunk), 'error': chunk[0].get('error')}), flush=True)
    summary = summarise(rows)
    payload = {'protocol': {'rooms': [min(rooms), max(rooms)], 'visits': 14, 'severity': 0.0, 'offset': 0,
                            'confidence': 'qualified-contact duration in seconds',
                            'selection': 'keep the k longest contacts; random controls sample the same k',
                            'reference': 'selectcount026.py base 7/12 F1 0.8135, prefix6 4/12 0.7274, random6 8/36 0.6435'},
               'summary': summary, 'rows': rows}
    (out / 'confidence030.json').write_text(json.dumps(payload, indent=1))
    print(json.dumps(summary, indent=1))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rooms', default='11500-11511')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--out', default='output/layout-recon/confidence030')
    a = parser.parse_args()
    lo, hi = a.rooms.split('-')
    run(list(range(int(lo), int(hi) + 1)), a.out, a.jobs)
