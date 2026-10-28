"""Independent reference-only geometry. No ROS, hardware, training, or original-file writes."""
import numpy as np
from scipy.spatial import cKDTree
from scipy import ndimage

WINDOWS = {'reference': (18., 24.), 'validation': (24.5, 29.5), 'visit1': (2., 6.), 'visit2': (44., 48.)}


def voxel_coords(points, size=.05, phase=(0., 0., 0.)):
    points = np.asarray(points)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError('Expected finite N by 3 points')
    # Keep source FLOAT32 arithmetic for exact replication of the frozen voxelizer.
    phase = np.asarray(phase, dtype=points.dtype)
    coords = np.floor((points-phase)/size).astype(np.int32)
    return np.unique(coords, axis=0)


def neighbor_distances(query, reference, tree=None):
    query = np.asarray(query)
    reference = np.asarray(reference)
    if not len(reference):
        raise ValueError('Reference is empty; absence is not a background measurement')
    if not len(query):
        return np.empty(0)
    tree = cKDTree(reference) if tree is None else tree
    return tree.query(query, k=1, p=np.inf, eps=0)[0]


def components(points, cell=.15):
    """26-neighbor occupied cells; all points in each cell belong to the same component."""
    points = np.asarray(points, dtype=float)
    if not len(points):
        return []
    grid = np.floor(points/cell).astype(np.int32)
    origin = grid.min(axis=0)
    ijk = grid-origin
    shape = tuple((ijk.max(axis=0)+1).tolist())
    if np.prod(shape) > 10_000_000:
        raise ValueError('Input exceeds the declared reference ROI')
    occupied = np.zeros(shape, dtype=bool)
    occupied[tuple(ijk.T)] = True
    labels, _ = ndimage.label(occupied, structure=np.ones((3, 3, 3), dtype=np.uint8))
    point_labels = labels[tuple(ijk.T)]
    order = np.argsort(point_labels, kind='stable')
    _, starts = np.unique(point_labels[order], return_index=True)
    ends = np.r_[starts[1:], len(order)]
    return [points[order[a:b]] for a, b in zip(starts, ends)]


def candidates(centres, min_voxels=20, min_height=.8):
    result = []
    for group in components(centres):
        if len(group) < min_voxels:
            continue
        low, high = group.min(axis=0), group.max(axis=0)
        span = high-low
        if span[2] < min_height:
            continue
        result.append({'n': len(group), 'c': group.mean(axis=0).tolist(),
                       'zspan': float(span[2]), 'width': float(span[0]), 'thickness': float(span[1]),
                       'bbox_min': low.tolist(), 'bbox_max': high.tolist()})
    result.sort(key=lambda c: (-c['n'], *c['c']))
    return result


def window_indices(times, interval):
    a, b = interval
    return np.flatnonzero((np.asarray(times) >= a) & (np.asarray(times) < b))


def summarize(frames, windows=None, exact_times=False):
    windows = WINDOWS if windows is None else windows
    time_key = 't_exact_s' if exact_times else 't'
    def window(name):
        a, b = windows[name]
        return [f for f in frames if a <= f.get(time_key, f['t']) < b]
    def stats(rows):
        valid = [f for f in rows if f['struct_valid']]
        return {'raw_frames': len(rows), 'struct_valid': len(valid), 'invalid': len(rows)-len(valid),
                'unique': sum(f['ncand'] == 1 for f in valid), 'none': sum(f['ncand'] == 0 for f in valid),
                'multi': sum(f['ncand'] > 1 for f in valid), 'occ_frames': sum(bool(f['occ']) for f in rows),
                'max_novelty': max((f['novel'] for f in rows), default=None),
                'mean_novelty': float(np.mean([f['novel'] for f in rows])) if rows else None}
    result = {name: stats(window(name)) for name in ['validation', 'visit1', 'visit2']}
    val = result['validation']
    result['V1'] = {'pass': bool(val['raw_frames'] and val['max_novelty'] is not None and val['max_novelty'] <= .001)}
    result['V2'] = {'pass': all(result[k]['unique'] >= 20 and result[k]['struct_valid'] and result[k]['unique']/result[k]['struct_valid'] >= .8 for k in ['visit1', 'visit2'])}
    result['V3'] = {'ambiguous': any(result[k]['multi'] for k in ['visit1', 'visit2'])}
    result['platforms'] = {}
    for name in ['visit1', 'visit2']:
        p = np.asarray([f['cands'][0]['c'] for f in window(name) if f['struct_valid'] and f['ncand'] == 1])
        result['platforms'][name] = None if not len(p) else {'n': len(p), 'median': np.median(p, axis=0).tolist(), 'std': p.std(axis=0).tolist()}
    result['primary_revisit_diff'] = None
    if result['V1']['pass'] and result['V2']['pass'] and not result['V3']['ambiguous']:
        a, b = [np.array(result['platforms'][name]['median']) for name in ['visit1', 'visit2']]
        result['primary_revisit_diff'] = {'2d_m': float(np.linalg.norm((b-a)[:2])), '3d_m': float(np.linalg.norm(b-a)), 'delta_xyz_m': (b-a).tolist()}
    return result


