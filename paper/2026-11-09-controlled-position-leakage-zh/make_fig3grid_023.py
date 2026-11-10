
"""Rebuild the twelve-room visit-by-severity grid from seeded realisations."""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Rectangle

ROOT = Path('D:/Project/imu环境重建')
OUT = ROOT / 'paper/2026-11-09-controlled-position-leakage-zh/figures/cvpr'
REP = json.loads((ROOT / 'output/layout-recon/matrix023/grid023.json').read_text())
TEAL, INK, MUTED = '#087F83', '#243B50', '#6B7C8A'
cmap = LinearSegmentedColormap.from_list('teals', ['#E8F1F2', '#9CC6C8', '#4E9A9C', TEAL, '#08403F'])
plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
                     'font.size': 7, 'text.color': INK, 'axes.labelcolor': INK,
                     'pdf.fonttype': 42, 'svg.fonttype': 'none'})

VIS = [6, 10, 14]
SEV = [0.0, 0.5, 1.0]
cell = {(v['visits'], v['severity']): v for v in REP['cells'].values()}
runs = REP['cells'][list(REP['cells'])[0]]['n'] / 12.0
rooms = np.array([[cell[(v, s)]['hits'] / runs for s in SEV] for v in VIS])   # rooms of 12, mean over runs
norm = Normalize(3.5, 7.5)

fig = plt.figure(figsize=(88 / 25.4, 62 / 25.4))
ax = fig.add_axes([.205, .345, .545, .495])
for i, v in enumerate(VIS):
    for j, s in enumerate(SEV):
        val = rooms[i, j]
        ax.add_patch(Rectangle((j, i), 1, 1, facecolor=cmap(norm(val)), edgecolor='white', lw=1.2))
        ax.text(j + .5, i + .5, '%.1f' % val, ha='center', va='center',
                fontsize=9.2, color='white' if val > 6.1 else INK)
ax.set_xlim(0, 3); ax.set_ylim(0, 3)
ax.set_xticks(np.arange(3) + .5); ax.set_xticklabels(['%g' % s for s in SEV], fontsize=6.6)
ax.set_yticks(np.arange(3) + .5); ax.set_yticklabels(['%d' % v for v in VIS], fontsize=6.6)
ax.set_xlabel('sensor severity s', fontsize=6.8, labelpad=2)
ax.set_ylabel('visits per room', fontsize=6.8, labelpad=3)
ax.tick_params(length=0, pad=2.5)
for sp in ax.spines.values():
    sp.set_visible(False)

sev = REP['severity_axis'][2]
vis0, vis5, vis1 = REP['visit_axis']
scale = 12.0 / (12 * runs)
fig.text(.03, .955, 'visits help only while the sensor is good', fontsize=7.8, fontweight='bold')
fig.text(.03, .895, '12 rooms  ·  coverage 1.0  ·  gated gyro tracker  ·  %d observations per cell' % (12 * runs),
         fontsize=6.0, color=MUTED)
fig.text(.03, .20, 'severity 0 to 1 at 14 visits: %.1f to %.1f rooms of 12 (Wilcoxon p=%.3f)' % (sev['sum_low'] * scale, sev['sum_high'] * scale, sev['p_wilcoxon']),
         fontsize=6.0, color=INK)
fig.text(.03, .13, 'visits 6 to 14: %+.1f rooms at severity 0 (p=%.2f), %+.1f at severity 1 (p=%.2f)' % (
    (vis0['sum_high'] - vis0['sum_low']) * scale, vis0['p_wilcoxon'],
    (vis1['sum_high'] - vis1['sum_low']) * scale, vis1['p_wilcoxon']), fontsize=6.0, color=MUTED)
fig.text(.03, .05, 'cells are means over three realisations; tests use per-room counts of 0 to 3', fontsize=5.6, color=MUTED)

for ext, kw in (('png', {'dpi': 600}), ('pdf', {}), ('svg', {}), ('tiff', {'dpi': 600, 'pil_kwargs': {'compression': 'tiff_lzw'}})):
    fig.savefig(OUT / ('fig3_budget_quality023.' + ext), facecolor='white', **kw)
print('ok')
