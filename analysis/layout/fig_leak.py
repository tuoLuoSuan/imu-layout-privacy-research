# 图：泄露曲线（残余不确定性 vs 活动跨度）。契约修正后重画（floor = 中心+尺寸）。
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
spans = np.arange(0.0, 2.61, 0.1)
fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.2), dpi=150)

ax = axes[0]
for tol, col in ((0.5, '#dd8452'), (1.0, '#55a868')):
    ys = [100 * LC.share_exceed(rows, float(s), tol, 'U') for s in spans]
    ax.plot(spans, ys, lw=2, color=col, label='容差 %.1f m（U：不知道贴哪面墙）' % tol)
    ax.plot([0], [ys[0]], 'o', ms=6, color=col)
    ax.text(0.05, ys[0] + 1.8, '%.1f%%' % ys[0], fontsize=8.5, color=col, fontproperties=cjk)
ysK = [100 * LC.share_exceed(rows, float(s), 0.5, 'K') for s in spans]
ax.plot(spans, ysK, lw=1.4, ls='--', color='#8172b3', label='容差 0.5 m（K：知道贴具体一面墙）')
ax.axhline(5, color='#888', lw=0.9, ls=':')
ax.text(1.55, 6.2, '5% 目标线', fontsize=8, color='#666', fontproperties=cjk)
ax.set_xlabel('活动在物体自由轴上的跨度 span (m)', fontproperties=cjk)
ax.set_ylabel('残余不确定性超过容差的参数比例 (%)', fontproperties=cjk)
ax.set_title('泄露曲线：%d 个场景、%d 个家具参数（floor 契约修正后重算）\n'
             '零跨度时中位残余 0.59 m；把 95%% 参数压进 0.5 m 需 1.7 m 跨度' %
             (len({r['scene'] for r in rows}), len(rows)), fontsize=10.5, loc='left', fontproperties=cjk)
ax.grid(alpha=0.25); ax.legend(fontsize=8, prop=cjk); ax.set_xlim(-0.02, 2.6)

ax = axes[1]
cats = [c for c in LC.CATS if any(r['cat'] == c for r in rows)]
med = [float(np.median(LC.residual([q for q in rows if q['cat'] == c], 0.0, 'U'))) for c in cats]
ys = np.arange(len(cats))
ax.barh(ys, med, color='#9ec9e8', height=0.62)
for j, v in enumerate(med):
    ax.text(v + 0.04, ys[j], '%.2f m' % v, va='center', fontsize=8.5, fontproperties=cjk)
ax.axvline(0.10, color='#c44e52', lw=1.2, ls='--')
ax.text(0.14, len(cats) - 0.55, '下限 2×锚点误差 = 0.10 m', color='#c44e52', fontsize=8,
        fontproperties=cjk)
ax.set_yticks(ys); ax.set_yticklabels(cats)
ax.invert_yaxis()
ax.set_xlabel('零跨度时的残余宽度中位 (m)', fontproperties=cjk)
ax.set_xlim(0, max(med) * 1.35)
ax.set_title('按类别：床最长、残余最大；椅/柜本身短，天然被封顶\n'
             '注意这不是「被墙定死」——iTHOR 家具普遍离墙 0.2–0.5 m', fontsize=10.5, loc='left', fontproperties=cjk)
ax.grid(axis='x', alpha=0.25)

fig.tight_layout()
fig.savefig(OUT, facecolor='white')
print('saved', OUT)
