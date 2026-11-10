"""Recomputed statistics for the 64-room category-quota batch (run 034).

The 034 batch applies the frozen selectbalanced032 rule set unchanged to the
fresh contiguous block 11700-11763, split into two stages by memory pressure:

  confirm64a  11700-11731
  confirm64b  11732-11763

This module reads the stage files back and redoes the summary and the paired
contrasts from the raw rows.  It deliberately does not import
selectbalanced032.paired(): the bug that motivated this file was a paired block
that used one seed of bal_random instead of the mean of its three seeds, so the
seed aggregation is recomputed here and asserted against the arm means.

Aggregation rule (a row is not a replicate; a room is):

  arm value per room = mean over that arm's rows for the room (1 row for
  base/bal_disperse/bal_oracle, 3 seeds for bal_random/plain_random), then the
  arm mean is the mean of those per-room values.

Contrasts: bal_disperse - bal_random, bal_random - plain_random,
bal_oracle - bal_random, each on the per-room values above.  The mean of the
per-room differences is asserted to equal (arm mean A) - (arm mean B) on the
same room set; the assertion gap is written into the output.

p values: exact two-sided Wilcoxon signed-rank with mid-ranks for ties and zero
differences dropped (the null distribution is enumerated exactly by dynamic
programming over the tied rank groups, no normal approximation), plus a
Monte-Carlo sign-flip p with a fixed seed as a distribution-free cross-check.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

ARMS = ('base', 'bal_random', 'bal_disperse', 'bal_oracle', 'plain_random')
RANDOM_ARMS = ('bal_random', 'plain_random')
CONTRASTS = (('bal_disperse', 'bal_random'),
             ('bal_random', 'plain_random'),
             ('bal_oracle', 'bal_random'))
DEFAULT_OUT = Path('output/layout-recon/select032_64')
DEFAULT_STAGES = ('confirm64a', 'confirm64b')
TOL = 1e-12
SIGNFLIP_DRAWS = 200000
SIGNFLIP_SEED = 20261111


def module_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def parse_rooms(spec):
    """Inclusive lo-hi range or comma list of room ids."""
    ids = set()
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            lo, hi = part.split('-')
            ids.update(range(int(lo), int(hi) + 1))
        else:
            ids.add(int(part))
    return ids


def load_stages(out, stages):
    """Stage payloads in the given order, with their source paths."""
    out = Path(out)
    payloads, sources = [], []
    for stage in stages:
        path = out / ('stage-%s.json' % stage)
        payload = json.loads(path.read_text(encoding='utf-8'))
        payloads.append(payload)
        sources.append({'stage': stage, 'path': path.as_posix(),
                        'rooms': payload['protocol']['rooms'],
                        'ids': payload['protocol']['ids'],
                        'n_rows': len(payload['rows']),
                        'elapsed_s': payload.get('elapsed_s'),
                        'finished_at': payload.get('finished_at'),
                        'experiment_module_sha256': payload['protocol']['module_sha256'],
                        'k': payload['protocol']['k'],
                        'rules': {key: payload['protocol'][key]
                                  for key in ('visits', 'severity', 'offset', 'streams',
                                              'quota', 'bal_random_seed', 'bal_disperse',
                                              'bal_oracle', 'plain_random_seed',
                                              'contact_position', 'non_contact_runs',
                                              'arm_chain')}})
    return payloads, sources


def all_rows(payloads):
    rows = []
    for payload in payloads:
        rows.extend(payload['rows'])
    return rows


def error_rows(rows):
    return [{'room': r['room'], 'arm': r['arm'], 'seed': r['seed'], 'status': r['status'],
             'error': r['error']} for r in rows if r.get('error')]


def room_values(rows, arm):
    """Per-room value for one arm: mean over that arm's rows for the room.

    Returns (values, seeds) where values maps room -> {'f1', 'hit', 'hit_rate'}
    and seeds maps room -> sorted list of the row seeds used.
    """
    by_room = {}
    for row in rows:
        if row['arm'] != arm or row.get('error'):
            continue
        by_room.setdefault(row['room'], []).append(row)
    values, seeds = {}, {}
    for room, group in by_room.items():
        values[room] = {'f1': float(np.mean([g['f1'] for g in group])),
                        'hit': float(sum(1.0 if g['all_instances_hit'] else 0.0 for g in group)),
                        'hit_rate': float(np.mean([1.0 if g['all_instances_hit'] else 0.0
                                                   for g in group])),
                        'n_rows': len(group)}
        seeds[room] = sorted(g['seed'] for g in group if g['seed'] is not None)
    return values, seeds


def arm_table(rows, arm):
    """Rooms, hits and F1 for one arm, aggregated over rooms rather than rows."""
    values, seeds = room_values(rows, arm)
    scored = [r for r in rows if r['arm'] == arm and not r.get('error')]
    rooms = sorted(values)
    per_room_seeds = {str(room): seeds[room] for room in rooms}
    uniform_seeds = (arm not in RANDOM_ARMS
                     or all(seeds[room] == [1, 2, 3] for room in rooms))
    return {'arm': arm, 'n_rooms': len(rooms), 'n_rows': sum(1 for r in rows if r['arm'] == arm),
            'n_scored_rows': len(scored),
            'n_error_rows': sum(1 for r in rows if r['arm'] == arm and r.get('error')),
            'whole_room_hits': int(sum(1 for r in scored if r['all_instances_hit'])),
            'whole_room_hits_out_of': len(scored),
            'hit_rate_per_room': float(np.mean([values[r]['hit_rate'] for r in rooms])) if rooms else None,
            'expected_hits_out_of_rooms': (float(np.sum([values[r]['hit_rate'] for r in rooms]))
                                           if rooms else None),
            'mean_f1': float(np.mean([values[r]['f1'] for r in rooms])) if rooms else None,
            'mean_f1_rows': float(np.mean([r['f1'] for r in scored])) if scored else None,
            'mean_k_used': float(np.mean([r['k_used'] for r in scored])) if scored else None,
            'status_counts': {s: sum(1 for r in scored if r['status'] == s)
                              for s in sorted({r['status'] for r in scored})},
            'seeds_per_room_uniform_1_2_3': bool(uniform_seeds),
            'per_room_seeds': per_room_seeds if arm in RANDOM_ARMS else None,
            'per_room': {str(r): {'f1': values[r]['f1'], 'hit_rate': values[r]['hit_rate'],
                                  'rows': values[r]['n_rows']} for r in rooms}}


def midranks(values):
    """Mid-ranks (average rank inside each tie group) of the absolute values."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(values[order[j + 1]] - values[order[i]]) <= TOL:
            j += 1
        rank = 0.5 * ((i + 1) + (j + 1))
        for k in range(i, j + 1):
            ranks[order[k]] = rank
        i = j + 1
    return ranks


