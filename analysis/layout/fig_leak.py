# 图：泄露曲线（残余不确定性 vs 活动跨度），以及按类别的残余分布。
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

rows = LC.params(ROOT)
spans = np.arange(0.0, 2.61, 0.05)
fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.2), dpi=150)

ax = axes[0]
for tol, col in ((0.3, '#4c72b0'), (0.5, '#dd8452'), (1.0, '#55a868')):
    ys = [100 * np.mean(LC.residual(rows, float(s)) > tol) for s in spans]
    ax.plot(spans, ys, lw=2, color=col, label='容差 %.1f m' % tol)
    y0 = ys[0]
    ax.plot([0], [y0], 'o', ms=6, color=col)
    ax.text(0.04, y0 + 1.6, '%.1f%%' % y0, fontsize=8.5, color=col, fontproperties=cjk)
ax.set_xlabel('活动在物体自由轴上的跨度 span (m)', fontproperties=cjk)
ax.set_ylabel('残余不确定性超过容差的参数比例 (%)', fontproperties=cjk)
ax.set_title('泄露曲线：%d 个场景、%d 个家具参数\n零跨度时仍有 81.3%% 的参数在 0.5 m 内，因为房间与物体各自把位置夹住了' %
             (len({r['scene'] for r in rows}), len(rows)), fontsize=10.5, loc='left', fontproperties=cjk)
ax.grid(alpha=0.25); ax.legend(fontsize=9, prop=cjk); ax.set_xlim(-0.02, 2.6)

ax = axes[1]
cats = [c for c in LC.CATS if any(r['cat'] == c for r in rows)]
BUCK = [(0.0, '被墙定死 / 残余 0', '#9ec9e8'),
        (0.5, '0 – 0.5 m', '#dd8452'),
        (1.0, '0.5 – 1.0 m', '#c44e52'),
        (99.0, '> 1.0 m', '#8172b3')]
ys = np.arange(len(cats))
left = np.zeros(len(cats))
for cap, lab, col in BUCK:
    prev = 0.0
    frac = []
    for c in cats:
        r = LC.residual([q for q in rows if q['cat'] == c], 0.0)
        frac.append(100.0 * np.mean((r > prev) & (r <= cap)) if cap > 0 else 100.0 * np.mean(r <= 0.0))
        prev = cap
    ax.barh(ys, frac, left=left, color=col, label=lab, height=0.62)
    for j, f in enumerate(frac):
        if f >= 6:
            ax.text(left[j] + f / 2, ys[j], '%.0f%%' % f, ha='center', va='center',
                    fontsize=8, color='white', fontproperties=cjk)
    left = left + np.array(frac)
ax.set_yticks(ys); ax.set_yticklabels(cats)
ax.invert_yaxis()
ax.set_xlabel('该类别参数占比 (%)', fontproperties=cjk)
ax.set_xlim(0, 100)
ax.set_title('按类别拆开：零跨度时的不确定性构成\n椅/柜本身很短，残余天然被封顶；床和搁架才可能出现 1 m 以上的滑动',
             fontsize=10.5, loc='left', fontproperties=cjk)
ax.legend(fontsize=8, prop=cjk, loc='lower right', framealpha=0.92)
ax.grid(axis='x', alpha=0.25)

fig.tight_layout()
fig.savefig(OUT, facecolor='white')
print('saved', OUT)
