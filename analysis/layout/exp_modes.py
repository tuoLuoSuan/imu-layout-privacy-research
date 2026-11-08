# 多模式候选：不选一个答案，而是留一组假设，看「覆盖真值」与「区域大小」怎么一起变。
#
# 为什么需要：单模式求解器必须在离散候选（柜墙 × 桌墙 × 床朝向 × 间隙）里 argmax，
# 一旦 argmax 挑错，输出是「又窄又错」。这里把 top-K 候选并起来当输出集合，
# 用两个数评价：命中（集合里只要有一个解，误差 <= 0.5 m）与区域（集合的包围盒面积）。
import io, json, os, sys, glob
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout_core as LC
import sim_eval as SE

TYPES = ('bed', 'desk', 'cab', 'chair')
HIT = 0.50          # 命中判据：中心误差 <= 0.5 m（与噪声实验的「大位移」阈值一致）
KS = (1, 2, 3, 5, 10, 20)


def centre(b):
    return np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2])


def union_area(boxes):
    """候选框并集的面积（用网格近似太慢，这里用「并集包围盒」当区域大小的上界度量，
    并另报两两最大距离）。"""
    x0 = min(b[0] for b in boxes); x1 = max(b[2] for b in boxes)
    y0 = min(b[1] for b in boxes); y1 = max(b[3] for b in boxes)
    return float((x1 - x0) * (y1 - y0)), float(np.hypot(x1 - x0, y1 - y0))


def longest_axis_hit(box, gt, axis):
    """该轴是否被覆盖：真值中心落在候选区间 [b_axis_center ± 0.5] 内。"""
    c = (box[axis] + box[axis + 2]) / 2
    g = (gt[axis] + gt[axis + 2]) / 2
    return abs(c - g) <= HIT


def evaluate_candidate_set(candidates, truth):
    rec = {}
    for obj, target in truth.items():
        boxes = [candidate['boxes'][obj] for candidate in candidates if obj in candidate.get('boxes', {})]
        if not boxes:
            rec[obj] = {'hit': False, 'area': None, 'diag': None, 'n': 0,
                        'best_err': None, 'center_diameter': None, 'center_envelope_area': None}
            continue
        centers = np.array([centre(box) for box in boxes])
        errors = np.linalg.norm(centers - centre(target), axis=1)
        area, diag = union_area(boxes)
        diameter = float(np.linalg.norm(centers[:, None] - centers[None, :], axis=2).max())
        rec[obj] = {'hit': bool(errors.min() <= HIT), 'area': area, 'diag': diag,
                    'n': len(boxes), 'best_err': float(errors.min()), 'center_diameter': diameter,
                    'center_envelope_area': float(np.prod(np.ptp(centers, axis=0)))}
    rec['full_layout_hit'] = any(
        all(obj in candidate.get('boxes', {}) and
            np.linalg.norm(centre(candidate['boxes'][obj]) - centre(target)) <= HIT
            for obj, target in truth.items()) for candidate in candidates)
    return rec


def run_scene(sc):
    sz = {'bed': sc['sizes']['bed'], 'desk': sc['sizes']['desk'],
          'cab': sc['sizes']['cab'], 'chair': sc['sizes']['chair'][0]}
    A = SE.anchors_true(sc)
    tr = SE.traj_of(sc, A)
    res = LC.solve(sc['W'], sc['L'], sc['S'], A, sz, traj=tr, candidate_limit=None)
    if res.get('status') != 'ok':
        return None, res
    cands = res['candidates']
    out = []
    for K in KS:
        sub = cands[:K]
        rec = dict(K=K, **evaluate_candidate_set(sub, sc['gt']))
        out.append(rec)
    # 模式数与「每模式留一个代表」臂：不需要保留 20 个近重复候选
    seen = set(); reps = []
    for c in cands:
        key = (c['wall'], c['desk_wall'], tuple(c.get('bed_direction') or ()))
        if key in seen:
            continue
        seen.add(key); reps.append(c)
    rec = dict(K='modes', **evaluate_candidate_set(reps, sc['gt']))
    out.append(rec)
    return {'rows': out, 'n_modes': len(seen), 'n_cands': len(cands)}, res


if __name__ == '__main__':
    scenes = [SE.load_scene(f) for f in sorted(glob.glob(os.path.join(__import__('paths').THOR, 'FloorPlan*.json')))]
    scenes = [s for s in scenes if s]
    print('场景 %d' % len(scenes))
    per_K = {str(K): [] for K in KS}
    per_K['modes'] = []
    fails = 0
    modes = []
    for sc in scenes:
        r, res = run_scene(sc)
        if r is None:
            fails += 1
            for K in list(KS) + ['modes']:
                row = dict(K=K, **evaluate_candidate_set([], sc['gt']))
                row['failed'] = True
                per_K[str(K)].append(row)
            continue
        modes.append(r['n_modes'])
        for row in r['rows']:
            per_K[str(row['K'])].append(row)
    print('求解失败 %d' % fails)
    print('%-5s %8s %8s %8s %8s %8s' % ('K', 'bed', 'desk', 'cab', 'chair', 'area_desk'))
    for K in list(KS) + ['modes']:
        rows = per_K[str(K)]
        line = ['%-5s' % K]
        for k in ('bed', 'desk', 'cab', 'chair'):
            v = [r[k]['hit'] for r in rows if k in r]
            line.append('%7.0f%%' % (100 * np.mean(v)) if v else '    -  ')
        a = [r['desk']['area'] for r in rows if 'desk' in r and r['desk']['area'] is not None]
        line.append('%8.2f' % np.median(a) if a else '    -  ')
        print(' '.join(line))
    print('模式数（柜墙×桌墙×床方向）中位 %d，最大 %d' % (int(np.median(modes)), max(modes)))
    for k in ('bed', 'desk', 'cab'):
        e = [r[k]['best_err'] for r in per_K['20'] if k in r and r[k]['best_err'] is not None]
        e1 = [r[k]['best_err'] for r in per_K['1'] if k in r and r[k]['best_err'] is not None]
        print('%-5s 最优候选误差中位：K=1 %.2f m / K=20 %.2f m' % (k, np.median(e1), np.median(e)))
    json.dump({'scenes': len(scenes), 'fails': fails, 'hit_m': HIT,
               'per_K': {str(K): per_K[str(K)] for K in list(KS) + ['modes']}, 'n_modes': modes},
              io.open(os.path.join(HERE, 'modes.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
