# 网格化布局放置：每个家具在 (x, y, 旋转) 上搜索，用"走过的自由空间"+"动作锚点"打分。
# 不假设贴墙、不假设桌柜同墙、不假设椅子离桌固定距离。
import numpy as np

GRID = 0.10          # 栅格边长 m
WALK_R = 0.25        # 走过的可通行半径 m
W_WALK = 3.0         # 压到走过区域的惩罚
W_WALL = 0.35        # 贴墙奖励
W_ANCHOR = 1.0       # 锚点违反惩罚
CAB_STAND = 0.50     # 站位到柜面前沿的期望距离 m（按 AI2-THOR 实测标定）
DESK_AT = 0.05       # 椅心到桌最近边的下限 m
DESK_AT_MAX = 0.90   # 上限：椅子必须够得着桌子
DESK_FACE = 0.45     # 有朝向时：椅心到桌面前沿的距离

def grid_of(W, L):
    nx, ny = int(round(W/GRID)), int(round(L/GRID))
    return np.zeros((ny, nx), bool), nx, ny

def mark_walk(G, traj, W, L):
    ny, nx = G.shape
    if traj is None: return
    P, lab = traj
    k = max(1, int(round(WALK_R/GRID)))
    for p in np.asarray(P)[np.asarray(lab, dtype=bool)]:
        i0 = int(round(p[0]/GRID)); j0 = int(round(p[1]/GRID))
        i1, i2 = max(0, i0-k), min(nx, i0+k+1)
        j1, j2 = max(0, j0-k), min(ny, j0+k+1)
        if i1 < i2 and j1 < j2:
            G[j1:j2, i1:i2] = True

def cells(box, ny, nx):
    x0, y0, x1, y1 = box
    i1 = max(0, int(np.floor(x0/GRID))); i2 = min(nx, int(np.ceil(x1/GRID)))
    j1 = max(0, int(np.floor(y0/GRID))); j2 = min(ny, int(np.ceil(y1/GRID)))
    return j1, j2, i1, i2

def touches_wall(box, W, L, tol=0.06):
    x0, y0, x1, y1 = box
    return (x0 <= tol) or (y0 <= tol) or (x1 >= W-tol) or (y1 >= L-tol)

def inside(box, W, L, eps=0.01):
    return box[0] >= -eps and box[1] >= -eps and box[2] <= W+eps and box[3] <= L+eps

def overlap(a, b, eps=0.01):
    return min(a[2], b[2]) - max(a[0], b[0]) > eps and min(a[3], b[3]) - max(a[1], b[1]) > eps

def place(W, L, traj, anchors, sizes, order=('cab', 'bed', 'desk', 'chair'), wall_bonus=None):
    """逐物体贪心放置：先放锚点约束最硬的（柜），再床、桌、椅。"""
    G, nx, ny = grid_of(W, L)
    mark_walk(G, traj, W, L)
    out = {}
    for name in order:
        if name == 'chair':
            cs = sizes['chair']
            cx, cy = anchors['seated']
            box = (cx-cs/2, cy-cs/2, cx+cs/2, cy+cs/2)
            out['chair'] = box
            continue
        if name == 'bed':
            bw, bl = sizes['bed']
        elif name == 'desk':
            ddep, dlen = sizes['desk']
        else:
            cd, cl = sizes['cab']

        best = None
        if name == 'chair': continue
        # 候选：以锚点为中心的一圈范围
        if name == 'bed':
            ax, ay = anchors['lying']
        elif name == 'desk':
            ax, ay = anchors['seated']
        else:
            ax, ay = anchors['cabinet']
        R = 1.6
        step = GRID
        xs = np.arange(max(0, ax-R), min(W, ax+R)+1e-9, step)
        ys = np.arange(max(0, ay-R), min(L, ay+R)+1e-9, step)
        for rot in (0, 1):
            if name == 'bed':
                w_, h_ = (bw, bl) if rot == 0 else (bl, bw)
            elif name == 'desk':
                w_, h_ = (ddep, dlen) if rot == 0 else (dlen, ddep)
            else:
                w_, h_ = (cd, cl) if rot == 0 else (cl, cd)
            for x0 in xs:
                for y0 in ys:
                    box = (x0-w_/2, y0-h_/2, x0+w_/2, y0+h_/2)
                    if not inside(box, W, L): continue
                    if any(overlap(box, b) for b in out.values()): continue
                    j1, j2, i1, i2 = cells(box, ny, nx)
                    if j2 <= j1 or i2 <= i1: continue
                    pen = float(G[j1:j2, i1:i2].mean())
                    # 锚点项
                    if name == 'cab':
                        d = rect_dist(box, anchors['cabinet'])
                        aterm = ((d - CAB_STAND) / 0.25) ** 2
                    elif name == 'bed':
                        aterm = 0.0 if point_in(box, anchors['lying']) else 6.0
                    else:  # desk：椅子就贴在桌前（AI2-THOR 实测椅到桌最近边中位 0.00 m）
                        d = rect_dist(box, anchors['seated'])
                        aterm = ((d - DESK_AT) / 0.20) ** 2
                        if point_in(box, anchors['seated']): aterm += 6.0
                    wb = W_WALL if touches_wall(box, W, L) else 0.0
                    sc = W_ANCHOR*aterm + W_WALK*pen - wb
                    if best is None or sc < best[0]:
                        best = (sc, box)
        if best is None:
            return None
        out[name] = best[1]
    return out

