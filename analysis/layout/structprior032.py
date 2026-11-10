"""Structural-prior layout sampler (032).

Question: how much of a room layout is recoverable from the *declarations*
alone -- outer shell, start point and inventory -- with no inertial evidence?

This module samples N layouts from a hand-written structural prior (wall
hugging, bed long edge on a wall, chair tucked at a desk, start point left
free) and scores them against truth.  Two numbers are reported and never
mixed:

* prior-alone  -- the distribution of F1 over the N samples.  This is what an
  estimator that only knows the declarations gets when it has no evidence to
  choose between samples.
* truth-aided upper bound -- best of the N samples, selected with the ground
  truth.  It is a ceiling of this sampling family, never a result.

Truth is read only in _evaluate; _plan strips it, so the sampler cannot see it.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
try:
    from . import exp_bias014 as E, multi_instance as M
except ImportError:  # direct script execution
    from analysis.layout import exp_bias014 as E, multi_instance as M

SEED_BASE = 910000
CLEARANCE = 0.02          # minimum gap between two boxes
WALL_GAP_MAX = 0.05       # wall item: gap between box edge and wall
START_CLEARANCE = 0.05    # start is a reachable free position, keep it free
CHAIR_GAP = (0.02, 0.15)  # chair sits at a desk face
ITEM_TRIES = 400          # pose draws per item inside one layout attempt
ATTEMPT_CAP = 20000       # layout attempts per room
TOLERANCE = 0.5           # instance match tolerance (M.score_instances default)

WALL_CATEGORIES = {'bed', 'desk', 'cab', 'store'}
CHAIR_CATEGORIES = {'chair'}

KNOWN_BATCHES = (('batch1', 11500, 11511), ('batch2', 11200, 11231))


# ----------------------------------------------------------------- primitives
def _clearance(a, b):
    """Max axis separation of two boxes; negative means overlap by that much."""
    return max(max(a[0] - b[2], b[0] - a[2]), max(a[1] - b[3], b[1] - a[3]))


def _start_distance(box, S):
    dx = max(box[0] - S[0], 0.0, S[0] - box[2])
    dy = max(box[1] - S[1], 0.0, S[1] - box[3])
    return math.hypot(dx, dy)


def _free(box, boxes, W, L, S):
    if box[0] < -1e-9 or box[1] < -1e-9 or box[2] > W + 1e-9 or box[3] > L + 1e-9:
        return False
    if _start_distance(box, S) < START_CLEARANCE - 1e-12:
        return False
    for other in boxes.values():
        if _clearance(box, other) < CLEARANCE - 1e-12:
            return False
    return True


def _wall_pose(rng, W, L, w, h, long_edge_on_wall):
    """Draw a pose whose touching edge lies within WALL_GAP_MAX of a wall."""
    side = rng.randrange(4)
    if long_edge_on_wall:
        long_, short = (w, h) if w >= h else (h, w)
        if side < 2:
            bw, bh = long_, short
        else:
            bw, bh = short, long_
    elif rng.random() < 0.5:
        bw, bh = w, h
    else:
        bw, bh = h, w
    if (bw > W + 1e-9) if side < 2 else (bh > L + 1e-9):
        return None
    gap = rng.uniform(0.0, WALL_GAP_MAX)
    if side == 0:
        x0 = rng.uniform(0.0, W - bw) if W > bw else 0.0
        return (x0, gap, x0 + bw, gap + bh), side
    if side == 1:
        x0 = rng.uniform(0.0, W - bw) if W > bw else 0.0
        return (x0, L - gap - bh, x0 + bw, L - gap), side
    if side == 2:
        y0 = rng.uniform(0.0, L - bh) if L > bh else 0.0
        return (gap, y0, gap + bw, y0 + bh), side
    y0 = rng.uniform(0.0, L - bh) if L > bh else 0.0
    return (W - gap - bw, y0, W - gap, y0 + bh), side


def _flush_box(W, L, bw, bh, side, off):
    if side == 0:
        return (off, 0.0, off + bw, bh)
    if side == 1:
        return (off, L - bh, off + bw, L)
    if side == 2:
        return (0.0, off, bw, off + bh)
    return (W - bw, off, W, off + bh)


def _chair_pose(rng, W, L, w, h, desks, S):
    """Tuck the chair at a face of the desk nearest the start point."""
    if not desks:
        return None
    if rng.random() < 0.5:
        cw, ch = w, h
    else:
        cw, ch = h, w
    key, dbox = min(desks, key=lambda d: (math.hypot((d[1][0] + d[1][2]) / 2 - S[0],
                                                     (d[1][1] + d[1][3]) / 2 - S[1]), d[0]))
    dx0, dy0, dx1, dy1 = dbox
    side = rng.randrange(4)
    gap = rng.uniform(*CHAIR_GAP)
    if side == 0:
        if dx1 - dx0 < cw:
            return None
        x0 = rng.uniform(dx0, dx1 - cw)
        y1 = dy0 - gap
        return (x0, y1 - ch, x0 + cw, y1), key
    if side == 1:
        if dx1 - dx0 < cw:
            return None
        x0 = rng.uniform(dx0, dx1 - cw)
        y0 = dy1 + gap
        return (x0, y0, x0 + cw, y0 + ch), key
    if side == 2:
        if dy1 - dy0 < ch:
            return None
        y0 = rng.uniform(dy0, dy1 - ch)
        x1 = dx0 - gap
        return (x1 - cw, y0, x1, y0 + ch), key
    if dy1 - dy0 < ch:
        return None
    y0 = rng.uniform(dy0, dy1 - ch)
    x0 = dx1 + gap
    return (x0, y0, x0 + cw, y0 + ch), key


# -------------------------------------------------------------------- sampler
def sample_layout(rng, plan):
    """One layout attempt from the structural prior; None when it fails."""
    W, L = plan['W'], plan['L']
    S = np.asarray(plan['S'], float)
    boxes, sides, attached = {}, {}, {}
    wall_items = [it for it in plan['inventory'] if it['category'] not in CHAIR_CATEGORIES]
    chairs = [it for it in plan['inventory'] if it['category'] in CHAIR_CATEGORIES]
    rng.shuffle(wall_items)
    for it in wall_items:
        w, h = float(it['dimensions'][0]), float(it['dimensions'][1])
        long_edge = it['category'] == 'bed'
        placed = None
        for _ in range(ITEM_TRIES):
            pose = _wall_pose(rng, W, L, w, h, long_edge)
            if pose is None:
                continue
            if _free(pose[0], boxes, W, L, S):
                placed = pose
                break
        if placed is None:
            return None
        boxes[it['id']] = placed[0]
        sides[it['id']] = placed[1]
    desks = [(it['id'], boxes[it['id']]) for it in plan['inventory']
             if it['category'] == 'desk' and it['id'] in boxes]
    for it in chairs:
        w, h = float(it['dimensions'][0]), float(it['dimensions'][1])
        placed = None
        for _ in range(ITEM_TRIES):
            if desks:
                pose = _chair_pose(rng, W, L, w, h, desks, S)
                if pose is None:
                    continue
                box, desk_id = pose
                if _free(box, boxes, W, L, S):
                    placed = (box, desk_id)
                    break
            else:
                pose = _wall_pose(rng, W, L, w, h, False)
                if pose is None:
                    continue
                if _free(pose[0], boxes, W, L, S):
                    placed = (pose[0], 'wall')
                    break
        if placed is None:
            return None
        boxes[it['id']] = placed[0]
        sides[it['id']] = 'chair'
        attached[it['id']] = placed[1]
    return {'boxes': boxes, 'sides': sides, 'attached': attached}


def validate_layout(layout, plan):
    """Assert every sampled layout: inside, pairwise clearance, wall prior."""
    W, L = plan['W'], plan['L']
    S = np.asarray(plan['S'], float)
    dims = {it['id']: [float(it['dimensions'][0]), float(it['dimensions'][1])]
            for it in plan['inventory']}
    boxes, sides, attached = layout['boxes'], layout['sides'], layout['attached']
    assert set(boxes) == set(dims), 'layout is missing inventory items'
    for key, box in boxes.items():
        x0, y0, x1, y1 = box
        assert x0 >= -1e-9 and y0 >= -1e-9 and x1 <= W + 1e-9 and y1 <= L + 1e-9, ('outside room', key)
        assert x1 - x0 > 0 and y1 - y0 > 0, ('degenerate box', key)
        cat = M.category(key)
        if cat not in CHAIR_CATEGORIES:
            side = sides[key]
            gap = (y0 if side == 0 else L - y1 if side == 1 else x0 if side == 2 else W - x1)
            assert -1e-9 <= gap <= WALL_GAP_MAX + 1e-9, ('wall gap', key, gap)
            if cat == 'bed':
                along = (x1 - x0) if side < 2 else (y1 - y0)
                assert abs(along - max(dims[key])) <= 1e-9, ('bed long edge not on wall', key)
        assert _start_distance(box, S) >= START_CLEARANCE - 1e-9, ('start point blocked', key)
    keys = sorted(boxes)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            assert _clearance(boxes[keys[i]], boxes[keys[j]]) >= CLEARANCE - 1e-9, \
                ('overlap', keys[i], keys[j])
    for key, desk_id in attached.items():
        if desk_id == 'wall':
            continue
        assert desk_id in boxes and _clearance(boxes[key], boxes[desk_id]) <= CHAIR_GAP[1] + 1e-9, \
            ('chair not at its desk', key)
    return True


def deterministic_layout(plan):
    """Inventory-order flush-to-wall layout: a deterministic member of the family."""
    W, L = plan['W'], plan['L']
    S = np.asarray(plan['S'], float)
    boxes, sides = {}, {}
    for index, it in enumerate(plan['inventory']):
        w, h = float(it['dimensions'][0]), float(it['dimensions'][1])
        long_, short = (w, h) if w >= h else (h, w)
        done = False
        for step in range(4):
            side = (index + step) % 4
            if it['category'] == 'bed':
                orientations = [(long_, short)] if side < 2 else [(short, long_)]
            else:
                orientations = [(w, h), (h, w)]
            for bw, bh in orientations:
                span = W - bw if side < 2 else L - bh
                if span < -1e-9:
                    continue
                offsets = [round(float(v), 6) for v in np.arange(0.0, span + 1e-9, 0.05)]
                if abs(offsets[-1] - span) > 1e-9:
                    offsets.append(round(float(span), 6))
                for off in offsets:
                    box = _flush_box(W, L, bw, bh, side, off)
                    if _free(box, boxes, W, L, S):
                        boxes[it['id']] = box
                        sides[it['id']] = side
                        done = True
                        break
                if done:
                    break
            if done:
                break
        if not done:
            return None
    return {'boxes': boxes, 'sides': sides, 'attached': {}}


# ----------------------------------------------------------------- evaluation
def _plan(scene):
    """Sampling input: shell, start, inventory.  Truth is deliberately dropped."""
    plan = {'W': float(scene['W']), 'L': float(scene['L']),
            'S': [float(v) for v in scene['S']],
            'inventory': [{'id': it['id'], 'category': it['category'],
                           'dimensions': [float(it['dimensions'][0]), float(it['dimensions'][1])]}
                          for it in scene['inventory']]}
    assert 'gt' not in plan
    return plan


def _stats(arr):
    return {'f1_mean': float(arr.mean()), 'f1_median': float(np.median(arr)),
            'f1_p05': float(np.percentile(arr, 5)), 'f1_p95': float(np.percentile(arr, 95)),
            'f1_min': float(arr.min()), 'f1_max': float(arr.max()),
            'whole_room_rate': float((arr >= 1.0 - 1e-12).mean())}


def _score(boxes, gt):
    pred = {k: np.asarray(v, float) for k, v in boxes.items()}
    return M.score_instances(pred, gt)


def _evaluate(payload):
    room = payload['room']
    native = Path(payload['native'])
    samples = payload['samples']
    attempt_cap = payload['attempts']
    scene = M.load_native(native)
    plan = _plan(scene)
    gt = scene['gt']
    rng = random.Random(SEED_BASE + room)
    f1s, attempts, failed = [], 0, 0
    class_tp, class_truth, tp_sum = {}, {}, 0
    while len(f1s) < samples and attempts < attempt_cap:
        attempts += 1
        layout = sample_layout(rng, plan)
        if layout is None:
            failed += 1
            continue
        validate_layout(layout, plan)
        score = _score(layout['boxes'], gt)
        f1s.append(float(score['f1']))
        tp_sum += int(score['tp'])
        for cls, rec in score['per_class'].items():
            class_tp[cls] = class_tp.get(cls, 0.0) + rec['tp']
            class_truth[cls] = rec['n_truth']
    arr = np.round(np.asarray(f1s, float), 6)
    best = int(np.argmax(arr)) if len(arr) else -1
    det = deterministic_layout(plan)
    if det is None:
        det_rec = {'status': 'incomplete', 'f1': 0.0, 'all_instances_hit': False,
                   'placed': 0, 'declared': len(plan['inventory'])}
    else:
        validate_layout(det, plan)
        dsc = _score(det['boxes'], gt)
        det_rec = {'status': 'placed', 'f1': float(dsc['f1']),
                   'all_instances_hit': bool(dsc['all_instances_hit']),
                   'tp': int(dsc['tp']), 'placed': len(det['boxes']),
                   'declared': len(plan['inventory'])}
    return {
        'room': room,
        'n_samples': int(len(arr)),
        'attempts': int(attempts),
        'failed_attempts': int(failed),
        'failure_rate': float(failed / attempts) if attempts else 0.0,
        'prior_alone': dict(_stats(arr), tp_sum=int(tp_sum),
                            tp_mean=float(tp_sum / len(arr))) if len(arr) else {},
        'truth_aided_upper_bound': {
            'index': best, 'f1': float(arr[best]) if len(arr) else 0.0,
            'all_instances_hit': bool(len(arr) and arr[best] >= 1.0 - 1e-12)},
        'per_class_tp_rate': {c: float(class_tp[c] / (len(arr) * class_truth[c]))
                              for c in sorted(class_tp) if class_truth.get(c) and len(arr)},
        'deterministic': det_rec,
        'sample_f1': [float(v) for v in arr],
    }


def _aggregate(records):
    arr = np.concatenate([np.asarray(r['sample_f1'], float) for r in records]) if records else np.zeros(0)
    per_room_mean = np.asarray([r['prior_alone']['f1_mean'] for r in records], float) if records else np.zeros(0)
    per_room_rate = np.asarray([r['prior_alone']['whole_room_rate'] for r in records], float) if records else np.zeros(0)
    best = np.asarray([r['truth_aided_upper_bound']['f1'] for r in records], float) if records else np.zeros(0)
    det = [r['deterministic'] for r in records]
    attempts = int(sum(r['attempts'] for r in records))
    failed = int(sum(r['failed_attempts'] for r in records))
    tp_sum = int(sum(r['prior_alone'].get('tp_sum', 0) for r in records))
    return {
        'n_rooms': len(records),
        'n_samples': int(len(arr)),
        'prior_alone': {
            'sample_f1_mean': float(arr.mean()) if len(arr) else 0.0,
            'sample_f1_median': float(np.median(arr)) if len(arr) else 0.0,
            'sample_f1_p05': float(np.percentile(arr, 5)) if len(arr) else 0.0,
            'sample_f1_p95': float(np.percentile(arr, 95)) if len(arr) else 0.0,
            'whole_room_rate': float((arr >= 1.0 - 1e-12).mean()) if len(arr) else 0.0,
            'per_room_f1_mean_mean': float(per_room_mean.mean()) if len(per_room_mean) else 0.0,
            'per_room_f1_mean_min': float(per_room_mean.min()) if len(per_room_mean) else 0.0,
            'per_room_f1_mean_max': float(per_room_mean.max()) if len(per_room_mean) else 0.0,
            'per_room_whole_room_rate_mean': float(per_room_rate.mean()) if len(per_room_rate) else 0.0,
            'tp_mean': float(tp_sum / len(arr)) if len(arr) else 0.0,
        },
        'validation': {
            'layouts_validated': int(len(arr)),
            'violations': 0,
            'how': 'validate_layout() asserts room bounds, pairwise clearance and the wall/bed/chair prior before every score',
        },
        'truth_aided_upper_bound': {
            'label': 'truth-aided, ceiling of this sampling family only',
            'mean_best_f1': float(best.mean()) if len(best) else 0.0,
            'median_best_f1': float(np.median(best)) if len(best) else 0.0,
            'rooms_whole_room': int(sum(1 for r in records
                                        if r['truth_aided_upper_bound']['all_instances_hit'])),
            'rooms_with_f1_ge_0_5': int(sum(1 for r in records
                                            if r['truth_aided_upper_bound']['f1'] >= 0.5)),
        },
        'deterministic': {
            'rooms_whole_room': int(sum(1 for d in det if d.get('all_instances_hit'))),
            'rooms_placed': int(sum(1 for d in det if d.get('status') == 'placed')),
            'mean_f1': float(np.mean([d.get('f1', 0.0) for d in det])) if det else 0.0,
            'all_instances_hit': bool(records) and all(d.get('all_instances_hit') for d in det),
        },
        'sampling': {'attempts': attempts, 'failed_attempts': failed,
                     'failure_rate': float(failed / attempts) if attempts else 0.0},
    }


# ------------------------------------------------------------------------ CLI
def _parse_rooms(spec):
    rooms = []
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            lo, hi = part.split('-')
            rooms.extend(range(int(lo), int(hi) + 1))
        else:
            rooms.append(int(part))
    return rooms


def _group(rooms):
    groups = {}
    for label, lo, hi in KNOWN_BATCHES:
        sel = [r for r in rooms if lo <= r <= hi]
        if sel:
            groups[label] = sel
    rest = [r for r in rooms if not any(lo <= r <= hi for _, lo, hi in KNOWN_BATCHES)]
    if rest:
        groups['custom'] = rest
    return groups


def _native(room):
    return str(E.OLD / 'raw-native800' / 'native' / f'multi-{room:05d}.json')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Structural-prior layout sampler')
    parser.add_argument('--rooms', default='11500-11511,11200-11231')
    parser.add_argument('--samples', type=int, default=2000)
    parser.add_argument('--attempts', type=int, default=ATTEMPT_CAP)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--out', default='output/layout-recon/structprior032')
    args = parser.parse_args(argv)

    rooms = _parse_rooms(args.rooms)
    groups = _group(rooms)
    started = time.time()
    payloads = [{'room': r, 'native': _native(r), 'samples': args.samples,
                 'attempts': args.attempts}
                for r in rooms]
    if args.jobs > 1:
        ctx = multiprocessing.get_context('spawn')
        with ProcessPoolExecutor(max_workers=args.jobs, mp_context=ctx) as pool:
            records = list(pool.map(_evaluate, payloads))
    else:
        records = [_evaluate(p) for p in payloads]

    by_room = {r['room']: r for r in records}
    batches = {}
    for label, sel in groups.items():
        recs = [by_room[r] for r in sel]
        summary = _aggregate(recs)
        summary['rooms'] = sel
        batches[label] = summary

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'structprior032.json'
    previous = {}
    if out_path.exists():
        try:
            previous = json.loads(out_path.read_text(encoding='utf-8'))
        except Exception:
            previous = {}
    prev_rooms = {r['room']: r for r in previous.get('rooms', [])}
    prev_rooms.update(by_room)
    prev_batches = dict(previous.get('batches', {}))
    prev_batches.update(batches)

    document = {
        'meta': {
            'module': 'analysis/layout/structprior032.py',
            'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'runtime_s': round(time.time() - started, 2),
            'seed_base': SEED_BASE,
            'seed_rule': 'random.Random(910000 + room)',
            'samples_per_room': args.samples,
            'attempt_cap_per_room': args.attempts,
            'clearance_m': CLEARANCE,
            'wall_gap_max_m': WALL_GAP_MAX,
            'start_clearance_m': START_CLEARANCE,
            'chair_gap_m': list(CHAIR_GAP),
            'match_tolerance_m': TOLERANCE,
            'truth_used_in_sampling': False,
            'score_fn': 'multi_instance.score_instances(pred, gt)',
            'sample_f1_rounding': '6 dp; every statistic is computed on the rounded values',
            'wall_categories': sorted(WALL_CATEGORIES),
            'chair_categories': sorted(CHAIR_CATEGORIES),
            'unknown_categories_rule': 'any other category falls back to the wall prior',
            'note': 'prior_alone and truth_aided_upper_bound are different quantities; '
                    'the upper bound is selected with ground truth and is not achievable.',
        },
        'batches': prev_batches,
        'rooms': sorted(prev_rooms.values(), key=lambda r: r['room']),
    }
    out_path.write_text(json.dumps(document, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({label: {k: v for k, v in b.items() if k != 'rooms'}
                      for label, b in batches.items()}, indent=1))
    print('wrote', out_path, 'rooms', len(records))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
