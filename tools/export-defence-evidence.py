"""Audit frozen per-query scores and expose all coordinate-input conditions.

No matcher, classifier, threshold selection or raw-IMU defence is run here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

BUDGETS = [8, 16, 32]
CONDITIONS = [(0., 'none')] + [(s, k) for s in [.3, .5, 1., 1.5] for k in ['iid', 'brownian', 'common']]
COHORTS = ['all', 'singleton', 'alias', 'dorm', 'apartment', 'conference', 'office', 'classroom', 'hotel']
SEED = 20261101


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rate(values):
    x = np.asarray(values, float).ravel()
    n = float(x.sum())
    return dict(numerator=n, denominator=len(x), value=n/len(x))


def distance_distortion(truth, observed):
    i, j = np.triu_indices(len(truth), 1)
    a = np.linalg.norm(truth[i]-truth[j], axis=1)
    b = np.linalg.norm(observed[i]-observed[j], axis=1)
    return float(np.sqrt(np.mean((a-b)**2)))


def house_intervals(values, families, seed=SEED, draws=1000):
    """N houses x 4 routes x P values; keep all routes within each house."""
    x = np.asarray(values).mean(axis=1)
    rng = np.random.default_rng(seed)
    weights = np.zeros((draws, len(x)))
    families = np.asarray(families)
    for f in sorted(set(families)):
        ids = np.flatnonzero(families == f)
        draws_ids = rng.integers(0, len(ids), size=(draws, len(ids)))
        for b in range(draws):
            weights[b, ids] = np.bincount(draws_ids[b], minlength=len(ids))
    samples = weights @ x / len(x)
    return np.quantile(samples, [.025, .975], axis=0).T


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    base = args.source_root/'output/prospective-space/2026-10-30-simulation-abstention-and-action-plan-001/six-family-geometry-library-001/noisy-candidate-ranking-001'
    paths = [base/'run/test-summary.json', base/'run/test-metrics.npz', base/'run/test-houses.json', base/'noise_core.py', base/'run_stage.py', base/'freeze.json']
    inputs = [dict(path=p.relative_to(args.source_root).as_posix(), bytes=p.stat().st_size, sha256=sha(p)) for p in paths]
    summary = json.loads(paths[0].read_text(encoding='utf-8'))
    metadata = json.loads(paths[2].read_text(encoding='utf-8'))['rows']
    with np.load(paths[1]) as z:
        metrics = z['metrics'][..., 5, :3].copy()
        counts = z['observed_unique_sites'].copy()
        points = z['observed_points'].copy()
    assert metrics.shape == (600, 4, 3, 13, 3)
    distortion = np.zeros((600, 4, 3, 13))
    for hi in range(600):
        for ri in range(4):
            for bi in range(3):
                q = counts[hi, ri, bi]
                true = points[hi, ri, bi, 0, :q]
                for ci in range(13):
                    distortion[hi, ri, bi, ci] = distance_distortion(true, points[hi, ri, bi, ci, :q])
    rows = []
    max_error = 0.
    for cohort in COHORTS:
        ids = np.array([i for i, m in enumerate(metadata) if cohort == 'all' or m['cohort'] == cohort or m['family'] == cohort])
        values = metrics[ids].reshape(len(ids), 4, -1)
        ci_values = house_intervals(values, [metadata[i]['family'] for i in ids]).reshape(3, 13, 3, 2)
        for bi, budget in enumerate(BUDGETS):
            for ci, (sigma, structure) in enumerate(CONDITIONS):
                original = next(r for r in summary['rows'] if r['cohort'] == cohort and r['visits'] == budget and r['sigma'] == sigma and r['structure'] == structure and r['method'] == 'partial_normalized_spectrum')
                results = {}
                for mi, metric in enumerate(['top1', 'top5', 'top10']):
                    rr = rate(metrics[ids, :, bi, ci, mi])
                    error = abs(rr['value']-original[metric])
                    max_error = max(max_error, error)
                    assert error < 1e-12, (cohort, budget, sigma, structure, metric, error)
                    results[metric] = dict(rate=rr, house_bootstrap95=ci_values[bi, ci, mi].tolist())
                if structure == 'common':
                    assert np.array_equal(metrics[ids, :, bi, ci], metrics[ids, :, bi, 0])
                    assert np.max(distortion[ids, :, bi, ci]) < 1e-12
                rows.append(dict(cohort=cohort, visits=budget, sigma=sigma, structure=structure,
                    houses=len(ids), queries=len(ids)*4, **results,
                    answer_rate=dict(numerator=len(ids)*4, denominator=len(ids)*4, value=1.),
                    observed_unique_sites_mean=rate(counts[ids, :, bi]),
                    distance_distortion_rms_m_mean=rate(distortion[ids, :, bi, ci]),
                    independent_replication=False, invariant_control=structure == 'common'))
    flags = {k: summary[k] for k in ['formal_score', 'real_candidate_rank', 'real_room_ranking', 'real_room_family_count', 'physical_clock_accepted', 'sensor_window_join_allowed', 'scientific_geometry_ground_truth_verified', 'generalization_accuracy_validated', 'collection_open']}
    output = dict(schema='defence-evidence-v1', rows=rows, source_inputs=inputs, flags=flags,
        provenance=dict(ranking_scores_recomputed=False, stored_query_scores_reaggregated=True,
            summary_maximum_absolute_error=max_error, conditions=39, cohorts=9,
            test_scores_seen_before_freeze=True, post_audit_exploratory=True),
        condition=dict(method='partial_normalized_spectrum', lambda_value=0, oracle_grouping=True,
            known_closed_catalog_size=600, raw_imu_defence_implemented=False, normal_function_utility_measured=False,
            adaptive_scorer_validated=False, grouping_family_defence_validated=False,
            common_scores_reused_from_noiseless_by_original_runner=True,
            brownian_definition='sigma*cumsum(z)/sqrt(32); prefix retains this denominator',
            noise_sigma_is_measured_error=False),
        uncertainty=dict(unit='house; four routes retained', draws=1000, seed=SEED,
            scope='pointwise, conditional on current cohort family counts and generator; no multiplicity-adjusted claims'),
        geometry_proxy='Mean of query-level RMS errors of corresponding site-pair distances; metres; not navigation/action utility.',
        scope='Coordinate-input sensitivity of one fixed attack. All conditions paired on the same houses. Common translation is a mathematical invariance check, not independent evidence. No deployed defence or end-to-end raw IMU claim.')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir/'defence-evidence.json'
    with target.open('xb') as stream:
        stream.write((json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode('utf-8'))
    for p, record in zip(paths, inputs):
        assert sha(p) == record['sha256'], p
    print(json.dumps(dict(rows=len(rows), max_summary_error=max_error, bytes=target.stat().st_size, sha256=sha(target)), ensure_ascii=False))


if __name__ == '__main__':
    main()
