"""Figure 4: what declared side information can and cannot recover.

Panel a: two independent prior-only estimators on the same 32 confirmation
records, the truth-selected best draw of the sampling family, and the device
chain on the same records.  Panel b: the truth-selected ceiling as a function
of inventory size, which is where it collapses.
"""
import json

import numpy as np

import figstyle032 as S
S.use_style(7.2)
import matplotlib.pyplot as plt

ROOT = S.ROOT
batches = json.load(open(ROOT / 'output/layout-recon/structprior032/structprior032.json'))['batches']
dev = json.load(open(ROOT / 'output/research-sync/2026-11-10-prior-only-019/prior-only-batch2.json'))['summary']
b2 = batches['batch2']
rows = [
    ('Declared priors, our decoder', dev['prior_only_mean_room_f1'], '0/32', S.GREY),
    ('Declared priors, 2,000 draws', b2['prior_alone']['sample_f1_mean'], '0/32', '#B6C2CA'),
    ('Best draw, chosen with truth', b2['truth_aided_upper_bound']['mean_best_f1'], '4/32', S.AMBER),
    ('Raw inertial chain', dev['raw_mean_room_f1'], '21/32', S.BLUE),
]

W, H = 174.0, 62.0
fig = plt.figure()
ax = fig.add_axes([.205, .285, .235, .50])
axb = fig.add_axes([.635, .285, .30, .50])

ys = np.arange(len(rows))[::-1]
for y, (label, f1, hits, colr) in zip(ys, rows):
    ax.barh(y, f1, height=.56, color=colr, edgecolor='none')
    if f1 >= .70:
        ax.text(f1 - .018, y, '%.3f' % f1, va='center', ha='right', fontsize=6.8, color='white')
    else:
        ax.text(f1 + .015, y, '%.3f' % f1, va='center', ha='left', fontsize=6.8, color=S.INK)
    ax.text(1.16, y, hits, transform=ax.get_yaxis_transform(), va='center', ha='left',
            fontsize=6.8, color=S.INK, fontweight='bold' if hits == '21/32' else 'normal')
ax.set_yticks(ys)
ax.set_yticklabels([r[0] for r in rows], fontsize=6.8)
ax.set_xlim(0, .88)
ax.set_ylim(-.6, len(rows) - .35)
ax.set_xticks([0, .25, .5, .75])
ax.set_xlabel('Mean position F1', labelpad=1.5)
ax.tick_params(axis='y', length=0)
ax.grid(axis='x', color=S.GRID, lw=.45)
ax.set_axisbelow(True)
ax.text(1.16, len(rows) - .42, 'exact rooms', transform=ax.get_yaxis_transform(), ha='left',
        va='center', fontsize=6.2, color=S.MUTED)
S.panel_label(ax, 'a', x=-.62, y=1.03)

by = {4: (.950, '4/5'), 5: (.725, '0/13'), 6: (.716, '0/14'), 7: (.595, '0/12')}
items = sorted(by)
axb.plot(items, [by[i][0] for i in items], color=S.AMBER, lw=1.1, marker='o', ms=3.4,
         mec='white', mew=.5)
for i in items:
    axb.annotate(by[i][1], (i, by[i][0]), textcoords='offset points', xytext=(0, 7),
                 ha='center', fontsize=6.4, color=S.INK)
axb.set_xlim(3.4, 7.6)
axb.set_ylim(.4, 1.02)
axb.set_xticks(items)
axb.set_yticks([.5, .75, 1.0])
axb.set_xlabel('Declared items per room', labelpad=1.5)
axb.set_ylabel('Best-draw F1', labelpad=2.5)
axb.grid(axis='y', color=S.GRID, lw=.45)
axb.set_axisbelow(True)
S.panel_label(axb, 'b', x=-.22, y=1.03)
fig.text(.02, .055, 'Both panels use rooms 11200-11231 and the same declared inputs; labels in b give exact rooms over rooms at that inventory size.',
         fontsize=6.2, color=S.MUTED, ha='left')
fig.text(.02, .012, 'The truth-selected row and panel b are ceilings of one sampling family, not estimators.',
         fontsize=6.2, color=S.MUTED, ha='left')
S.save(fig, 'fig_prior033', W, H)
print('ok', rows)