def wilcoxon_exact(diffs):
    """Exact two-sided Wilcoxon signed-rank p from the enumerated null law.

    Zero differences are dropped (they carry no sign information).  Tied
    absolute values share a mid-rank; the null distribution is built by
    convolving the per-tie-group sign counts, so the result is exact for the
    observed tie pattern rather than a normal approximation.  Ranks are doubled
    so that the half-integers introduced by averaging stay integral.
    """
    d = [float(x) for x in diffs if abs(float(x)) > TOL]
    n = len(d)
    if n == 0:
        return {'n_nonzero': 0, 'statistic': 0.0, 'p_two_sided': None,
                'method': 'exact signed-rank, no non-zero difference'}
    ranks = midranks([abs(x) for x in d])
    groups = {}
    for rank in ranks:
        groups[rank] = groups.get(rank, 0) + 1
    total = 0
    counts = np.zeros(1, dtype=object)
    counts[0] = 1
    for rank in sorted(groups):
        m = groups[rank]
        v = int(round(2 * rank))
        add = np.zeros(m * v + 1, dtype=object)
        for k in range(m + 1):
            add[k * v] = math.comb(m, k)
        updated = np.zeros(len(counts) + len(add) - 1, dtype=object)
        for s in range(len(counts)):
            if counts[s]:
                for a in range(len(add)):
                    if add[a]:
                        updated[s + a] += counts[s] * add[a]
        counts = updated
        total += m * v
    statistic = int(sum(int(round(2 * rank)) for x, rank in zip(d, ranks) if x > 0))
    patterns = int(sum(counts))
    p_greater = int(sum(counts[s] for s in range(statistic, len(counts)))) / patterns
    p_less = int(sum(counts[s] for s in range(0, statistic + 1))) / patterns
    return {'n_nonzero': n, 'n_pairs': int(sum(groups.values())),
            'tie_groups': len(groups), 'sign_patterns': patterns,
            'statistic': float(statistic / 2.0),
            'p_greater': float(p_greater), 'p_less': float(p_less),
            'p_two_sided': float(min(1.0, 2.0 * min(p_greater, p_less))),
            'method': 'exact two-sided signed-rank, mid-ranks for ties, zeros dropped'}


