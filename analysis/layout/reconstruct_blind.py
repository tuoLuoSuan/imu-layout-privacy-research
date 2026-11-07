# 半盲重建：给房间外框 2.84x4.045 与家具尺寸表；门的位置、每件家具贴哪面墙、落在哪，全由轨迹+动作推。
import numpy as np, json, io, os, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import matplotlib.font_manager as fm
cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')

W, L = 2.84, 4.045
S_PT = np.array([0.825, 3.845])   # 起点是室内 S 点，不是门洞：离门墙 0.20 m
BED_W, BED_L = 1.525, 2.085
DESK_D, DESK_LEN, CAB_LEN = 0.60, 1.20, 0.90
CHAIR_S, CH_W = 0.44, 0.55
TOL = 0.18

def anchors_from(sess):
    d = np.load(os.path.join(sess, 'ronin-xy.npy'))
    t = d[:, 0] - 0.5
    P = np.column_stack([d[:, 1], d[:, 2]])
    runs = [tuple(r) for r in json.load(io.open(os.path.join(sess, 'actions.json'), encoding='utf-8'))['runs']]
    lab = np.array(['']*len(t), dtype=object)
    for l, a1, b1 in runs: lab[(t >= a1) & (t <= b1)] = l
    out = {}
    for l, a1, b1 in runs:
        if l not in ('seated', 'cabinet', 'lying') or b1 - a1 < 1.0: continue
        m = (t >= a1) & (t <= b1)
        if m.sum() < 3: continue
        n = max(2, int(m.sum()*0.25))
        out.setdefault(l, P[m][-n:].mean(axis=0))
    return t, P, lab, out

def rect(cx, cy, w, h): return (cx-w/2, cy-h/2, cx+w/2, cy+h/2)

def search(sess, verbose=True):
    t, P, lab, A = anchors_from(sess)
    if len(A) < 3: return None, 'anchors'
    ch0, ca0, li0 = A['seated'], A['cabinet'], A['lying']
    Wp0 = P[lab == 'walk']
    best = None; stats = dict(reach=0, span=0, pen=0, size=0, ok=0)
    for deg in np.arange(0, 360, 1.0):
        a = np.radians(deg); c, s = np.cos(a), np.sin(a); R = np.array([[c, s], [-s, c]])
        Q = P @ R; Wp = Wp0 @ R; ch = ch0 @ R; ca = ca0 @ R; li = li0 @ R
        for nrm in (np.array([1.0, 0]), np.array([-1.0, 0]), np.array([0, 1.0]), np.array([0, -1.0])):
            tang = np.array([-nrm[1], nrm[0]])
            wall = ch @ nrm - (CH_W + DESK_D)
            if abs((ca @ nrm - wall) - (CH_W + DESK_D)) > TOL:
                stats['reach'] += 1; continue
            dc0 = ch @ tang; cc0 = ca @ tang
            if min(dc0+DESK_LEN/2, cc0+CAB_LEN/2) - max(dc0-DESK_LEN/2, cc0-CAB_LEN/2) > 0.02:
                cc0 = (dc0 - DESK_LEN/2 - CAB_LEN/2) if cc0 < dc0 else (dc0 + DESK_LEN/2 + CAB_LEN/2)
            p1 = nrm*(wall + DESK_D/2) + tang*dc0
            p2 = nrm*(wall + DESK_D/2) + tang*cc0
            desk = rect(p1[0], p1[1], DESK_D, DESK_LEN) if abs(nrm[0]) > 0 else rect(p1[0], p1[1], DESK_LEN, DESK_D)
            cab = rect(p2[0], p2[1], DESK_D, CAB_LEN) if abs(nrm[0]) > 0 else rect(p2[0], p2[1], CAB_LEN, DESK_D)
            chair = rect(ch[0], ch[1], CHAIR_S, CHAIR_S)
            for u in (np.array([1.0, 0]), np.array([-1.0, 0]), np.array([0, 1.0]), np.array([0, -1.0])):
                v = np.array([-u[1], u[0]])
                for tsh in (-0.5, -0.25, 0.0, 0.25, 0.5):
                    bc = li + u*(BED_L/2) + v*tsh
                    bed = rect(bc[0], bc[1], BED_L, BED_W) if abs(u[0]) > 0 else rect(bc[0], bc[1], BED_W, BED_L)
                    boxes = [desk, cab, chair, bed]
                    rw = 0.0; ov = 0
                    for b in boxes:
                        ins = ((Wp[:, 0] > b[0]+0.05) & (Wp[:, 0] < b[2]-0.05) & (Wp[:, 1] > b[1]+0.05) & (Wp[:, 1] < b[3]-0.05))
                        rw += ins.sum() / max(1, len(Wp))
                    for i in range(4):
                        for j in range(i+1, 4):
                            ox = min(boxes[i][2], boxes[j][2]) - max(boxes[i][0], boxes[j][0])
                            oy = min(boxes[i][3], boxes[j][3]) - max(boxes[i][1], boxes[j][1])
                            if ox > 0.01 and oy > 0.01: ov += 1
                    pen = 6.0*rw + 2.0*ov
                    if pen > 1.0:
                        stats['pen'] += 1; continue
                    bx0 = min(min(b[0] for b in boxes), Q[:, 0].min()); bx1 = max(max(b[2] for b in boxes), Q[:, 0].max())
                    by0 = min(min(b[1] for b in boxes), Q[:, 1].min()); by1 = max(max(b[3] for b in boxes), Q[:, 1].max())
                    over = max(0.0, (bx1-bx0)-W) + max(0.0, (by1-by0)-L)
                    stats['ok'] += 1
                    ax = Q[0][0] - S_PT[0]
                    ay = Q[0][1] - S_PT[1]
                    fout = 0.0
                    for b in boxes:
                        dx = max(0.0, (b[0]-ax)) + max(0.0, ax+W-b[2])
                        dy = max(0.0, (b[1]-ay)) + max(0.0, ay+L-b[3])
                        fout += dx*dy + 0.05*(dx+dy)
                    flush = sum(1 for b in boxes
                                if abs(b[0]-ax) < 0.08 or abs(b[2]-(ax+W)) < 0.08
                                or abs(b[1]-ay) < 0.08 or abs(b[3]-(ay+L)) < 0.08)
                    sc = -fout*10.0 + flush*0.15 - pen*3.0
                    if best is None or sc > best[0]:
                        best = (sc, deg, ax, ay, boxes, pen, flush, over)
    if best is None: return None, stats
    sc, deg, ax, ay, boxes, pen, flush, over = best
    sh = lambda b: (max(b[0]-ax, 0.0), max(b[1]-ay, 0.0), min(b[2]-ax, W), min(b[3]-ay, L))
    SH[0], SH[1] = ax, ay
    return dict(deg=deg, desk=sh(boxes[0]), cab=sh(boxes[1]), chair=sh(boxes[2]), bed=sh(boxes[3]), flush=flush, pen=pen, over=over, stats=stats), None

