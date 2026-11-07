# -*- coding: utf-8 -*-
# 图：稳健性审计 —— 上界到底有没有信息量，换容差哪些结论会翻。
import io, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

HERE = os.path.dirname(os.path.abspath(__file__))
cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
D = json.load(io.open(os.path.join(HERE, 'robust.json'), encoding='utf-8'))

fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.0), dpi=150)

ax = axes[0]
names = ['place', 'joint']
x = np.arange(2)
auc = [D['a'][k]['auc'] for k in names]
lo = [D['a'][k]['auc'] - D['a'][k]['ci'][0] for k in names]
hi = [D['a'][k]['ci'][1] - D['a'][k]['auc'] for k in names]
base = [D['a'][k]['auc_size'] for k in names]
ax.bar(x - 0.18, auc, 0.34, yerr=[lo, hi], capsize=4, color='#4c72b0',
       label='区间说「会越界」的样本，实测误差确实更大')
ax.bar(x + 0.18, base, 0.34, color='#bbbbbb', label='基线：只用物体尺寸（没有区间信息）')
fig.canvas.draw()
for i, (a, b) in enumerate(zip(auc, base)):
    ax.text(i - 0.18, a + hi[i] + 0.05, '%.2f' % a, ha='center', fontsize=9, fontproperties=cjk)
    ax.text(i + 0.18, b + 0.045, '%.2f' % b, ha='center', fontsize=9, fontproperties=cjk)
ax.axhline(0.5, ls=':', color='#888', lw=1)
ax.text(1.42, 0.52, '0.5 = 纯猜测', fontsize=8.5, color='#666', fontproperties=cjk, ha='right')
ax.set_xticks(x); ax.set_xticklabels(['place 后端', 'joint 后端'], fontproperties=cjk)
ax.set_ylim(0, 1.12); ax.set_ylabel('AUC（越界 vs 合规 的误差可分性）', fontproperties=cjk)
ax.grid(axis='y', alpha=0.3)
ax.set_title('区间不紧，但它知道「哪里会错」\n'
             '越界 9 条吃掉全部误差质量的 48%（place）', fontsize=10.5, loc='left', fontproperties=cjk)
ax.legend(fontsize=8.5, prop=cjk, loc='lower left')

ax = axes[1]
B = [r for r in D['b'] if abs(r['reach_cab'] - 0.60) < 1e-9]
tols = [r['tol'] for r in B]
cov = [r['cover'] for r in B]
wide = [r['n_wide'] for r in B]
ax.plot(tols, cov, 'o-', color='#55a868', lw=2, label='真值落在残余区间内的轴数（共 6）')
ax.plot(tols, wide, 's--', color='#c44e52', lw=1.6, label='残余宽度 > 容差的轴数（= 不由墙决定）')
for t, c, w in zip(tols, cov, wide):
    ax.text(t, c + 0.12, '%d' % c, ha='center', fontsize=8.5, fontproperties=cjk)
    ax.text(t + 0.006, w + 0.16, '%d' % w, ha='left', fontsize=8.5, color='#c44e52', fontproperties=cjk)
ax.axvspan(0.15, 0.25, color='#4c72b0', alpha=0.10)
ax.text(0.20, 6.55, '结论不变区：\n只有椅子两轴由活动跨度决定', ha='center', fontsize=9,
        fontproperties=cjk, color='#2b4f7a')
ax.set_xlabel('贴墙 / 相邻 容差 TOL (m)', fontproperties=cjk)
ax.set_ylabel('轴数（共 6：柜 x,y；椅 x,y；床 x,y）', fontproperties=cjk)
ax.set_ylim(0, 7.2); ax.grid(alpha=0.3)
ax.set_title('换容差时什么会翻：床是否算「贴墙」\n'
             'TOL 0.15–0.25 时覆盖 6/6，且唯一自由轴是椅子', fontsize=10.5, loc='left', fontproperties=cjk)
ax.legend(fontsize=8.5, prop=cjk, loc='lower right')

fig.suptitle('稳健性审计：区间上界的信息量，以及结论对假设的敏感性', fontsize=12.5, fontproperties=cjk)
fig.tight_layout(rect=[0, 0, 1, 0.93])
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'output', 'layout-recon', 'robust.png')
fig.savefig(out, facecolor='white')
print('saved', os.path.abspath(out))
