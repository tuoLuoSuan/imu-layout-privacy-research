# 系统性偏移：比独立高斯更接近真实 RoNIN 的失效——整段轨迹的尺度与偏航角是错的。
# 对同一场景的所有锚点施加同一个相似变换（s, theta），模拟「RoNIN 尺度差 5% / 朝向差 3 度」
# 这类**相关**误差，与 exp_noise_flip.py 的独立高斯对照。
import glob, io, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths, sim_eval as SE, layout_core as LC

ARMS = (('s5_t3', 0.05, 3.0), ('s10_t5', 0.10, 5.0))
N_DRAW = 8
FLIP = 0.5
TYPES = ('bed', 'desk', 'cab', 'chair')
rng = np.random.default_rng(11)

scenes = [s for s in (SE.load_scene(f) for f in sorted(glob.glob(os.path.join(paths.THOR, 'FloorPlan*.json')))) if s]
rows, solves, fails = [], 0, 0
for sc in scenes:
    a = SE.anchors_true(sc); tr = SE.traj_of(sc, a)
    sz = {'bed': sc['sizes']['bed'], 'desk': sc['sizes']['desk'],
          'cab': sc['sizes']['cab'], 'chair': sc['sizes']['chair'][0]}
    p0 = tr[0][0]  # traj_of 返回 (P, mask)，起点取轨迹首点
    solves += 1
    base = LC.solve(sc['W'], sc['L'], sc['S'], a, sz, traj=tr)
    if base.get('status') != 'ok':
        fails += 1
        continue
    B0 = base['boxes']
    for name, sg_s, sg_t in ARMS:
        for _ in range(N_DRAW):
            s = 1.0 + rng.normal(0, sg_s)
            th = np.radians(rng.normal(0, sg_t))
            R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
            # 以起点为支点：RoNIN 的尺度/朝向误差在起点为零，越远越大
            a2 = {k: p0 + s * R @ (np.asarray(v, float) - p0) for k, v in a.items()}
            solves += 1
            r = LC.solve(sc['W'], sc['L'], sc['S'], a2, sz, traj=tr)
            if r.get('status') != 'ok':
                fails += 1
                for k in TYPES:
                    rows.append(dict(scene=sc['scene'], arm=name, obj=k, disp=None, fail=True))
                continue
            for k in TYPES:
                if k in B0 and k in r['boxes']:
                    d = float(max(abs(r['boxes'][k][i] - B0[k][i]) for i in range(4)))
                    rows.append(dict(scene=sc['scene'], arm=name, obj=k, disp=d, fail=False))

print('系统性偏移：求解 %d 次（失败 %d），结果行 %d' % (solves, fails, len(rows)))
for name, sg_s, sg_t in ARMS:
    sel = [r for r in rows if r['arm'] == name]
    d = np.array([r['disp'] for r in sel if r['disp'] is not None])
    f = 100 * np.mean([r['fail'] or (r['disp'] is not None and r['disp'] > FLIP) for r in sel])
    print('%-8s 尺度 %2.0f%% 朝向 %.0f deg  n=%d  中位 %.3f  p90 %.3f  大位移率 %.1f%%'
          % (name, 100 * sg_s, sg_t, len(sel), np.median(d), np.percentile(d, 90), f))
print()
for k in TYPES:
    print('%-6s' % k, end='')
    for name, _, _ in ARMS:
        sel = [r for r in rows if r['arm'] == name and r['obj'] == k]
        f = 100 * np.mean([r['fail'] or (r['disp'] is not None and r['disp'] > FLIP) for r in sel])
        print('  %5.1f%%' % f, end='')
    print()
json.dump(dict(solves=solves, fails=fails, rows=rows),
          io.open(os.path.join(HERE, 'drift_flip.json'), 'w', encoding='utf-8'), ensure_ascii=False)
