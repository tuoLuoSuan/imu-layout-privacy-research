# 一致性过滤的量化：误拒率、漏拒率、以及「平均」会把锚点拉走多少。
# 事件按真值物体占地采样（人沿物体自由轴走动），加 sigma 位置噪声；
# 离群事件用一个随机的房间内其它位置模拟（就是真实录音里那两次误检）。
import glob, io, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths, sim_eval as SE, identifiability as ID

TOL = ID.TOL
SIGMA = 0.15
N_RUN = 300
rng = np.random.default_rng(11)
CLASSES = (('cab', 'cabinet'), ('chair', 'seated'), ('bed', 'lying'))


def free_axis(box):
    return 0 if (box[2] - box[0]) >= (box[3] - box[1]) else 1


def genuine(box, k):
    ax = free_axis(box); oth = 1 - ax
    lo, hi = box[ax], box[ax + 2]
    c_o = (box[oth] + box[oth + 2]) / 2
    pts = np.zeros((k, 2))
    pts[:, ax] = rng.uniform(lo, hi, k)
    pts[:, oth] = c_o
    return pts + rng.normal(0, SIGMA, (k, 2))


def filter_(pos, size):
    """与 identifiability.consistency 同一判据。"""
    counts = rng.integers(20, 101, len(pos))
    ev = [{'pos': p, 'n': int(n)} for p, n in zip(pos, counts)]
    kept, rej = ID.consistency(ev, size)
    return kept, rej


scenes = [SE.load_scene(f) for f in sorted(glob.glob(os.path.join(paths.THOR, 'FloorPlan*.json')))]
scenes = [s for s in scenes if s]

rec = []
for sc in scenes:
    room = np.array([[0, 0], [sc['W'], 0], [0, sc['L']], [sc['W'], sc['L']]])
    for key, lab in CLASSES:
        if key not in sc['gt']:
            continue
        box = sc['gt'][key]
        size = (box[2] - box[0], box[3] - box[1])
        # A. 全是真事件
        for k in (2, 3, 5, 8):
            fr = 0.0; ea = []; ek = []
            for _ in range(N_RUN):
                pos = genuine(box, k)
                kept, rej = filter_(pos, size)
                fr += len(rej) / k
                allm = pos.mean(0); keepm = pos[kept].mean(0)
                truth = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
                ek.append(np.linalg.norm(keepm - truth))
            rec.append(dict(kind='genuine', scene=sc['scene'], obj=key, k=k,
                            false_reject=fr / N_RUN, err_filtered=float(np.median(ek))))
        # B. 一个离群事件
        for k in (3, 5):
            hit = 0; fr = 0.0; ea = []; ek = []
            for _ in range(N_RUN):
                pos = genuine(box, k - 1)
                out = rng.uniform([0.3, 0.3], [sc['W'] - 0.3, sc['L'] - 0.3])
                pos = np.vstack([pos, out[None, :]])
                permutation = rng.permutation(k)
                pos = pos[permutation]
                outlier_index = int(np.flatnonzero(permutation == k - 1)[0])
                kept, rej = filter_(pos, size)
                hit += outlier_index in rej
                fr += sum(1 for i in rej if i != outlier_index) / (k - 1)
                truth = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
                ea.append(np.linalg.norm(pos.mean(0) - truth))
                ek.append(np.linalg.norm(pos[kept].mean(0) - truth))
            rec.append(dict(kind='outlier', scene=sc['scene'], obj=key, k=k,
                            detect=hit / N_RUN, false_reject=fr / N_RUN,
                            err_all=float(np.median(ea)), err_filtered=float(np.median(ek))))

gen = [r for r in rec if r['kind'] == 'genuine']
out = [r for r in rec if r['kind'] == 'outlier']
print('场景 %d，记录 %d 条' % (len(scenes), len(rec)))
print('A 全真事件：误拒率 中位 %.1f%%，最大 %.1f%%' % (
    100 * np.median([r['false_reject'] for r in gen]), 100 * max(r['false_reject'] for r in gen)))
for k in (2, 3, 5, 8):
    s = [r for r in gen if r['k'] == k]
    print('   k=%d：误拒 %.2f%%，过滤后锚点误差中位 %.2f m' % (
        k, 100 * np.mean([r['false_reject'] for r in s]), np.median([r['err_filtered'] for r in s])))
print('B 一个离群：检出率 中位 %.1f%%，最小 %.1f%%' % (
    100 * np.median([r['detect'] for r in out]), 100 * min(r['detect'] for r in out)))
for k in (3, 5):
    s = [r for r in out if r['k'] == k]
    print('   k=%d：检出 %.0f%%，真事件误拒 %.1f%%，锚点误差 平均后 %.2f -> 过滤后 %.2f m' % (
        k, 100 * np.mean([r['detect'] for r in s]), 100 * np.mean([r['false_reject'] for r in s]),
        np.median([r['err_all'] for r in s]), np.median([r['err_filtered'] for r in s])))
json.dump(rec, io.open(os.path.join(HERE, 'exp_consistency.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
