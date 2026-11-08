# 通用布局求解核心：房间尺寸、起点、三个锚点、家具尺寸全部作为参数传入。
# 模拟用参数化后端；真实单房仍由 layout_solver 独立求解，二者参数不可混称。
import numpy as np

DEFAULTS = dict(SIGMA=0.30, CH_W=0.55, REACH=0.575, W_PEN=4.0, W_SUPPORT=0.6)

def solve(W, L, S, anchors, sizes, opt=None, traj=None, avail=None, candidate_limit=20):
    """avail 缺省 = anchors 的全部键。给子集时只放「有锚点」的家具（部分解），
    定墙至少需要 seated / cabinet 之一，否则返回 status=insufficient。"""
    o = dict(DEFAULTS); o.update(opt or {})
    avail = set(anchors) if avail is None else set(avail)
    SIGMA = o['SIGMA']; CH_W = o['CH_W']; REACH = o['REACH']
    bw, bl = sizes['bed']; ddep, dlen = sizes['desk']; cd, cl = sizes['cab']; cs = sizes['chair']
    DCH = CH_W + ddep
    DCA = REACH + cd
    walls = ('left', 'right', 'down', 'up')
    S = np.asarray(S, float)

    def support(ch, ca):
        dch = None if ch is None else {'left': ch[0], 'right': W-ch[0], 'down': ch[1], 'up': L-ch[1]}
        dca = None if ca is None else {'left': ca[0], 'right': W-ca[0], 'down': ca[1], 'up': L-ca[1]}
        s = {}
        for k in walls:
            l1 = 1.0 if dch is None else np.exp(-0.5*((dch[k]-DCH)/SIGMA)**2)
            l2 = 1.0 if dca is None else np.exp(-0.5*((dca[k]-DCA)/SIGMA)**2)
            s[k] = float(l1*l2)
        return s, {'chair': dch, 'cabinet': dca}

    def slab(wall, along, ln, dep, g=0.0):
        if wall == 'left':  return (g, along-ln/2, g+dep, along+ln/2)
        if wall == 'right': return (W-g-dep, along-ln/2, W-g, along+ln/2)
        if wall == 'down':  return (along-ln/2, g, along+ln/2, g+dep)
        return (along-ln/2, L-g-dep, along+ln/2, L-g)

    def _pen(tr, boxes):
        # 只惩罚走路点进入桌柜；床和椅子允许轨迹进入占地，包括预测为 walk 的过渡点。
        if tr is None: return 0.0
        P, lab = tr
        if len(P) == 0: return 0.0
        tot = 0.0
        for nm in ('desk', 'cab'):
            if nm not in boxes: continue
            b = boxes[nm]
            ins = (P[:, 0] > b[0]) & (P[:, 0] < b[2]) & (P[:, 1] > b[1]) & (P[:, 1] < b[3])
            tot += float(np.mean(ins & lab))
        return tot

    def build2(cab_wall, desk_wall, ca_along, ch_along, u, tsh, gap=0.0):
        ch = anchors['seated'] if 'seated' in avail else None
        li = anchors['lying'] if 'lying' in avail else None
        boxes = {}
        sep = (dlen + cl)/2 + 0.02
        if ca_along is not None:
            boxes['cab'] = slab(cab_wall, ca_along, cl, cd, gap)
        if ch_along is not None:
            if ca_along is not None and cab_wall == desk_wall and abs(ch_along - ca_along) < sep:
                ch_along = ca_along + sep if ch_along >= ca_along else ca_along - sep
            boxes['desk'] = slab(desk_wall, ch_along, dlen, ddep, gap)
        if ch is not None:
            boxes['chair'] = (ch[0]-cs/2, ch[1]-cs/2, ch[0]+cs/2, ch[1]+cs/2)
        if li is not None:
            v = np.array([-u[1], u[0]]); bc = np.asarray(li)+u*(bl/2)+v*tsh
            boxes['bed'] = (bc[0]-bl/2, bc[1]-bw/2, bc[0]+bl/2, bc[1]+bw/2) if abs(u[0]) > 0 else \
                           (bc[0]-bw/2, bc[1]-bl/2, bc[0]+bw/2, bc[1]+bl/2)
        if not boxes: return None
        ks = list(boxes)
        for i in range(len(ks)):
            for j in range(i+1, len(ks)):
                a1, a2 = boxes[ks[i]], boxes[ks[j]]
                if min(a1[2], a2[2])-max(a1[0], a2[0]) > 0.02 and min(a1[3], a2[3])-max(a1[1], a2[1]) > 0.02:
                    return None
        out = (max(0.0, -min(b[0] for b in boxes.values())) + max(0.0, max(b[2] for b in boxes.values())-W)
               + max(0.0, -min(b[1] for b in boxes.values())) + max(0.0, max(b[3] for b in boxes.values())-L))
        if out > 0.05: return None
        return boxes

    def build(wall, u, tsh, gap=0.0):
        ch = anchors['seated']; ca = anchors['cabinet']; li = anchors['lying']
        axis = 'x' if wall in ('left', 'right') else 'y'
        ca_along = ca[1] if axis == 'x' else ca[0]
        ch_along = ch[1] if axis == 'x' else ch[0]
        cab = slab(wall, ca_along, cl, cd, gap)
        sep = (dlen + cl)/2 + 0.02
        desk_along = ch_along if abs(ch_along-ca_along) >= sep else (ca_along+sep if ch_along >= ca_along else ca_along-sep)
        desk = slab(wall, desk_along, dlen, ddep, gap)
        chair = (ch[0]-cs/2, ch[1]-cs/2, ch[0]+cs/2, ch[1]+cs/2)
        v = np.array([-u[1], u[0]]); bc = np.asarray(li)+u*(bl/2)+v*tsh
        bed = (bc[0]-bl/2, bc[1]-bw/2, bc[0]+bl/2, bc[1]+bw/2) if abs(u[0]) > 0 else \
              (bc[0]-bw/2, bc[1]-bl/2, bc[0]+bw/2, bc[1]+bl/2)
        boxes = {'cab': cab, 'desk': desk, 'chair': chair, 'bed': bed}
        ks = list(boxes)
        for i in range(4):
            for j in range(i+1, 4):
                a1, a2 = boxes[ks[i]], boxes[ks[j]]
                if min(a1[2], a2[2])-max(a1[0], a2[0]) > 0.02 and min(a1[3], a2[3])-max(a1[1], a2[1]) > 0.02:
                    return None
        out = (max(0.0, -min(b[0] for b in boxes.values())) + max(0.0, max(b[2] for b in boxes.values())-W)
               + max(0.0, -min(b[1] for b in boxes.values())) + max(0.0, max(b[3] for b in boxes.values())-L))
        if out > 0.05: return None
        return boxes

    if not ({'seated', 'cabinet'} & avail):
        return {'status': 'insufficient', 'reason': 'wall inference needs seated or cabinet anchor'}
    ch = np.asarray(anchors['seated'], float) if 'seated' in avail else None
    ca = np.asarray(anchors['cabinet'], float) if 'cabinet' in avail else None
    # 4 面柜墙 × 4 面桌墙 全枚举联合比较，不做单点 argmax
    dch = None if ch is None else {'left': ch[0], 'right': W-ch[0], 'down': ch[1], 'up': L-ch[1]}
    dca = None if ca is None else {'left': ca[0], 'right': W-ca[0], 'down': ca[1], 'up': L-ca[1]}
    l_cab = {k: (1.0 if dca is None else float(np.exp(-0.5*((dca[k]-DCA)/SIGMA)**2))) for k in walls}
    l_desk = {k: (1.0 if dch is None else float(np.exp(-0.5*((dch[k]-ddep)/SIGMA)**2))) for k in walls}
    best = None; cands = []
    for cab_wall in (walls if ca is not None else ('left',)):
        axis_c = 'x' if cab_wall in ('left', 'right') else 'y'
        ca_along = None if ca is None else (ca[1] if axis_c == 'x' else ca[0])
        for desk_wall in (walls if ch is not None else ('left',)):
            axis_d = 'x' if desk_wall in ('left', 'right') else 'y'
            ch_along0 = None if ch is None else (ch[1] if axis_d == 'x' else ch[0])
            for u in (np.array([1.,0.]), np.array([-1.,0.]), np.array([0.,1.]), np.array([0.,-1.])):
                for tsh in (-0.5, -0.25, 0.0, 0.25, 0.5):
                    for gap in (0.0, 0.15, 0.30, 0.45):
                        b = build2(cab_wall, desk_wall, ca_along, ch_along0, u, tsh, gap)
                        if b is None: continue
                        pen = _pen(traj, b)
                        sup = float(np.sqrt(l_cab[cab_wall] * l_desk[desk_wall]))
                        sc = pen*o['W_PEN'] - sup*o['W_SUPPORT'] + gap*0.06
                        cands.append({'score': float(sc), 'wall': cab_wall, 'desk_wall': desk_wall,
                                      'bed_direction': [float(x) for x in u] if 'lying' in avail else None,
                                      'support': sup, 'gap': gap,
                                      'dist_cab': None if dca is None else dca[cab_wall],
                                      'dist_chair': None if dch is None else dch[desk_wall],
                                      'boxes': {k: [float(x) for x in v] for k, v in b.items()}})
                        if best is None or sc < best[0]:
                            best = (sc, cab_wall, b, sup, {'cabinet': dca, 'chair': dch}, pen, gap, desk_wall)
    if best is None:
        return {'status': 'no_solution', 'l_cab': l_cab, 'l_desk': l_desk}
    sc, wall, boxes, sup, dist, pen, gap, dwall = best
    cands.sort(key=lambda d: d['score'])
    top = {}
    for c2 in cands[:20]: top[c2['wall']] = top.get(c2['wall'], 0) + 1
    return {'status': 'ok', 'rot_deg': 0.0,
            'cabinet_wall': wall if ca is not None else None,
            'desk_wall': dwall if ch is not None else None,
            'wall_support': float(sup),
            'boxes': {k: [float(x) for x in v] for k, v in boxes.items()},
            'available': sorted(avail),
            'wall_distance_m': None if dca is None else float(dca[wall]),
            'chair_wall_distance_m': None if dch is None else float(dch[dwall]),
            'candidate_walls_top20': top,
            'candidates': cands if candidate_limit is None else cands[:candidate_limit],
            'l_cab': l_cab, 'l_desk': l_desk, 'wall_gap': gap}
