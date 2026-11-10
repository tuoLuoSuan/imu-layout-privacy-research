"""Paired room-level contrasts for Figure 2, from frozen evaluations only."""
import json
from pathlib import Path

import numpy as np


def paired_interval(n, only_before, only_after, seed=18018):
    """Room-bootstrap difference using its sufficient discordance counts."""
    if n <= 0 or min(only_before, only_after) < 0 or only_before + only_after > n:
        raise ValueError('Invalid paired outcome counts')
    probability = [only_before / n, only_after / n, 1 - (only_before + only_after) / n]
    samples = np.random.default_rng(seed).multinomial(n, probability, size=50000)
    differences = (samples[:, 1] - samples[:, 0]) / n
    return (100 * np.quantile(differences, [.025, .975])).tolist()


def build_contrasts(root):
    root = Path(root)
    paper = root / 'paper/2026-11-09-controlled-position-leakage-zh/source-data'
    old = root / 'output/research-sync/2026-11-09-joint-input-and-recovery-010'

    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))

    def paired_records(files, before, after):
        pairs = []
        for path in files:
            rows = read(path)['rows']
            lookup = {r['arm']: r['score']['all_instances_hit'] for r in rows}
            pairs.append((lookup[before], lookup[after]))
        return len(pairs), sum(a for a, b in pairs), sum(b for a, b in pairs), \
            sum(a and not b for a, b in pairs), sum(b and not a for a, b in pairs)

    rows = []

    def add(key, layer, n, before, after, only_before, only_after, source, interval=None):
        if after - before != only_after - only_before:
            raise AssertionError('Paired counts do not reconcile')
        rows.append(dict(key=key, layer=layer, n=n, before=before, after=after,
                         only_before=only_before, only_after=only_after,
                         delta_pp=100 * (after - before) / n,
                         interval95_pp=paired_interval(n, only_before, only_after) if interval is None else interval,
                         interval_method='paired room percentile bootstrap', source=str(source)))

    source = paper / 'geometry-mechanism.json'
    geometry = read(source)['all10000']['outline|1.0|14']
    add('r1', 0, geometry['n_rooms'], geometry['repeat_whole_hits'], geometry['dispersed_whole_hits'],
        geometry['a_only'], geometry['b_only'], source,
        interval=(100 * np.array(geometry['whole_difference_bootstrap_ci'])).tolist())

    source = root / 'output/layout-recon/desk-wall-1000/rooms'
    result = paired_records(sorted(source.glob('*.json')), 'none', 'wall_0.15')
    if result[:3] != (1000, 651, 826):
        raise AssertionError('Desk-prior cohort does not match frozen result')
    add('r2', 0, *result, source)

    source = old / 'geometry-confirm1000/audit.json'
    decoder = next(r for r in read(source)['paired']
                   if r['coverage'] == 1. and r['visits'] == 14 and
                   r['a'] == 'post64_wall40k' and r['b'] == 'depth_portfolio')
    add('r3', 0, decoder['n_rooms'], decoder['both'] + decoder['a_only'],
        decoder['both'] + decoder['b_only'], decoder['a_only'], decoder['b_only'], source,
        interval=(100 * np.array(decoder['whole_difference_bootstrap95'])).tolist())

    first = root / 'output/research-sync/2026-11-09-bias-aware-input-014/confirm32'
    second = root / 'output/research-sync/2026-11-09-bias-confirm-014b/run-gg'
    files = sorted(first.glob('*-s0.5.json')) + sorted(second.glob('*-s0.5.json'))
    result = paired_records(files, 'reference', 'bias014')
    if result[:3] != (64, 25, 34):
        raise AssertionError('Gyro severity0.5 cohorts do not match frozen result')
    add('r4', 1, *result, f'{first}; {second}')
    result = paired_records(sorted(first.glob('*-s1.json')), 'reference', 'bias014')
    if result[:3] != (32, 3, 14):
        raise AssertionError('Gyro severity1 cohort does not match frozen result')
    add('r5', 1, *result, first)

    source = paper / 'raw32-audit.json'
    raw = read(source)
    pair = raw['paired']['truth_pose_same_predicted_actions']
    add('r6', 2, raw['n'], raw['summary']['new_raw']['whole'],
        raw['summary']['truth_pose_same_predicted_actions']['whole'], pair['new_only'], pair['other_only'], source,
        interval=[-pair['paired_bootstrap95_pp'][1], -pair['paired_bootstrap95_pp'][0]])
    return rows
