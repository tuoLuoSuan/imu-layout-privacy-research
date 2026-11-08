# -*- coding: utf-8 -*-
"""前缀实验：只给前 T 秒原始 IMU，端到端能得到什么布局。
前端（RoNIN 轨迹）与后端（动作锚点 + 求解器）都真跑，不复用整段结果。
同时验证：前缀轨迹应与整段轨迹在同一时刻几乎重合（因果积分），
所以误差变化只能来自「可用事件变少」，不是前端被截断弄坏了。"""
import hashlib, io, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from analysis.phone_ronin.adapter import prepare_features, make_windows, predict, integrate_centers
import analysis.layout.layout_solver as LS
import paths
import action_model as AM

SESS = paths.SESSION
PHONE = os.path.join(SESS, 'phone')
REF = {'bed': (1.17, 1.96, 2.695, 4.045), 'desk': (0.05, 1.05, 0.65, 2.10),
       'cab': (0.05, 0.0, 0.65, 1.05), 'chair': (1.11, 0.92, 1.55, 1.36)}
GRID = [8, 12, 16, 20, 25, 30, 35, 40, 45, 50, 56.5]


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
    channels = AM.load_phone(SESS, require_receipts=True)
    ta, acceleration, aa = channels['accelerometer']
    tg, gyro, ga = channels['gyroscope']
    model = AM.load_model()
    sha = hashlib.sha256(open(paths.RONIN_CKPT, 'rb').read()).hexdigest()
    full_a = [(float(t), *map(float, x)) for t, x in zip(ta, acceleration)]
    full_g = [(float(t), *map(float, x)) for t, x in zip(tg, gyro)]
    full = run_frontend(full_a, full_g, sha)

    output_root = os.path.join(paths.REPO, 'output', 'layout-recon', 'causal-prefix-20261108')
    rows = []
    for T in GRID:
        ma, mg = (ta <= T) & (aa <= T), (tg <= T) & (ga <= T)
        A = [(float(t), *map(float, x)) for t, x in zip(ta[ma], acceleration[ma])]
        G = [(float(t), *map(float, x)) for t, x in zip(tg[mg], gyro[mg])]
        if len(A) < 400:
            continue
        d = run_frontend(A, G, sha)
        # 与整段轨迹在同一时间窗上的最大偏差（因果积分 ⇒ 应接近 0）
        m = full[:, 0] <= d[-1, 0]
        ref_t, ref_p = full[m, 0], full[m, 1:3]
        dev = float(np.max(np.abs(d[:, 1:3] - np.column_stack(
            [np.interp(d[:, 0], ref_t, ref_p[:, 0]), np.interp(d[:, 0], ref_t, ref_p[:, 1])]))))
        timeline = AM.predict_timeline(model, ta, acceleration, tg, gyro, budget_s=T,
                                       accel_arrivals=aa, gyro_arrivals=ga)
        avail = timeline['runs']
        tmp = os.path.join(output_root, 'T-' + str(T))
        os.makedirs(tmp, exist_ok=True)
        np.save(os.path.join(tmp, 'ronin-xy.npy'), d)
        json.dump(timeline, io.open(os.path.join(tmp, 'actions.json'), 'w', encoding='utf-8'))
        res = LS.solve(tmp, save=False, allow_partial=True)
        pred = res[0] if isinstance(res, tuple) else res
        row = {'T': T, 'windows': int(len(d)), 'traj_end': [float(d[-1, 1]), float(d[-1, 2])],
               'traj_dev_vs_full': dev, 'status': pred['status'],
               'events': [list(r) for r in avail], 'err': {}, 'boxes': {},
               'action_windows': timeline['windows'],
               'last_action_available_s': max((w['available_s'] for w in timeline['windows']), default=None)}
        for k, b in (pred.get('boxes') or {}).items():
            row['boxes'][k] = [float(v) for v in b]
            row['err'][k] = err(b, REF[k])
        rows.append(row)
        print('T=%5.1f s  win %4d  dev %.2e m  %-13s %s' % (
            T, len(d), dev, pred['status'],
            ' '.join('%s %.3f' % (k, row['err'][k]) for k in ('bed', 'desk', 'cab', 'chair') if k in row['err'])))
    out = os.path.join(HERE, 'prefix.json')
    json.dump({'grid': GRID, 'rows': rows, 'causal_action_recomputed': True,
               'frozen_action_model': str(AM.MODEL_PATH),
               'budget_basis': 'sensor time and callback receipt from first phone acceleration event'},
              io.open(out, 'w', encoding='utf-8'), indent=1)
    print('written', out)


if __name__ == '__main__':
    main()
