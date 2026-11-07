# -*- coding: utf-8 -*-
# 稳健性审计：① 区间上界到底有没有信息量（AUC + bootstrap）；② 换容差/换 reach 时哪些结论会翻。
import io, json, os, sys
import numpy as np
import identifiability as ID

HERE = os.path.dirname(os.path.abspath(__file__))
SESS = os.path.join(HERE, '..', '..', 'output', 'layout-recon', 's-59d570ee')
REF = {'bed': (1.17, 1.96, 2.695, 4.045), 'desk': (0.05, 1.05, 0.65, 2.10),
       'cab': (0.05, 0.0, 0.65, 1.05), 'chair': (1.11, 0.92, 1.55, 1.36)}
RNG = np.random.default_rng(11)


def auc(x, y):
    """P(x 里的一例大于 y 里的一例)。"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) == 0 or len(y) == 0:
        return float('nan')
    s = 0.0
    for v in x:
        s += float((v > y).sum()) + 0.5 * float((v == y).sum())
    return s / (len(x) * len(y))


def part_a():
    rows = json.load(io.open(os.path.join(HERE, 'pred_vs_actual.json'), encoding='utf-8'))
    out = {}
    for be in ('place', 'joint'):
        R = [r for r in rows if r['backend'] == be]
        P = np.array([r['pred'] for r in R]); M = np.array([r['meas'] for r in R])
        bad = M > P + 1e-9
        a = auc(M[bad], M[~bad])
        boots = []
        for _ in range(2000):
            idx = RNG.integers(0, len(R), len(R))
            b2 = bad[idx]; m2 = M[idx]
            if b2.sum() and (~b2).sum():
                boots.append(auc(m2[b2], m2[~b2]))
        lo, hi = np.percentile(boots, [2.5, 97.5])
        # 基线：不做区间分析，只用「物体越大误差越大」
        area = np.array([obj_extent(r) for r in R])
        a_size = auc(area[bad], area[~bad])
        out[be] = dict(n=len(R), n_bad=int(bad.sum()), auc=float(a),
                       ci=[float(lo), float(hi)], auc_size=float(a_size),
                       share_err_bad=float(M[bad].sum() / M.sum()) if bad.any() else 0.0,
                       med_bad=float(np.median(M[bad])) if bad.any() else 0.0,
                       med_ok=float(np.median(M[~bad])) if (~bad).any() else 0.0)
    return out


SIZES = {'bed': (1.53, 2.08), 'desk': (0.60, 1.20), 'cab': (0.90, 0.60), 'chair': (0.44, 0.44)}


def obj_extent(r):
    a, b = SIZES.get(r['obj'], (0.6, 0.6))
    return max(a, b)


def part_b():
    old_tol, old_reach = ID.TOL, dict(ID.REACH)
    rows = []
    try:
        for tol in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
            for reach_cab in (0.30, 0.45, 0.60, 0.75):
                ID.TOL = tol
                ID.REACH.update({'cabinet': reach_cab, 'seated': 0.0, 'lying': 0.05})
                res = ID.analyze(SESS, truth=REF)
                w, tin, kinds = [], [], []
                for r in res['rows']:
                    for ax in ('x', 'y'):
                        A = r['axes'][ax]
                        w.append(A['width_m'] if A['width_m'] is not None else float('nan'))
                        tin.append(A['truth_in'])
                        kinds.append(A['prior_kind'])
                w = np.array(w, float)
                tin = [v for v in tin if v is not None]
                rows.append(dict(tol=tol, reach_cab=reach_cab,
                                 cover=int(sum(1 for v in tin if v)), n=len(tin),
                                 med_w=float(np.nanmedian(w)),
                                 n_wide=int(np.nansum(w > tol + 1e-9)),
                                 kinds=kinds,
                                 wide=[r['object'] + ':' + ax
                                       for r in res['rows'] for ax in ('x', 'y')
                                       if r['axes'][ax]['width_m'] is not None
                                       and r['axes'][ax]['width_m'] > tol + 1e-9]))
    finally:
        ID.TOL = old_tol; ID.REACH.update(old_reach)
    return rows


def part_c():
    """只改 lying 的 reach：床沿容差是否会让「床被墙钉死」这个结论翻。"""
    old = dict(ID.REACH)
    out = []
    try:
        for rl in (0.00, 0.05, 0.10, 0.20, 0.40):
            ID.REACH['lying'] = rl
            res = ID.analyze(SESS, truth=REF)
            row = {'reach_lying': rl}
            for r in res['rows']:
                if r['object'] == 'bed':
                    for ax in ('x', 'y'):
                        A = r['axes'][ax]
                        row[ax] = [A['width_m'], A['truth_in']]
            out.append(row)
    finally:
        ID.REACH.update(old)
    return out


if __name__ == '__main__':
    A = part_a(); B = part_b(); C = part_c()
    print('== A 区间上界的信息量（越界 = 实测超过预测）')
    for k, v in A.items():
        print('  %-5s n=%d 越界 %d  AUC %.2f [%.2f, %.2f]  只用尺寸做基线 AUC %.2f'
              % (k, v['n'], v['n_bad'], v['auc'], v['ci'][0], v['ci'][1], v['auc_size']))
        print('        越界样本实测中位 %.2f / 合规 %.2f；越界样本占全部误差质量 %.0f%%'
              % (v['med_bad'], v['med_ok'], 100 * v['share_err_bad']))
    print('== B 容差 × reach 扫描（真实房间 6 个轴参数）')
    print('  tol  reach  cover  med_w  n(宽>tol)  哪些轴')
    for r in B:
        print('  %.2f %.2f   %d/%d   %.3f   %d   %s'
              % (r['tol'], r['reach_cab'], r['cover'], r['n'], r['med_w'], r['n_wide'],
                 ','.join(r['wide']) if r['wide'] else '-'))
    print('== C 只改躺点 reach（床两轴）')
    for r in C:
        print('  reach_lying %.2f  bed x %s  y %s' % (r['reach_lying'], r.get('x'), r.get('y')))
    json.dump(dict(a=A, b=B, c=C), io.open(os.path.join(HERE, 'robust.json'), 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)
    print('saved robust.json')
