# -*- coding: utf-8 -*-
# 图：前缀实验 —— 只给前 T 秒原始录音，端到端能出什么。
import io, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

HERE = os.path.dirname(os.path.abspath(__file__))
cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
D = json.load(io.open(os.path.join(HERE, 'prefix.json'), encoding='utf-8'))
ROWS = D['rows']
NAME = {'bed': '床', 'desk': '桌', 'cab': '柜', 'chair': '椅'}
COL = {'bed': '#4c72b0', 'desk': '#dd8452', 'cab': '#55a868', 'chair': '#8172b3'}
FULL = {'bed': 0.122, 'desk': 0.056, 'cab': 0.050, 'chair': 0.194}

fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.0), dpi=150,
                         gridspec_kw={'width_ratios': [1.15, 1.0]})

ax = axes[0]
Ts = [r['T'] for r in ROWS]
for o in ('bed', 'desk', 'cab', 'chair'):
    xs = [r['T'] for r in ROWS if o in r['err']]
    ys = [r['err'][o] for r in ROWS if o in r['err']]
    if not xs:
        continue
    ax.plot(xs, ys, '-o', ms=5, color=COL[o], label=NAME[o])
    ax.annotate('%.3f' % ys[0], (xs[0], ys[0]), textcoords='offset points',
                xytext=(0, 7), ha='center', fontsize=8, color=COL[o])
ax.axvspan(0, 15, color='#dddddd', alpha=0.55)
ax.axvspan(15, 24.5, color='#f2e6c8', alpha=0.55)
ax.axvspan(24.5, 44, color='#dcebd6', alpha=0.55)
ax.text(7.5, 0.9, '无解\n（坐事件没跑完）', ha='center', fontsize=9, fontproperties=cjk)
ax.text(19.7, 0.9, '只有椅\n（墙由椅子自己定）', ha='center', fontsize=9, fontproperties=cjk)
ax.text(34, 0.9, '桌柜椅\n（开柜事件进来）', ha='center', fontsize=9, fontproperties=cjk)
ax.text(50, 0.9, '四件齐\n（躺事件进来）', ha='center', fontsize=9, fontproperties=cjk)
ax.set_xlabel('只用到前 T 秒原始 IMU（整段 56.5 s）', fontproperties=cjk)
ax.set_ylabel('中心误差 (m)，对雷达真值', fontproperties=cjk)
ax.set_ylim(0, 1.0)
ax.grid(alpha=0.3)
ax.legend(fontsize=9, prop=cjk, loc='center right')
ax.set_title('同一段录音截断到前 T 秒：误差不是随 T 单调下降，而是「某条事件一进来就跳一下」\n'
             '（床 0.122 m 在 T=45 s 才出现；T<45 s 时床根本放不出来）', fontsize=10, loc='left', fontproperties=cjk)

ax = axes[1]
runs = [tuple(r) for r in ROWS[-1]['events']]
LAB = {'seated': '坐', 'cabinet': '开柜', 'lying': '躺', 'walk': '走', 'other': '其它'}
YS = {'walk': 0, 'seated': 1, 'cabinet': 2, 'lying': 3}
for l, a, b in runs:
    if l not in YS:
        continue
    ax.barh(YS[l], b - a, left=a, height=0.5, color='#8ab4d8' if l != 'lying' else '#4c72b0')
    ax.text((a + b) / 2, YS[l], LAB[l], ha='center', va='center', fontsize=8, fontproperties=cjk)
for x, t in ((16, 'T=16 s\n首个解'), (25, 'T=25 s\n桌柜椅'), (45, 'T=45 s\n四件齐')):
    ax.axvline(x, color='#c44e52', ls='--', lw=1.2)
    ax.text(x + 0.6, 3.62, t, fontsize=8.5, color='#c44e52', fontproperties=cjk, va='top')
ax.set_yticks([0, 1, 2, 3])
ax.set_yticklabels(['走', '坐', '开柜', '躺'], fontproperties=cjk)
ax.set_xlim(0, 56.5); ax.set_ylim(-0.6, 3.8)
ax.set_xlabel('时间 (s)', fontproperties=cjk)
ax.grid(axis='x', alpha=0.3)
ax.set_title('事件时间线：最后一条有用的事件在 40.5 s 结束；后面 16 s 的录音对布局没有贡献\n'
             '（前缀轨迹与整段轨迹的最大偏差 1.5e-8 m ， 截断没有改变前端）', fontsize=10, loc='left', fontproperties=cjk)

fig.suptitle('前缀实验（真实录音 s-59d570ee，端到端真跑）', fontsize=12.5, fontproperties=cjk)
fig.tight_layout(rect=[0, 0, 1, 0.92])
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'output', 'layout-recon', 'prefix.png')
fig.savefig(out, facecolor='white')
print('saved', os.path.abspath(out))
