# 真实录音上的消融：同一类动作多次发生时，「只取第一次」/「全部平均」/「一致性过滤后合并」
# 三条路线对最终布局的影响。真值来自雷达（与 analyze.py 同一份 REF）。
import os, sys, json, io
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reconstruct_blind as RB
import layout_solver as LS
import identifiability as ID

REF = {'bed': (1.17, 1.96, 2.695, 4.045), 'desk': (0.05, 1.05, 0.65, 2.10), 'cab': (0.05, 0.0, 0.65, 1.05),
       'chair': (1.11, 0.92, 1.55, 1.36)}


def errs(boxes):
    out = {}
    for k, b in boxes.items():
        r = REF[k]
        out[k] = {'max_abs_m': float(max(abs(b[i] - r[i]) for i in range(4))),
                  'center_m': float(np.hypot((b[0]+b[2]-r[0]-r[2])/2, (b[1]+b[3]-r[1]-r[3])/2))}
    return out


def run(sess):
    t, P = ID.traj(sess)
    runs = json.load(io.open(os.path.join(sess, 'actions.json'), encoding='utf-8'))['runs']
    evs = ID.events(t, P, runs)
    _, _, _, A0 = RB.anchors_from(sess)
    A_avg = {k: np.mean([e['pos'] for e in v], axis=0) for k, v in evs.items()}
    A_flt = {}
    for k, v in evs.items():
        size = (0.9, 0.6) if k == 'cabinet' else ((0.44, 0.44) if k == 'seated' else (1.525, 2.085))
        kept, _ = ID.consistency(v, size)
        A_flt[k] = np.mean([v[i]['pos'] for i in kept], axis=0)
    res = {}
    for name, A in (('first_event', A0), ('all_averaged', A_avg), ('consistency', A_flt)):
        p, _ = LS.solve(sess, save=False, anchors=dict(A))
        res[name] = {'status': p.get('status'), 'rot_deg': p.get('rot_deg'),
                     'cabinet_wall': p.get('cabinet_wall'), 'errors': errs(p['boxes']) if p.get('status') == 'ok' else None}
    return res, {k: {kk: list(map(float, vv)) for kk, vv in A.items()} for k, A in
                 (('first_event', A0), ('all_averaged', A_avg), ('consistency', A_flt))}


if __name__ == '__main__':
    sess = sys.argv[1]
    res, anc = run(sess)
    for name, r in res.items():
        print('== %s  status=%s rot=%s wall=%s' % (name, r['status'], r['rot_deg'], r['cabinet_wall']))
        if r['errors']:
            print('   ' + '  '.join('%s %.3f/%.3f' % (k, v['max_abs_m'], v['center_m']) for k, v in r['errors'].items()))
    print('anchors(RoNIN 系)')
    for name, A in anc.items():
        print('  %-13s %s' % (name, ' '.join('%s(%.2f,%.2f)' % (k, v[0], v[1]) for k, v in A.items())))
    json.dump({'sessions': {os.path.basename(sess): res}, 'anchors': anc},
              io.open(os.path.join(HERE, 'exp_average.json'), 'w', encoding='utf-8'), indent=1)
