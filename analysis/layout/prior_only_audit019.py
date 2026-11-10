"""Prior-only control over declared 32-room batches, admission-gated.

A batch is admitted only when every room has the three declared priors keys,
a frozen results.json carrying an arm-new_raw row, and a native truth file.
A rejected batch is recorded with its failing condition and never decoded, so
the decoder receives only room, start and inventory.  Pooling is refused below
two admitted disjoint batches: one batch is reported as a single-batch control.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from . import multi_instance as M
from .oriented_raw011 import decode
from .figure_contrasts018 import paired_interval

NATIVE = Path('output/research-sync/2026-11-09-joint-input-and-recovery-010/raw-native800/native')
REFERENCE = Path('output/research-sync/2026-11-10-figure-room-bounds-018/prior-only-control.json')
CANDIDATES = [
    {'label': '11100-11131', 'root': 'output/research-sync/2026-11-09-raw-input-repair-011/confirm32',
     'pattern': 'multi-{room}', 'rooms': range(11100, 11132)},
    {'label': '11200-11231', 'root': 'output/research-sync/2026-11-09-paper-and-raw-input-012/wall-fresh32/records',
     'pattern': 'multi-{room}', 'rooms': range(11200, 11232)},
    {'label': '11300-11331', 'root': 'output/research-sync/2026-11-09-wall-pool-013/confirm32/records',
     'pattern': 'multi-{room}', 'rooms': range(11300, 11332)},
    {'label': '11500-11531', 'root': 'output/research-sync/2026-11-09-bias-aware-input-014/confirm32/records',
     'pattern': 'multi-{room}-s0.5', 'rooms': range(11500, 11532)},
    {'label': '11600-11631/run-b', 'root': 'output/research-sync/2026-11-09-bias-confirm-014b/run-b/records',
     'pattern': 'multi-{room}-s0.5', 'rooms': range(11600, 11632)},
    {'label': '11600-11631/run-gg', 'root': 'output/research-sync/2026-11-09-bias-confirm-014b/run-gg/records',
     'pattern': 'multi-{room}-s0.5', 'rooms': range(11600, 11632)},
]


def check_batch(batch):
    root, pattern = Path(batch['root']), batch['pattern']
    failures = []
    if len(batch['rooms']) != 32:
        failures.append({'room': None, 'condition': 'wrong_room_count'})
    for room in batch['rooms']:
        source = root / pattern.format(room=room)
        priors_path = source / 'input/known-priors.json'
        if not priors_path.is_file():
            failures.append({'room': room, 'condition': 'missing_known_priors'})
            continue
        if set(json.loads(priors_path.read_text())) != {'room', 'start', 'inventory'}:
            failures.append({'room': room, 'condition': 'priors_keys_not_room_start_inventory'})
            continue
        results_path = source / 'results.json'
        if not results_path.is_file():
            failures.append({'room': room, 'condition': 'missing_results_json'})
            continue
        if not any(r.get('arm') == 'new_raw' for r in json.loads(results_path.read_text()).get('rows', [])):
            failures.append({'room': room, 'condition': 'missing_new_raw_row'})
            continue
        if not (NATIVE / f'multi-{room}.json').is_file():
            failures.append({'room': room, 'condition': 'missing_native_truth'})
    counts = {}
    for failure in failures:
        counts[failure['condition']] = counts.get(failure['condition'], 0) + 1
    return {'label': batch['label'], 'root': batch['root'], 'pattern': pattern,
            'rooms': list(batch['rooms']), 'admitted': not failures,
            'failures': counts, 'examples': failures[:3]}


def run_batch(batch):
    root, pattern = Path(batch['root']), batch['pattern']
    rows = []
    for room in batch['rooms']:
        source = root / pattern.format(room=room)
        priors_path = source / 'input/known-priors.json'
        declared = json.loads(priors_path.read_text())
        priors = {key: declared[key] for key in ('room', 'start', 'inventory')}
        try:
            result = decode(priors, np.arange(3.), np.zeros((3, 2)), np.tile(np.eye(3), (3, 1, 1)),
                            [], np.zeros(3, bool), candidate_limit=128, support_cost_weight=.3)
        except Exception as exc:
            result = {'status': 'evaluation_error', 'boxes': {}, 'error': repr(exc)}
        # Evaluation files are opened only after the prior-only decode completes.
        frozen = json.loads((source / 'results.json').read_text())
        truth = M.load_native(NATIVE / f'multi-{room}.json')['gt']
        control = M.score_instances(result['boxes'], truth)
        primary = next(r for r in frozen['rows'] if r['arm'] == 'new_raw')
        rows.append({'batch': batch['label'], 'room': room, 'prior_only_prediction': result,
                     'prior_only_score': control, 'raw_score': primary['score'],
                     'priors_sha256': hashlib.sha256(priors_path.read_bytes()).hexdigest()})
        print(batch['label'], room, result['status'], control['f1'], flush=True)
    return rows


def summarize(rows):
    a = np.array([r['prior_only_score']['all_instances_hit'] for r in rows])
    b = np.array([r['raw_score']['all_instances_hit'] for r in rows])
    only_prior, only_raw = int(np.sum(a & ~b)), int(np.sum(b & ~a))
    return {'n': len(rows), 'prior_only_whole': int(a.sum()), 'raw_whole': int(b.sum()),
            'prior_only_mean_room_f1': float(np.mean([r['prior_only_score']['f1'] for r in rows])),
            'raw_mean_room_f1': float(np.mean([r['raw_score']['f1'] for r in rows])),
            'prior_only_ok': int(sum(r['prior_only_prediction']['status'] == 'ok' for r in rows)),
            'only_prior': only_prior, 'only_raw': only_raw,
            'paired_difference95_pp': paired_interval(len(rows), only_prior, only_raw),
            'mcnemar_p_unadjusted': float(binomtest(only_prior, only_prior + only_raw, .5).pvalue)
            if only_prior + only_raw else 1.}


def reproduction(report):
    if not REFERENCE.is_file():
        return {'reference': str(REFERENCE), 'checked': False}
    stored = json.loads(REFERENCE.read_text())['summary']
    differences = {}
    for key, value in stored.items():
        observed = report.get(key)
        if isinstance(value, list):
            same = np.allclose(observed, value, rtol=0, atol=1e-12)
        elif isinstance(value, float):
            same = bool(np.isclose(observed, value, rtol=0, atol=1e-12))
        else:
            same = observed == value
        if not same:
            differences[key] = {'stored': value, 'observed': observed}
    return {'reference': str(REFERENCE), 'checked': True, 'matches': not differences,
            'differences': differences}


def main(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    gate = [check_batch(batch) for batch in CANDIDATES]
    admitted, seen = [], set()
    for batch, report in zip(CANDIDATES, gate):
        if not report['admitted']:
            continue
        overlap = set(batch['rooms']) & seen
        if overlap:
            report['admitted'] = False
            report['failures']['rooms_overlap'] = len(overlap)
            continue
        seen.update(batch['rooms'])
        admitted.append(batch)
    rows, batches = [], []
    for batch in admitted:
        batch_rows = run_batch(batch)
        rows += batch_rows
        batches.append({'label': batch['label'], 'root': batch['root'],
                        'summary': summarize(batch_rows)})
    status = 'ok' if len(admitted) >= 2 else 'second_batch_missing'
    pooled = summarize(rows) if rows else None
    if pooled is not None:
        pooled['batches'] = [batch['label'] for batch in admitted]
    reference = next((reproduction(b['summary']) for b in batches if b['label'] == '11100-11131'), None)
    payload = {'scope': __doc__,
               'design_status': 'post-hoc control; no model/parameter selection; admission gated by declared artifacts',
               'status': status,
               'configuration': {'candidate_limit': 128, 'support_cost_weight': .3,
                                 'contacts': 0, 'walk_points': 0, 'pose_source': 'none',
                                 'inference_inputs': ['room', 'start', 'inventory'],
                                 'admission_reads_result_labels_only': True,
                                 'truth_read_during_decode': False,
                                 'required_rooms_per_batch': 32},
               'batch_gate': {'admitted': [batch['label'] for batch in admitted],
                              'rejected': [report for report in gate if not report['admitted']],
                              'candidates': gate},
               'batches': batches, 'pooled': pooled, 'reproduction_018': reference, 'rows': rows}
    (output / 'prior-only-control.json').write_text(json.dumps(payload, indent=1), encoding='utf-8')
    print('STATUS', status, 'admitted', [batch['label'] for batch in admitted], flush=True)
    print(json.dumps(pooled), flush=True)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='output/research-sync/2026-11-10-prior-only-019')
    args = parser.parse_args()
    main(args.out)
