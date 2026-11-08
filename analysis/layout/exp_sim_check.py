# -*- coding: utf-8 -*-
"""合成 IMU 的第一道验收：物理自检 + 前端是否在这个输入域内可用。

不调参、不看布局；只回答四件事：
1) 静止段的重力与零角速度对不对；2) 已知旋转能否用陀螺积出来；
3) 冻结的 RoNIN 前端在合成流上还走不走得对；4) 冻结的动作模型能不能把事件认出来。
任一项不过就报告「合成域不匹配」，不放大到多房。
"""
import csv, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import sim_motion as SM
import action_model as AM
import paths
from analysis.phone_ronin.adapter import prepare_features, make_windows, predict, integrate_centers
from analysis.layout.simulation_validation import physical_report,required_actions_available

FIELDS = ['sequence', 'sensor_timestamp_ns', 'received_elapsed_realtime_ns',
          'writer_dequeued_elapsed_realtime_ns', 'x', 'y', 'z', 'accuracy']


def write_session(dst, gen):
    phone = os.path.join(dst, 'phone')
    os.makedirs(phone, exist_ok=True)
    for name, arr in (('accelerometer', gen['acc']), ('gyroscope', gen['gyro'])):
        with open(os.path.join(phone, name + '.csv'), 'w', newline='', encoding='utf-8') as h:
            w = csv.writer(h)
            w.writerow(FIELDS)
            for i, (ts, v) in enumerate(zip(gen['ts_ns'], arr), 1):
                ts = int(ts)
                w.writerow([i, ts, ts + 5000000, ts + 9000000,
                            '%.6f' % v[0], '%.6f' % v[1], '%.6f' % v[2], 3])


def rigid(src, dst):
    """只允许旋转 + 平移（禁止尺度与反射），Kabsch。"""
    cs, cd = src.mean(axis=0), dst.mean(axis=0)
    H = (src - cs).T @ (dst - cd)
    U, _, Vt = np.linalg.svd(H)
    D = np.diag([1.0, np.sign(np.linalg.det(Vt.T @ U.T))])
    R = Vt.T @ D @ U.T
    return lambda P: (P - cs) @ R.T + cd, R


def body_path(gen):
    m = SM.Motion()
    return np.array([m.state(float(t))[0] for t in gen['t']])


def label_at(gen, t):
    for a, b, lab in gen['truth']['segments']:
        if a <= t < b:
            return lab
    return gen['truth']['segments'][-1][2]