def point_in(b, p, eps=0.0):
    return b[0]-eps <= p[0] <= b[2]+eps and b[1]-eps <= p[1] <= b[3]+eps

def rect_dist(b, p):
    dx = max(b[0]-p[0], 0.0, p[0]-b[2])
    dy = max(b[1]-p[1], 0.0, p[1]-b[3])
    return float(np.hypot(dx, dy))

def place_wall(W, L, traj, anchors, sizes, order=('cab', 'bed', 'desk', 'chair'),
               gaps=(0.0, 0.10, 0.20, 0.30, 0.40), step=0.10):
    """每个家具的候选都限定为「背面贴某面墙、间隙 g」；沿墙位置自由枚举，不再钉在锚点投影上。"""
    G, nx, ny = grid_of(W, L)
    mark_walk(G, traj, W, L)
    out = {}
    walls = ('left', 'right', 'down', 'up')
    for name in order:
        if name == 'chair':
            cs = sizes['chair']; cx, cy = anchors['seated']
            out['chair'] = (cx-cs/2, cy-cs/2, cx+cs/2, cy+cs/2)
            continue
        if name == 'bed':
            w_, h_ = sizes['bed']
        elif name == 'desk':
            d_, l_ = sizes['desk']; w_, h_ = d_, l_
        else:
            d_, l_ = sizes['cab']; w_, h_ = d_, l_
        best = None
        for wall in walls:
            horiz = wall in ('left', 'right')
            along_max = L if horiz else W
            dep, ln = (w_, h_) if horiz else (h_, w_)
            for g in gaps:
                for a in np.arange(ln/2, along_max-ln/2+1e-9, step):
                    if wall == 'left':   box = (g, a-ln/2, g+dep, a+ln/2)
                    elif wall == 'right':box = (W-g-dep, a-ln/2, W-g, a+ln/2)
                    elif wall == 'down': box = (a-ln/2, g, a+ln/2, g+dep)
                    else:                box = (a-ln/2, L-g-dep, a+ln/2, L-g)
                    if not inside(box, W, L): continue
                    if any(overlap(box, b) for b in out.values()): continue
                    j1, j2, i1, i2 = cells(box, ny, nx)
                    if j2 <= j1 or i2 <= i1: continue
                    pen = float(G[j1:j2, i1:i2].mean())
                    if name == 'cab':
                        d = rect_dist(box, anchors['cabinet']); aterm = ((d - CAB_STAND)/0.25)**2
                    elif name == 'desk':
                        d = rect_dist(box, anchors['seated']); aterm = ((d - DESK_AT)/0.20)**2
                        if point_in(box, anchors['seated']): aterm += 6.0
                    else:
                        aterm = 0.0 if point_in(box, anchors['lying']) else 6.0
                    sc = W_ANCHOR*aterm + W_WALK*pen + g*0.15
                    if best is None or sc < best[0]:
                        best = (sc, box)
        if best is None: return None
        out[name] = best[1]
    return out