def fit_similarity(source, reference, allow_scale=True):
    source, reference = np.asarray(source, float), np.asarray(reference, float)
    if source.shape != reference.shape or source.ndim != 2 or source.shape[1] != 2 or len(source) < 2:
        raise ValueError('Require at least two known correspondences in 2D')
    pc, qc = source.mean(axis=0), reference.mean(axis=0)
    x, y = source-pc, reference-qc
    denominator = np.sum(x*x)
    if denominator <= 1e-15 or np.sum(y*y) <= 1e-15:
        raise ValueError('Collapsed anchor baseline')
    u, singular, vt = np.linalg.svd(x.T@y)
    correction = np.diag([1., 1. if np.linalg.det(vt.T@u.T) >= 0 else -1.])
    rotation = vt.T@correction@u.T
    scale = float(np.sum(singular*np.diag(correction))/denominator) if allow_scale else 1.
    if scale <= 0:
        raise ValueError('Nonpositive scale is outside the direct-similarity contract')
    return {'scale': scale, 'rotation': rotation, 'translation': qc-scale*(rotation@pc)}


def apply_similarity(points, transform):
    return transform['scale']*(np.asarray(points)@transform['rotation'].T)+transform['translation']


class ConservativeTracker:
    """Association prototype: forecasts never become reference measurements."""
    def __init__(self, max_speed=3., base_gate=.15, max_gap=1.):
        self.max_speed, self.base_gate, self.max_gap = max_speed, base_gate, max_gap
        self.last_t = None
        self.last = None
        self.velocity = np.zeros(2)
        self.track_id = 0
        self.input_t = None

    def step(self, t, candidates):
        t = float(t)
        if self.input_t is not None and t <= self.input_t:
            raise ValueError('Tracker timestamps must increase')
        self.input_t = t
        gap = None if self.last_t is None else t-self.last_t
        forecast = None if gap is None or gap > self.max_gap else self.last+gap*self.velocity
        row = {'t': t, 'state': 'missing', 'track_id': self.track_id or None,
               'candidate_count': len(candidates), 'observed_xy': None,
               'predicted_xy': None if forecast is None else forecast.tolist(), 'measurement_imputed': False}
        if len(candidates) > 1:
            row['state'] = 'ambiguous'
            return row
        if not candidates:
            return row
        observed = np.asarray(candidates[0]['c'][:2], dtype=float)
        if forecast is not None:
            gate = self.base_gate+self.max_speed*gap
            row['gate_m'] = gate
            row['innovation_m'] = float(np.linalg.norm(observed-forecast))
            if row['innovation_m'] > gate:
                row['state'] = 'rejected_jump'
                return row
        if self.last_t is None or gap > self.max_gap:
            self.track_id += 1
            self.velocity = np.zeros(2)
            row['state'] = 'acquired'
        else:
            self.velocity = (observed-self.last)/gap
            row['state'] = 'observed'
        self.last, self.last_t = observed, t
        row['track_id'], row['observed_xy'] = self.track_id, observed.tolist()
        return row
