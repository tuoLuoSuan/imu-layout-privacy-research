# 可辨识性：每件家具参数的残余区间 = 事件区间 ∩ 先验区间（端点求交，不是宽度取 min）。
# 事件区间：同类动作的每次发生都必须落在同一件家具上，故位置 p 满足 |p - e_i| <= L/2 + EPS（逐轴），
#           交集 = [max e - L/2 - EPS, min e + L/2 + EPS]，宽度 max(0, L + 2EPS - span)。
# 先验区间：贴墙（间隙 <= TOL）-> [0, TOL] 或 [room-L-TOL, room-L]，宽 TOL；
#           与另一件家具相邻（间隙 <= TOL）-> [邻居边, 邻居边 + TOL]，宽 TOL；
#           两者都不满足 -> U 档 [L/2, room - L/2]，宽 room - L（不知道贴哪面墙）。
# 空交集 = 事件与先验矛盾，标 conflict（不是「完全确定」）。动作次数、时长、路程都不进公式。
import io, json, os, sys
import numpy as np

HALF = 0.5
TOL = 0.10            # 贴墙 / 相邻判定
EPS = 0.05            # 锚点位置误差容差，与 leakage_curve.EPS 一致
# 交互锚点是「人所在的位置」，不是家具中心：开柜时人是站在柜门前一臂远，躺是躺在家具边缘。
# 实测（s-59d570ee 对雷达真值）：坐进椅子 0.00 m、躺到床沿 0.08 m、站在柜门前 0.54 m。
REACH = {'cabinet': 0.60, 'seated': 0.0, 'lying': 0.05}
CLASSES = ('cabinet', 'seated', 'lying')
OBJ = {'cabinet': 'cab', 'seated': 'chair', 'lying': 'bed'}
AXES = ('x', 'y')


def traj(sess):
    d = np.load(os.path.join(sess, 'ronin-xy.npy'))
    return d[:, 0] - HALF, np.column_stack([d[:, 1], d[:, 2]])


def events(t, P, runs):
    """每类动作的每一次发生：时间窗 + 锚点（尾部 25% 均值，与锚点定义一致）。"""
    out = {}
    for lab, a1, b1 in runs:
        if lab not in CLASSES or b1 - a1 < 1.0:
            continue
        m = (t >= a1) & (t <= b1)
        if m.sum() < 3:
            continue
        n = max(2, int(m.sum() * 0.25))
        out.setdefault(lab, []).append(
            {'t0': float(a1), 't1': float(b1), 'n': int(m.sum()), 'pos': P[m][-n:].mean(axis=0)})
    return out


def consistency(pos, size):
    """同一件家具的多次交互必须相互相容：以样本最多的一次为种子，纳入距离 <= 物体对角 + TOL 的事件。"""
    if len(pos) < 2:
        return list(range(len(pos))), []
    diag = float(np.hypot(size[0], size[1]))
    seed = int(np.argmax([p['n'] for p in pos]))
    kept = [seed] + [i for i in range(len(pos))
                     if i != seed and np.linalg.norm(pos[i]['pos'] - pos[seed]['pos']) <= diag + TOL]
    kept = sorted(set(kept))
    rej = [i for i in range(len(pos)) if i not in kept]
    return kept, rej


def world_size(box, axis):
    """该轴上的世界长度。尺寸必须取自世界框，不能按 sizes 的声明顺序猜（柜的 [0.9, 0.6]
    在真值框里是 x=0.60 / y=0.90，按顺序取会把逐轴约束套到错误的尺度上）。"""
    return float(box[axis + 2]) - float(box[axis])


def prior_interval(box, room, size_axis, axis, others=None):
    """返回 (lo, hi, kind, gap)。参数化统一为【该轴上物体最小坐标 q】：q = c - L/2。

    与 analyze() 里的事件区间 q in [max e - L - d, min e + d] 同一参数化。
    历史上 free 分支返回 [L/2, room-L/2]（中心），与事件区间的 q 求交会得到很窄、
    却排除真值的区间——这是 2026-11-07 复核指出的第一号错误。
    size_axis 保留在签名里只为向后兼容，实际长度一律取世界框。"""
    lo, hi = float(box[axis]), float(box[axis + 2])
    L = hi - lo
    d0, d1 = lo, float(room[axis] - hi)
    if d0 < -TOL or d1 < -TOL:
        # 负间隙超出容差 = 几何记录本身有问题，不能当成「贴墙」参与统计
        return lo, hi, 'geom_error', min(d0, d1)
    if d0 <= TOL:
        return 0.0, TOL, 'wall_lo', d0
    if d1 <= TOL:
        return float(room[axis] - L) - TOL, float(room[axis] - L), 'wall_hi', d1
    if others:
        p = 1 - axis                      # 垂直轴
        for ob in others:
            # 相邻要求：本轴上首尾相接，且【垂直轴的投影确实重叠】
            # （旧写法拿本物体的当前轴范围去和别人垂直轴比，相距很远的也会被判相邻）
            if min(float(box[p + 2]), float(ob[p + 2])) - max(float(box[p]), float(ob[p])) <= 0.0:
                continue
            olo, ohi = float(ob[axis]), float(ob[axis + 2])
            if abs(lo - ohi) <= TOL:
                return ohi, ohi + TOL, 'adjacent_lo', abs(lo - ohi)
            if abs(hi - olo) <= TOL:
                return olo - L - TOL, olo - L, 'adjacent_hi', abs(hi - olo)
    return 0.0, float(room[axis]) - L, 'free', None


