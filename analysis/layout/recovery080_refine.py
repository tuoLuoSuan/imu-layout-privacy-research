"""080: bounded object-level refinement of coarse layouts (no truth at inference)."""
from pathlib import Path
import json, numpy as np, torch
from torch import nn

CATS = ['bed', 'cab', 'desk', 'chair']
HALF = 23.0  # grid half-steps per axis: (extent - size) / (2*23)


def half_step(room, size):
    W, L = room
    return np.array([(W - size[0]) / (2 * HALF), (L - size[1]) / (2 * HALF)], dtype=np.float32)


def features(obs, key, box):
    W, L = obs['room']
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = x1 - x0, y1 - y0
    cat = key.split('#')[0]
    f = [cx / W, cy / L, w / W, h / L,
         min(x0, W - x1) / W, min(y0, L - y1) / L,
         min(x0, 1.0), min(W - x1, 1.0), min(y0, 1.0), min(L - y1, 1.0)]
    f += [1.0 if c == cat else 0.0 for c in CATS]
    contact = [e['pos'] for e in obs['events'] if e['object'] == cat]
    if contact:
        d = np.array([[cx - p[0], cy - p[1]] for p in contact], dtype=np.float32)
        dist = np.linalg.norm(d, axis=1)
        i = int(dist.argmin())
        f += [d[i, 0] / min(W, L), d[i, 1] / min(W, L), dist[i] / min(W, L)]
    else:
        f += [0.0, 0.0, 1.0]
    walk = np.asarray(obs['walk'], dtype=np.float32).reshape(-1, 2)
    if len(walk):
        dist = np.linalg.norm(walk - np.array([cx, cy], dtype=np.float32), axis=1)
        i = int(dist.argmin())
        f += [(walk[i, 0] - cx) / min(W, L), (walk[i, 1] - cy) / min(W, L), dist[i] / min(W, L)]
    else:
        f += [0.0, 0.0, 1.0]
    f += [len(contact) / 3.0, len(obs['inventory']) / 8.0]
    return np.asarray(f, dtype=np.float32)


def build_view(obs, coarse):
    keys = sorted(coarse)
    X = np.stack([features(obs, k, coarse[k]) for k in keys])
    step = np.stack([half_step(obs['room'], np.array(coarse[k][2:4]) - np.array(coarse[k][:2])) for k in keys])
    return keys, X, step


class Refine080(nn.Module):
    def __init__(self, width=64, dim=20):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(dim, width), nn.SiLU(), nn.Linear(width, width), nn.SiLU())
        self.head = nn.Linear(width, 2)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)

    def forward(self, x, step):
        return float(1.0) * step * torch.tanh(self.head(self.body(x)))


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def apply_delta(box, d):
    return [box[0] + d[0], box[1] + d[1], box[2] + d[0], box[3] + d[1]]


def clip_box(box, room):
    W, L = room
    w, h = box[2] - box[0], box[3] - box[1]
    cx = min(max((box[0] + box[2]) / 2, w / 2), W - w / 2)
    cy = min(max((box[1] + box[3]) / 2, h / 2), L - h / 2)
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
