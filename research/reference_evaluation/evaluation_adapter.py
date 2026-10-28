"""Offline, evaluator-only clock admission and held-out echo comparison.

Input bounds are evidence supplied by the evaluator, never inferred from trajectory
agreement. A software admission is not validation of physical sample timing.
"""
import math
import numpy as np
from reference_core import fit_similarity, apply_similarity


def clock_offset_interval(client_send, server_receive, server_send, client_receive):
    """NTP-style causal bounds for server minus client offset, seconds.

    Assumes nonnegative transport delays, common rate over the exchange and no
    clock step. Does not assume symmetric latency. Not a sensor sample clock.
    """
    p1, v2, v3, p4 = map(float, (client_send, server_receive, server_send, client_receive))
    if not all(math.isfinite(v) for v in (p1, v2, v3, p4)) or p4 < p1 or v3 < v2:
        raise ValueError('Invalid clock exchange')
    lo, hi = v3-p4, v2-p1
    if lo > hi:
        raise ValueError('Exchange incompatible with causal equal-rate clock model')
    return [lo, hi]


def admit_interval(clock, session_id, source_id, target_id, source_interval, minimum_common_s=1.):
    """Map an exact source interval through explicitly uncertain adjacent anchors.

    Piecewise-affine behavior between anchors remains an assumption. No
    extrapolation, first-frame alignment or trajectory-derived mapping is allowed.
    """
    result = dict(status='unknown_clock', common_target_interior_s=None,
                  physical_clock_validated=False, physical_sample_join_validated=False)
    if clock is None:
        return result
    if not all(isinstance(v, str) and v.strip() for v in (session_id, source_id, target_id)):
        raise ValueError('Explicit nonempty clock and session identities required')
    gap_limit = float(clock['max_anchor_gap_s'])
    if not math.isfinite(gap_limit) or gap_limit <= 0 or not math.isfinite(minimum_common_s) or minimum_common_s <= 0:
        raise ValueError('Finite positive gap and common-window bounds required')
    if (clock['session_id'], clock['source_id'], clock['target_id']) != (session_id, source_id, target_id):
        raise ValueError('Clock/session identity mismatch')
    if clock['evidence'] != 'independent_software_observed' or clock['affine_between_anchors_assumed'] is not True:
        raise ValueError('Independent observed clock anchors and declared affine assumption required')
    anchors = np.array([[a['source_s'], a['target_low_s'], a['target_high_s']] for a in clock['anchors']], float)
    if anchors.ndim != 2 or anchors.shape[1] != 3 or len(anchors) < 2 or not np.isfinite(anchors).all():
        raise ValueError('At least two finite anchors required')
    if np.any(np.diff(anchors[:, 0]) <= 0) or np.any(anchors[:, 1] > anchors[:, 2]) or np.any(anchors[1:, 1] <= anchors[:-1, 2]):
        raise ValueError('Ordered disjoint anchor intervals required')
    a, b = map(float, source_interval)
    if not math.isfinite(a+b) or a >= b or minimum_common_s <= 0:
        raise ValueError('Ordered finite source interval required')
    if a < anchors[0, 0] or b > anchors[-1, 0]:
        result['status'] = 'outside_anchor_support'; return result
    involved = (anchors[:-1, 0] < b) & (anchors[1:, 0] > a)
    if np.any(np.diff(anchors[:, 0])[involved] > gap_limit):
        result['status'] = 'anchor_gap_exceeded'; return result
    start = [float(np.interp(a, anchors[:, 0], anchors[:, k])) for k in [1, 2]]
    end = [float(np.interp(b, anchors[:, 0], anchors[:, k])) for k in [1, 2]]
    common = [start[1], end[0]]
    result.update(start_target_envelope_s=start, end_target_envelope_s=end,
                  common_target_interior_s=common if common[1] > common[0] else None,
                  status='admitted_under_software_clock_assumptions' if common[1]-common[0] >= minimum_common_s else 'insufficient_common_interior')
    return result


def evaluate_sites(model, echo, ids, fit_ids):
    """Compare pre-admitted stationary visits. No alignment from held-out visits.

    The radar echo centroid and the pocket phone are different reference objects;
    output is an echo discrepancy, never an absolute phone-position error.
    """
    model, echo = np.asarray(model, float), np.asarray(echo, float)
    if model.shape != echo.shape or model.shape != (len(ids), 2) or not np.isfinite(model).all() or not np.isfinite(echo).all():
        raise ValueError('Matching finite two-dimensional site aggregates required')
    if len(set(ids)) != len(ids) or len(fit_ids) != 2 or len(set(fit_ids)) != 2 or not set(fit_ids) <= set(ids):
        raise ValueError('Unique visit IDs and exactly two explicit fit visits required')
    fit = [ids.index(k) for k in fit_ids]
    held = [i for i in range(len(ids)) if i not in fit]
    if not held:
        raise ValueError('Independent held-out visit required')
    result = dict(fit_ids=fit_ids, heldout_ids=[ids[i] for i in held],
                  physical_phone_position_error_m=None, room_coordinates=None,
                  role='evaluator_only_not_attacker_input', reference_definition='visible_echo_centroid')
    for name, scale in [('rigid_nominal_units', False), ('similarity', True)]:
        tr = fit_similarity(model[fit], echo[fit], allow_scale=scale)
        pred = apply_similarity(model, tr)
        result[name] = dict(scale=tr['scale'], transform={k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in tr.items()},
                            fit_discrepancies_m=np.linalg.norm(pred[fit]-echo[fit], axis=1).tolist(),
                            heldout=[dict(id=ids[i], echo_discrepancy_m=float(np.linalg.norm(pred[i]-echo[i]))) for i in held])
    return result
