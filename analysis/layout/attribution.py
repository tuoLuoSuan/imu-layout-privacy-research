# 证据归因：把某一个锚点推开一点，看哪件家具跟着动。
# 这是真实房间上的留一/扰动实验——不需要真值，回答的是「这条结论是靠哪条证据撑住的」。
import io, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout_solver as LS
import reconstruct_blind as RB

CLASSES = ('seated', 'cabinet', 'lying')
OBJS = ('bed', 'desk', 'cab', 'chair')
DELTAS = (-0.20, -0.10, 0.10, 0.20)


def boxes_of(p):
    return p['boxes'] if p.get('status') == 'ok' else None


def run(sess):
    _, _, _, A0 = RB.anchors_from(sess)
    base = LS.solve(sess, save=False)[0]
    if base.get('status') != 'ok':
        raise SystemExit('base solve failed: %s' % base.get('status'))
    B0 = base['boxes']
    rows = []
    for lab in CLASSES:
        for ax in (0, 1):
            for d in DELTAS:
                A = {k: np.array(v, float) for k, v in A0.items()}
                A[lab] = A[lab].copy()
                A[lab][ax] += d
                p = LS.solve(sess, save=False, anchors=A)[0]
                B = boxes_of(p)
                rec = {'class': lab, 'axis': 'xy'[ax], 'delta': d, 'status': p.get('status')}
                for o in OBJS:
                    if B is None:
                        rec[o] = None
                    else:
                        rec[o] = float(max(abs(B[o][i] - B0[o][i]) for i in range(4)))
                rows.append(rec)
    return rows


def summarize(rows):
    out = {}
    for lab in CLASSES:
        sel = [r for r in rows if r['class'] == lab]
        okr = [r for r in sel if r['status'] == 'ok']
        out[lab] = {o: (float(np.median([r[o] for r in okr])) if okr else None) for o in OBJS}
        out[lab]['n_ok'] = len(okr)
        out[lab]['n_all'] = len(sel)
    return out


if __name__ == '__main__':
    sess = sys.argv[1] if len(sys.argv) > 1 else 'output/layout-recon/s-59d570ee'
    rows = run(sess)
    s = summarize(rows)
    print('扰动 3 个锚点 × 2 轴 × 4 个位移 = %d 次求解' % len(rows))
    print('%-8s %8s %8s %8s %8s   %s' % ('被推的锚点', '床', '桌', '柜', '椅', '解出/总'))
    for lab in CLASSES:
        d = s[lab]
        print('%-8s %8s %8s %8s %8s   %d/%d' % (
            lab, *['   -   ' if d[o] is None else '%.3f' % d[o] for o in OBJS], d['n_ok'], d['n_all']))
    bad = [r for r in rows if r['status'] != 'ok']
    if bad:
        print('扰动后解不出的情况：')
        for r in bad[:8]:
            print('   %-8s %s%+.2f -> %s' % (r['class'], r['axis'], r['delta'], r['status']))
    json.dump({'session': os.path.basename(sess), 'rows': rows, 'summary': s},
              io.open(os.path.join(HERE, 'attribution.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