def place_hybrid(W, L, traj, anchors, sizes, gaps=(0.0, 0.10, 0.20, 0.30, 0.40), step=0.10, sigma=0.30):
    """柜：臂展定墙 + 沿锚点投影 + 间隙搜索（模板法最准的那条路）；
       桌/床：贴墙自由枚举（沿墙位置不钉在锚点投影上）。"""
    G, nx, ny = grid_of(W, L)
    mark_walk(G, traj, W, L)
    walls = ('left', 'right', 'down', 'up')
    ch = anchors['seated']; ca = anchors['cabinet']; li = anchors['lying']
    out = {}

    # --- 柜：臂展定墙 ---
    cd, cl = sizes['cab']
    dca = {'left': ca[0], 'right': W-ca[0], 'down': ca[1], 'up': L-ca[1]}
    l_cab = {k: float(np.exp(-0.5*((dca[k]-(CAB_STAND+cd))/sigma)**2)) for k in walls}
    cab_wall = max(walls, key=lambda k: l_cab[k])
    horiz = cab_wall in ('left', 'right')
    ca_along = ca[1] if horiz else ca[0]
    best = None
    for g in gaps:
        for da in (-0.3, -0.15, 0.0, 0.15, 0.3):
            a = ca_along + da
            if cab_wall == 'left':   box = (g, a-cl/2, g+cd, a+cl/2)
            elif cab_wall == 'right':box = (W-g-cd, a-cl/2, W-g, a+cl/2)
            elif cab_wall == 'down': box = (a-cl/2, g, a+cl/2, g+cd)
            else:                    box = (a-cl/2, L-g-cd, a+cl/2, L-g)
            if not inside(box, W, L): continue
            j1, j2, i1, i2 = cells(box, ny, nx)
            if j2 <= j1 or i2 <= i1: continue
            pen = float(G[j1:j2, i1:i2].mean())
            d = rect_dist(box, ca)
            sc = W_ANCHOR*((d-CAB_STAND)/0.25)**2 + W_WALK*pen + g*0.15
            if best is None or sc < best[0]: best = (sc, box)
    if best is None: return None
    out['cab'] = best[1]

    # --- 床与桌：贴墙自由枚举 ---
    for name, order_sz in (('bed', sizes['bed']), ('desk', sizes['desk'])):
        w_, h_ = order_sz
        best = None
        for wall in walls:
            hz = wall in ('left', 'right')
            along_max = L if hz else W
            dep, ln = (h_, w_) if hz else (w_, h_)
            for g in gaps:
                for a in np.arange(ln/2, along_max-ln/2+1e-9, step):
                    if wall == 'left':   box = (g, a-ln/2, g+dep, a+ln/2)
                    elif wall == 'right':box = (W-g-dep, a-ln/2, W-g, a+ln/2)
                    elif wall == 'down': box = (a-ln/2, g, a+ln/2, g+dep)
                    else:                box = (a-ln/2, L-g-dep, a+ln/2, L-g)
                    if not inside(box, W, L): continue
                    if any(overlap(box, b) for b in out.values()): continue
                    j1, j2, i1, i2 = cells(box, ny, nx)
                    if j2 <= j1 or i2 <= i1: continue
                    pen = float(G[j1:j2, i1:i2].mean())
                    if name == 'desk':
                        d = rect_dist(box, ch); aterm = ((d-DESK_AT)/0.20)**2
                        # 椅子塞在桌下时坐点落在桌内是正常的，不再惩罚
                    else:
                        aterm = 0.0 if point_in(box, li) else 6.0
                    sc = W_ANCHOR*aterm + W_WALK*pen + g*0.15
                    if best is None or sc < best[0]: best = (sc, box)
        if best is None: return None
        out[name] = best[1]
    cs = sizes['chair']
    out['chair'] = (ch[0]-cs/2, ch[1]-cs/2, ch[0]+cs/2, ch[1]+cs/2)
    return out

