"""Figure 3: evidence quality, and what contact selection does inside one record.

Panel a: whole-room recovery across the nine visit-by-severity cells, three
handset-noise realisations each.  Panel b: one 14-interaction record cut down to
six contacts by four selectors that see no evaluation truth, plus a
truth-assisted upper arm.  Both panels count rooms, not repetitions.
"""
import json

import numpy as np
from matplotlib.patches import Rectangle

import figstyle032 as S
S.use_style(7.2)
import matplotlib.pyplot as plt

W, H = 174.0, 74.0
MM = 1 / 25.4

def box(x_mm, y_mm, w_mm, h_mm):
    return [x_mm / W, 1 - (y_mm + h_mm) / H, w_mm / W, h_mm / H]

ROOT = S.ROOT
grid = json.load(open(ROOT / 'output/layout-recon/matrix023/grid023.json'))['cells']
sel = json.load(open(ROOT / 'output/layout-recon/select026b/select026.json'))['summary']

vis, sev = [6, 10, 14], [0.0, 0.5, 1.0]
fig = plt.figure()
axg = fig.add_axes(box(16, 16, 42, 42))
axs = fig.add_axes(box(88, 20, 56, 34))

for i, v in enumerate(vis):
    for j, s in enumerate(sev):
        c = grid['v%d-s%.1f' % (v, s)]
        dark = c['rate'] > .48
        axg.add_patch(Rectangle((j, i), 1, 1, facecolor=S.CMAP(c['rate'] / .75),
                                edgecolor='white', lw=1.0))
        axg.text(j + .5, i + .60, '%.0f%%' % (100 * c['rate']), ha='center', va='center',
                 fontsize=8.4, fontweight='bold', color='white' if dark else S.INK)
        axg.text(j + .5, i + .28, '%d/36' % c['hits'], ha='center', va='center', fontsize=6.6,
                 color='#E4F0F1' if dark else S.MUTED)
axg.set_xlim(0, 3); axg.set_ylim(0, 3)
axg.set_xticks(np.arange(3) + .5); axg.set_xticklabels(['0', '0.5', '1'])
axg.set_yticks(np.arange(3) + .5); axg.set_yticklabels(['%d' % v for v in vis])
axg.set_xlabel('Severity s', labelpad=1.5)
axg.set_ylabel('Visits', labelpad=2.5)
axg.tick_params(length=0)
for sp in axg.spines.values():
    sp.set_visible(False)
S.panel_label(axg, 'a', x=-.24, y=1.02)
axg.set_title('Whole-room recovery', loc='left', pad=3)

arms = [('oracle', 'truth-assisted, 6', S.AMBER),
        ('disperse', 'most spread, 6', '#7FA3BE'),
        ('random', 'random, 6', '#A9C0D0'),
        ('prefix', 'first, 6', S.GREY),
        ('base', 'all 14', S.INK)]
ys = np.arange(len(arms))[::-1]
for y, (k, label, colr) in zip(ys, arms):
    v = sel[k]
    axs.plot([.60, .86], [y, y], color='#E7ECEF', lw=.6, zorder=1)
    axs.plot(v['mean_f1'], y, 'o', ms=5.6, color=colr, mec='white', mew=.5, zorder=3)
    axs.text(v['mean_f1'], y - .34, '%.3f' % v['mean_f1'], ha='center', va='top',
             fontsize=6.4, color=S.INK)
    n = v['n_scored']
    axs.text(.868, y, ('%d/%d' % (v['whole_room_hits'], n)) if n == 12 else ('%d/36' % v['whole_room_hits']),
             ha='left', va='center', fontsize=6.8, color=S.INK)
axs.set_xlim(.62, .86)
axs.set_ylim(-.7, len(arms) - .3)
axs.set_yticks(ys)
axs.set_yticklabels([a[1] for a in arms], fontsize=6.8)
axs.set_xticks([.65, .70, .75, .80, .85])
axs.set_xlabel('Mean position F1', labelpad=1.5)
axs.tick_params(axis='y', length=0)
axs.grid(axis='x', color=S.GRID, lw=.45)
axs.set_axisbelow(True)
S.panel_label(axs, 'b', x=-.44, y=1.02)
axs.set_title('Contact selection in one record', loc='left', pad=3)
axs.text(.868, len(arms) - .55, 'rooms', ha='left', va='center', fontsize=6.2, color=S.MUTED)
fig.text(.02, .085, 'a, three handset-noise realisations per cell: 36 observations of the same 12 rooms.',
         fontsize=6.3, color=S.MUTED, ha='left')
fig.text(.02, .035, 'b, rooms 11500-11511 at 14 visits and severity 0; recording, front end and decoder fixed.',
         fontsize=6.3, color=S.MUTED, ha='left')
S.save(fig, 'fig_evidence032', W, H)
print('ok')