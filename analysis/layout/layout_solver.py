# 唯一求解器：所有入口（analyze / compare / 评价）都调这里，输出一致的 prediction.json。
# 规则：房间外框与家具尺寸为已知先验；柜墙由「手臂够得着」的支持度决定；桌柜同墙；椅子正对桌子；
#       床尾线过躺点、床朝背离走道方向伸出；床与椅子允许轨迹进入占地（不算错误）。
import numpy as np, json, io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reconstruct_blind as RB

W, L = RB.W, RB.L
S_PT = RB.S_PT
BED_W, BED_L = RB.BED_W, RB.BED_L
DEPTH, DESK_LEN, CAB_LEN = 0.60, 1.20, 0.90
CHAIR_S, CH_W = 0.44, 0.55
ARM_MID, ARM_TOL = 0.575, 0.175
SIGMA = 0.30                       # 似然带宽：两路锚点联合，AI2-THOR 24 场景噪声扫描标定
D_CHAIR = CH_W + DEPTH             # 椅心到桌墙 = 1.15
D_CAB = ARM_MID + DEPTH            # 站位到柜墙 = 1.175
WALLS = ('left', 'right', 'down', 'up')
VERSION = 'layout-solver-2'   # v2: 四面墙由坐/柜两路锚点联合似然打分，替代单锚点硬带

def support(ch, ca):
    """两路锚点（坐、开柜）联合给四面墙打分；缺哪一路就只用另一路（单锚点）。
    返回 (似然, 四墙距离明细)；缺失的那一路明细为 None。"""
    dch = None if ch is None else {'left': ch[0], 'right': W - ch[0], 'down': ch[1], 'up': L - ch[1]}
    dca = None if ca is None else {'left': ca[0], 'right': W - ca[0], 'down': ca[1], 'up': L - ca[1]}
    s = {}
    for k in WALLS:
        l1 = 1.0 if dch is None else np.exp(-0.5 * ((dch[k] - D_CHAIR) / SIGMA) ** 2)
        l2 = 1.0 if dca is None else np.exp(-0.5 * ((dca[k] - D_CAB) / SIGMA) ** 2)
        s[k] = float(l1 * l2)
    return s, {'chair': dch, 'cabinet': dca}

def premise_check(ch, ca):
    """前提自检（无需真值）：椅子单独定的墙 vs 柜子单独定的墙。
    两者不一致时，「椅子在桌前」这一结构前提可疑，输出的候选集不可信。
    AI2-THOR 15 场景实测：一致时覆盖 8/8，不一致时覆盖 3/7。"""
    dch = {'left': ch[0], 'right': W - ch[0], 'down': ch[1], 'up': L - ch[1]}
    dca = {'left': ca[0], 'right': W - ca[0], 'down': ca[1], 'up': L - ca[1]}
    wc = min(WALLS, key=lambda k: abs(dch[k] - D_CHAIR))
    wk = min(WALLS, key=lambda k: abs(dca[k] - D_CAB))
    return wc, wk, wc == wk

def box_bed(li, u, tsh):
    v = np.array([-u[1], u[0]])
    bc = li + u*(BED_L/2) + v*tsh
    if abs(u[0]) > 0: return (bc[0]-BED_L/2, bc[1]-BED_W/2, bc[0]+BED_L/2, bc[1]+BED_W/2)
    return (bc[0]-BED_W/2, bc[1]-BED_L/2, bc[0]+BED_W/2, bc[1]+BED_L/2)

