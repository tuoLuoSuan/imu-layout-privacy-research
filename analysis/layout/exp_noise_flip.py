# 锚点噪声多大时布局开始崩？15 个 iTHOR 场景上给真值锚点加高斯噪声，重解，
# 统计每件家具的最大边位移与「翻到另一处」的比例（位移 > 0.5 m 记为翻转）。
import glob, io, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths, sim_eval as SE, layout_core as LC

SIGMAS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30)
N_DRAW = 8
FLIP = 0.5
TYPES = ('bed', 'desk', 'cab', 'chair')
rng = np.random.default_rng(5)

scenes = [s for s in (SE.load_scene(f) for f in sorted(glob.glob(os.path.join(paths.THOR, 'FloorPlan*.json')))) if s]
rows = []
for sc in scenes:
    a = SE.anchors_true(sc); tr = SE.traj_of(sc, a)
    sz = {'bed': sc['sizes']['bed'], 'desk': sc['sizes']['desk'],
          'cab': sc['sizes']['cab'], 'chair': sc['sizes']['chair'][0]}
    base = LC.solve(sc['W'], sc['L'], sc['S'], a, sz, traj=tr)
    if base.get('status') != 'ok':
        continue
    B0 = base['boxes']
    for sig in SIGMAS:
        for _ in range(N_DRAW if sig > 0 else 1):
            a2 = {k: np.asarray(v, float) + (rng.normal(0, sig, 2) if sig > 0 else 0.0) for k, v in a.items()}
            r = LC.solve(sc['W'], sc['L'], sc['S'], a2, sz, traj=tr)
            if r.get('status') != 'ok':
                rows.append(dict(scene=sc['scene'], sigma=sig, obj='*', disp=None, fail=True))
                continue
            for k in TYPES:
                if k not in B0 or k not in r['boxes']:
                    continue
                d = float(max(abs(r['boxes'][k][i] - B0[k][i]) for i in range(4)))
                rows.append(dict(scene=sc['scene'], sigma=sig, obj=k, disp=d, fail=False))

print('求解 %d 次' % len(rows))
print('%-6s %6s %10s %10s %10s' % ('sigma', 'n', '中位位移', 'p90 位移', '翻转率(>0.5m)'))
for sig in SIGMAS:
    sel = [r for r in rows if r['sigma'] == sig]
    d = np.array([r['disp'] for r in sel if r['disp'] is not None])
    f = 100 * np.mean([r['fail'] or (r['disp'] is not None and r['disp'] > FLIP) for r in sel])
    print('%-6.2f %6d %10.3f %10.3f %9.1f%%' % (sig, len(sel), np.median(d) if len(d) else -1,
                                                 np.percentile(d, 90) if len(d) else -1, f))
print()
for k in TYPES:
    print('%-6s' % k, end='')
    for sig in SIGMAS:
        sel = [r for r in rows if r['sigma'] == sig and r['obj'] == k and r['disp'] is not None]
        f = 100 * np.mean([r['disp'] > FLIP for r in sel]) if sel else 0.0
        print('  %5.1f%%' % f, end='')
    print('   （翻转率随 sigma，从 0 到 0.30）')
json.dump(rows, io.open(os.path.join(HERE, 'noise_flip.json'), 'w', encoding='utf-8'), ensure_ascii=False)