def _cab_armwall(W, L, G, nx, ny, ca, sizes, gaps=(0.0,0.10,0.20,0.30,0.40,0.50), sigma=0.30, taken=()):
    cd, cl = sizes
    walls = ('left','right','down','up')
    dca = {'left': ca[0], 'right': W-ca[0], 'down': ca[1], 'up': L-ca[1]}
    l = {k: float(np.exp(-0.5*((dca[k]-(CAB_STAND+cd))/sigma)**2)) for k in walls}
    wall = max(walls, key=lambda k: l[k])
    hz = wall in ('left','right')
    a0 = ca[1] if hz else ca[0]
    best = None
    for g in gaps:
        for da in (-0.2, -0.1, 0.0, 0.1, 0.2):
            a = a0 + da
            if wall == 'left':   box = (g, a-cl/2, g+cd, a+cl/2)
            elif wall == 'right':box = (W-g-cd, a-cl/2, W-g, a+cl/2)
            elif wall == 'down': box = (a-cl/2, g, a+cl/2, g+cd)
            else:                box = (a-cl/2, L-g-cd, a+cl/2, L-g)
            if not inside(box, W, L): continue
            if any(overlap(box, t) for t in taken): continue
            j1,j2,i1,i2 = cells(box, ny, nx)
            if j2<=j1 or i2<=i1: continue
            pen = float(G[j1:j2,i1:i2].mean())
            sc = W_WALK*pen + g*0.15 + abs(da)*0.5
            if best is None or sc < best[0]: best = (sc, box)
    return best[1] if best else None


def _desk_wallfree(W, L, G, nx, ny, ch, sizes, gaps=(0.0,0.10,0.20,0.30,0.40), step=0.10, taken=()):
    ddep, dlen = sizes
    walls = ('left','right','down','up')
    best = None
    for wall in walls:
        hz = wall in ('left','right')
        along_max = L if hz else W
        dep, ln = (ddep, dlen) if hz else (dlen, ddep)
        for g in gaps:
            for a in np.arange(ln/2, along_max-ln/2+1e-9, step):
                if wall == 'left':   box = (g, a-ln/2, g+dep, a+ln/2)
                elif wall == 'right':box = (W-g-dep, a-ln/2, W-g, a+ln/2)
                elif wall == 'down': box = (a-ln/2, g, a+ln/2, g+dep)
                else:                box = (a-ln/2, L-g-dep, a+ln/2, L-g)
                if not inside(box, W, L): continue
                if any(overlap(box, t) for t in taken): continue
                j1,j2,i1,i2 = cells(box, ny, nx)
                if j2<=j1 or i2<=i1: continue
                pen = float(G[j1:j2,i1:i2].mean())
                d = rect_dist(box, ch)
                # 椅子到桌面的距离在不同房间差别很大（真实房间 0.58 m，AI2-THOR 中位 0.00 m）
                # 所以用区间先验而不是单点
                aterm = 0.0 if d <= DESK_AT_MAX else ((d-DESK_AT_MAX)/0.20)**2
                # 椅子塞在桌下时坐点落在桌内是正常的，不再惩罚
                hz2 = wall in ('left', 'right')
                ch_along = ch[1] if hz2 else ch[0]
                sc = W_ANCHOR*aterm + W_WALK*pen + g*0.60 + abs(a - ch_along)*0.40
                if best is None or sc < best[0]: best = (sc, box)
    return best[1] if best else None


def _bed_foot(W, L, G, nx, ny, li, sizes, ymax=40, taken=(), head_wall_weight=1.0, return_candidates=False, facing=None):
    bw, bl = sizes
    best = None
    candidates = []
    for u in (np.array([1.,0.]), np.array([-1.,0.]), np.array([0.,1.]), np.array([0.,-1.])):
        direction_best = None
        for tsh in np.arange(-0.5, 0.51, 0.25):
            v = np.array([-u[1], u[0]])
            bc = np.asarray(li) + u*(bl/2) + v*tsh
            if abs(u[0]) > 0:
                box = (bc[0]-bl/2, bc[1]-bw/2, bc[0]+bl/2, bc[1]+bw/2)
            else:
                box = (bc[0]-bw/2, bc[1]-bl/2, bc[0]+bw/2, bc[1]+bl/2)
            if not inside(box, W, L): continue
            if any(overlap(box, t) for t in taken): continue
            j1,j2,i1,i2 = cells(box, ny, nx)
            if j2<=j1 or i2<=i1: continue
            # 床允许轨迹进入占地，包含预测为 walk 的接触与过渡点。
            # 已知经典摆放条件下，床头接近墙。权重为零时关闭此先验。
            if u[0] > 0:
                head_gap = W - box[2]
            elif u[0] < 0:
                head_gap = box[0]
            elif u[1] > 0:
                head_gap = L - box[3]
            else:
                head_gap = box[1]
            sc = head_wall_weight*max(0.0, head_gap) + abs(tsh)*0.3
            if best is None or sc < best[0]: best = (sc, box)
            if direction_best is None or sc < direction_best[0]:
                direction_best = (sc, box)
        if direction_best is not None:
            candidates.append(direction_best)
    if return_candidates:
        return sorted(candidates, key=lambda candidate: candidate[0])
    return best[1] if best else None


