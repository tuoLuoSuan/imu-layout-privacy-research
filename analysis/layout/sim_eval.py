# 六臂评估：在 AI2-THOR 场景上比较 真锚点 / 带噪锚点 / 打乱锚点 / 单锚点
import json, io, os, glob, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout_core as LC

THOR = __import__('paths').THOR
REACH = 0.575; CH_W = 0.55
TYPES = ('bed', 'desk', 'cab', 'chair')

def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iz = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iz
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter/ua if ua > 0 else 0.0

def nearest_wall(cx, cz, W, L):
    d = {'left': cx, 'right': W-cx, 'down': cz, 'up': L-cz}
    return min(d, key=d.get)

def load_scene(f):
    d = json.load(io.open(f, encoding='utf-8'))
    fl = d.get('floor')
    if not fl: return None
    cx, cz, sx, sz = fl
    W, L = float(sx), float(sz); x0, z0 = cx-W/2, cz-L/2
    by = {}
    for o in d['objects']:
        t = o['type']
        key = 'cab' if t in ('Cabinet', 'Shelf') else ('bed' if t == 'Bed' else ('desk' if t == 'Desk' else ('chair' if t == 'Chair' else None)))
        if key: by.setdefault(key, []).append(o)
    if not {'bed', 'desk', 'chair'} <= set(by): return None
    gt = {}; sizes = {}
    for k, arr in by.items():
        o = max(arr, key=lambda t: t['size']['x']*t['size']['z'])
        ox, oz = o['center']['x']-x0, o['center']['z']-z0
        hx, hz = o['size']['x']/2, o['size']['z']/2
        gt[k] = (ox-hx, oz-hz, ox+hx, oz+hz)
    if 'cab' not in by: return None
    # 模型尺寸：床用 (宽, 长)，桌/柜用 (深, 长)
    def dims(k):
        o = max(by[k], key=lambda t: t['size']['x']*t['size']['z'])
        sx_, sz_ = o['size']['x'], o['size']['z']
        if k == 'bed': return (min(sx_, sz_), max(sx_, sz_))
        if k == 'chair': return (max(sx_, sz_),)
        return (min(sx_, sz_), max(sx_, sz_))
    S = (d['agent']['x']-x0, d['agent']['z']-z0)
    return dict(W=W, L=L, gt=gt, S=S, sizes={k: dims(k) for k in gt},
                scene=os.path.basename(f)[:-5])

def anchors_true(sc):
    W, L = sc['W'], sc['L']; gt = sc['gt']
    bed, chair, cab = gt['bed'], gt['chair'], gt['cab']
    a_ch = ((chair[0]+chair[2])/2, (chair[1]+chair[3])/2)
    ccx, ccz = (cab[0]+cab[2])/2, (cab[1]+cab[3])/2
    w = nearest_wall(ccx, ccz, W, L)
    dd = LC.DEFAULTS['REACH'] + sc['sizes']['cab'][0]
    a_cab = {'left': (dd, ccz), 'right': (W-dd, ccz), 'down': (ccx, dd), 'up': (ccx, L-dd)}[w]
    # 床尾：沿床的【长轴】，取"头侧贴墙"的对端；短边中点
    x0, z0, x1, z1 = bed
    if (x1-x0) >= (z1-z0):
        head_left = x0 <= (W - x1)
        a_li = (x1 if head_left else x0, (z0+z1)/2)
    else:
        head_down = z0 <= (L - z1)
        a_li = ((x0+x1)/2, z1 if head_down else z0)
    return {'seated': a_ch, 'cabinet': a_cab, 'lying': a_li}

def traj_of(sc, a):
    """合成一条走一遍的路径：S -> 椅 -> 柜 -> 床尾 -> S，全部按 walk 标注。"""
    pts = [np.asarray(sc['S'], float), np.asarray(a['seated'], float),
           np.asarray(a['cabinet'], float), np.asarray(a['lying'], float),
           np.asarray(sc['S'], float)]
    P = []
    for i in range(len(pts)-1):
        for t in np.linspace(0, 1, 20, endpoint=False):
            P.append(pts[i]*(1-t) + pts[i+1]*t)
    P.append(pts[-1])
    P = np.array(P)
    return P, np.ones(len(P), bool)

def run_arm(sc, anchors, sizes_override=None):
    sz = dict(sizes_override) if sizes_override else {
        'bed': sc['sizes']['bed'], 'desk': sc['sizes']['desk'],
        'cab': sc['sizes']['cab'], 'chair': sc['sizes']['chair'][0]}
    tr = traj_of(sc, anchors)
    return LC.solve(sc['W'], sc['L'], sc['S'], anchors, sz, traj=tr)

def score(sc, res):
    if res.get('status') != 'ok': return None
    out = {}
    for k in TYPES:
        if k not in sc['gt'] or k not in res['boxes']: continue
        p = res['boxes'][k]; g = sc['gt'][k]
        ce = float(np.hypot((p[0]+p[2])/2-(g[0]+g[2])/2, (p[1]+p[3])/2-(g[1]+g[3])/2))
        out[k] = (ce, iou(p, g))
    return out

scenes = []
for f in sorted(glob.glob(os.path.join(THOR, 'FloorPlan*.json'))):
    s = load_scene(f)
    if s: scenes.append(s)
print('可用场景 %d' % len(scenes))
rng = np.random.default_rng(3)

def agg(rows):
    if not rows: return {}
    per = {}
    for k in TYPES:
        ce = [r[k][0] for r in rows if k in r]; io = [r[k][1] for r in rows if k in r]
        if ce: per[k] = (len(ce), float(np.median(ce)), float(np.mean(np.array(io) >= 0.5)))
    return per

print('%-14s %6s | %s' % ('arm', 'n', 'per-type: n / median centre err (m) / IoU>=0.5 rate'))
for arm in ('oracle', 'noise0.10', 'noise0.20', 'noise0.30', 'shuffle', 'chair_only'):
    rows = []; nfail = 0
    for sc in scenes:
        a0 = anchors_true(sc)
        trials = 1 if arm in ('oracle',) else 25
        for _ in range(trials):
            a = dict(a0)
            if arm.startswith('noise'):
                sg = float(arm.replace('noise', ''))
                a = {k: (np.array(v)+rng.normal(0, sg, 2)) for k, v in a0.items()}
            elif arm == 'shuffle':
                ks = list(a0); vs = [a0[k] for k in ks]
                rng.shuffle(vs); a = dict(zip(ks, vs))
            elif arm == 'chair_only':
                a = {'seated': a0['seated'], 'cabinet': a0['seated'], 'lying': a0['lying']}
            res = run_arm(sc, a)
            s = score(sc, res)
            if s is None: nfail += 1
            else: rows.append(s)
    per = agg(rows)
    txt = ' '.join('%s %.2f/%.0f%%' % (k, v[1], 100*v[2]) for k, v in per.items())
    print('%-14s %6d | %s  (fail %d)' % (arm, len(rows), txt, nfail))