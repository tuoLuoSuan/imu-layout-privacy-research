# 可辨识性：每件家具参数的残余区间 = 事件区间 ∩ 先验区间。
# 事件区间：同类动作的每次发生都必须落在同一件家具上，故位置 p 满足 |p - e_i| <= L/2（逐轴），
#           交集宽度 = max(0, L - span)，span 为该轴上的事件锚点跨度。
# 先验区间：贴墙（<= TOL）由墙定死为 0；桌柜相邻（<= TOL）互相定死为 0。
# 两者取交：width = min(事件区间, 先验区间)。动作的次数、时长、走过的路程都不进入公式。
import io, json, os, sys
import numpy as np

HALF = 0.5
TOL = 0.10            # 贴墙 / 相邻判定
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


def prior_width(box, room, size_axis, axis):
    """贴墙 -> 0；不贴墙 -> 房间长度 - 物体长度。"""
    lo, hi = box[axis], box[axis + 2]
    d0, d1 = float(lo), float(room[axis] - hi)
    if min(d0, d1) <= TOL:
        return 0.0, min(d0, d1)
    return max(0.0, float(room[axis] - size_axis)), min(d0, d1)


def analyze(sess, truth=None):
    pred = json.load(io.open(os.path.join(sess, 'prediction.json'), encoding='utf-8'))
    runs = json.load(io.open(os.path.join(sess, 'actions.json'), encoding='utf-8'))['runs']
    t, P = traj(sess)
    evs = events(t, P, runs)
    a = np.radians(pred['rot_deg'])
    c, s = np.cos(a), np.sin(a)
    R = np.array([[c, s], [-s, c]])
    off = (P @ R)[0] - np.array(pred['start_anchored_at'])

    rows = []
    for lab in CLASSES:
        obj = OBJ[lab]
        box = pred['boxes'][obj]
        size = [float(v) for v in pred['sizes'][obj]]
        ev = evs.get(lab, [])
        for e in ev:
            e['room'] = list(map(float, e['pos'] @ R - off))
        kept, rej = consistency(ev, size)
        sub = np.array([ev[i]['room'] for i in kept]) if kept else np.zeros((0, 2))
        row = {'class': lab, 'object': obj, 'n_events': len(ev), 'kept': kept, 'rejected': rej,
               'events': [{'t0': e['t0'], 't1': e['t1'], 'room': e['room']} for e in ev],
               'size_m': size, 'axes': {}}
        for k, ax in enumerate(AXES):
            if len(sub) == 0:
                span = None
                ew = None
            else:
                span = float(sub[:, k].max() - sub[:, k].min())
                ew = max(0.0, size[k] - span)
            pw, gap = prior_width(box, pred['room'], size[k], k)
            row['axes'][ax] = {'span_m': span, 'anchor_width_m': ew, 'prior_width_m': pw,
                               'wall_gap_m': gap,
                               'width_m': None if ew is None else float(min(ew, pw))}
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
    print('%-6s %2s %-9s %6s %6s %6s %6s %6s %6s' %
          ('obj', 'n', 'kept/rejj', 'axis', 'span', 'L', 'event', 'prior', 'width'))
    for r in res['rows']:
        for k, ax in enumerate(AXES):
            A = r['axes'][ax]
            f = lambda v: '   -  ' if v is None else '%.2f' % v
            print('%-6s %2d %-9s %6s %6s %6.2f %6s %6.2f %6s' % (
                r['object'], r['n_events'], '%s/%s' % (r['kept'], r['rejected']), ax,
                f(A['span_m']), r['size_m'][k], f(A['anchor_width_m']),
                A['prior_width_m'], f(A['width_m'])))


if __name__ == '__main__':
    sess = sys.argv[1]
    res = analyze(sess)
    report(res)
    json.dump(res, io.open(os.path.join(sess, 'identifiability.json'), 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)
    print('saved', os.path.join(sess, 'identifiability.json'))
