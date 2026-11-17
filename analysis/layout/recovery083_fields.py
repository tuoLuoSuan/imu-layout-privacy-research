"""083 spatial fields: unordered walk points -> 64x64 distance field + observed mask + contact heatmaps."""
import numpy as np

CATS = ['bed', 'cab', 'desk', 'chair']
GRID = 64
REACH = 0.35


def _xy(a):
    a = np.asarray(a, dtype=np.float32)
    return a.reshape(-1, 2)


def fields(observation, grid=GRID, reach=REACH, sigma=0.15):
    w, h = observation['room']
    gx = (np.arange(grid, dtype=np.float32) + 0.5) / grid * w
    gy = (np.arange(grid, dtype=np.float32) + 0.5) / grid * h
    X, Y = np.meshgrid(gx, gy)
    pts = _xy(observation['walk']) if len(observation['walk']) else np.zeros((0, 2), np.float32)
    if len(pts):
        d = np.sqrt((X[..., None] - pts[None, None, :, 0]) ** 2 + (Y[..., None] - pts[None, None, :, 1]) ** 2)
        dist = d.min(-1)
    else:
        dist = np.full((grid, grid), 3.0, np.float32)
    walk = np.clip(dist, 0, 3.0) / 3.0
    seen = (dist <= reach).astype(np.float32)
    heat = np.zeros((4, grid, grid), np.float32)
    for e in observation['events']:
        cat = e['object'] if isinstance(e, dict) else None
        if cat not in CATS:
            continue
        pos = np.asarray(e['pos'] if isinstance(e, dict) else e, dtype=np.float32).reshape(-1)[:2]
        g = np.exp(-((X - pos[0]) ** 2 + (Y - pos[1]) ** 2) / (2 * sigma ** 2))
        heat[CATS.index(cat)] = np.maximum(heat[CATS.index(cat)], g)
    return np.stack([walk, seen] + [heat[i] for i in range(4)]).astype(np.float32)


def scalar_features(observation, cat, size):
    w, h = observation['room']
    onehot = np.zeros(4, np.float32)
    onehot[cat] = 1.0
    return np.concatenate([[w / 8.0, h / 8.0], onehot, [size[0] / 2.0, size[1] / 2.0]]).astype(np.float32)
