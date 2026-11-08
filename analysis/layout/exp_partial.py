# -*- coding: utf-8 -*-
# 部分事件：三锚点不齐时不再整体失败，而是只放「有锚点」的家具。
# 问题：每条交互到底给自己的家具带来多少，给别人的家具带来多少。
import glob, io, json, os, sys
import numpy as np
import sim_eval as SE
import layout_core as LC
import paths

HERE = os.path.dirname(os.path.abspath(__file__))
SUBSETS = [('scl', ('seated', 'cabinet', 'lying')), ('sc', ('seated', 'cabinet')),
           ('sl', ('seated', 'lying')), ('cl', ('cabinet', 'lying')),
           ('s', ('seated',)), ('c', ('cabinet',)), ('l', ('lying',))]
OBJ = {'seated': 'chair', 'cabinet': 'cab', 'lying': 'bed'}
OBJS = ('bed', 'desk', 'cab', 'chair')


def err(box, gt):
    return float(np.hypot((box[0] + box[2] - gt[0] - gt[2]) / 2, (box[1] + box[3] - gt[1] - gt[3]) / 2))


def main():
    rows = []
    files = sorted(glob.glob(os.path.join(paths.THOR, 'FloorPlan*.json')))
    if not files:
        raise ValueError('No scene files found in IMU_LAYOUT_THOR')
    for f in files:
        sc = SE.load_scene(f)
        if not sc:
            continue
        a = SE.anchors_true(sc)
        sz = {'bed': sc['sizes']['bed'], 'desk': sc['sizes']['desk'],
              'cab': sc['sizes']['cab'], 'chair': sc['sizes']['chair'][0]}
        for name, keys in SUBSETS:
            sub = {k: a[k] for k in keys}
            r = LC.solve(sc['W'], sc['L'], sc['S'], sub, sz)
            row = {'scene': sc['scene'], 'subset': name, 'status': r['status'], 'obj': {}}
            if r['status'] == 'ok':
                for k in OBJS:
                    if k in r['boxes'] and k in sc['gt']:
                        row['obj'][k] = [float(x) for x in r['boxes'][k]]
                        row.setdefault('err', {})[k] = err(r['boxes'][k], sc['gt'][k])
            rows.append(row)
    return rows


if __name__ == '__main__':
    rows = main()
    names = [s[0] for s in SUBSETS]
    print('场景数 %d' % len(set(r['scene'] for r in rows)))
    print('== 各子集的求解状态')
    for nm in names:
        st = [r['status'] for r in rows if r['subset'] == nm]
        ok = sum(1 for v in st if v == 'ok')
        print('  %-4s ok %2d / %2d  %s' % (nm, ok, len(st),
              '' if ok == len(st) else ('insufficient %d' % st.count('insufficient')
                                        + ' no_solution %d' % st.count('no_solution'))))
    print('== 每个子集能给哪些家具定值，以及命中率（中心误差 <= 0.5 m）与中位误差')
    print('  子集  ' + ''.join('%-16s' % o for o in OBJS))
    for nm in names:
        line = '  %-4s  ' % nm
        for o in OBJS:
            e = [r['err'][o] for r in rows if r['subset'] == nm and 'err' in r and o in r['err']]
            if not e:
                line += '%-16s' % '-'
            else:
                hit = 100 * np.mean([v <= 0.5 for v in e])
                line += '%-16s' % ('%.2f m / %2d%% (n=%d)' % (np.median(e), hit, len(e)))
        print(line)
    # 交叉影响：删掉一个锚点，别人的框变不变
    print('== 删掉一个锚点后，其他家具的解是否改变（同一个场景、同一后端）')
    base = {(r['scene']): r for r in rows if r['subset'] == 'scl'}
    for nm in ('sc', 'sl', 'cl', 's', 'c'):
        ch = {}
        for r in rows:
            if r['subset'] != nm or r['status'] != 'ok':
                continue
            b = base.get(r['scene'])
            if not b or b['status'] != 'ok':
                continue
            for o in OBJS:
                if o in r['obj'] and o in b.get('obj', {}):
                    d = max(abs(x - y) for x, y in zip(r['obj'][o], b['obj'][o]))
                    ch.setdefault(o, []).append(d > 1e-9)
        print('  去掉 %-4s ' % nm + '  '.join('%s 变 %d/%d' % (o, sum(v), len(v)) for o, v in ch.items()))
    json.dump(rows, io.open(os.path.join(HERE, 'partial.json'), 'w', encoding='utf-8'), indent=1)
    print('saved partial.json')
