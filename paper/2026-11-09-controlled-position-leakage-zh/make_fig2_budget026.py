import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Rectangle

ROOT = Path('D:/Project/imu环境重建')
P = ROOT / 'paper/2026-11-09-controlled-position-leakage-zh'
OUT = P / 'figures/cvpr'
rows = list(csv.DictReader(open(P / 'source-data/cvpr/f1_activity019.csv', encoding='utf-8-sig')))
cells = [r for r in rows if r['panel'] == 'heatmap' and r['f1'].strip() and r['coverage'].strip()]
fl = lambda r, k: float(r[k])
covs = sorted({fl(c, 'coverage') for c in cells}); vis = sorted({fl(c, 'visits') for c in cells})
F1 = {(fl(c, 'coverage'), fl(c, 'visits')): fl(c, 'f1') for c in cells}
TEAL, INK, MUTED = '#087F83', '#243B50', '#6B7C8A'
cmap = LinearSegmentedColormap.from_list('teals', ['#E8F1F2', '#9CC6C8', '#4E9A9C', TEAL, '#08403F'])

plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
                     'font.size': 7.2, 'text.color': INK, 'axes.labelcolor': INK, 'pdf.fonttype': 42,
                     'svg.fonttype': 'none'})
fig = plt.figure(figsize=(88 / 25.4, 116 / 25.4))
axh = fig.add_axes([.145, .690, .82, .205])
ax3 = fig.add_axes([.020, .030, .96, .505], projection='3d')
norm = Normalize(0, 100)

for i, v in enumerate(vis):
    for j, c in enumerate(covs):
        if (c, v) in F1:
            val = 100 * F1[(c, v)]
            axh.add_patch(Rectangle((j, i), 1, 1, facecolor=cmap(norm(val)), edgecolor='white', lw=1.0))
            axh.text(j + .5, i + .5, '%.1f' % val, ha='center', va='center', fontsize=7.4,
                     color='white' if val >= 58 else INK)
        else:
            axh.add_patch(Rectangle((j, i), 1, 1, facecolor='white', edgecolor='#D8DFE4', lw=.8, hatch='///'))
axh.set_xlim(0, len(covs)); axh.set_ylim(0, len(vis))
axh.set_xticks(np.arange(len(covs)) + .5); axh.set_xticklabels(['%d' % round(100 * c) for c in covs], fontsize=7.5)
axh.set_yticks(np.arange(len(vis)) + .5); axh.set_yticklabels(['%d' % v for v in vis], fontsize=7.5)
axh.set_xlabel('Walking coverage (%)', labelpad=2, fontsize=7.9)
axh.set_ylabel('Interactions per room', labelpad=3, fontsize=7.9)
for s in axh.spines.values(): s.set_visible(False)
axh.tick_params(length=0, pad=2)
fig.text(.055, .972, 'a   measured position F1 (%), 43 cells', fontsize=8.7, fontweight='bold')
fig.text(.055, .940, '10,000 rooms per cell  \u00b7  outline decoder', fontsize=7.4, color=MUTED)

xs = np.array([100 * c for (c, v) in F1]); ys = np.array([v for (c, v) in F1]); zs = np.array([100 * F1[(c, v)] for (c, v) in F1])
for x, y, z in zip(xs, ys, zs):
    ax3.plot([x, x], [y, y], [0, z], color='#D6E0E6', lw=.35, alpha=.75, ls=(0, (1.2, 2.0)), zorder=0)
for v in vis:
    sel = ys == v
    ax3.plot(xs[sel], ys[sel], zs[sel], color='#7FB3B5', lw=.6, alpha=.55, zorder=1)
ax3.scatter(xs, ys, zs, c=zs, cmap=cmap, norm=norm, s=11, edgecolors='white', linewidths=.3, depthshade=False, zorder=3)
ax3.set_xlim(0, 102); ax3.set_zlim(0, 100)
ax3.set_xticks([0, 25, 50, 75, 100]); ax3.set_zticks([0, 25, 50, 75, 100])
ax3.set_yticks([2, 5, 8, 11, 14]); ax3.set_yticklabels(['2', '5', '8', '11', '14'])
ax3.tick_params(labelsize=7.2, pad=0, colors=MUTED)
ax3.set_xlabel('coverage (%)', fontsize=7.6, labelpad=-4)
ax3.set_ylabel('interactions', fontsize=7.6, labelpad=2)
ax3.set_zlabel('F1 (%)', fontsize=7.6, labelpad=-6)
for lab in (ax3.xaxis.label, ax3.yaxis.label, ax3.zaxis.label):
    lab.set_rotation(0)
ax3.set_box_aspect((1.5, 1, .95)); ax3.view_init(elev=20, azim=-62)
for a in (ax3.xaxis, ax3.yaxis, ax3.zaxis):
    a.pane.set_facecolor('#F8FAFB'); a.pane.set_edgecolor('#DCE5EA')
    a.pane.set_alpha(1.0); a.line.set_color('#B7C4CC'); a.line.set_linewidth(.5)
    a._axinfo['grid'].update(color='#DFE8ED', linewidth=.5)
fig.text(.055, .578, 'b   the same 43 cells in depth', fontsize=8.7, fontweight='bold')
for ext, kw in (('png', {'dpi': 600}), ('pdf', {}), ('svg', {})):
    fig.savefig(OUT / ('fig_budget026.' + ext), facecolor='white', **kw)
print('ok', fig.get_size_inches() * 25.4)
