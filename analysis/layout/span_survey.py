# 现有真实录音里，同一类动作发生过几次、跨度多大？——用现有数据看「跨度项」有没有被真实数据覆盖过。
import glob, io, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import identifiability as ID

SIZE = {'cabinet': (0.9, 0.6), 'seated': (0.44, 0.44), 'lying': (1.525, 2.085)}
rows = []
for sess in sorted(glob.glob('output/layout-recon/*')):
    ap = os.path.join(sess, 'actions.json')
    rp = os.path.join(sess, 'ronin-xy.npy')
    if not (os.path.exists(ap) and os.path.exists(rp)):
        continue
    t, P = ID.traj(sess)
    runs = json.load(io.open(ap, encoding='utf-8'))['runs']
    evs = ID.events(t, P, runs)
    rec = {'session': os.path.basename(sess), 'classes': {}}
    for lab in ID.CLASSES:
        ev = evs.get(lab, [])
        if not ev:
            continue
        kept, rej = ID.consistency(ev, SIZE[lab])
        pos = np.array([e['pos'] for e in ev])
        span_all = float(np.linalg.norm(pos.max(0) - pos.min(0))) if len(pos) > 1 else 0.0
        kp = pos[kept]
        span_kept = float(np.linalg.norm(kp.max(0) - kp.min(0))) if len(kp) > 1 else 0.0
        L = max(SIZE[lab])
        rec['classes'][lab] = {'n': len(ev), 'kept': len(kept), 'rej': len(rej),
                               'span_all': span_all, 'span_kept': span_kept, 'L': L,
                               'inconsistent': bool(span_kept > L + ID.TOL),
                               'durations': [round((e['t1'] - e['t0']), 1) for e in ev]}
    rows.append(rec)

print('有动作与轨迹的会话 %d 个' % len(rows))
print('%-24s %-8s %2s %5s %7s %7s' % ('session', 'class', 'n', 'kept', 'span_all', 'span_kept'))
for r in rows:
    for lab, d in r['classes'].items():
        print('%-24s %-8s %2d %5d %7.2f %7.2f' % (r['session'][:24], lab, d['n'], d['kept'],
                                                   d['span_all'], d['span_kept']))
hit = [(r['session'], lab, d) for r in rows for lab, d in r['classes'].items() if d['kept'] > 1]
print()
print('过滤后仍有 >=2 次事件（真实数据里跨度 > 0）的：%d 项' % len(hit))
for s, lab, d in hit:
    print('  %-24s %-8s span %.2f m / L %.2f m（%d 次，拒 %d）%s' % (
        s[:24], lab, d['span_kept'], d['L'], d['kept'], d['rej'],
        '  -> 不一致：两次不可能落在同一件上' if d['inconsistent'] else ''))
valid = [h for h in hit if not h[2]['inconsistent']]
print('其中「跨度有效且 > 0」的：%d 项' % len(valid))
json.dump(rows, io.open(os.path.join(HERE, 'span_survey.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
