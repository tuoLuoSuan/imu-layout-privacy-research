# -*- coding: utf-8 -*-
# 图：部分事件 —— 每个锚点给谁带来价值，以及删掉一个锚点会不会改变别人的答案。
import io, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

HERE = os.path.dirname(os.path.abspath(__file__))
cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
ROWS = json.load(io.open(os.path.join(HERE, 'partial.json'), encoding='utf-8'))
SUBS = ['scl', 'sc', 'sl', 'cl', 's', 'c']
NAME = {'bed': '床', 'desk': '桌', 'cab': '柜', 'chair': '椅'}
COL = {'bed': '#4c72b0', 'desk': '#dd8452', 'cab': '#55a868', 'chair': '#8172b3'}
LAB = {'scl': '坐+柜+躺', 'sc': '坐+柜', 'sl': '坐+躺', 'cl': '柜+躺', 's': '只坐', 'c': '只柜'}

fig, axes = plt.subplots(1, 2, figsize=(13.4, 5.2), dpi=150)

ax = axes[0]
objs = ['bed', 'desk', 'cab']
w = 0.26
for j, o in enumerate(objs):
    for i, s in enumerate(SUBS):
        e = [r['err'][o] for r in ROWS if r['subset'] == s and 'err' in r and o in r['err']]
        if not e:
            continue
        ax.bar(i + (j - 1) * w, np.median(e), w * 0.9, color=COL[o],
               label=NAME[o] if i == 0 else None)
    # 标注命中率
ax.set_xticks(range(len(SUBS)))
ax.set_xticklabels([LAB[s] for s in SUBS], fontproperties=cjk)
ax.set_ylabel('中心误差中位 (m)', fontproperties=cjk)
ax.grid(axis='y', alpha=0.3)
ax.legend(fontsize=9, prop=cjk)
ax.set_title('越靠左证据越多；但柜在「只柜」时反而更准（0.45 vs 0.51 m）\n'
             '椅恒为 0（框就以坐锚点为中心，属平凡覆盖，未画）', fontsize=10.5, loc='left', fontproperties=cjk)

ax = axes[1]
pairs = [('去掉躺', 'desk', 8), ('去掉坐', 'desk', 8), ('去掉躺', 'bed', 2), ('去掉柜', 'bed', 4),
         ('去掉柜', 'cab', 3), ('去掉坐', 'chair', 0)]
labels = ['%s→%s' % (a.replace('去掉', '去'), NAME[o]) for a, o, _ in pairs]
vals = [v for _, _, v in pairs]
cols = ['#c44e52' if v >= 5 else ('#dd8452' if v > 0 else '#bbbbbb') for v in vals]
ax.barh(range(len(vals)), vals, color=cols)
for i, v in enumerate(vals):
    ax.text(v + 0.12, i, '%d / 15' % v, va='center', fontsize=9, fontproperties=cjk)
ax.set_yticks(range(len(vals))); ax.set_yticklabels(labels, fontproperties=cjk)
ax.invert_yaxis()
ax.set_xlim(0, 16); ax.set_xlabel('删掉这个锚点后，其他家具的框发生变化的场景数', fontproperties=cjk)
ax.grid(axis='x', alpha=0.3)
ax.set_title('但联合求解是不重叠约束耦合的：\n删掉躺，桌的框在 8/15 个场景里也变了', fontsize=10.5,
             loc='left', fontproperties=cjk)

fig.suptitle('部分事件：证据的对象局部性是区间模型的属性，不是求解器的', fontsize=12.5, fontproperties=cjk)
fig.tight_layout(rect=[0, 0, 1, 0.93])
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'output', 'layout-recon', 'partial.png')
fig.savefig(out, facecolor='white')
print('saved', os.path.abspath(out))
