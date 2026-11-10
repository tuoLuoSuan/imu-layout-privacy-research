"""Post-hoc prior-only control on the frozen011 confirmation rooms.

Same directional decoder, candidate cap, support weight, room/start/inventory.
No signal, pose, walk point, contact, heading or event association is supplied.
This is a control for one finite estimator, not a best-prior-only bound.
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


def main(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    raw = Path('output/research-sync/2026-11-09-raw-input-repair-011/confirm32')
    native = Path('output/research-sync/2026-11-09-joint-input-and-recovery-010/raw-native800/native')
    rows = []
    for room in range(11100, 11132):
        source = raw / f'multi-{room:05d}'
        priors_path = source / 'input/known-priors.json'
        priors = json.loads(priors_path.read_text())
        if set(priors) != {'room', 'start', 'inventory'}:
            raise ValueError('Control accepts only declared room/start/inventory')
        try:
            result = decode(priors, np.arange(3.), np.zeros((3, 2)), np.tile(np.eye(3), (3, 1, 1)),
                            [], np.zeros(3, bool), candidate_limit=128, support_cost_weight=.3)
        except Exception as exc:
            result = {'status': 'evaluation_error', 'boxes': {}, 'error': repr(exc)}
        # Evaluation files are opened only after the prior-only decode completes.
        frozen = json.loads((source / 'results.json').read_text())
        truth = M.load_native(native / f'multi-{room:05d}.json')['gt']
        control = M.score_instances(result['boxes'], truth)
        primary = next(r for r in frozen['rows'] if r['arm'] == 'new_raw')
        rows.append({'room': room, 'prior_only_prediction': result, 'prior_only_score': control,
                     'raw_score': primary['score'], 'priors_sha256': hashlib.sha256(priors_path.read_bytes()).hexdigest()})
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
    payload = {'scope': __doc__, 'design_status': 'post-hoc control; no model/parameter selection; awaiting independent DS review',
               'configuration': {'candidate_limit': 128, 'support_cost_weight': .3,
                                 'contacts': 0, 'walk_points': 0, 'pose_source': 'none',
                                 'inference_inputs': ['room', 'start', 'inventory'], 'truth_read_during_decode': False},
               'summary': summary, 'rows': rows}
    (output / 'prior-only-control.json').write_text(json.dumps(payload, indent=1), encoding='utf-8')
    print(json.dumps(summary), flush=True)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='output/research-sync/2026-11-10-figure-room-bounds-018')
    args = parser.parse_args()
    main(args.out)
