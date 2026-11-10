"""Instance-identity ablation on the 14-visit severity-0 record.

Collective Landmark Mapper's warning: two objects of the same category are not
the same instance.  This module keeps the recording, the front end and the
decoder fixed and only edits the declared inventory -- the analyst is told there
is one cabinet instead of two (and, as a second arm, one chair instead of two).
The question is not "does dropping an item cost a box" (it must), but whether
the surviving boxes of the other categories are dragged away with it.

Arms: base (declared inventory as generated), drop_cab, drop_chair.
Run: python -m analysis.layout.inventory029 --rooms 11500-11511 --jobs 4
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
from .selectcount026 import build, front_end, walk_mask

CATEGORY_OF_DROP = {'drop_cab': 'cab', 'drop_chair': 'chair'}


def decode_with(t, path, Rm, runs, priors):
    p, point_detail = loops(t, path, Rm, runs, priors)
    p, wall_detail = wall(t, p, Rm, runs, priors)
    pred = prior_decode(priors, t, p, Rm, runs, walk_mask(t, runs), 'base')
    return pred, {'point_plane_loops': point_detail, 'cabinet_wall': wall_detail}


def drop_one(inventory, category):
    keep, dropped = [], None
    for entry in inventory:
        if category and entry['category'] == category:
            dropped = entry
            category = None
            continue
        keep.append(entry)
    return keep, dropped


def room_rows(room, out):
    state = build(room, out)
    model = load(E.MODEL)
    t, A, path, Rm, runs, _info = front_end(state, model)
    base_priors = state['priors']
    rows = []
    for arm in ('base', 'drop_cab', 'drop_chair'):
        priors = dict(base_priors)
        dropped = None
        if arm != 'base':
            priors['inventory'], dropped = drop_one(base_priors['inventory'], CATEGORY_OF_DROP[arm])
        pred, detail = decode_with(t, path, Rm, runs, priors)
        score = M.score_instances(pred['boxes'], state['scene']['gt'])
        per_class = {k: int(v['tp']) for k, v in score.get('per_class', {}).items()} if isinstance(score.get('per_class'), dict) else {}
        rows.append({'room': room, 'arm': arm, 'status': pred['status'],
                     'all_instances_hit': bool(score['all_instances_hit']), 'f1': float(score['f1']),
                     'tp': int(score['tp']), 'n_pred': len(pred['boxes']), 'n_events': len(pred['events']),
                     'per_class_tp': per_class,
                     'dropped': None if dropped is None else {'id': dropped['id'], 'category': dropped['category']},
                     'refinement': detail})
    return rows


def worker(task):
    room, out = task
    try:
        return room_rows(room, Path(out))
    except Exception as exc:  # keep the room in the denominator
        return [{'room': room, 'arm': 'error', 'error': repr(exc)}]


def summarise(rows):
    out = {}
    for arm in ('base', 'drop_cab', 'drop_chair'):
        sub = [r for r in rows if r.get('arm') == arm]
        good = [r for r in sub if 'f1' in r]
        classes = sorted({k for r in good for k in r['per_class_tp']})
        out[arm] = {'n': len(sub), 'errors': len(sub) - len(good),
                    'whole_room_hits': sum(1 for r in good if r['all_instances_hit']),
                    'mean_f1': float(sum(r['f1'] for r in good) / len(good)) if good else None,
                    'mean_tp': float(sum(r['tp'] for r in good) / len(good)) if good else None,
                    'per_class_tp_sum': {c: int(sum(r['per_class_tp'].get(c, 0) for r in good)) for c in classes}}
    return out


def run(rooms, out, jobs=4):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [(room, out) for room in rooms]
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        for chunk in pool.map(worker, tasks):
            rows.extend(chunk)
            print(json.dumps({'last': chunk[-1].get('room'), 'arm': chunk[-1].get('arm'),
                              'f1': chunk[-1].get('f1')}), flush=True)
    summary = summarise(rows)
    payload = {'protocol': {'rooms': [min(rooms), max(rooms)], 'visits': 14, 'severity': 0.0,
                            'offset': 0, 'arms': ['base', 'drop_cab', 'drop_chair'],
                            'drop_rule': 'remove the first inventory entry of that category, keep the rest',
                            'source': 'selectcount026.build/front_end, priorcost014.decode_arm base'},
               'summary': summary, 'rows': rows}
    (out / 'inventory029.json').write_text(json.dumps(payload, indent=1), encoding='utf-8')
    print(json.dumps(summary, indent=1))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rooms', default='11500-11511')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--out', default='output/layout-recon/inventory029')
    a = parser.parse_args()
    lo, hi = a.rooms.split('-')
    run(list(range(int(lo), int(hi) + 1)), a.out, a.jobs)
