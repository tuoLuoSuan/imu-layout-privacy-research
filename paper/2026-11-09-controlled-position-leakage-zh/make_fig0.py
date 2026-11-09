"""图0：三层证据链总纲图。数值全部来自已冻结结果，不重算推断。"""
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as B

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

ROWS_A = [
    ('同点重复（3,978/10,000）', 39.78, 3978, 10000, B.GRAY),
    ('分散接触（6,470/10,000）', 64.70, 6470, 10000, B.BLUE),
    ('＋ 桌近墙先验（826/1,000）', 82.60, 826, 1000, B.TEAL),
    ('＋ 桌近墙先验 ＋ 有限解码器（945/1,000）', 94.50, 945, 1000, B.GOLD),
]
ROWS_B = [
    ('冻结原始双设备（17/32）', 53.13, 17, 32, B.TEAL),
    ('真值位姿 ＋ 预测动作（26/32）', 81.25, 26, 32, B.BLUE),
]

fig = plt.figure(figsize=(183 / 25.4, 122 / 25.4))
gs = fig.add_gridspec(3, 2, width_ratios=[1, .004], height_ratios=[1.55, 1.0, .42],
                      left=.405, right=.965, top=.845, bottom=.115, hspace=.62, wspace=0)
axA = fig.add_subplot(gs[0, 0]); axB = fig.add_subplot(gs[1, 0], sharex=axA); axC = fig.add_subplot(gs[2, 0], sharex=axA)


def draw(ax, rows, gap=.9):
    for i, (lab, pct, k, n, col) in enumerate(rows):
        y = len(rows) - 1 - i
        lo, hi = B.wilson(k, n)
        ax.plot([0, pct], [y, y], color='#d7dee3', lw=2.2, solid_capstyle='butt', zorder=1)
        ax.plot([lo, hi], [y, y], color=col, lw=1.0, alpha=.55, zorder=2)
        ax.scatter([pct], [y], s=42, color=col, edgecolors='white', linewidths=.9, zorder=3)
        ax.text(-2.2, y, lab, ha='right', va='center', fontsize=7.4, color=B.INK)
        ax.text(pct + 1.6, y, '%.1f%%' % pct, ha='left', va='center', fontsize=7.4,
                color=col, fontweight='bold')
        if not (lo <= pct <= hi):
            pass
    ax.set_ylim(-.65, len(rows) - .35)
    ax.set_yticks([])
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.spines['bottom'].set_color('#8f9aa3')


draw(axA, ROWS_A)
axA.set_title('几何证据层：同路线、同访次（100% 覆盖 / 14 次交互）只改变接触落点', loc='left', fontsize=7.6,
              color='#526574', pad=6)
axA.annotate('', xy=(82.6, 1.42), xytext=(64.70, 1.42),
             arrowprops=dict(arrowstyle='-|>', color=B.GOLD, lw=.9, shrinkA=0, shrinkB=2))
axA.text(73.6, 1.52, '+17.9 pp', ha='center', fontsize=6.6, color=B.GOLD)
axA.annotate('', xy=(94.5, .42), xytext=(82.6, .42),
             arrowprops=dict(arrowstyle='-|>', color=B.GOLD, lw=.9, shrinkA=0, shrinkB=2))
axA.text(88.5, .52, '+11.9 pp', ha='center', fontsize=6.6, color=B.GOLD)

draw(axB, ROWS_B)
axB.set_title('设备证据层：同一 32 条冻结长记录与同一解码器，只改变前端位姿', loc='left', fontsize=7.6,
              color='#526574', pad=6)
axB.annotate('', xy=(81.25, .42), xytext=(53.13, .42),
             arrowprops=dict(arrowstyle='-|>', color=B.BLUE, lw=.9, shrinkA=0, shrinkB=2))
axB.text(67.2, .52, '+28.1 pp', ha='center', fontsize=6.6, color=B.BLUE)

axC.set_ylim(-.5, 1.0); axC.set_yticks([])
for s in ('top', 'right', 'left'):
    axC.spines[s].set_visible(False)
axC.spines['bottom'].set_color('#8f9aa3')
axC.plot([0, 100], [.5, .5], color='#d7dee3', lw=2.2, solid_capstyle='butt')
axC.scatter([100], [.5], s=42, color=B.GOLD, edgecolors='white', linewidths=.9, zorder=3)
axC.text(-2.2, .5, '真实单房原生产链（4/4，n=1，仅存在性）', ha='right', va='center', fontsize=7.2, color=B.INK)
axC.text(99, .95, '中心误差 0.09–0.23 m', ha='right', va='center', fontsize=6.6, color=B.GOLD)
axC.set_title('真实记录层：单间宿舍，不做跨域推断', loc='left', fontsize=7.6, color='#526574', pad=6)

for ax in (axA, axB, axC):
    ax.set_xlim(0, 104)
    ax.set_xticks(range(0, 101, 20))
    ax.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.tick_params(axis='x', labelsize=6.8, colors='#526574', length=2.5)
for ax in (axA, axB):
    ax.axvline(80, color=B.GOLD, ls=(0, (3, 2.4)), lw=.7, alpha=.75, zorder=0)

axC.set_xlabel('整屋全中率（%）：该房全部目标命中且无多报少报', fontsize=7.2, color='#526574', labelpad=4)

fig.text(.028, .955, '三层证据链：几何上界、设备取得与真实单房', fontsize=11, fontweight='bold', color=B.INK)
fig.text(.028, .905, '各层的房间集合、分母与解码器不同，纵向不可连成同一条响应曲线；横线为 Wilson 95% 区间，金色虚线为 80% 展示端点',
         fontsize=7.0, color='#526574')
fig.text(.028, .045, '几何层为受控生成族；设备层为同域冻结长记录；真实层为单间宿舍的零错时复放。', fontsize=6.2, color='#526574')

fig.canvas.draw()
for ext in ('pdf', 'svg', 'png'):
    fig.savefig(B.F / ('图0_三层证据链.' + ext), facecolor='white', dpi=600)
plt.close(fig)
B.source('fig0-source.csv', [
    {'stage': 'geometry', 'arm': 'repeat', 'k': 3978, 'n': 10000, 'pct': 39.78},
    {'stage': 'geometry', 'arm': 'dispersed', 'k': 6470, 'n': 10000, 'pct': 64.70},
    {'stage': 'geometry', 'arm': 'dispersed_wall', 'k': 826, 'n': 1000, 'pct': 82.60},
    {'stage': 'geometry', 'arm': 'dispersed_wall_depth', 'k': 945, 'n': 1000, 'pct': 94.50},
    {'stage': 'device', 'arm': 'frozen_raw', 'k': 17, 'n': 32, 'pct': 53.13},
    {'stage': 'device', 'arm': 'truth_pose', 'k': 26, 'n': 32, 'pct': 81.25},
    {'stage': 'real', 'arm': 'single_room', 'k': 4, 'n': 4, 'pct': 100.0},
])
print('ok')