def analyze(sess, truth=None):
    pred = json.load(io.open(os.path.join(sess, 'prediction.json'), encoding='utf-8'))
    runs = json.load(io.open(os.path.join(sess, 'actions.json'), encoding='utf-8'))['runs']
    t, P = traj(sess)
    evs = events(t, P, runs)
    a = np.radians(pred['rot_deg'])
    c, s = np.cos(a), np.sin(a)
    R = np.array([[c, s], [-s, c]])
    off = (P @ R)[0] - np.array(pred['start_anchored_at'])

    boxes = pred['boxes']
    rows = []
    for lab in CLASSES:
        obj = OBJ[lab]
        box = boxes[obj]
        # 逐轴长度取世界框（sizes 的顺序是家具局部坐标，柜/桌的顺序与世界轴不一致）
        size = [world_size(box, 0), world_size(box, 1)]
        others = [boxes[o] for o in boxes if o != obj]
        ev = evs.get(lab, [])
        for e in ev:
            e['room'] = list(map(float, e['pos'] @ R - off))
        kept, rej = consistency(ev, size)
        sub = np.array([ev[i]['room'] for i in kept]) if kept else np.zeros((0, 2))
        row = {'class': lab, 'object': obj, 'n_events': len(ev), 'kept': kept, 'rejected': rej,
               'events': [{'t0': e['t0'], 't1': e['t1'], 'room': e['room']} for e in ev],
               'size_m': size, 'declared_size': [float(v) for v in pred['sizes'][obj]], 'axes': {}}
        for k, ax in enumerate(AXES):
            reach = REACH[lab]
            if len(sub) == 0:
                span = None
                e_lo, e_hi = -np.inf, np.inf
                bad = False
            else:
                span = float(sub[:, k].max() - sub[:, k].min())
                # 约束 |e - (min + L/2)| <= L/2 + d  =>  min in [e - L - d, e + d]
                d = reach + EPS
                e_lo = float(sub[:, k].max()) - size[k] - d
                e_hi = float(sub[:, k].min()) + d
                # 事件区间为空：这些事件不可能落在同一件家具上 —— 矛盾，不是「完全确定」。
                bad = span > size[k] + 2 * (reach + EPS) + TOL
            p_lo, p_hi, kind, gap = prior_interval(box, pred['room'], size[k], k, others)
            if bad:
                w = None
                conflict = True
                lo = hi = None
            else:
                lo, hi = max(e_lo, p_lo), min(e_hi, p_hi)
                w = max(0.0, float(hi - lo))
                conflict = bool(w <= 0.0 and np.isfinite(e_lo))
            tin = None
            if truth and obj in truth and lo is not None:
                tq = float(truth[obj][k])
                tin = bool(lo - 1e-9 <= tq <= hi + 1e-9)
            row['axes'][ax] = {'span_m': span, 'reach_m': reach,
                               'event_interval': [None if not np.isfinite(e_lo) else e_lo,
                                                  None if not np.isfinite(e_hi) else e_hi],
                               'truth_q': None if not (truth and obj in truth) else float(truth[obj][k]),
                               'truth_in': tin,
                               'prior_interval': [float(p_lo), float(p_hi)], 'prior_kind': kind,
                               'wall_gap_m': gap, 'inconsistent': bool(bad), 'conflict': conflict,
                               'width_m': None if w is None else float(w)}
        if truth and obj in truth:
            tb = truth[obj]
            row['error_m'] = float(np.hypot((box[0] + box[2] - tb[0] - tb[2]) / 2,
                                            (box[1] + box[3] - tb[1] - tb[3]) / 2))
            row['max_abs_m'] = float(max(abs(box[i] - tb[i]) for i in range(4)))
            row['box'] = [float(v) for v in box]
            row['truth'] = [float(v) for v in tb]
        rows.append(row)
    return {'session': os.path.basename(os.path.normpath(sess)), 'tol_m': TOL,
            'rot_deg': pred['rot_deg'], 'room': pred['room'], 'rows': rows}


def report(res):
    print('%-6s %2s %-9s %5s %6s %6s %-11s %6s %6s' %
          ('obj', 'n', 'kept/rej', 'axis', 'span', 'L', 'prior', 'prior_w', 'width'))
    for r in res['rows']:
        for k, ax in enumerate(AXES):
            A = r['axes'][ax]
            f = lambda v: '   -  ' if v is None else '%.2f' % v
            print('%-6s %2d %-9s %5s %6s %6.2f %-11s %6.2f %6s %s' % (
                r['object'], r['n_events'], '%s/%s' % (r['kept'], r['rejected']), ax,
                f(A['span_m']), r['size_m'][k], A['prior_kind'],
                A['prior_interval'][1] - A['prior_interval'][0],
                f(A['width_m']),
                'INCONSISTENT' if A['inconsistent'] else ('CONFLICT' if A['conflict'] else '')))


if __name__ == '__main__':
    sess = sys.argv[1]
    res = analyze(sess)
    report(res)
    json.dump(res, io.open(os.path.join(sess, 'identifiability.json'), 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)
    print('saved', os.path.join(sess, 'identifiability.json'))
