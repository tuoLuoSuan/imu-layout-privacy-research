"""Reference-only acceptance gate for detector candidates; never a clock or label.

No cue detector is implemented here. Adequate energy is necessary, not evidence
of a known cue. Legacy unvalidated candidate files must not be consumed directly.
"""
import copy
import json
import math
from pathlib import Path
import numpy as np

RMS_FLOOR = 1e-4
PEAK_FLOOR = 1e-3
CORRELATION_FLOOR = .6
KIND = 'reference_audio_cue_support'

def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def _contract(source_sha256, support_s, expected_roles):
    if (not isinstance(source_sha256, str) or len(source_sha256) != 64
            or any(c not in '0123456789abcdef' for c in source_sha256)):
        raise ValueError('A lowercase source SHA-256 is required')
    if (not isinstance(support_s, (list, tuple)) or len(support_s) != 2
            or not all(_number(x) for x in support_s) or support_s[1] <= support_s[0]):
        raise ValueError('Ordered finite authoritative audio support is required')
    if (not isinstance(expected_roles, (list, tuple)) or not expected_roles
            or not all(isinstance(x, str) and x for x in expected_roles)
            or len(set(expected_roles)) != len(expected_roles)):
        raise ValueError('Unique required cue roles are required')

def _candidate_reasons(candidate, support_s, expected_roles):
    if not isinstance(candidate, dict):
        return ['no_cue_candidates']
    matches = candidate.get('matches')
    if not isinstance(matches, list) or not all(isinstance(m, dict) for m in matches):
        return ['invalid_cue_candidates']
    reasons = []
    if [m.get('role') for m in matches] != list(expected_roles):
        reasons.append('incomplete_or_unordered_required_roles')
    if not _number(candidate.get('global_audio_offset_s')):
        reasons.append('invalid_offset')
    previous_end = -math.inf
    for m in matches:
        a, b, rho = [m.get(k) for k in ['video_pts_s', 'tone_end_video_pts_s', 'correlation']]
        if not all(_number(x) for x in [a, b, rho]):
            reasons.append('invalid_candidate_number')
            continue
        if not CORRELATION_FLOOR <= rho <= 1. + 1e-8:
            reasons.append('insufficient_candidate_correlation')
        if not support_s[0] <= a < b <= support_s[1] or a < previous_end:
            reasons.append('candidate_outside_support_or_overlapping')
        previous_end = b
    return list(dict.fromkeys(reasons))

def validate_cue_candidates(samples, candidate, *, expected_roles, source_sha256, support_s):
    """Gate already-detected candidates; rejected output has no usable timing.

    samples must be mono normalized PCM. support_s is supplied from the decoder's
    actual PTS; array indices must not be substituted for container timestamps.
    """
    _contract(source_sha256, support_s, expected_roles)
    result = {'schema_version': 1, 'kind': KIND, 'source_sha256': source_sha256,
              'support_s': list(support_s), 'expected_roles': list(expected_roles),
              'accepted': False, 'status': 'no_usable_recorded_cues', 'reasons': [],
              'global_audio_offset_s': None, 'matches': [],
              'energy_gate_does_not_prove_cues': True,
              'clock_accepted': False, 'action_reference_created': False,
              'physical_av_sync_verified': False}
    quality = {'sample_count': 0, 'rms': None, 'peak': None, 'energy_gate_pass': False,
               'rms_floor': RMS_FLOOR, 'peak_floor': PEAK_FLOOR,
               'engineering_floor_not_physical_silence_test': True}
    result['audio_quality'] = quality
    try:
        x = np.asarray(samples, dtype=float)
    except (TypeError, ValueError):
        result['reasons'] = ['invalid_pcm']
        return result
    if x.ndim != 1 or not x.size or not np.isfinite(x).all() or np.max(np.abs(x)) > 1.:
        result['reasons'] = ['invalid_pcm']
        return result
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x * x)))
    quality.update(sample_count=int(x.size), rms=rms, peak=peak,
                   energy_gate_pass=rms >= RMS_FLOOR and peak >= PEAK_FLOOR)
    if not quality['energy_gate_pass']:
        result['reasons'] = ['insufficient_audio_energy']
        return result
    result['reasons'] = _candidate_reasons(candidate, support_s, expected_roles)
    if result['reasons']:
        result['status'] = 'rejected_cue_candidates'
        return result
    result.update(accepted=True, status='candidate_recorded_cues_only',
                  global_audio_offset_s=float(candidate['global_audio_offset_s']),
                  matches=copy.deepcopy(candidate['matches']))
    return result

def load_cue_support(path, *, source_sha256):
    """Read validated audio support, rejecting legacy candidates and rejections.

    The SHA binds this file to the caller's source; it is not a signature or an
    independent proof of the detector's correctness or physical timing accuracy.
    """
    result = json.loads(Path(path).read_text(encoding='utf-8'))
    if (not isinstance(result, dict) or result.get('kind') != KIND
            or result.get('schema_version') != 1 or result.get('accepted') is not True
            or result.get('status') != 'candidate_recorded_cues_only'
            or result.get('source_sha256') != source_sha256):
        raise ValueError('Unvalidated, rejected, or wrong-source audio support')
    _contract(source_sha256, result.get('support_s'), result.get('expected_roles'))
    if _candidate_reasons(result, result['support_s'], result['expected_roles']):
        raise ValueError('Invalid validated-candidate structure')
    quality = result.get('audio_quality', {})
    if (quality.get('energy_gate_pass') is not True or not _number(quality.get('rms'))
            or not _number(quality.get('peak')) or quality['rms'] < RMS_FLOOR
            or quality['peak'] < PEAK_FLOOR
            or any(result.get(k) is not False for k in
                   ['clock_accepted', 'action_reference_created', 'physical_av_sync_verified'])):
        raise ValueError('Missing audio support or unsupported physical claim')
    return result