def sign_flip(diffs, draws=SIGNFLIP_DRAWS, seed=SIGNFLIP_SEED):
    """Monte-Carlo two-sided sign-flip p (not exact; draw count is recorded)."""
    d = np.asarray([float(x) for x in diffs if abs(float(x)) > TOL], float)
    if not len(d):
        return {'n_nonzero': 0, 'p_two_sided': None}
    rng = np.random.default_rng(seed)
    observed = abs(float(d.sum()))
    hits, done, chunk = 0, 0, 20000
    while done < draws:
        size = min(chunk, draws - done)
        signs = rng.integers(0, 2, size=(size, len(d))) * 2 - 1
        stats = np.abs(signs @ d)
        hits += int(np.count_nonzero(stats >= observed - 1e-15))
        done += size
    return {'n_nonzero': len(d), 'draws': draws, 'seed': seed,
            'observed_abs_sum': observed,
            'p_two_sided': float((hits + 1) / (draws + 1)),
            'method': 'monte-carlo two-sided sign flip'}


def contrast(rows, a, b):
    """Paired per-room contrast a - b on seed-mean room values."""
    va, sa = room_values(rows, a)
    vb, sb = room_values(rows, b)
    rooms = sorted(set(va) & set(vb))
    missing = {'a_only': sorted(set(va) - set(vb)), 'b_only': sorted(set(vb) - set(va))}
    per_room = []
    for room in rooms:
        diff = va[room]['f1'] - vb[room]['f1']
        per_room.append({'room': room,
                         'f1_a': va[room]['f1'], 'f1_b': vb[room]['f1'],
                         'diff': diff,
                         'sign': 1 if diff > TOL else (-1 if diff < -TOL else 0),
                         'hit_a': va[room]['hit_rate'], 'hit_b': vb[room]['hit_rate'],
                         'hit_diff': va[room]['hit_rate'] - vb[room]['hit_rate']})
    diffs = [p['diff'] for p in per_room]
    mean_diff = float(np.mean(diffs)) if diffs else None
    mean_a = float(np.mean([va[r]['f1'] for r in rooms])) if rooms else None
    mean_b = float(np.mean([vb[r]['f1'] for r in rooms])) if rooms else None
    gap = abs(mean_diff - (mean_a - mean_b)) if diffs else None
    sd = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else None
    se = float(sd / math.sqrt(len(diffs))) if sd is not None else None
    result = {
        'a': a, 'b': b, 'n_rooms': len(rooms),
        'mean_f1_a': mean_a, 'mean_f1_b': mean_b,
        'arm_mean_difference': (mean_a - mean_b) if diffs else None,
        'mean_diff': mean_diff,
        'better': sum(1 for p in per_room if p['sign'] > 0),
        'worse': sum(1 for p in per_room if p['sign'] < 0),
        'equal': sum(1 for p in per_room if p['sign'] == 0),
        'sd_diff': sd, 'se_diff': se,
        'ci95_normal': ([mean_diff - 1.959963984540054 * se,
                         mean_diff + 1.959963984540054 * se] if se is not None else None),
        'mean_hit_diff': float(np.mean([p['hit_diff'] for p in per_room])) if per_room else None,
        'hit_better': sum(1 for p in per_room if p['hit_diff'] > TOL),
        'hit_worse': sum(1 for p in per_room if p['hit_diff'] < -TOL),
        'hit_equal': sum(1 for p in per_room if abs(p['hit_diff']) <= TOL),
        'seeds_used_a': {'uniform_1_2_3': all(sa[r] == [1, 2, 3] for r in rooms) if a in RANDOM_ARMS else None,
                         'per_room': {str(r): sa[r] for r in rooms} if a in RANDOM_ARMS else None},
        'seeds_used_b': {'uniform_1_2_3': all(sb[r] == [1, 2, 3] for r in rooms) if b in RANDOM_ARMS else None,
                         'per_room': {str(r): sb[r] for r in rooms} if b in RANDOM_ARMS else None},
        'missing': missing,
        'assertion': {'criterion': 'mean(per-room diff) == mean_f1_a - mean_f1_b on the same room set',
                      'paired_mean': mean_diff, 'arm_mean_difference': (mean_a - mean_b) if diffs else None,
                      'abs_gap': gap, 'tolerance': TOL,
                      'passed': bool(gap is not None and gap <= TOL)},
        'wilcoxon_exact': wilcoxon_exact(diffs),
        'sign_flip_mc': sign_flip(diffs),
        'per_room': per_room,
    }
    return result


