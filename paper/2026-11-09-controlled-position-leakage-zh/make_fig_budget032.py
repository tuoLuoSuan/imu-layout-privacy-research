"""Figure 2: the activity-budget surface and its marginal at full coverage.

Panel a carries all 43 measured cells.  Panel b answers the question the paper
opens with, how many interactions are worth collecting, by cutting panel a at
full coverage; a second copy of the whole surface would add no information.
"""
import csv

import numpy as np
from matplotlib.patches import Rectangle

import figstyle032 as S
S.use_style(7.2)
import matplotlib.pyplot as plt

rows = list(csv.DictReader(open(S.DATA / 'f1_activity019.csv', encoding='utf-8-sig')))
cells = [r for r in rows if r['panel'] == 'heatmap' and r['f1'].strip() and r['coverage'].strip()]
fl = lambda r, k: float(r[k])
covs = sorted({fl(c, 'coverage') for c in cells})
vis = sorted({fl(c, 'visits') for c in cells})
F1 = {(fl(c, 'coverage'), fl(c, 'visits')): 100 * fl(c, 'f1') for c in cells}

fig = plt.figure()
axh = fig.add_axes([.115, .500, .80, .350])
axm = fig.add_axes([.115, .085, .80, .265])

for i, v in enumerate(vis):
    for j, c in enumerate(covs):
        if (c, v) in F1:
            val = F1[(c, v)]
            axh.add_patch(Rectangle((j, i), 1, 1, facecolor=S.CMAP(val / 100),
                                    edgecolor='white', lw=.9))
            axh.text(j + .5, i + .5, '%.1f' % val, ha='center', va='center', fontsize=7.0,
                     color='white' if val >= 62 else S.INK)
        else:
            axh.add_patch(Rectangle((j, i), 1, 1, facecolor='white', edgecolor='#D5DDE2',
                                    lw=.7, hatch='///'))
axh.set_xlim(0, len(covs)); axh.set_ylim(0, len(vis))
axh.set_xticks(np.arange(len(covs)) + .5)
axh.set_xticklabels(['%d' % round(100 * c) for c in covs])
axh.set_yticks(np.arange(len(vis)) + .5)
axh.set_yticklabels(['%d' % v for v in vis])
axh.set_xlabel('Walking coverage (%)', labelpad=1.5)
axh.set_ylabel('Interactions per room', labelpad=2.5)
axh.tick_params(length=0)
for sp in axh.spines.values():
    sp.set_visible(False)
S.panel_label(axh, 'a', x=-.085, y=1.035)
axh.set_title('Room-macro position F1 (%), 43 measured cells', loc='left', pad=3)

y = np.array([F1[(1.0, v)] for v in vis])
axm.plot(vis, y, color=S.BLUE, lw=1.1, marker='o', ms=3.0, mec='white', mew=.5, zorder=3)
axm.set_xlim(-1, 16.5)
axm.set_ylim(55, 96)
axm.set_xticks([0, 2, 5, 8, 11, 14])
axm.set_yticks([60, 70, 80, 90])
axm.grid(axis='y', color=S.GRID, lw=.45)
axm.set_axisbelow(True)
axm.set_xlabel('Interactions per room at full coverage', labelpad=1.5)
axm.set_ylabel('Position F1 (%)', labelpad=2.5)
S.panel_label(axm, 'b', x=-.085, y=1.11)
axm.set_title('What the interaction axis buys at full coverage', loc='left', pad=3)
for v, yy in zip(vis, y):
    axm.annotate('%.1f' % yy, (v, yy), textcoords='offset points', xytext=(0, 6),
                 ha='center', fontsize=6.8, color=S.INK)
axm.text(12.6, 81.0, '+3.3 pt\nfor 3 more', fontsize=6.5, color=S.MUTED, ha='left', va='top')
S.save(fig, 'fig_budget032', 88, 108)
print('ok', [round(v, 1) for v in y])