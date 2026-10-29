"""Offline stop proposals from sensor data, with evaluator-only temporal matching."""
import itertools
import math
import numpy as np
from scipy.optimize import linear_sum_assignment


def clocks(t):
    t = np.asarray(t, float)
    if t.ndim != 1 or len(t) < 2 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError('Strictly increasing finite times required')
    return t, float(np.median(np.diff(t)))


def segment_mask(times, mask, minimum_s=2., merge_gap_s=.25):
    t, dt = clocks(times)
    mask = np.asarray(mask, bool)
    if mask.shape != t.shape or minimum_s <= 0 or merge_gap_s < 0:
        raise ValueError('Matching mask and nonnegative duration rules required')
    boundaries = np.r_[0, np.flatnonzero(np.diff(t) > 1.5 * dt) + 1, len(t)]
    result = []
    for lo, hi in zip(boundaries[:-1], boundaries[1:]):
        active = np.flatnonzero(mask[lo:hi]) + lo
        if not len(active):
            continue
        runs = np.split(active, np.flatnonzero(np.diff(active) > 1) + 1)
        merged = []
        first, last = int(runs[0][0]), int(runs[0][-1])
        for run in runs[1:]:
            start, end = int(run[0]), int(run[-1])
            if t[start] - (t[last] + dt) <= merge_gap_s + 1e-9:
                last = end
            else:
                merged.append((first, last)); first, last = start, end
        merged.append((first, last))
        for first, last in merged:
            end = float(t[last + 1]) if last + 1 < hi else float(t[last] + dt)
            if end - t[first] >= minimum_s - 1e-9:
                result.append(dict(start_s=float(t[first]), end_s=end, samples=last - first + 1))
    return result


def imu_mask(times, features, window_s=1., gyro_max=.15, accel_std_max=.35):
    t, dt = clocks(times)
    if np.max(np.abs(np.diff(t) - dt)) > dt * .01:
        raise ValueError('IMU features must use the existing uniform sample grid')
    f = np.asarray(features, float)
    if f.shape != (len(t), 6) or not np.isfinite(f).all():
        raise ValueError('Six finite gyro/acceleration columns required')
    size = int(round(window_s / dt))
    if size < 2:
        raise ValueError('Trailing window too short')
    g = np.full(len(t), np.nan); a = np.full(len(t), np.nan)
    if len(t) < size:
        return np.zeros(len(t), bool), dict(gyro_rms=g, acceleration_vector_std=a)
    sums = np.vstack([np.zeros((1, 6)), np.cumsum(f, axis=0)])
    squares = np.vstack([np.zeros((1, 6)), np.cumsum(f * f, axis=0)])
    mean = (sums[size:] - sums[:-size]) / size
    mean_square = (squares[size:] - squares[:-size]) / size
    g[size - 1:] = np.sqrt(np.maximum(0, mean_square[:, :3].sum(axis=1)))
    a[size - 1:] = np.sqrt(np.maximum(0, (mean_square[:, 3:] - mean[:, 3:] ** 2).sum(axis=1)))
    return (g <= gyro_max) & (a <= accel_std_max), dict(gyro_rms=g, acceleration_vector_std=a)


def segment_positions(segments, times, xy):
    t, _ = clocks(times)
    xy = np.asarray(xy, float)
    if xy.shape != (len(t), 2) or not np.isfinite(xy).all():
        raise ValueError('Finite XY trajectory required')
    result = []
    for segment in segments:
        selected = (t >= segment['start_s']) & (t < segment['end_s'])
        count = int(selected.sum())
        result.append(dict(**segment, xy=np.median(xy[selected], axis=0).tolist() if count >= 2 else None,
                           model_samples=count, position_valid=count >= 2))
    return result


def associate(detected, reference_windows, minimum_coverage=.5):
    reference = np.asarray(reference_windows, float)
    if reference.ndim != 2 or reference.shape[1] != 2 or np.any(reference[:, 1] <= reference[:, 0]):
        raise ValueError('Positive reference intervals required')
    overlaps = np.zeros((len(reference), len(detected)))
    for i, (lo, hi) in enumerate(reference):
        for j, segment in enumerate(detected):
            overlaps[i, j] = max(0., min(hi, segment['end_s']) - max(lo, segment['start_s']))
    coverages = overlaps / (reference[:, 1] - reference[:, 0])[:, None]
    valid = coverages >= minimum_coverage
    mapping = [None] * len(reference)
    if len(detected):
        priority = (overlaps.max(initial=0) + 1) * (len(reference) + 1)
        weights = valid * (priority + overlaps)
        rows, columns = linear_sum_assignment(-weights)
        for i, j in zip(rows, columns):
            if valid[i, j]: mapping[int(i)] = int(j)
    return dict(reference_to_detected=mapping, reference_coverage=coverages.tolist(),
                reference_with_multiple_candidates=np.flatnonzero(valid.sum(axis=1) > 1).tolist(),
                detected_covering_multiple_references=np.flatnonzero(valid.sum(axis=0) > 1).tolist(),
                unmatched_detected=[j for j in range(len(detected)) if j not in mapping],
                matched_references=sum(j is not None for j in mapping))


def score_queries(points, mapping, labels, policy='nearest'):
    if len(mapping) != len(labels):
        raise ValueError('Mapping and evaluator labels must agree')
    points = np.asarray(points, float)
    inverse = {j: i for i, j in enumerate(mapping) if j is not None}
    details = []
    for i, label in enumerate(labels):
        if not any(labels[k] == label for k in range(i)):
            continue
        target = mapping[i]
        choices = []
        if target is not None and target > 0:
            if policy == 'nearest':
                d = np.linalg.norm(points[:target] - points[target], axis=1)
                norm = float(np.sqrt(np.mean(d * d)))
                d = d / norm if norm > 0 else np.zeros_like(d)
                choices = np.flatnonzero(np.isclose(d, d.min(), rtol=0, atol=1e-12)).tolist()
            elif policy == 'last': choices = [target - 1]
            elif policy == 'first': choices = [0]
            elif policy == 'random': choices = list(range(target))
            else: raise ValueError('Unknown history policy')
        known_correct = [j for j in choices if j in inverse and labels[inverse[j]] == label]
        unresolved = [j for j in choices if j not in inverse]
        low = len(known_correct) / len(choices) if choices else 0.
        high = (len(known_correct) + len(unresolved)) / len(choices) if choices else 0.
        details.append(dict(reference_visit=i + 1, detected_target_index=target,
                            predicted_detected_indices=choices, known_correct_indices=known_correct,
                            unlabelled_predicted_indices=unresolved,
                            target_missing=target is None, correct_lower=low, correct_upper=high))
    return dict(queries=len(details), correct_lower=sum(q['correct_lower'] for q in details),
                correct_upper=sum(q['correct_upper'] for q in details),
                missing_targets=sum(q['target_missing'] for q in details),
                unresolved_queries=sum(bool(q['unlabelled_predicted_indices']) for q in details), details=details)


def expected_random_ap(n, m):
    if not 0 < m <= n:
        raise ValueError('Positive number of positives at most total required')
    harmonic = sum(1 / k for k in range(1, n + 1))
    analytic = 1. if n == 1 else harmonic / n + (m - 1) / (n - 1) * (1 - harmonic / n)
    total = 0.; count = 0
    for positions in itertools.combinations(range(1, n + 1), m):
        total += sum(rank / pos for rank, pos in enumerate(positions, 1)) / m
        count += 1
    return dict(analytic=analytic, enumerated=total / count, rankings=count, constant_score_ap=m / n,
                no_random_draws=True)