SH = [0.0, 0.0]

def draw(sess, out, tag):
    d = np.load(os.path.join(sess, 'ronin-xy.npy')); P = np.column_stack([d[:, 1], d[:, 2]])
    a = np.radians(out['deg']); c, s = np.cos(a), np.sin(a)
    Q = P @ np.array([[c, s], [-s, c]])
    # 用与搜索一致的房间放置重画
    fig, ax = plt.subplots(figsize=(8, 10), dpi=150)
    ax.add_patch(Rectangle((0, 0), W, L, fill=False, ec='#111', lw=2.4))
    t, P, lab, A = anchors_from(sess)
    Qb = P @ np.array([[c, s], [-s, c]])
    ax.plot(Qb[:, 0] - SH[0], Qb[:, 1] - SH[1], '-', lw=1.1, color='#888')
    for b, col, ec, tx in ((out['bed'], '#a8c4e6', '#4167a0', '床'), (out['desk'], '#ffe08a', '#d99b00', '桌'), (out['cab'], '#c9b6e4', '#7a5aa8', '柜'), (out['chair'], '#f6a6bc', '#c2185b', '椅')):
        ax.add_patch(Rectangle((b[0], b[1]), b[2]-b[0], b[3]-b[1], fc=col, ec=ec, lw=1.8))
        ax.text((b[0]+b[2])/2, (b[1]+b[3])/2, tx, ha='center', va='center', fontsize=13, fontproperties=cjk)
    ax.set_aspect('equal'); ax.set_xlim(-0.3, W+0.3); ax.set_ylim(-0.3, L+0.3); ax.grid(alpha=0.2, lw=0.4)
    ax.set_title('%s 半盲重建：只给房间外框与家具尺寸\n贴哪面墙、家具在哪全由动作推（旋转 %.0f，贴墙 %d 处）' % (tag, out['deg'], out['flush']), fontsize=10.5, loc='left', fontproperties=cjk)
    fig.tight_layout(); o = os.path.join(sess, 'blind.png'); fig.savefig(o); return o

if __name__ == '__main__':
    sess = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('IMU_LAYOUT_SESSION', '')
    tag = os.path.basename(sess)
    out, why = search(sess)
    if out is None:
        print('无可行解:', why); sys.exit(1)
    print('%s  旋转 %.0f 度  贴墙 %d 处  惩罚 %.2f' % (tag, out['deg'], out['flush'], out['pen']))
    for nm, b in (('桌', out['desk']), ('柜', out['cab']), ('椅', out['chair']), ('床', out['bed'])):
        print('  %-3s x %.2f-%.2f (%.2f)  y %.2f-%.2f (%.2f)' % (nm, b[0], b[2], b[2]-b[0], b[1], b[3], b[3]-b[1]))
    print('  起点钉 S=(%.3f, %.3f)   统计 %s' % (S_PT[0], S_PT[1], out['stats']))
    print('  图:', draw(sess, out, tag))