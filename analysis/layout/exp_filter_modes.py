"""候选集 + 一致性过滤：把 top-K 当假设集合，再用「互相一致」把假设剪掉。

背景（RESULTS §5）：K=1 的 argmax 过度自信（床 5/14），并上 top-20 能覆盖到 14/14，
但那是「集合里有对的」，不是「输出对」。这里问的是第三个问题：
在没有任何真值信息的前提下，用候选之间的一致性把 collection 剪成一个答案，
能不能既保住覆盖率、又把「又窄又错」的比例压下来。

过滤规则（不看真值）：两条候选互相一致 = 四件家具的中心两两距离 <= 该家具对角 + 0.10 m。
取「一致伙伴最多」的候选作种子，其一致集合为输出簇，簇内取到其余成员中心距离和最小的那条当代表。
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout_core as LC
import paths
import sim_eval as SE

HIT = 0.50
TOL = 0.10
KS = (1, 5, 10, 20)


def centre(b):
    return np.array([(b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0])


def diag(b):
    return float(np.hypot(b[2] - b[0], b[3] - b[1]))


def consistent(a, b):
    for obj in ('bed', 'desk', 'cab', 'chair'):
        if obj not in a.get('boxes', {}) or obj not in b.get('boxes', {}):
            continue
        d = diag(a['boxes'][obj])
        if np.linalg.norm(centre(a['boxes'][obj]) - centre(b['boxes'][obj])) > d + TOL:
            return False
    return True


def filter_candidates(cands):
    """返回 (代表候选, 簇大小总候选数, 簇内中心最大距离)。"""
    n = len(cands)
    if n == 0:
        return None, 0, 0.0
    adj = [[consistent(cands[i], cands[j]) for j in range(n)] for i in range(n)]
    counts = [sum(row) for row in adj]
    seed = int(np.argmax(counts))
    cluster = [j for j in range(n) if adj[seed][j]]
    if len(cluster) == 1:
        return cands[seed], 1, 0.0
    pts = np.array([np.concatenate([centre(cands[j]['boxes'][o]) for o in ('bed', 'desk', 'cab', 'chair')
                                    if o in cands[j].get('boxes', {})]) for j in cluster])
    medoid = int(np.argmin(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(axis=2).sum(axis=1)))
    spread = float(np.linalg.norm(pts - pts[0], axis=1).max())
    return cands[cluster[medoid]], len(cluster), spread


def score(boxes, truth):
    rec = {}
    for obj, gt in truth.items():
        if obj not in boxes:
            rec[obj] = None
            continue
        err = float(np.linalg.norm(centre(boxes[obj]) - centre(gt)))
        rec[obj] = {'err': err, 'hit': bool(err <= HIT), 'width': float(np.hypot(boxes[obj][2] - boxes[obj][0],
                                                                                 boxes[obj][3] - boxes[obj][1]))}
    return rec


def run():
    scenes = [SE.load_scene(f) for f in sorted(glob.glob(os.path.join(paths.THOR, 'FloorPlan*.json')))]
    scenes = [s for s in scenes if s]
    rows = []
    for sc in scenes:
        sz = {'bed': sc['sizes']['bed'], 'desk': sc['sizes']['desk'],
              'cab': sc['sizes']['cab'], 'chair': sc['sizes']['chair'][0]}
        A = SE.anchors_true(sc)
        tr = SE.traj_of(sc, A)
        res = LC.solve(sc['W'], sc['L'], sc['S'], A, sz, traj=tr, candidate_limit=None)
        if res.get('status') != 'ok':
            rows.append(dict(scene=sc['scene'], failed=True))
            continue
        cands = res['candidates']
        for K in KS:
            sub = cands[:K]
            rep, n_cluster, spread = filter_candidates(sub)
            naive = {}
            for obj in ('bed', 'desk', 'cab', 'chair'):
                errs = [np.linalg.norm(centre(c['boxes'][obj]) - centre(sc['gt'][obj]))
                        for c in sub if obj in c.get('boxes', {})]
                naive[obj] = {'best_err': float(min(errs)) if errs else None,
                              'hit': bool(errs and min(errs) <= HIT)}
            rows.append(dict(scene=sc['scene'], K=K, n_cands=len(sub), cluster=n_cluster, spread=spread,
                             naive=naive,
                             filtered=score(rep['boxes'], sc['gt']) if rep else None,
                             rep_wall=rep.get('wall') if rep else None))
    out = dict(hit_m=HIT, tol=TOL, ks=list(KS), rows=rows)
    with open(os.path.join(HERE, 'filter_modes.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return out


def report(out):
    rows = [r for r in out['rows'] if not r.get('failed')]
    print('场景 %d（失败 %d）' % (len({r['scene'] for r in rows}), sum(1 for r in out['rows'] if r.get('failed'))))
    print('%-4s %26s %26s' % ('K', '覆盖：集合里有对的', '过滤成单答案：代表对'))
    for K in out['ks']:
        sub = [r for r in rows if r['K'] == K]
        line = ['%-4d' % K]
        for key in ('naive', 'filtered'):
            cells = []
            for obj in ('bed', 'desk', 'cab', 'chair'):
                if key == 'naive':
                    v = [r['naive'][obj]['hit'] for r in sub if r['naive'][obj]['hit'] is not None]
                else:
                    v = [r['filtered'][obj]['hit'] for r in sub if r['filtered'] and r['filtered'].get(obj)]
                cells.append('%3.0f%%' % (100 * np.mean(v)) if v else '  - ')
            line.append(' '.join(cells))
        print(' '.join(line))
    print('（列序：床 桌 柜 椅）')
    for K in out['ks']:
        sub = [r for r in rows if r['K'] == K and r['filtered']]
        err = [r['filtered'][o]['err'] for r in sub for o in ('bed', 'desk', 'cab', 'chair') if r['filtered'].get(o)]
        narrow_wrong = [1 for r in sub for o in ('bed', 'desk', 'cab', 'chair')
                        if r['filtered'].get(o) and r['filtered'][o]['err'] > HIT and r['spread'] < 0.5]
        clu = [r['cluster'] / r['n_cands'] for r in sub]
        print('K=%-3d 代表误差中位 %.3f m，窄却错 %d 例，簇占候选比中位 %.2f'
              % (K, float(np.median(err)), len(narrow_wrong), float(np.median(clu))))


if __name__ == '__main__':
    report(run())
