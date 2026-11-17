"""Observation-only composition of frozen 078 heads and bounded 080 refinement.

Routing reads actual supplied events only. No real-room heuristics are enabled.
This remains the declared-relation synthetic geometry contract, not raw IMU.
"""
from pathlib import Path
import numpy as np
import torch

from .recovery076_data import sha
from .recovery078_runtime import load_checkpoint as load078, predict as predict078
from .recovery080_refine import Refine080, build_view, apply_delta, clip_box

LEGACY_REFINER_SHA = 'd9bb4dd78738b375892ab1f53cbfc4b8d4925022846923d9f3287b54d4e29a6e'
LEGACY_FEATURE_SHA = '51707a08d03a41b2dcbf73198e19c8889ef9f8114842ba8d3e0e98f9bee7d6ee'


def choose_head(observation, models):
    if len(observation['events']) == 6 and models.get('k6') is not None:
        return 'k6', models['k6']
    return 'k2', models['k2']


def refine_boxes(observation, boxes, model, policy='nonzero'):
    if policy not in ('none', 'nonzero', 'all'):
        raise ValueError('Unknown refinement policy')
    if not boxes or policy == 'none' or (policy == 'nonzero' and not observation['events']):
        return dict(boxes), False
    keys, x, step = build_view(observation, boxes)
    with torch.inference_mode():
        delta = model(torch.from_numpy(x), torch.from_numpy(step)).numpy()
    if not np.isfinite(delta).all():
        raise FloatingPointError('Nonfinite refinement')
    return {k: [float(v) for v in clip_box(apply_delta(boxes[k], delta[i]), observation['room'])]
            for i, k in enumerate(keys)}, True


def load_models(k2_path, teacher_path, refiner_path, k6_path=None):
    model, saved, teacher, teacher_saved = load078(k2_path, teacher_path)
    heads = {'k2': (model, saved), 'k6': None}
    if saved['protocol']['candidate_protocol']['args'].get('only_contacts') != 2:
        raise ValueError('K2 routing head must specialize on actual contact count 2')
    if k6_path:
        aux, aux_saved, _, _ = load078(k6_path, teacher_path)
        if aux_saved['protocol']['candidate_protocol']['args'].get('only_contacts') != 6:
            raise ValueError('K6 routing head must specialize on actual contact count 6')
        heads['k6'] = (aux, aux_saved)
    state = torch.load(refiner_path, map_location='cpu', weights_only=True)
    feature_sha = state.get('protocol', {}).get('feature_source_sha256')
    if feature_sha is None:
        if sha(refiner_path) != LEGACY_REFINER_SHA:
            raise ValueError('Unbound legacy refiner; require audited checkpoint or 081 training protocol')
        feature_sha = LEGACY_FEATURE_SHA
    if sha(Path(__file__).with_name('recovery080_refine.py')) != feature_sha:
        raise ValueError('Refiner feature source differs from frozen training contract')
    refiner = Refine080(state['width'], state['dim'])
    refiner.load_state_dict(state['state_dict']); refiner.eval()
    paths = {'k2': k2_path, 'teacher': teacher_path, 'refiner': refiner_path}
    if k6_path:
        paths['k6'] = k6_path
    source_names = ('recovery081_runtime.py', 'recovery080_refine.py', 'recovery078_runtime.py',
                    'recovery078_candidates.py', 'recovery078_model.py', 'recovery076_data.py',
                    'recovery077_runtime.py', 'recovery077_model.py', 'recovery076_model.py')
    lock = {'checkpoint_sha256': {k: sha(p) for k, p in paths.items()},
            'source_sha256': {n: sha(Path(__file__).with_name(n)) for n in source_names},
            'search': {'candidates': 160, 'beam': 128},
            'real_room_rules': False,
            'scope': 'conditional synthetic geometry with shared declared desk_relation; not raw IMU'}
    return {**heads, 'teacher': teacher, 'teacher_saved': teacher_saved, 'refiner': refiner, 'lock': lock}


def predict(observation, models, policy='nonzero'):
    name, (model, saved) = choose_head(observation, models)
    coarse = predict078(observation, model, saved, models['teacher'], models['teacher_saved'],
                        search=models['lock']['search'])
    boxes, applied = refine_boxes(observation, coarse['boxes'], models['refiner'], policy)
    return {**coarse, 'coarse_boxes': coarse['boxes'], 'boxes': boxes,
            'head_081': name, 'actual_contact_count': len(observation['events']),
            'refinement_applied': applied, 'refinement_policy': policy,
            'model_lock': models['lock']}
