# 图：多模式候选的可靠性曲线 —— 保留多少候选，命中率涨多少、区域涨多少。
import io, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

HERE = os.path.dirname(os.path.abspath(__file__))
cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
D = json.load(io.open(os.path.join(HERE, 'modes.json'), encoding='utf-8'))
KS = ['1', '2', '3', '5', '10', '20']
NAME = {'bed': '床', 'desk': '桌', 'cab': '柜', 'chair': '椅'}
COL = {'bed': '#4c72b0', 'desk': '#dd8452', 'cab': '#55a868', 'chair': '#8172b3'}

fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.2), dpi=150)

ax = axes[0]
x = np.arange(len(KS))
for k in ('bed', 'desk', 'cab'):
    ys = [100 * np.mean([r[k]['hit'] for r in D['per_K'][K] if k in r]) for K in KS]
    ax.plot(x, ys, 'o-', color=COL[k], label=NAME[k], lw=2)
    ax.text(x[-1] + 0.08, ys[-1], '%.0f%%' % ys[-1], color=COL[k], fontsize=9, fontproperties=cjk, va='center')
ax.set_xticks(x); ax.set_xticklabels(KS)
ax.set_xlabel('保留的候选数 K', fontproperties=cjk)
ax.set_ylabel('命中率（候选集里有一个解误差 <= 0.5 m）', fontproperties=cjk)
ax.set_ylim(0, 105); ax.grid(alpha=0.3)
ax.set_title('AI2-THOR 15 场景：只留 argmax（K=1）时床 40%、柜 47%、桌 7%\n'
             '桌到 K=20 也只有 27%——它的误差不是候选排序问题', fontsize=10.5, loc='left', fontproperties=cjk)
ax.legend(fontsize=9, prop=cjk, loc='lower right')

ax = axes[1]
a = [np.median([r['desk']['area'] for r in D['per_K'][K] if 'desk' in r]) for K in KS]
ax.plot(x, a, 'o-', color='#c44e52', lw=2, label='桌候选集包围盒面积（中位）')
for i, v in enumerate(a):
    ax.text(x[i], v + 0.10, '%.2f' % v, ha='center', fontsize=8.5, fontproperties=cjk)
ax.set_xticks(x); ax.set_xticklabels(KS)
ax.set_xlabel('保留的候选数 K', fontproperties=cjk)
ax.set_ylabel('区域面积 (m²)', fontproperties=cjk)
ax.grid(alpha=0.3)
e1 = np.median([r['desk']['best_err'] for r in D['per_K']['1'] if 'desk' in r])
e20 = np.median([r['desk']['best_err'] for r in D['per_K']['20'] if 'desk' in r])
ax.set_title('代价是区域变大：1.07 -> 4.20 m²\n'
             '而桌的最优候选误差只从 %.2f m 降到 %.2f m（结构误差，留候选救不了）' % (e1, e20),
             fontsize=10.5, loc='left', fontproperties=cjk)
ax.legend(fontsize=9, prop=cjk, loc='lower right')

fig.suptitle('单模式 argmax 过度自信：把候选并起来能救床，救不了桌', fontsize=12.5, fontproperties=cjk)
fig.tight_layout(rect=[0, 0, 1, 0.93])
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'output', 'layout-recon', 'modes.png')
fig.savefig(out, facecolor='white')
print('saved', os.path.abspath(out))
