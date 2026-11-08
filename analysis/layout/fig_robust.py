import json
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
HERE = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({'font.family': ['Arial', 'SimSun'], 'font.size': 7,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'pdf.fonttype': 42, 'svg.fonttype': 'none'})
cjk = FontProperties(family=['Arial', 'SimSun'])

with open(os.path.join(HERE, 'robust.json'), encoding='utf-8') as handle:
    data = json.load(handle)
fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.9), layout='constrained')
for index, backend in enumerate(('place', 'joint')):
    row = data['a'][backend]
    for offset, field, limits, color, label in (
        (-0.17, 'auc', 'ci', '#248a85', '几何宽度'),
        (0.17, 'auc_size', 'ci_size', '#aaaaaa', '类别尺寸')):
        value = row[field]
        error = [[value - row[limits][0]], [row[limits][1] - value]]
        axes[0].bar(index + offset, value, 0.30, color=color,
                    yerr=error, capsize=2, label=label if index == 0 else None)
axes[0].axhline(0.5, color='#777', linestyle=':', linewidth=0.8)
axes[0].set(xticks=[0, 1], xticklabels=['place', 'joint'], ylim=(0, 1.05), ylabel='AUC')
axes[0].set_title('a 误差超过 0.5 m 的探索性排序', loc='left', fontproperties=cjk)
axes[0].legend(prop=cjk, frameon=False, fontsize=7)
selected = [row for row in data['b'] if row['reach_cab'] == 0.6]
axes[1].plot([row['tol'] for row in selected], [row['cover'] for row in selected],
             'o-', color='#248a85', markersize=3, label='覆盖真值')
axes[1].plot([row['tol'] for row in selected], [row['n_wide'] for row in selected],
             's--', color='#cc873f', markersize=3, label='宽度超过容差')
axes[1].set(xlabel='假定容差 (m)', ylabel='轴数', ylim=(0, 6.5))
axes[1].set_title('b 单房六轴的假设敏感性', loc='left', fontproperties=cjk)
axes[1].legend(prop=cjk, frameon=False, fontsize=7)
for axis in axes:
    axis.grid(False)
fig.suptitle('a：按房重抽 95% 区间；b：单房描述性计数；均为 oracle 诊断', fontproperties=cjk, fontsize=8)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '../../output/layout-recon/robust.png')
fig.savefig(out, dpi=300, facecolor='white')
fig.savefig(os.path.splitext(out)[0] + '.pdf', facecolor='white')
fig.savefig(os.path.splitext(out)[0] + '.svg', facecolor='white')
print(os.path.abspath(out))
