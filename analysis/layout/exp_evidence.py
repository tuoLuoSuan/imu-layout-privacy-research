# 证据累积与临界事件：每多一条交互，哪件家具的残余区间缩多少、真值还在不在区间里。
#
# 与 identifiability.py 共用同一套 q 参数化公式（q = 该轴最小坐标）：
#   事件区间  q in [a_max - L - d, a_min + d]，d = reach + EPS，a 是同类的交互位置
#   先验区间  U 档 [0, room - L]（不知道贴哪面墙），K 档只在确实贴墙时才缩到 TOL
# 动作次数/时长/路程不进公式；区间按端点求交，空交集记 conflict（窄却错）。
#
# 两个数据集：
#   iTHOR 25 场景：锚点取 sim_eval.anchors_true（几何真值），逐类累加证据
#   真实录音 s-59d570ee：锚点取 identifiability.events（一致性过滤后的真实事件），
#                       逐【单个事件】枚举，找临界事件（删掉它区间就变宽的那条）
import io, json, os, sys, glob, itertools
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import identifiability as ID
import sim_eval as SE
import leakage_curve as LC

CLASS_OF = {'cab': 'cabinet', 'chair': 'seated', 'bed': 'lying'}
SUBSETS = [(), ('seated',), ('cabinet',), ('lying',),
           ('seated', 'cabinet'), ('seated', 'lying'), ('cabinet', 'lying'),
           ('seated', 'cabinet', 'lying')]


def axis_row(obj, cls, box, room, anchors, k, truth_q, prior='U', others=None):
    """单轴一行：返回 (width, covers, prior_width, event_width, conflict)。

    prior='U'：只知道房间尺寸，不知道贴哪面墙（iTHOR 统计用这一档）。
    prior='box'：用 identifiability.prior_interval 的贴墙/相邻判定（真实房间用这一档，与
    RESULTS「可辨识性」节逐项对齐；注意它读的是预测框，属于「贴墙这件事已经知道」的档位）。"""
    L = ID.world_size(box, k)
    if prior == 'box':
        p_lo, p_hi, _kind, _gap = ID.prior_interval(box, room, L, k, others)
    else:
        p_lo, p_hi = 0.0, float(room[k]) - L
    if cls not in anchors:
        cover = bool(p_lo - 1e-9 <= truth_q <= p_hi + 1e-9)
        return p_hi - p_lo, cover, p_hi - p_lo, None, False
    a = np.asarray(anchors[cls], float)
    a = np.atleast_2d(a)
    d = ID.REACH[cls] + ID.EPS
    e_lo, e_hi = float(a[:, k].max()) - L - d, float(a[:, k].min()) + d
    lo, hi = max(e_lo, p_lo), min(e_hi, p_hi)
    w = max(0.0, hi - lo)
    conflict = bool(hi < lo)
    cover = bool(lo - 1e-9 <= truth_q <= hi + 1e-9)
    return w, cover, p_hi - p_lo, e_hi - e_lo, conflict


def thor_rows(root):
    """iTHOR：每场景每物件每轴一行，带该场景的真值框与真值锚点。"""
    out = []
    for f in sorted(glob.glob(os.path.join(root, 'FloorPlan*.json'))):
        sc = SE.load_scene(f)
        if not sc:
            continue
        A = SE.anchors_true(sc)
        room = (sc['W'], sc['L'])
        for obj, cls in CLASS_OF.items():
            if obj not in sc['gt']:
                continue
            box = sc['gt'][obj]
            for k in (0, 1):
                out.append(dict(scene=sc['scene'], obj=obj, cls=cls, box=box, room=room,
                                anchors=A, axis=k, truth_q=float(box[k]),
                                L=ID.world_size(box, k)))
    return out


