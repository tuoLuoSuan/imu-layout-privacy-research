"""Prior-only control on the second independent 32-room set (11200-11231).

Same estimator, cap and support weight as prior_only_audit018.  The comparator is
that set's own stored raw arm (frozen011), read from the frozen per-room record;
the two batches are reported separately and never pooled.

Run: python -m analysis.layout.prior_only_batch2_020
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

SET = Path('output/research-sync/2026-11-09-paper-and-raw-input-012/wall-fresh32')
NATIVE = Path('output/research-sync/2026-11-09-joint-input-and-recovery-010/raw-native800/native')
ARMS = ('frozen011', 'wall012')


def main(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for room in range(11200, 11232):
        source = SET / 'records' / f'multi-{room:05d}' / 'input'
        priors_path = source / 'known-priors.json'
        priors = json.loads(priors_path.read_text())
        if set(priors) != {'room', 'start', 'inventory'}:
            raise ValueError('Control accepts only declared room/start/inventory')
        try:
            result = decode(priors, np.arange(3.), np.zeros((3, 2)), np.tile(np.eye(3), (3, 1, 1)),
                            [], np.zeros(3, bool), candidate_limit=128, support_cost_weight=.3)
        except Exception as exc:
            result = {'status': 'evaluation_error', 'boxes': {}, 'error': repr(exc)}
        frozen = json.loads((SET / f'multi-{room:05d}.json').read_text())
        arms = {row['arm']: row for row in frozen['rows']}
        truth = M.load_native(NATIVE / f'multi-{room:05d}.json')['gt']
        control = M.score_instances(result['boxes'], truth)
        rows.append({'room': room, 'prior_only_prediction': result, 'prior_only_score': control,
                     'raw_arm': 'frozen011', 'raw_score': arms['frozen011']['score'],
                     'stored_scores': {name: arms[name]['score'] for name in ARMS if name in arms},
                     'priors_sha256': hashlib.sha256(priors_path.read_bytes()).hexdigest()})
        print(room, result['status'], control['f1'], flush=True)
    a = np.array([r['prior_only_score']['all_instances_hit'] for r in rows])
    b = np.array([r['raw_score']['all_instances_hit'] for r in rows])
    only_a, only_b = int(np.sum(a & ~b)), int(np.sum(b & ~a))
    summary = {'n': len(rows), 'prior_only_whole': int(a.sum()), 'raw_whole': int(b.sum()),
               'prior_only_mean_room_f1': float(np.mean([r['prior_only_score']['f1'] for r in rows])),
               'raw_mean_room_f1': float(np.mean([r['raw_score']['f1'] for r in rows])),
               'prior_only_ok': sum(r['prior_only_prediction']['status'] == 'ok' for r in rows),
               'only_prior': only_a, 'only_raw': only_b,
               'paired_difference95_pp': paired_interval(len(rows), only_a, only_b),
               'mcnemar_p_unadjusted': float(binomtest(only_a, only_a + only_b, .5).pvalue) if only_a + only_b else 1.}
    payload = {'scope': 'second independent 32-room set, prior-only arm; comparator is this set''s own stored raw arm (frozen011). Reported separately from batch 1, never pooled.',
               'design_status': 'post-hoc control; no model or parameter selection',
               'batch': '11200-11231',
               'configuration': {'candidate_limit': 128, 'support_cost_weight': 0.3, 'contacts': 0,
                                 'walk_points': 0, 'pose_source': 'none',
                                 'inference_inputs': ['room', 'start', 'inventory']},
               'comparator_note': 'frozen011 is the stored frozen raw arm of this batch; its configuration matches the 11100 batch new_raw row (candidate cap 128, contact-loop refine, heading regularization), as recorded in analysis/layout/exp_heading012.py. No arm equivalence is asserted beyond that stored row.',
               'summary': summary, 'rows': rows}
    (output / 'prior-only-batch2.json').write_text(json.dumps(payload))
    print(json.dumps(summary, indent=1))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='output/research-sync/2026-11-10-prior-only-019')
    main(parser.parse_args().out)
