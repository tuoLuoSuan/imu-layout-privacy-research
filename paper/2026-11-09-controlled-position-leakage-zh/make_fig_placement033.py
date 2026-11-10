"""Figure 5: the placement effect, measured end-to-end.

The geometric layer varies contact placement with ideal trajectories.  This
figure asks whether the same intervention is still visible once the contacts are
acquired from noisy phone and wrist streams, refined and decoded under the
declared priors: same room, same route, same fourteen contacts, same sensor
model, same seeds, same chain.  Only the placement protocol differs.
"""
import json
import math

import numpy as np

import figstyle032 as S
S.use_style(7.2)
import matplotlib.pyplot as plt

ROOT = S.ROOT
paired = json.load(open(ROOT / 'output/layout-recon/placement033/paired.json'))
geo = dict(rep=39.78, disp=64.70, lo=24.00, hi=25.84)
fresh = paired['fresh64']
pooled = paired['pooled76']

W, H = 174.0, 56.0
fig = plt.figure()
axd = fig.add_axes([.075, .55, .26, .28])
axf = fig.add_axes([.545, .30, .40, .46])

cells = [('', fresh['dispersed'] - fresh['b'], S.GREY),
         ('dispersed only', fresh['b'], S.BLUE),
         ('repeat only', fresh['c'], S.AMBER),
         ('neither', fresh['n'] - fresh['dispersed'] - fresh['c'], '#D6DEE3')]
left = 0.
for label, n, colr in cells:
    axd.barh(0, n, left=left, height=.42, color=colr, edgecolor='white', lw=.8)
    axd.text(left + n / 2, 0, str(n), ha='center', va='center', fontsize=7.0,
             color='white' if colr in (S.BLUE, S.AMBER) else S.INK)
    left += n
axd.set_xlim(0, fresh['n'])
axd.set_ylim(-.55, .55)
axd.set_yticks([])
axd.set_xlabel('Rooms (n = 64)', labelpad=1.5)
axd.tick_params(length=0)
for sp in axd.spines.values():
    sp.set_visible(False)
S.panel_label(axd, 'a', x=-.16, y=1.06)
axd.set_title('Paired outcomes, fresh 64 rooms', loc='left', pad=3)
fig.text(.075, .355, '%d vs %d discordant; exact McNemar p = %.1e' % (fresh['b'], fresh['c'], fresh['p']),
         fontsize=6.2, color=S.MUTED, ha='left')

pts = [('Geometric, 10k rooms', geo['disp'] - geo['rep'], geo['lo'], geo['hi'], S.GREY),
       ('Device, fresh 64', fresh['dispersed'] / fresh['n'] * 100 - fresh['repeat'] / fresh['n'] * 100,
        fresh['boot'][0], fresh['boot'][1], S.BLUE),
       ('Device, development 12', paired['dev12']['dispersed'] / paired['dev12']['n'] * 100
        - paired['dev12']['repeat'] / paired['dev12']['n'] * 100,
        paired['dev12']['boot'][0], paired['dev12']['boot'][1], '#B6C2CA'),
       ('Device, pooled 76', pooled['dispersed'] / pooled['n'] * 100 - pooled['repeat'] / pooled['n'] * 100,
        pooled['boot'][0], pooled['boot'][1], '#4C86AE')]
ys = np.arange(len(pts))[::-1]
axf.axvline(0, color=S.INK, lw=.6)
for y, (label, eff, lo, hi, colr) in zip(ys, pts):
    axf.plot([lo, hi], [y, y], color=colr, lw=1.4, solid_capstyle='round')
    axf.plot(eff, y, 'o', ms=4.8, color=colr, mec='white', mew=.5, zorder=3)
    axf.text(hi + 1.2, y, '%+.1f  [%+.1f, %+.1f]' % (eff, lo, hi), va='center', fontsize=6.6, color=S.INK)
axf.set_yticks(ys)
axf.set_yticklabels([p[0] for p in pts], fontsize=6.9)
axf.set_xlim(-40, 55)
axf.set_ylim(-.6, len(pts) - .35)
axf.set_xticks([-40, -20, 0, 20, 40])
axf.set_xlabel('Change in whole-room recovery (percentage points)', labelpad=1.5)
axf.tick_params(axis='y', length=0)
axf.grid(axis='x', color=S.GRID, lw=.45)
axf.set_axisbelow(True)
S.panel_label(axf, 'b', x=-.46, y=1.06)
axf.set_title('Dispersed minus repeated placement', loc='left', pad=3)
fig.text(.02, .165, 'a, rooms 11700-11763; both arms share route, contacts, seeds, refiners and decoder.',
         fontsize=6.2, color=S.MUTED, ha='left')
fig.text(.02, .085, 'b, room-bootstrap 95% intervals; the geometric row has its own denominator.',
         fontsize=6.2, color=S.MUTED, ha='left')
S.save(fig, 'fig_placement033', W, H)
print('ok', fresh, pooled)