def summarize(rows, anchors_of, prior='U'):
    """anchors_of(row) -> {class: 2D 点}；返回宽度与覆盖率统计。"""
    W, C, I10, NW, conflicts, N = [], [], [], [], [], 0
    for r in rows:
        others = [x['box'] for x in rows if x['obj'] != r['obj']
                  and x.get('scene') == r.get('scene')]
        w, cov, pw, ew, cf = axis_row(r['obj'], r['cls'], r['box'], r['room'],
                                      anchors_of(r), r['axis'], r['truth_q'],
                                      prior=prior, others=others)
        W.append(w); C.append(cov); N += 1
        conflicts.append(cf)
        identified = bool(w <= 0.10 + 1e-9 and not cf)
        I10.append(identified)
        if identified:
            if not cov:
                NW.append(1)
    W = np.asarray(W); C = np.asarray(C, bool)
    per = {}
    for obj in sorted(set(r['obj'] for r in rows)):
        idx = [i for i, r in enumerate(rows) if r['obj'] == obj]
        per[obj] = dict(width_median=float(np.median(W[idx])), cover=float(np.mean(C[idx])))
    return dict(n=int(N), width_median=float(np.median(W)), width_mean=float(W.mean()),
                cover=float(C.mean()), identified=float(np.mean(np.asarray(I10))) if I10 else 0.0,
                narrow_wrong=(len(NW) / max(1, sum(I10))), per_object=per,
                conflict_fraction=float(np.mean(conflicts)),
                analysis_scope='Conditional intervals given supplied object frames and prior modes')


def thor_experiment(root):
    rows = thor_rows(root)
    out = {'n_axes': len(rows), 'n_scenes': len(set(r['scene'] for r in rows)), 'regime': 'U', 'subsets': []}
    for sub in SUBSETS:
        s = summarize(rows, lambda r, sub=sub: {c: r['anchors'][c] for c in sub if c in r['anchors']})
        s['subset'] = list(sub)
        # 逐物件拆开：每件家具只吃自己那一类的证据
        per = {}
        for obj in CLASS_OF:
            rs = [r for r in rows if r['obj'] == obj]
            per[obj] = summarize(rs, lambda r, sub=sub: {c: r['anchors'][c] for c in sub if c in r['anchors']})
        s['per_object'] = per
        out['subsets'].append(s)
    return out