def build(deg, P, A, wall, beddir, tsh, avail=None):
    """按「有哪些锚点」放家具：柜要 cabinet，桌要 cabinet+seated，椅要 seated，床要 lying。
    缺锚点的家具直接不出现（部分解），而不是整体失败。"""
    avail = set(A) if avail is None else set(avail)
    a = np.radians(deg); c, s = np.cos(a), np.sin(a); R = np.array([[c, s], [-s, c]])
    Q = P @ R
    off = Q[0] - S_PT
    Q = Q - off
    ch = A['seated'] @ R - off if 'seated' in avail else None
    ca = A['cabinet'] @ R - off if 'cabinet' in avail else None
    li = A['lying'] @ R - off if 'lying' in avail else None
    axis = 'x' if wall in ('left', 'right') else 'y'
    def slab(along, ln):
        if wall == 'left':  return (0.0, along - ln/2, DEPTH, along + ln/2)
        if wall == 'right': return (W - DEPTH, along - ln/2, W, along + ln/2)
        if wall == 'down':  return (along - ln/2, 0.0, along + ln/2, DEPTH)
        return (along - ln/2, L - DEPTH, along + ln/2, L)
    boxes = {}
    if ca is not None:
        ca_along = ca[1] if axis == 'x' else ca[0]
        boxes['cab'] = slab(ca_along, CAB_LEN)
    if ch is not None:
        boxes['chair'] = (ch[0]-CHAIR_S/2, ch[1]-CHAIR_S/2, ch[0]+CHAIR_S/2, ch[1]+CHAIR_S/2)
    if ca is not None and ch is not None:
        ch_along = ch[1] if axis == 'x' else ch[0]
        gap = (DESK_LEN + CAB_LEN)/2 + 0.02
        desk_along = ch_along if abs(ch_along - ca_along) >= gap else (ca_along + gap if ch_along >= ca_along else ca_along - gap)
        boxes['desk'] = slab(desk_along, DESK_LEN)
    if li is not None:
        boxes['bed'] = box_bed(li, beddir, tsh)
    if not boxes:
        return None
    ks = list(boxes)
    for i in range(len(ks)):
        for j in range(i+1, len(ks)):
            a1, a2 = boxes[ks[i]], boxes[ks[j]]
            if min(a1[2], a2[2]) - max(a1[0], a2[0]) > 0.02 and min(a1[3], a2[3]) - max(a1[1], a2[1]) > 0.02:
                return None
    out = max(0.0, -min(b[0] for b in boxes.values())) + max(0.0, max(b[2] for b in boxes.values()) - W) \
        + max(0.0, -min(b[1] for b in boxes.values())) + max(0.0, max(b[3] for b in boxes.values()) - L)
    if out > 0.05: return None
    return Q, boxes

def watch_block(sess):
    """手表通道（三轴加速度）的旁证摘要；无手表数据时返回 None，不影响求解。"""
    try:
        import watch_channel as WC
        acts = None
        ap = os.path.join(sess, 'actions.json')
        if os.path.exists(ap):
            acts = [tuple(r) for r in json.load(io.open(ap, encoding='utf-8'))['runs']]
        return WC.summarize(sess, acts)
    except Exception as e:
        return {'status': 'error', 'error': str(e)[:120]}

