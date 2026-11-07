# 图：可辨识性区间 vs 实测误差；以及「只取第一次 / 全部平均 / 一致性过滤」三条锚点路线。
import os, sys, json, io
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import identifiability as ID

cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
SESS = sys.argv[1] if len(sys.argv) > 1 else os.path.join('output/layout-recon/s-59d570ee')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(SESS, 'identifiability.png')

REF = {'bed': (1.17, 1.96, 2.695, 4.045), 'desk': (0.05, 1.05, 0.65, 2.10),
       'cab': (0.05, 0.0, 0.65, 1.05), 'chair': (1.11, 0.92, 1.55, 1.36)}
res = ID.analyze(SESS, truth=REF)
abl = json.load(io.open(os.path.join(HERE, 'exp_average.json'), encoding='utf-8'))
NAME = {'cab': '柜', 'chair': '椅', 'bed': '床', 'desk': '桌'}
ORDER = ['cab', 'chair', 'bed']

fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.4), dpi=150)
ax = axes[0]
h = 0.32
xs = np.arange(len(ORDER))
resid, meas, notes = [], [], []
for obj in ORDER:
    r = [q for q in res['rows'] if q['object'] == obj][0]
    A = r['axes']

    def ev_w(ax):
        lo, hi = A[ax]['event_interval']
        return np.inf if lo is None else hi - lo

    resid.append(max(A[a]['width_m'] for a in ('x', 'y')))
    meas.append(r.get('error_m', 0.0))
    notes.append('事件 %.2f / 先验 %.2f (%s)' % (
        min(ev_w(a) for a in ('x', 'y')),
        min(A[a]['prior_interval'][1] - A[a]['prior_interval'][0] for a in ('x', 'y')),
        A['x']['prior_kind']))
ax.bar(xs - h / 2, resid, h, label='残余可辨识宽度（预测）', color='#55a868')
ax.bar(xs + h / 2, meas, h, label='实测位置误差', color='#c44e52')
for j in range(len(ORDER)):
    ax.text(j - h / 2, resid[j] + 0.012, '%.2f' % resid[j], ha='center', fontsize=8.5, fontproperties=cjk)
    ax.text(j + h / 2, meas[j] + 0.012, '%.3f' % meas[j], ha='center', fontsize=8.5, fontproperties=cjk)
    ax.text(j, -0.075, notes[j], ha='center', fontsize=7.5, color='#666', fontproperties=cjk)
ax.set_ylim(0, 0.65)
ax.set_xticks(xs)
ax.set_xticklabels([NAME[o] for o in ORDER], fontproperties=cjk)
ax.set_ylabel('长度 (m)', fontproperties=cjk)
ax.set_title('残余宽度 = 事件区间 ∩ 先验区间（端点求交）\n柜/床的残余 = 贴墙容差 0.10 m；离墙的椅子还剩 0.54 m，只能靠活动范围收窄\n真值覆盖 5/6（床离右墙 0.145 m，超出 0.10 m 容差）', fontsize=10.5,
             loc='left', fontproperties=cjk)
ax.legend(fontsize=8.5, prop=cjk, loc='upper left'); ax.grid(axis='y', alpha=0.25)

ax = axes[1]
routes = [('first_event', '只取第一次（现状）'), ('all_averaged', '全部平均'), ('consistency', '一致性过滤')]
objs = ['cab', 'desk']
w = 0.26
for i, (key, lab) in enumerate(routes):
    vals = [abl['sessions'][list(abl['sessions'])[0]][key]['errors'][o]['center_m'] for o in objs]
    ax.bar(np.arange(len(objs)) + (i - 1) * w, vals, w, label=lab,
           color=['#4c72b0', '#c44e52', '#55a868'][i])
    for j, v in enumerate(vals):
        ax.text(j + (i - 1) * w, v + 0.04, '%.3f' % v, ha='center', fontsize=8,
                fontproperties=cjk)
ax.set_xticks(np.arange(len(objs)))
ax.set_xticklabels([NAME[o] for o in objs], fontproperties=cjk)
ax.set_ylabel('位置误差 (m)', fontproperties=cjk)
ax.set_title('同类动作发生两次时，平均会把锚点拉走\n柜：0.050 m -> 1.829 m（36 倍）', fontsize=11,
             loc='left', fontproperties=cjk)
ax.legend(fontsize=8.5, prop=cjk); ax.grid(axis='y', alpha=0.25)

fig.suptitle('s-59d570ee：可辨识性与锚点聚合方式', fontsize=12.5, fontproperties=cjk)
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(OUT, facecolor='white')
print('saved', OUT)
