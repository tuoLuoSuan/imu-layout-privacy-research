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

with open(os.path.join(HERE, 'modes.json'), encoding='utf-8') as handle:
    data = json.load(handle)
counts = ['1', '2', '3', '5', '10', '20']
x = np.arange(len(counts))
fig, axes = plt.subplots(2, 2, figsize=(6.3, 5.0), layout='constrained')
for obj, name, color in [('bed', '床', '#248a85'), ('desk', '桌', '#cc873f'), ('cab', '柜/架', '#888888')]:
    values = [[row[obj] for row in data['per_K'][count] if obj in row] for count in counts]
    axes[0, 0].plot(x, [100 * np.mean([v['hit'] for v in rows]) for rows in values],
                     'o-', markersize=3, color=color, label=name)
    axes[0, 1].plot(x, [np.nanmedian([np.nan if v['center_diameter'] is None else v['center_diameter'] for v in rows]) for rows in values],
                     'o-', markersize=3, color=color, label=name)
    axes[1, 0].plot(x, [np.nanmedian([np.nan if v['area'] is None else v['area'] for v in rows]) for rows in values],
                     'o-', markersize=3, color=color, label=name)
axes[1, 1].plot(x, [100 * np.mean([row['full_layout_hit'] for row in data['per_K'][count]])
                         for count in counts], 'o-', markersize=3, color='#248a85')
for axis in axes.flat:
    axis.set_xticks(x, counts)
    axis.set_xlabel('候选数 K（离散档位）', fontproperties=cjk)
    axis.grid(False)
axes[0, 0].set_title('a 逐家具候选命中', loc='left', fontproperties=cjk)
axes[0, 0].set(ylabel='命中率 (%)', ylim=(0, 105))
axes[0, 0].legend(prop=cjk, frameon=False, fontsize=7)
axes[0, 1].set_title('b 同对象的位置分歧', loc='left', fontproperties=cjk)
axes[0, 1].set_ylabel('中心直径中位 (m)', fontproperties=cjk)
axes[1, 0].set_title('c 同对象的占地包围盒', loc='left', fontproperties=cjk)
axes[1, 0].set_ylabel('面积中位 (m²)', fontproperties=cjk)
axes[1, 1].set_title('d 同一候选的完整布局命中', loc='left', fontproperties=cjk)
axes[1, 1].set(ylabel='命中率 (%)', ylim=(0, 105))
if all(not row['full_layout_hit'] for count in counts for row in data['per_K'][count]):
    axes[1, 1].text(0.5, 0.62, '0 / %d' % data['scenes'], transform=axes[1, 1].transAxes,
                    ha='center', fontsize=22, color='#cc873f')
    axes[1, 1].text(0.5, 0.42, '所测候选数均未命中完整布局', transform=axes[1, 1].transAxes,
                    ha='center', fontproperties=cjk, fontsize=8)
fig.suptitle('几何输入诊断；中心误差容限 0.5 m，场景 n=%d' % data['scenes'], fontproperties=cjk, fontsize=8)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '../../output/layout-recon/modes.png')
fig.savefig(out, dpi=300, facecolor='white')
fig.savefig(os.path.splitext(out)[0] + '.pdf', facecolor='white')
fig.savefig(os.path.splitext(out)[0] + '.svg', facecolor='white')
print(os.path.abspath(out))