def place_best(W, L, traj, anchors, sizes, order=('bed','cab','desk'), bed_head_wall_weight=1.0, facing=None):
    """facing: {'seated': v, 'cabinet': v, 'lying': v}，来自轨迹切线；与墙判定不一致时自动退回。"""
    """有限回溯床方向，优先放下已知目标。床头靠墙先验可用零权重关闭。"""
    G, nx, ny = grid_of(W, L)
    mark_walk(G, traj, W, L)
    bed_candidates = [(0.0, None)]
    if 'bed' in order:
        bed_candidates = _bed_foot(W, L, G, nx, ny, anchors['lying'], sizes['bed'],
                                   head_wall_weight=bed_head_wall_weight,
                                   return_candidates=True) or bed_candidates
    best = None
    for bed_score, bed_box in bed_candidates:
        out = {}
        fns = {'bed': lambda t: bed_box,
               'cab': lambda t: _cab_armwall(W, L, G, nx, ny, anchors['cabinet'], sizes['cab'], taken=t),
               'desk': lambda t: _desk_template(W, L, anchors['seated'], out.get('cab'), sizes['desk'],
                                            facing=(facing or {}).get('seated'))}
        for name in order:
            b = fns[name](tuple(out.values()))
            if b is None: continue
            if any(overlap(b, other) for other in out.values()): continue
            out[name] = b
        cs = sizes['chair']; cx, cy = anchors['seated']
        out['chair'] = (cx-cs/2, cy-cs/2, cx+cs/2, cy+cs/2)
        rank = (-sum(name in out for name in order), bed_score)
        if best is None or rank < best[0]:
            best = (rank, out)
    return best[1]

def _desk_template(W, L, ch, cab_box, sizes, sigma=0.30, gaps=(0.0, 0.06, 0.12), facing=None):
    """桌：墙由"椅子就在桌前"定（椅心到墙 ≈ 桌深），沿墙位置取椅子投影，与柜冲突时沿墙推开。
       这是模板法在真实房间里给出 0.056 m 的那条规则。"""
    ddep, dlen = sizes
    walls = ('left','right','down','up')
    dch = {'left': ch[0], 'right': W-ch[0], 'down': ch[1], 'up': L-ch[1]}
    l = {k: float(np.exp(-0.5*((dch[k]-ddep)/sigma)**2)) for k in walls}
    wall = max(walls, key=lambda k: l[k])
    # 朝向一致时才采用：法向分量的符号要与判出的墙一致
    fdir = None
    if facing is not None:
        f = np.asarray(facing, float); nf = np.linalg.norm(f)
        if nf > 1e-9:
            f = f/nf
            nvec = {'left': np.array([-1.,0.]), 'right': np.array([1.,0.]),
                    'down': np.array([0.,-1.]), 'up': np.array([0.,1.])}[wall]
            if float(f @ nvec) > 0.5:
                fdir = f
    hz = wall in ('left','right')
    cl = max(cab_box[2]-cab_box[0], cab_box[3]-cab_box[1]) if cab_box else 0.0
    ch_along = ch[1] if hz else ch[0]
    sep = (dlen + cl)/2 + 0.02
    if cab_box is None:
        cab_along = None
    else:
        cab_along = ((cab_box[1]+cab_box[3])/2) if hz else ((cab_box[0]+cab_box[2])/2)
    best = None
    for g in gaps:
        das = [0.0] if cab_along is None else [0.0, sep-abs(ch_along-cab_along), -(sep-abs(ch_along-cab_along)),
                                               sep-abs(ch_along-cab_along)+0.25, -(sep-abs(ch_along-cab_along)+0.25)]
        for da in das:
            a = ch_along + da
            if wall == 'left':   box = (g, a-dlen/2, g+ddep, a+dlen/2)
            elif wall == 'right':box = (W-g-ddep, a-dlen/2, W-g, a+dlen/2)
            elif wall == 'down': box = (a-dlen/2, g, a+dlen/2, g+ddep)
            else:                box = (a-dlen/2, L-g-ddep, a+dlen/2, L-g)
            if not inside(box, W, L): continue
            if cab_box is not None and overlap(box, cab_box): continue
            sc = abs(da)*0.30 + g*0.60
            if fdir is not None:
                # 朝向已知：法向位置由朝向定，沿墙仍取椅子投影
                tgt = np.asarray(ch) + fdir*(DESK_FACE + ddep/2)
                gc = (tgt[0] if hz else tgt[1]) - g
                gc = float(np.clip(gc, 0.0, (W-ddep) if hz else (L-ddep)))
                if wall == 'left':   box = (gc, a-dlen/2, gc+ddep, a+dlen/2)
                elif wall == 'right':box = (W-gc-ddep, a-dlen/2, W-gc, a+dlen/2)
                elif wall == 'down': box = (a-dlen/2, gc, a+dlen/2, gc+ddep)
                else:                box = (a-dlen/2, L-gc-ddep, a+dlen/2, L-gc)
            if best is None or sc < best[0]: best = (sc, box)
    return best[1] if best else None