def analyse(payloads, sources=None):
    rows = all_rows(payloads)
    arms = {arm: arm_table(rows, arm) for arm in ARMS}
    rooms = sorted({r['room'] for r in rows})
    contrasts = [contrast(rows, a, b) for a, b in CONTRASTS]
    errs = error_rows(rows)
    payload = {
        'generated_by': 'analysis/layout/selectbalanced64_034.py',
        'generated_by_sha256': module_sha256(),
        'sources': sources or [],
        'aggregation': ('per-room value = mean over that arm\'s rows in the room '
                        '(3 seeds for bal_random/plain_random), arm mean = mean over rooms'),
        'batch': {'n_rooms': len(rooms), 'rooms': [min(rooms), max(rooms)] if rooms else None,
                  'ids': rooms,
                  'n_contact_rows': len(rows),
                  'n_error_rows': len(errs)},
        'arms': arms,
        'contrasts': contrasts,
        'assertions': {
            'paired_mean_equals_arm_mean_difference': {
                'passed': all(c['assertion']['passed'] for c in contrasts),
                'criterion': '|mean(per-room diff) - (mean_f1_a - mean_f1_b)| <= 1e-12',
                'rows': [{'contrast': '%s - %s' % (c['a'], c['b']),
                          'paired_mean': c['assertion']['paired_mean'],
                          'arm_mean_difference': c['assertion']['arm_mean_difference'],
                          'abs_gap': c['assertion']['abs_gap'],
                          'passed': c['assertion']['passed']} for c in contrasts]},
            'seed_mean_not_single_seed': {
                'passed': all(arms[a]['seeds_per_room_uniform_1_2_3'] for a in RANDOM_ARMS
                              if arms[a]['n_rooms']),
                'criterion': 'every room contributes exactly seeds 1, 2, 3 to each random arm',
                'detail': {a: {'n_rooms': arms[a]['n_rooms'],
                               'uniform_1_2_3': arms[a]['seeds_per_room_uniform_1_2_3']}
                           for a in RANDOM_ARMS}},
        },
        'error_rows': errs,
    }
    if len(sources) > 1:
        rule_sets = {json.dumps(s['rules'], sort_keys=True) for s in sources}
        hashes = {s['experiment_module_sha256'] for s in sources}
        payload['sources_consistent'] = {
            'passed': len(rule_sets) == 1 and len(hashes) == 1,
            'criterion': 'identical frozen rules and experiment module sha256 across stages',
            'n_rule_sets': len(rule_sets), 'experiment_module_sha256': sorted(hashes)}
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--stages', default=','.join(DEFAULT_STAGES))
    parser.add_argument('--target', default=None)
    parser.add_argument('--rooms', default=None,
                        help='optional filter: inclusive lo-hi range or comma list')
    args = parser.parse_args()
    stages = [s.strip() for s in args.stages.split(',') if s.strip()]
    payloads, sources = load_stages(args.out, stages)
    room_filter = None
    if args.rooms:
        room_filter = parse_rooms(args.rooms)
        payloads = [dict(p, rows=[r for r in p['rows'] if r['room'] in room_filter])
                    for p in payloads]
    payload = analyse(payloads, sources)
    payload['room_filter'] = (None if room_filter is None
                              else {'rooms': args.rooms, 'ids': sorted(room_filter),
                                    'n_rooms': len(room_filter)})
    target = Path(args.target) if args.target else Path(args.out) / 'paired64.json'
    target.write_text(json.dumps(payload, indent=1, default=float), encoding='utf-8')
    table = {a: [v['n_rooms'], v['whole_room_hits'], v['whole_room_hits_out_of'],
                 None if v['mean_f1'] is None else round(v['mean_f1'], 4)]
             for a, v in payload['arms'].items()}
    pairs = [{'contrast': '%s - %s' % (c['a'], c['b']), 'mean_diff': round(c['mean_diff'], 4),
              'better_worse_equal': [c['better'], c['worse'], c['equal']],
              'p_wilcoxon_exact': c['wilcoxon_exact']['p_two_sided'],
              'p_sign_flip_mc': c['sign_flip_mc']['p_two_sided'],
              'assert_abs_gap': c['assertion']['abs_gap'],
              'assert_passed': c['assertion']['passed']} for c in payload['contrasts']]
    print(json.dumps({'file': target.as_posix(), 'n_rooms': payload['batch']['n_rooms'],
                      'error_rows': len(payload['error_rows']), 'arms': table,
                      'contrasts': pairs,
                      'assertions': payload['assertions']
                      ['paired_mean_equals_arm_mean_difference']['passed']},
                     indent=1, default=float))


if __name__ == '__main__':
    main()