def run(outdir):
    os.makedirs(outdir, exist_ok=True)
    gen = SM.generate(fs=120.0, seed=7)
    write_session(outdir, gen)
    body = body_path(gen)
    truth = gen['truth']
    res = {'fs': gen['fs'], 'duration_s': float(gen['t'][-1]),
           'units': 'acc m/s^2 (includes gravity), gyro rad/s, timestamps ns, shared accel origin',
           'signals': {'accelerometer': list(map(list, np.round(gen['acc'][:2], 4))),
                       'gyroscope': list(map(list, np.round(gen['gyro'][:2], 4)))},
           'segments': truth['segments']}
    res['physics']=physical_report(gen)

    # 1) 静止重力：0-4 s 站着不动（other 档）
    still = (gen['t'] >= 1.0) & (gen['t'] < 4.0)
    an = np.linalg.norm(gen['acc'][still], axis=1)
    gy = np.linalg.norm(gen['gyro'][still], axis=1)
    res['static'] = {'n': int(still.sum()), 'acc_norm_mean': float(an.mean()),
                     'acc_norm_std': float(an.std()), 'gyro_norm_rms': float(np.sqrt((gy ** 2).mean())),
                     'acc_mean_xyz_including_gravity': [float(v) for v in gen['acc'][still].mean(axis=0)]}

    # 2) 已知旋转：只用 t=0 的真值姿态做初值，靠陀螺积分整段，算与真值的夹角（与 yaw 规范无关）
    def expm(w, dt):
        th = float(np.linalg.norm(w)) * dt
        if th < 1e-15:
            return np.eye(3)
        k = w / np.linalg.norm(w)
        K = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
        return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K)

    Rt = truth['R']
    Rint = Rt[0].copy()
    ang = np.zeros(len(gen['t']))
    for k in range(len(gen['t'])):
        ang[k] = math.degrees(math.acos(np.clip((np.trace(Rint.T @ Rt[k]) - 1) / 2, -1.0, 1.0)))
        Rint = Rint @ expm(gen['gyro'][k], 1.0 / gen['fs'])
    rot = [{'t': float(gen['t'][k]), 'drift_deg': float(ang[k])}
           for k in range(0, len(gen['t']), max(1, len(gen['t']) // 12))]
    res['rotation'] = {'drift_deg_final': float(ang[-1]), 'drift_deg_max': float(ang.max()),
                       'drift_deg_median': float(np.median(ang)), 'samples': rot}

    # 3) 前端：冻结 RoNIN 在合成流上
    ch = AM.load_phone(outdir)
    ta, A, aa = ch['accelerometer']; tg, G, ga = ch['gyroscope']
    A = list(map(tuple, A)); G = list(map(tuple, G))
    times, feats, info = prepare_features([(float(t), *map(float, x)) for t, x in zip(ta, A)],
                                         [(float(t), *map(float, x)) for t, x in zip(tg, G)])
    windows, wt = make_windows(times, feats)
    pred, _ = predict(windows, paths.RONIN_ARCH, paths.RONIN_CKPT,
                      __import__('hashlib').sha256(open(paths.RONIN_CKPT, 'rb').read()).hexdigest())
    # The network interval is [start,end]; location integration is indexed by its centre.
    t_est = np.asarray(wt, float)[:, 2]
    xy = integrate_centers(t_est, pred)
    tb = gen['t']
    truth_at = np.column_stack([np.interp(t_est, tb, body[:, 0]), np.interp(t_est, tb, body[:, 1])])
    # 诊断用整体刚性对齐（只允许旋转+平移、禁止尺度）：只看形状，不看绝对定位是否收敛
    fit_mask = np.ones(len(t_est), bool)
    f, R = rigid(xy[fit_mask], truth_at[fit_mask])
    est = f(xy)
    err = np.linalg.norm(est - truth_at, axis=1)
    seg_true = float(np.linalg.norm(np.diff(truth_at, axis=0), axis=1).sum())
    seg_est = float(np.linalg.norm(np.diff(est, axis=0), axis=1).sum())
    res['frontend'] = {'windows': int(len(t_est)), 'truth_path_m': seg_true, 'est_path_m': seg_est,
                       'path_ratio': seg_est / seg_true if seg_true else None,
                       'end_err_m': float(err[-1]), 'median_err_m': float(np.median(err)),
                       'p90_err_m': float(np.quantile(err, 0.9)),
                       'max_err_m': float(err.max()),
                       'evaluation_time':'RoNIN target-interval centre',
                       'scope':'Compatibility with this frozen estimator, not generator physical validity'}

    # 4) 事件：冻结五类模型 vs 真值分段
    model = AM.load_model()
    tl = AM.predict_timeline(model, ta, A, tg, G)
    wins = tl['windows']
    tlab = [label_at(gen, w['center_s']) for w in wins]
    plab = [w['label'] for w in wins]
    classes = sorted(set(tlab) | set(plab))
    conf = {c: {d: 0 for d in classes} for c in classes}
    for a, b in zip(tlab, plab):
        conf[a][b] += 1
    per = {}
    for c in classes:
        tp = conf[c][c]; tot = sum(conf[c].values()); hit = sum(conf[d][c] for d in classes)
        per[c] = {'n': tot, 'recall': tp / tot if tot else None,
                  'precision': tp / hit if hit else None}
    res['events'] = {'windows': len(wins), 'confusion': conf, 'per_class': per,
                     'time_definition': tl['time_definition']}

    # 5) 误差分解：真值锚点 vs 前端锚点（不是布局误差）
    anc = []
    for a, b, lab in truth['segments']:
        if lab not in ('seated', 'cabinet', 'lying'):
            continue
        m = (tb >= a) & (tb < b)
        me = (t_est >= a) & (t_est < b)
        if m.sum() < 2 or me.sum() < 2:
            continue
        p_true = body[m].mean(axis=0)
        p_est = est[me].mean(axis=0)
        anc.append({'event': [a, b, lab], 'truth': [float(v) for v in p_true],
                    'frontend': [float(v) for v in p_est],
                    'err_m': float(np.linalg.norm(p_est - p_true))})
    res['anchors'] = anc

    ok = {'static': abs(res['static']['acc_norm_mean'] - SM.G) <= 0.15 and res['static']['acc_norm_std'] <= 0.15
          and res['static']['gyro_norm_rms'] <= 0.05,
          'rotation': res['rotation']['drift_deg_final'] <= 10.0,
          'shape': 0.8 <= res['frontend']['path_ratio'] <= 1.25,
          'events': required_actions_available(per)}
    res['checks'] = ok
    res['generator_verdict']='kinematically-consistent' if res['physics']['passed'] else 'kinematic-check-failed'
    res['frontend_compatibility']='passes-current-diagnostics' if all(ok.values()) else 'synthetic-domain-mismatch'
    res['verdict']=res['generator_verdict']+' / '+res['frontend_compatibility']
    json.dump(res, open(os.path.join(outdir, 'sim-check.json'), 'w'), indent=1)
    return res, est, truth_at, t_est, plt_dump(wins, tlab, plab)


def plt_dump(wins, tlab, plab):
    return {'center': [w['center_s'] for w in wins], 'truth': tlab, 'pred': plab}


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'output/layout-recon/2026-11-08-sim-check')
    res, est, truth_at, t_est, tl = run(out)
    print('verdict', res['verdict'], res['checks'])
    print('static', json.dumps(res['static']))
    print('rotation drift final %.2f deg, max %.2f deg' % (res['rotation']['drift_deg_final'], res['rotation']['drift_deg_max']))
    print('frontend', json.dumps(res['frontend']))
    for c, v in res['events']['per_class'].items():
        print('  event', c, v)
    for a in res['anchors']:
        print('  anchor', a['event'][2], 'err %.3f m' % a['err_m'])
    np.save(os.path.join(out, 'sim-est.npy'), np.column_stack([t_est, est, truth_at]))
    fig_path = os.path.join(out, 'sim-check.png')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False
        fig, ax = plt.subplots(1, 2, figsize=(12.6, 4.6))
        ax[0].plot(truth_at[:, 0], truth_at[:, 1], lw=2.0, color='#333', label='合成真值（人体）')
        ax[0].plot(est[:, 0], est[:, 1], lw=1.4, color='#d62728', label='RoNIN 在合成流上')
        ax[0].set_aspect('equal'); ax[0].legend(fontsize=8); ax[0].grid(alpha=.25)
        ax[0].set_title('前端在合成域：路程比 %.2f，末端差 %.2f m' % (res['frontend']['path_ratio'], res['frontend']['end_err_m']), fontsize=9)
        order = {'other': 0, 'walk': 1, 'seated': 2, 'cabinet': 3, 'lying': 4}
        ax[1].plot(tl['center'], [order.get(v, 0) for v in tl['truth']], '.', ms=3, color='#333', label='真值')
        ax[1].plot(tl['center'], [order.get(v, 0) for v in tl['pred']], 'x', ms=3, color='#1f77b4', label='五类模型')
        ax[1].set_yticks(list(order.values())); ax[1].set_yticklabels(list(order.keys()), fontsize=8)
        ax[1].legend(fontsize=8); ax[1].grid(alpha=.25); ax[1].set_xlabel('time (s)')
        ax[1].set_title('冻结动作模型在合成流上', fontsize=9)
        fig.tight_layout(); fig.savefig(fig_path, facecolor='white')
        print('saved', fig_path)
    except Exception as exc:
        print('figure skipped:', exc)
    print('json', os.path.join(out, 'sim-check.json'))