def place_orders(W, L, traj, anchors, sizes, orders=None, bed_head_wall_weight=1.0, facing=None):
    """枚举放置顺序，取"放下的件数最多、锚点一致性最好"的那个结果。"""
    import itertools
    if orders is None:
        orders = list(itertools.permutations(('bed', 'cab', 'desk')))
    best = None
    for od in orders:
        out = place_best(W, L, traj, anchors, sizes, order=od,
                         bed_head_wall_weight=bed_head_wall_weight, facing=facing)
        if not out: continue
        fit = 0.0
        if 'cab' in out:
            fit += abs(rect_dist(out['cab'], anchors['cabinet']) - CAB_STAND)
        if 'desk' in out:
            fit += abs(rect_dist(out['desk'], anchors['seated']) - DESK_AT)
        if 'bed' in out and not point_in(out['bed'], anchors['lying']):
            fit += 2.0
        n = sum(1 for k in ('bed', 'cab', 'desk') if k in out)
        rank = (-n, fit)
        if best is None or rank < best[0]:
            best = (rank, out)
    return best[1] if best else None
def _cands_bed(W, L, G, nx, ny, li, sizes, topk=5):
    bw, bl = sizes; out = []
    for u in (np.array([1.,0.]), np.array([-1.,0.]), np.array([0.,1.]), np.array([0.,-1.])):
        for tsh in np.arange(-0.5, 0.51, 0.25):
            v = np.array([-u[1], u[0]]); bc = np.asarray(li) + u*(bl/2) + v*tsh
            box = (bc[0]-bl/2, bc[1]-bw/2, bc[0]+bl/2, bc[1]+bw/2) if abs(u[0]) > 0 else (bc[0]-bw/2, bc[1]-bl/2, bc[0]+bw/2, bc[1]+bl/2)
            if not inside(box, W, L): continue
            j1,j2,i1,i2 = cells(box, ny, nx)
            if j2<=j1 or i2<=i1: continue
            pen = float(G[j1:j2,i1:i2].mean())
            sc = W_WALK*pen + abs(tsh)*0.3 + (0.0 if point_in(box, li) else 6.0)
            out.append((sc, box))
    out.sort(key=lambda t: t[0]); return out[:topk]

