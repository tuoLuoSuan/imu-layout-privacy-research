import json
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
data = json.loads((ROOT / 'output/layout-recon/matrix023/grid023.json').read_text())
cells = data['cells']
VIS = [6, 10, 14]; SEV = [0.0, 0.5, 1.0]
hits = {(c['visits'], c['severity']): (c['hits'], c['n']) for c in cells.values()}
TEAL, INK, MUTED = '#087F83', '#243B50', '#6B7C8A'
cmap = LinearSegmentedColormap.from_list('teals', ['#E4EEF0', '#9CC6C8', '#4E9A9C', TEAL, '#08403F'])

plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
                     'font.size': 7.0, 'text.color': INK, 'axes.labelcolor': INK, 'pdf.fonttype': 42,
                     'svg.fonttype': 'none'})
fig = plt.figure(figsize=(88 / 25.4, 88 / 25.4))
ax = fig.add_axes([.175, .400, .78, .470])
norm = Normalize(0, 100)
for i, v in enumerate(VIS):
    for j, s in enumerate(SEV):
        h, n = hits[(v, s)]
        val = 100 * h / n
        ax.add_patch(Rectangle((j, i), 1, 1, facecolor=cmap(norm(val)), edgecolor='white', lw=1.4))
        ax.text(j + .5, i + .585, '%.1f%%' % val, ha='center', va='center', fontsize=8.5, fontweight='bold',
                color='white' if val >= 54 else INK)
        ax.text(j + .5, i + .275, '%d/%d' % (h, n), ha='center', va='center', fontsize=7.2,
                color='white' if val >= 54 else MUTED)
ax.set_xlim(0, 3); ax.set_ylim(0, 3)
ax.set_xticks(np.arange(3) + .5); ax.set_xticklabels(['%g' % s for s in SEV], fontsize=7.6)
ax.set_yticks(np.arange(3) + .5); ax.set_yticklabels(['%d' % v for v in VIS], fontsize=7.6)
ax.set_xlabel('handset error severity s', fontsize=7.6, labelpad=3)
ax.set_ylabel('visits per room', fontsize=7.6, labelpad=4)
for sp in ax.spines.values(): sp.set_visible(False)
ax.tick_params(length=0, pad=3)
fig.text(.035, .965, 'visits help only while the sensor is good', fontsize=8.7, fontweight='bold')
fig.text(.035, .905, '12 rooms \u00b7 three handset-noise realisations \u00b7 36 observations per cell',
         fontsize=7.2, color=MUTED)
lines = [
    'severity 0 \u2192 1 at 14 visits: 63.9% \u2192 30.6%  (p = 0.016)',
    'visits 6 \u2192 14: +13.9 pp at s = 0, \u22128.3 pp at s = 1',
    'interaction \u221222.2 pp, sign-flip p = 0.125',
    'cells are means of three realisations; tests use per-room counts',
]
for k, text in enumerate(lines):
    fig.text(.035, .245 - k * .063, text, fontsize=7.2, color=INK if k < 3 else MUTED)
for ext, kw in (('png', {'dpi': 600}), ('pdf', {}), ('svg', {})):
    fig.savefig(OUT / ('fig_visits026.' + ext), facecolor='white', **kw)
print('ok', list(np.round(fig.get_size_inches() * 25.4, 1)))
