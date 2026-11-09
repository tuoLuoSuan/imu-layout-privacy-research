"""Opt-in012 input-only experiment. Frozen011 remains the paper's baseline.

Adds declared storage-wall side information to trajectory regularization.
Accepts raw phone6/watch3 streams and room/start/inventory only. No oracle mode.
"""
import argparse
import json
from pathlib import Path
from . import multi_raw010 as X
from .displacement011 import load, replay
from .contact_loops011 import refine as contact_refine
from .wall_refine012 import refine as wall_refine
from .oriented_raw011 import decode


def infer_saved(session, priors, motion_model, wrist_model):
    if set(priors) != {'room', 'start', 'inventory'}:
        raise ValueError('Only declared room/start/inventory accepted')
    model = load(motion_model)

    def front(t, A, G):
        return replay(t, A, G, model, heading_regularization=True)

    def refine(t, path, R, runs, known):
        path, contact = contact_refine(t, path, R, runs, known)
        path, wall = wall_refine(t, path, R, runs, known)
        return path, {'contact_loops': contact, 'storage_wall': wall}

    result = X.infer(session, priors, wrist_model, trajectory_frontend=front, candidate_limit=128,
                     trajectory_refiner=refine, layout_decoder=lambda *a: decode(*a, support_cost_weight=.3))
    result['input_contract'] = {'raw_phone_axes': 6, 'raw_watch_axes': 3, 'watch_gyro': False,
                                'cabinet_source': 'watch_only', 'reference_pose_read': False,
                                'reference_scene_read': False, 'cue_labels_read': False,
                                'known_priors': sorted(priors), 'same_domain_supervised_displacement': True,
                                'extra_side_information': 'Storage wall gap[0,0.15]m along depth normal; reach0.6m',
                                'experimental012_not_frozen011': True}
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for key in ['session', 'priors', 'model', 'wrist', 'out']:
        p.add_argument('--' + key, required=True)
    a = p.parse_args()
    result = infer_saved(a.session, json.loads(Path(a.priors).read_text()), a.model, a.wrist)
    Path(a.out).write_text(json.dumps(result, indent=1))