def _cands_cab(W, L, G, nx, ny, ca, sizes, topk=5, sigma=0.30):
    cd, cl = sizes; walls = ('left','right','down','up')
    dca = {'left': ca[0], 'right': W-ca[0], 'down': ca[1], 'up': L-ca[1]}
    l = {k: float(np.exp(-0.5*((dca[k]-(CAB_STAND+cd))/sigma)**2)) for k in walls}
    wall = max(walls, key=lambda k: l[k]); hz = wall in ('left','right')
    a0 = ca[1] if hz else ca[0]; out = []
    for g in (0.0,0.10,0.20,0.30,0.40,0.50):
        for da in (-0.3,-0.2,-0.1,0.0,0.1,0.2,0.3):
            a = a0 + da
            if wall=='left': box=(g, a-cl/2, g+cd, a+cl/2)
            elif wall=='right': box=(W-g-cd, a-cl/2, W-g, a+cl/2)
            elif wall=='down': box=(a-cl/2, g, a+cl/2, g+cd)
            else: box=(a-cl/2, L-g-cd, a+cl/2, L-g)
            if not inside(box, W, L): continue
            j1,j2,i1,i2 = cells(box, ny, nx)
            if j2<=j1 or i2<=i1: continue
            pen = float(G[j1:j2,i1:i2].mean())
            d = rect_dist(box, ca)
            sc = W_ANCHOR*((d-CAB_STAND)/0.25)**2 + W_WALK*pen + g*0.15 + abs(da)*0.5
            out.append((sc, box))
    out.sort(key=lambda t: t[0]); return out[:topk]

def _cands_desk(W, L, G, nx, ny, ch, sizes, topk=5, sigma=0.30):
    ddep, dlen = sizes; walls = ('left','right','down','up')
    dch = {'left': ch[0], 'right': W-ch[0], 'down': ch[1], 'up': L-ch[1]}
    l = {k: float(np.exp(-0.5*((dch[k]-ddep)/sigma)**2)) for k in walls}
    wall = max(walls, key=lambda k: l[k]); hz = wall in ('left','right')
    a0 = ch[1] if hz else ch[0]; out = []
    for g in (0.0,0.06,0.12,0.20):
        for da in np.arange(-0.8, 0.81, 0.2):
            a = a0 + da
            if wall=='left': box=(g, a-dlen/2, g+ddep, a+dlen/2)
            elif wall=='right': box=(W-g-ddep, a-dlen/2, W-g, a+dlen/2)
            elif wall=='down': box=(a-dlen/2, g, a+dlen/2, g+ddep)
            else: box=(a-dlen/2, L-g-ddep, a+dlen/2, L-g)
            if not inside(box, W, L): continue
            j1,j2,i1,i2 = cells(box, ny, nx)
            if j2<=j1 or i2<=i1: continue
            pen = float(G[j1:j2,i1:i2].mean())
            d = rect_dist(box, ch)
            aterm = 0.0 if d <= DESK_AT_MAX else ((d-DESK_AT_MAX)/0.20)**2
            # 椅子塞在桌下时坐点落在桌内是正常的，不再惩罚
            sc = W_ANCHOR*aterm + W_WALK*pen + g*0.60 + abs(da)*1.20
            out.append((sc, box))
    out.sort(key=lambda t: t[0]); return out[:topk]

def place_joint(W, L, traj, anchors, sizes, k=5, miss_pen=1.2):
    """每类保留 k 个候选，枚举组合，联合打分（含缺失惩罚），取最优。"""
    G, nx, ny = grid_of(W, L)
    mark_walk(G, traj, W, L)
    cb = _cands_bed(W, L, G, nx, ny, anchors['lying'], sizes['bed'], k)
    cc = _cands_cab(W, L, G, nx, ny, anchors['cabinet'], sizes['cab'], k)
    cd_ = _cands_desk(W, L, G, nx, ny, anchors['seated'], sizes['desk'], k)
    best = None
    for i in range(len(cb)+1):
        for j in range(len(cc)+1):
            for m in range(len(cd_)+1):
                if i==0 and j==0 and m==0: continue
                sel = {}; tot = 0.0; ok = True
                if i>0: sel['bed']=cb[i-1][1]; tot+=cb[i-1][0]
                if j>0: sel['cab']=cc[j-1][1]; tot+=cc[j-1][0]
                if m>0: sel['desk']=cd_[m-1][1]; tot+=cd_[m-1][0]
                ks = list(sel)
                for a1 in range(len(ks)):
                    for a2 in range(a1+1, len(ks)):
                        if overlap(sel[ks[a1]], sel[ks[a2]]): ok = False
                if not ok: continue
                tot += miss_pen*((0 if i>0 else 1)+(0 if j>0 else 1)+(0 if m>0 else 1))
                if best is None or tot < best[0]: best = (tot, dict(sel))
    if best is None: return None
    out = best[1]
    cs = sizes['chair']; cx, cy = anchors['seated']
    out['chair'] = (cx-cs/2, cy-cs/2, cx+cs/2, cy+cs/2)
    return out