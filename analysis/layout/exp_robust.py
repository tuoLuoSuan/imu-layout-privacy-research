# -*- coding: utf-8 -*-
# 稳健性审计：① 区间上界到底有没有信息量（AUC + bootstrap）；② 换容差/换 reach 时哪些结论会翻。
import io, json, os, sys
import numpy as np
import identifiability as ID
import paths

HERE = os.path.dirname(os.path.abspath(__file__))
SESS = paths.SESSION
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


def predictive_summary(rows, repeats=2000, error_threshold=0.5):
    """Exploratory oracle-width ranking of a fixed true-error endpoint."""
    prediction = np.array([r['pred'] for r in rows])
    measured = np.array([r['meas'] for r in rows])
    failed = measured > error_threshold
    point = auc(prediction[failed], prediction[~failed])
    scenes = sorted({r['scene'] for r in rows})
    blocks = [np.array([i for i, r in enumerate(rows) if r['scene'] == scene]) for scene in scenes]
    rng = np.random.default_rng(11)
    boots, size_boots = [], []
    size = np.array([obj_extent(r) for r in rows])
    for _ in range(repeats):
        selected = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])
        labels = failed[selected]
        if labels.any() and (~labels).any():
            score = prediction[selected]
            boots.append(auc(score[labels], score[~labels]))
            size_score = size[selected]
            size_boots.append(auc(size_score[labels], size_score[~labels]))
    limits = np.percentile(boots, [2.5, 97.5]).tolist() if boots else [None, None]
    size_limits = np.percentile(size_boots, [2.5, 97.5]).tolist() if size_boots else [None, None]
    violations = measured > prediction + 1e-9
    return dict(n=len(rows), n_rooms=len(scenes), n_bad=int(violations.sum()),
                n_failed=int(failed.sum()), auc=float(point), ci=limits,
                auc_size=auc(size[failed], size[~failed]), error_threshold_m=error_threshold,
                ci_size=size_limits,
                endpoint='maximum axis centre error above threshold',
                score_source='oracle geometry width; exploratory, not a runtime risk model',
                bootstrap_unit='room',
                share_err_bad=float(measured[violations].sum() / measured.sum()) if measured.sum() else 0.0,
                med_bad=float(np.median(measured[violations])) if violations.any() else None,
                med_ok=float(np.median(measured[~violations])) if (~violations).any() else None)


def part_a():
    rows = json.load(io.open(os.path.join(HERE, 'pred_vs_actual.json'), encoding='utf-8'))
    return {backend: predictive_summary([r for r in rows if r['backend'] == backend])
            for backend in ('place', 'joint')}


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
    print('== A 探索性 oracle 宽度诊断（端点为轴向中心误差 >0.5 m，按房重抽）')
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
