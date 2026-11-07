# -*- coding: utf-8 -*-
"""前缀实验：只给前 T 秒原始 IMU，端到端能得到什么布局。
前端（RoNIN 轨迹）与后端（动作锚点 + 求解器）都真跑，不复用整段结果。
同时验证：前缀轨迹应与整段轨迹在同一时刻几乎重合（因果积分），
所以误差变化只能来自「可用事件变少」，不是前端被截断弄坏了。"""
import csv, hashlib, io, json, os, shutil, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from analysis.phone_ronin.adapter import prepare_features, make_windows, predict, integrate_centers
import analysis.layout.layout_solver as LS
import paths

SESS = os.path.join(ROOT, 'output', 'layout-recon', 's-59d570ee')
PHONE = os.path.join(SESS, 'phone')
REF = {'bed': (1.17, 1.96, 2.695, 4.045), 'desk': (0.05, 1.05, 0.65, 2.10),
       'cab': (0.05, 0.0, 0.65, 1.05), 'chair': (1.11, 0.92, 1.55, 1.36)}
GRID = [8, 12, 16, 20, 25, 30, 35, 40, 45, 50, 56.5]


def load(name):
    rows = []
    with io.open(os.path.join(PHONE, name), encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            rows.append((int(r['sensor_timestamp_ns']), float(r['x']), float(r['y']), float(r['z'])))
    t0 = rows[0][0]
    return [((t - t0) / 1e9, x, y, z) for t, x, y, z in rows], t0


def cut(rows, T):
    return [r for r in rows if r[0] <= T]


def run_frontend(A, G, sha):
    times, feats, _ = prepare_features(A, G)
    windows, wt = make_windows(times, feats)
    pred, _ = predict(windows, paths.RONIN_ARCH, paths.RONIN_CKPT, sha)
    t = np.asarray(wt, dtype=np.float64)[:, 1]
    xy = integrate_centers(t, pred)
    sp = np.linalg.norm(pred, axis=1)
    return np.column_stack([t, xy, sp])


def err(box, ref):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    rx, ry = (ref[0] + ref[2]) / 2, (ref[1] + ref[3]) / 2
    return float(np.hypot(cx - rx, cy - ry))


def main():
    A_all, t0 = load('accelerometer.csv')
    G_all, _ = load('gyroscope.csv')
    runs = [tuple(r) for r in json.load(io.open(os.path.join(SESS, 'actions.json'), encoding='utf-8'))['runs']]
    sha = hashlib.sha256(open(paths.RONIN_CKPT, 'rb').read()).hexdigest()
    full = np.load(os.path.join(SESS, 'ronin-xy.npy'))

    tmp = os.path.join(HERE, '_prefix_tmp')
    rows = []
    for T in GRID:
        A, G = cut(A_all, T), cut(G_all, T)
        if len(A) < 400:
            continue
        d = run_frontend(A, G, sha)
        # 与整段轨迹在同一时间窗上的最大偏差（因果积分 ⇒ 应接近 0）
        m = full[:, 0] <= d[-1, 0]
        ref_t, ref_p = full[m, 0], full[m, 1:3]
        dev = float(np.max(np.abs(d[:, 1:3] - np.column_stack(
            [np.interp(d[:, 0], ref_t, ref_p[:, 0]), np.interp(d[:, 0], ref_t, ref_p[:, 1])]))))
        avail = [r for r in runs if r[2] <= T]
        if os.path.isdir(tmp):
            shutil.rmtree(tmp)
        os.makedirs(tmp)
        np.save(os.path.join(tmp, 'ronin-xy.npy'), d)
        json.dump({'runs': [list(r) for r in avail]}, io.open(os.path.join(tmp, 'actions.json'), 'w', encoding='utf-8'))
        res = LS.solve(tmp, save=False, allow_partial=True)
        pred = res[0] if isinstance(res, tuple) else res
        row = {'T': T, 'windows': int(len(d)), 'traj_end': [float(d[-1, 1]), float(d[-1, 2])],
               'traj_dev_vs_full': dev, 'status': pred['status'],
               'events': [list(r) for r in avail], 'err': {}, 'boxes': {}}
        for k, b in (pred.get('boxes') or {}).items():
            row['boxes'][k] = [float(v) for v in b]
            row['err'][k] = err(b, REF[k])
        rows.append(row)
        print('T=%5.1f s  win %4d  dev %.2e m  %-13s %s' % (
            T, len(d), dev, pred['status'],
            ' '.join('%s %.3f' % (k, row['err'][k]) for k in ('bed', 'desk', 'cab', 'chair') if k in row['err'])))
    shutil.rmtree(tmp, ignore_errors=True)
    out = os.path.join(HERE, 'prefix.json')
    json.dump({'grid': GRID, 'rows': rows}, io.open(out, 'w', encoding='utf-8'), indent=1)
    print('written', out)


if __name__ == '__main__':
    main()
