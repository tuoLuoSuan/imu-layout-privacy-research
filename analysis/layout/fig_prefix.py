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

with open(os.path.join(HERE, 'prefix.json'), encoding='utf-8') as handle:
    data = json.load(handle)
rows = data['rows']
fig, axes = plt.subplots(1, 2, figsize=(6.3, 3.0), layout='constrained')
for obj, name, color in [('bed', '床', '#248a85'), ('desk', '桌', '#cc873f'),
                          ('cab', '柜', '#888888'), ('chair', '椅', '#596ba0')]:
    available = [row for row in rows if obj in row['err']]
    axes[0].plot([row['T'] for row in available], [row['err'][obj] for row in available],
                 'o-', markersize=3, color=color, label=name)
axes[0].set(xlabel='可用原始数据预算 T (s)', ylabel='家具中心误差 (m)', ylim=(0, 0.6))
axes[0].set_title('a 每个前缀重算轨迹与动作', loc='left', fontproperties=cjk)
axes[0].legend(prop=cjk, frameon=False, fontsize=7)
labels = {'walk': (0, '走'), 'seated': (1, '坐'), 'cabinet': (2, '柜'), 'lying': (3, '躺')}
for window in rows[-1]['action_windows']:
    if window['label'] in labels:
        y, name = labels[window['label']]
        axes[1].plot(window['available_s'], y, '|', color='#248a85', markersize=5)
complete = [row['T'] for row in rows if len(row['boxes']) == 4]
if complete:
    axes[1].axvline(complete[0], linestyle='--', color='#cc873f', linewidth=1)
axes[1].set(xlabel='预测窗口可用时间 (s)', yticks=[0, 1, 2, 3],
            yticklabels=['走', '坐', '柜', '躺'], ylim=(-0.4, 3.4))
axes[1].set_title('b 当前预测窗口的时间支持', loc='left', fontproperties=cjk)
for axis in axes:
    axis.grid(False)
fig.suptitle('真实单房 n=1；冻结动作模型，前缀仅使用已到达样本', fontproperties=cjk, fontsize=8)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '../../output/layout-recon/prefix.png')
fig.savefig(out, dpi=300, facecolor='white')
fig.savefig(os.path.splitext(out)[0] + '.pdf', facecolor='white')
fig.savefig(os.path.splitext(out)[0] + '.svg', facecolor='white')
print(os.path.abspath(out))