def solve(sess, save=True, anchors=None, allow_partial=False):
    """allow_partial=True 时只放「有锚点」的家具，并允许单锚点定墙（部分解）。
    默认 False，保持生产行为：三锚点不齐就 missing_action。"""
    t, P, lab, A = RB.anchors_from(sess)
    if anchors is not None:
        A = anchors
    wx = watch_block(sess)
    avail = [k for k in ('seated', 'cabinet', 'lying') if k in A]
    missing = [k for k in ('seated', 'cabinet', 'lying') if k not in A]
    if allow_partial and not ({'seated', 'cabinet'} & set(avail)):
        _p = {'version': VERSION, 'status': 'insufficient', 'missing': missing, 'available': avail,
              'session': os.path.basename(os.path.normpath(sess)), 'watch': wx,
              'reason': 'wall inference needs at least one of seated / cabinet anchors'}
        if save:
            json.dump(_p, io.open(os.path.join(sess, 'prediction.json'), 'w', encoding='utf-8'), indent=1)
        return _p
    if missing and not allow_partial:
        _p = {'version': VERSION, 'status': 'missing_action', 'missing': missing, 'anchors': {},
              'session': os.path.basename(os.path.normpath(sess)), 'watch': wx}
        if save:
            json.dump(_p, io.open(os.path.join(sess, 'prediction.json'), 'w', encoding='utf-8'), indent=1)
        return _p
    best = None; cands = []
    for deg in np.arange(0, 360, 1.0):
        a = np.radians(deg); c, s = np.cos(a), np.sin(a); R = np.array([[c, s], [-s, c]])
        off = (P @ R)[0] - S_PT
        _ch = A['seated'] @ R - off if 'seated' in avail else None
        _ca = A['cabinet'] @ R - off if 'cabinet' in avail else None
        sup, dist = support(_ch, _ca)
        for wall in WALLS:
            if sup[wall] <= 0.0: continue
            for bd in (np.array([1.0,0.]), np.array([-1.0,0.]), np.array([0.,1.0]), np.array([0.,-1.0])):
                for tsh in (-0.5, -0.25, 0.0, 0.25, 0.5):
                    r = build(deg, P, A, wall, bd, tsh, avail)
                    if r is None: continue
                    Q, boxes = r
                    pen = 0.0
                    for nm in ('cab', 'desk'):
                        if nm not in boxes: continue
                        b = boxes[nm]
                        pen += float(np.mean((Q[:,0]>b[0]+0.05)&(Q[:,0]<b[2]-0.05)&(Q[:,1]>b[1]+0.05)&(Q[:,1]<b[3]-0.05)))
                    sc = pen*4.0 - sup[wall]*0.6
                    cands.append({'score': float(sc), 'rot': float(deg), 'wall': wall,
                                  'support': float(sup[wall]), 'dist': float(dist['cabinet'][wall])})
                    if best is None or sc < best[0]:
                        best = (sc, deg, wall, bd, tsh, boxes, Q, sup, dist, pen)
    if best is None:
        _p = {'version': VERSION, 'status': 'no_solution', 'session': os.path.basename(os.path.normpath(sess)),
              'anchors': {k: [float(v[0]), float(v[1])] for k, v in A.items()},
              'reason': 'no wall satisfies the arm-reach band, or furniture does not fit',
              'watch': wx}
        if save:
            json.dump(_p, io.open(os.path.join(sess, 'prediction.json'), 'w', encoding='utf-8'), indent=1)
        return _p
    sc, deg, wall, bd, tsh, boxes, Q, sup, dist, pen = best
    _a = np.radians(deg); _R = np.array([[np.cos(_a), np.sin(_a)], [-np.sin(_a), np.cos(_a)]])
    _off = (P @ _R)[0] - S_PT
    anc = {k: [float((A[k] @ _R - _off)[0]), float((A[k] @ _R - _off)[1])] for k in avail}
    if 'seated' in avail and 'cabinet' in avail:
        _wc, _wk, _ok = premise_check(A['seated'] @ _R - _off, A['cabinet'] @ _R - _off)
    else:
        _wc, _wk, _ok = None, None, None
    cands.sort(key=lambda d: d['score'])
    walls_top = {}
    for c2 in cands[:20]:
        walls_top[c2['wall']] = walls_top.get(c2['wall'], 0) + 1
    pred = {
        'version': VERSION, 'status': 'ok' if len(avail) == 3 else 'partial',
        'session': os.path.basename(os.path.normpath(sess)),
        'rot_deg': float(deg), 'start_anchored_at': [float(x) for x in S_PT],
        'room': [W, L],
        'cabinet_wall': wall, 'wall_support': float(sup[wall]),
        'wall_distance_m': None if dist['cabinet'] is None else float(dist['cabinet'][wall]),
        'chair_wall_distance_m': None if dist['chair'] is None else float(dist['chair'][wall]),
        'available': avail,
        'candidate_walls_top20': walls_top,
        'boxes': {k: [float(x) for x in v] for k, v in boxes.items()},
        'sizes': {'bed': [BED_W, BED_L], 'desk': [DESK_LEN, DEPTH], 'cab': [CAB_LEN, DEPTH], 'chair': [CHAIR_S, CHAIR_S]},
        'anchors': anc,
        'desk_cab_pass_through': float(pen),
        'premise': {'chair_wall': _wc, 'cabinet_wall': _wk, 'ok': bool(_ok)},
        'watch': wx,
        'candidates': cands[:20],
    }
    if save:
        json.dump(pred, io.open(os.path.join(sess, 'prediction.json'), 'w', encoding='utf-8'), indent=1)
    return pred, Q

if __name__ == '__main__':
    sess = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('IMU_LAYOUT_SESSION', '')
    out = solve(sess)
    p = out[0] if isinstance(out, tuple) else out
    print(json.dumps({k: p[k] for k in ('version','status','rot_deg','cabinet_wall','wall_support','candidate_walls_top20') if k in p}, ensure_ascii=False, indent=1))
    if p.get('status') == 'ok':
        for k, v in p['boxes'].items(): print(' %-5s %s' % (k, [round(x,2) for x in v]))