def real_experiment(sess, truth):
    """真实录音：逐【单个事件】枚举。行按 (事件, 轴) 展开，锚点同类多事件取均值。"""
    pred = json.load(io.open(os.path.join(sess, 'prediction.json'), encoding='utf-8'))
    runs = json.load(io.open(os.path.join(sess, 'actions.json'), encoding='utf-8'))['runs']
    t, P = ID.traj(sess)
    evs = ID.events(t, P, runs)
    a = np.radians(pred['rot_deg']); c, s = np.cos(a), np.sin(a)
    R = np.array([[c, s], [-s, c]])
    off = (P @ R)[0] - np.array(pred['start_anchored_at'])
    room = pred['room']

    rows = []
    for cls in ID.CLASSES:
        obj = ID.OBJ[cls]
        box = pred['boxes'][obj]
        ev = evs.get(cls, [])
        for e in ev:
            e['room'] = list(map(float, e['pos'] @ R - off))
        kept, _rej = ID.consistency(ev, [ID.world_size(box, 0), ID.world_size(box, 1)])
        for j, i in enumerate(kept):
            for k in (0, 1):
                rows.append(dict(cls=cls, obj=obj, box=box, room=room, axis=k,
                                 anchor=np.asarray(ev[i]['room'], float), ev=j,
                                 t0=float(ev[i]['t0']), truth_q=float(truth[obj][k]),
                                 L=ID.world_size(box, k)))
    n_by = {cls: len(set((r['cls'], r['ev']) for r in rows if r['cls'] == cls)) for cls in ID.CLASSES}
    out = {'session': os.path.basename(os.path.normpath(sess)), 'n_by_class': n_by,
           'event_times': sorted({(r['cls'], round(r['t0'], 2)) for r in rows}),
           'subsets': [], 'leave_one_out': []}

    def run(sel, prior='box'):
        """sel: {cls: [event index, ...]}；返回统计。"""
        keep = set()
        for i, r in enumerate(rows):
            if r['ev'] in sel.get(r['cls'], []):
                keep.add(i)
        anc = {}
        for i in sorted(keep):
            anc.setdefault(rows[i]['cls'], []).append(rows[i]['anchor'])
        anc = {k: np.unique(np.array(v), axis=0) for k, v in anc.items()}
        s = summarize(rows, lambda r, anc=anc: {r['cls']: anc[r['cls']]} if r['cls'] in anc else {},
                      prior=prior)
        s['selection'] = {k: sorted(v) for k, v in sel.items()}
        s['classes_active'] = sorted(anc)
        return s

    full = {cls: list(range(n_by[cls])) for cls in ID.CLASSES}
    seen = set()
    cands = [{}] + [{cls: [j]} for cls in ID.CLASSES for j in range(n_by[cls])] + [full]
    for sel in cands:
        key = json.dumps({k: sorted(v) for k, v in sel.items()}, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out['subsets'].append(run(sel))
    out['u_prior'] = run(full, prior='U')
    base = [s for s in out['subsets'] if s['classes_active'] == sorted(ID.CLASSES)][0]
    out['base_width_median'] = base['width_median']
    out['base_cover'] = base['cover']
    for cls in ID.CLASSES:
        for j in range(n_by[cls]):
            sel = {k: list(v) for k, v in full.items()}
            sel[cls].remove(j)
            sb, su = run(sel, prior='box'), run(sel, prior='U')
            out['leave_one_out'].append({
                'removed': [cls, j], 'box': sb, 'u': su,
                'delta_box': {o: sb['per_object'][o]['width_median'] - base['per_object'][o]['width_median']
                              for o in base['per_object']},
                'delta_u': {o: su['per_object'][o]['width_median'] - out['u_prior']['per_object'][o]['width_median']
                            for o in base['per_object']}})
    return out


if __name__ == '__main__':
    root = __import__('paths').THOR
    thor = thor_experiment(root)
    sess = sys.argv[1] if len(sys.argv) > 1 else 'output/layout-recon/s-59d570ee'
    REF = {'bed': (1.17, 1.96, 2.695, 4.045), 'desk': (0.05, 1.05, 0.65, 2.10),
           'cab': (0.05, 0.0, 0.65, 1.05), 'chair': (1.11, 0.92, 1.55, 1.36)}
    real = real_experiment(sess, REF)
    res = {'thor': thor, 'real': real}
    json.dump(res, io.open(os.path.join(HERE, 'evidence_accum.json'), 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)
    print('iTHOR 场景 %d / 轴 %d' % (thor['n_scenes'], thor['n_axes']))
    print('%-28s %6s %8s %8s %8s %10s' % ('subset', 'n', 'median', 'cover', 'ident10', 'narrow_wrong'))
    for s in thor['subsets']:
        print('%-28s %6d %8.3f %8.1f%% %7.1f%% %9.1f%%' % (
            '+'.join(s['subset']) or '(none)', s['n'], s['width_median'], 100 * s['cover'],
            100 * s['identified'], 100 * s['narrow_wrong']))
    print('\n真实录音（贴墙先验档，与 RESULTS 可辨识性节同口径）：全保留宽度中位 %.3f m / 覆盖 %.0f%%'
          % (real['base_width_median'], 100 * real['base_cover']))
    print('真实录音（U 档，不知道贴哪面墙）：宽度中位 %.3f m' % real['u_prior']['width_median'])
    print('逐事件删除（对象级宽度变化；括号内为 U 档）：')
    for r in real['leave_one_out']:
        parts = []
        for o in ('cab', 'chair', 'bed'):
            b = r['box']['per_object'][o]['width_median']
            u = r['u']['per_object'][o]['width_median']
            parts.append('%s %.2f (%.2f)' % (o, b, u))
        print('  去掉 %-8s #%d -> %s' % (r['removed'][0], r['removed'][1], '  '.join(parts)))
