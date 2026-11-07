# 残余宽度是不是真的预测了误差？
# 在 15 个 iTHOR 场景、真值锚点下，对每件家具取
#   预测 = 两轴残余宽度的大者（span = 0，锚点是一个点）
#   实测 = 两轴中心误差的大者
# 两个后端各算一遍：layout_core 的联合求解 / layout_free 的 place_orders（主表用的那条）。
import glob, io, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths, sim_eval as SE, identifiability as ID, layout_core as LC, layout_free as LF

TYPES = ('bed', 'desk', 'cab', 'chair')


def rank(a):
    a = np.asarray(a, float); o = np.argsort(a, kind='mergesort')
    r = np.empty(len(a), float); r[o] = np.arange(len(a), dtype=float)
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and a[o[j + 1]] == a[o[i]]:
            j += 1
        if j > i:
            r[o[i:j + 1]] = r[o[i:j + 1]].mean()
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = rank(x) - rank(x).mean(), rank(y) - rank(y).mean()
    d = np.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / d) if d > 0 else 0.0


def run(backend):
    rows = []
    for f in sorted(glob.glob(os.path.join(paths.THOR, 'FloorPlan*.json'))):
        sc = SE.load_scene(f)
        if not sc:
            continue
        a = SE.anchors_true(sc); tr = SE.traj_of(sc, a)
        sz = {'bed': sc['sizes']['bed'], 'desk': sc['sizes']['desk'],
              'cab': sc['sizes']['cab'], 'chair': sc['sizes']['chair'][0]}
        if backend == 'joint':
            res = LC.solve(sc['W'], sc['L'], sc['S'], a, sz, traj=tr)
            boxes = res.get('boxes') if res.get('status') == 'ok' else None
        else:
            boxes = LF.place_orders(sc['W'], sc['L'], tr, a, sz)
        if not boxes:
            continue
        room = [sc['W'], sc['L']]
        for k in TYPES:
            if k not in sc['gt'] or k not in boxes:
                continue
            g, p = sc['gt'][k], boxes[k]
            meas, pred = [], []
            for ax in (0, 1):
                ln = float(g[ax + 2] - g[ax])
                w, _ = ID.prior_width(g, room, ln, ax)
                pred.append(min(w, ln))
                meas.append(abs((p[ax] + p[ax + 2]) / 2 - (g[ax] + g[ax + 2]) / 2))
            wp = SE.nearest_wall((p[0] + p[2]) / 2, (p[1] + p[3]) / 2, sc['W'], sc['L'])
            wg = SE.nearest_wall((g[0] + g[2]) / 2, (g[1] + g[3]) / 2, sc['W'], sc['L'])
            rows.append(dict(backend=backend, scene=sc['scene'], obj=k, wall_ok=(wp == wg),
                             pred=float(max(pred)), meas=float(max(meas)),
                             pred_ax=[float(v) for v in pred], meas_ax=[float(v) for v in meas],
                             center=float(np.hypot(meas[0], meas[1]))))
    return rows


allrows = []
for b in ('place', 'joint'):
    R = run(b)
    allrows += R
    P = np.array([r['pred'] for r in R]); M = np.array([r['meas'] for r in R])
    bad = M > P + 1e-9
    print('== %s：%d 个样本' % (b, len(R)))
    print('   中心误差中位 %.2f m；预测中位 %.2f m' % (
        np.median([r['center'] for r in R]), np.median(P)))
    print('   上界成立 %d/%d = %.0f%%；Spearman %.2f' % (
        int((~bad).sum()), len(M), 100 * np.mean(~bad), spearman(P, M)))
    print('   越界 %d 条：实测中位 %.2f，合规 %d 条实测中位 %.2f' % (
        int(bad.sum()), np.median(M[bad]) if bad.any() else 0.0,
        int((~bad).sum()), np.median(M[~bad])))
    for k in TYPES:
        sel = [i for i, r in enumerate(R) if r['obj'] == k]
        q = P[sel]; m = M[sel]
        print('     %-5s n=%2d 预测中位 %.2f  实测中位 %.2f  越界 %d' % (
            k, len(sel), np.median(q), np.median(m), int((m > q + 1e-9).sum())))

R = [r for r in allrows if r['backend'] == 'place']
P = np.array([r['pred'] for r in R]); M = np.array([r['meas'] for r in R]); bad = M > P + 1e-9
wo = np.array([r['wall_ok'] for r in R])
print('== 越界 与 墙判定 的交叉表（place 后端，%d 个样本）' % len(R))
for v in (False, True):
    for w in (False, True):
        sel = (bad == v) & (wo == w)
        if sel.sum():
            print('   %s 上界 & 墙%s：n=%2d  实测中位 %.2f  最大 %.2f' % (
                '越过' if v else '守住', '判对' if w else '判错', int(sel.sum()),
                np.median(M[sel]), M[sel].max()))
print('   墙判对时上界守住 %d/%d；墙判错时守住 %d/%d' % (
    int((~bad[wo]).sum()), int(wo.sum()), int((~bad[~wo]).sum()), int((~wo).sum())))
json.dump(allrows, io.open(os.path.join(HERE, 'pred_vs_actual.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
