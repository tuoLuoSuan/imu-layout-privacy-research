# 图：泄露曲线（残余不确定性 vs 活动跨度），2026-11-07 第二次修正后重画。
# 修正内容：最小坐标 q 参数化、逐轴贴墙、负间隙单列、K 只覆盖真贴墙的参数、报覆盖率。
import os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import leakage_curve as LC

cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
ROOT = sys.argv[1] if len(sys.argv) > 1 else 'output/thor'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'output/layout-recon/leakage-curve.png'

ROOM = (2.84, 4.045)
REF = {'bed': (1.17, 1.96, 2.695, 4.045), 'desk': (0.05, 1.05, 0.65, 2.10),
       'cab': (0.05, 0.0, 0.65, 1.05), 'chair': (1.11, 0.92, 1.55, 1.36)}
real_gap = []
for k, b in REF.items():
    for ax in (0, 1):
        real_gap.append(min(b[ax] - 0.0, ROOM[ax] - b[ax + 2]))
real_gap = np.array(real_gap)

rows = LC.params(ROOT)
spans = np.arange(0.0, 2.61, 0.1)
fig, axes = plt.subplots(1, 3, figsize=(17.4, 5.2), dpi=150)

# (a) 实测 U 曲线 + 解析的「贴墙」情形
ax = axes[0]
for tol, col in ((0.5, '#dd8452'), (1.0, '#55a868')):
    ys = [100 * LC.share_exceed(rows, float(s), tol, 'U') for s in spans]
    ax.plot(spans, ys, lw=2, color=col, label='容差 %.1f m（U：不知道贴哪面墙）' % tol)
    ax.plot([0], [ys[0]], 'o', ms=6, color=col)
    ax.text(0.05, ys[0] + 1.8, '%.1f%%' % ys[0], fontsize=8.5, color=col, fontproperties=cjk)
ax.axhline(5, color='#888', lw=0.9, ls=':')
ax.text(1.55, 6.2, '5% 目标线', fontsize=8, color='#666', fontproperties=cjk)
ax.set_xlabel('活动在物体自由轴上的跨度 span (m)', fontproperties=cjk)
ax.set_ylabel('残余不确定性超过容差的参数比例 (%)', fontproperties=cjk)
ax.set_title('泄露曲线：%d 场景 %d 个参数（iTHOR 家具普遍不贴墙）\n'
             '若该轴真贴墙，残余恒等于贴墙容差，跨度不再起作用' %
             (len({r['scene'] for r in rows}), len(rows)), fontsize=10.5, loc='left', fontproperties=cjk)
ax.grid(alpha=0.25); ax.legend(fontsize=7.6, prop=cjk); ax.set_xlim(-0.02, 2.6)

# (b) 贴墙比例 vs 容差：iTHOR（实测）与真实房间
ax = axes[1]
tols = np.array([0.05, 0.10, 0.15, 0.20, 0.30, 0.50])
sim, real = [], []
for t in tols:
    sim.append(100 * np.mean([r['gap'] <= t + 1e-9 for r in rows]))
    real.append(100 * np.mean(real_gap <= t + 1e-9))
ax.plot(tols, sim, 'o-', color='#4c72b0', label='AI2-THOR 25 场景 364 轴参数')
ax.plot(tols, real, 's-', color='#c44e52', label='本房间 4 件家具 8 轴参数（含桌、椅）')
for t, v in zip(tols, sim):
    if t in (0.10, 0.30):
        ax.annotate('%.0f%%' % v, (t, v), textcoords='offset points', xytext=(2, 7), fontsize=8, fontproperties=cjk)
for t, v in zip(tols, real):
    if t in (0.10, 0.15):
        ax.annotate('%.0f%%' % v, (t, v), textcoords='offset points', xytext=(2, -13), fontsize=8,
                    color='#c44e52', fontproperties=cjk)
ax.set_xlabel('「贴墙」容差 (m)', fontproperties=cjk)
ax.set_ylabel('被判为贴墙的参数比例 (%)', fontproperties=cjk)
ax.set_title('贴墙比例是数据集属性，不是物理常数\n'
             'iTHOR 间隙中位 0.61 m；本房间 8 个轴里 4 个 <=0.10 m',
             fontsize=10.5, loc='left', fontproperties=cjk)
ax.grid(alpha=0.25); ax.legend(fontsize=8, prop=cjk); ax.set_ylim(-3, 103)

# (c) 按类别：零跨度时的残余（U 档）
ax = axes[2]
cats = [c for c in LC.CATS if any(r['cat'] == c for r in rows)]
med = [float(np.median(LC.residual([q for q in rows if q['cat'] == c], 0.0, 'U'))) for c in cats]
ys = np.arange(len(cats))
ax.barh(ys, med, color='#9ec9e8', height=0.62)
for j, v in enumerate(med):
    ax.text(v + 0.04, ys[j], '%.2f m' % v, va='center', fontsize=8.5, fontproperties=cjk)
ax.set_yticks(ys); ax.set_yticklabels(cats)
ax.invert_yaxis()
ax.set_xlabel('零跨度时的残余宽度中位 (m)', fontproperties=cjk)
ax.set_xlim(0, max(med) * 1.30)
ax.set_title('按类别（U 档）：床最长、残余最大\n'
             '物体越长，能被事件钉住的比例越小', fontsize=10.5, loc='left', fontproperties=cjk)
ax.grid(axis='x', alpha=0.25)

fig.tight_layout()
fig.savefig(OUT, facecolor='white')
print('saved', OUT)
print('iTHOR 贴墙(tol=0.10) %.1f%%  真实房间 %.1f%%' % (
    100 * np.mean([r['gap'] <= 0.10 + 1e-9 for r in rows]), 100 * np.mean(real_gap <= 0.10 + 1e-9)))
