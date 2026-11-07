# 图：证据归因（哪个锚点喂哪件家具）+ 误差传导（推 0.1/0.2 m 时家具动多少，含离散跳变）。
import io, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
H = os.path.dirname(os.path.abspath(__file__))
cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
d = json.load(io.open(os.path.join(H, 'attribution.json'), encoding='utf-8'))
rows = d['rows']
CL = [('seated', '坐'), ('cabinet', '开柜'), ('lying', '躺')]
OB = [('bed', '床'), ('desk', '桌'), ('cab', '柜'), ('chair', '椅')]

M = np.zeros((len(OB), len(CL)))
for i, (o, _) in enumerate(OB):
    for j, (c, _) in enumerate(CL):
        sel = [r for r in rows if r['class'] == c and r[o] is not None]
        M[i, j] = np.median([r[o] for r in sel])

fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.7), dpi=150, gridspec_kw={'width_ratios': [1, 1.15]})
ax = axes[0]
im = ax.imshow(M, cmap='YlOrRd', vmin=0, vmax=max(0.12, M.max()))
ax.set_xticks(range(len(CL))); ax.set_xticklabels([n for _, n in CL], fontproperties=cjk)
ax.set_yticks(range(len(OB))); ax.set_yticklabels([n for _, n in OB], fontproperties=cjk)
for i in range(len(OB)):
    for j in range(len(CL)):
        ax.text(j, i, '%.3f' % M[i, j], ha='center', va='center', fontsize=10,
                color='white' if M[i, j] > 0.6 * max(0.12, M.max()) else '#333')
ax.set_xlabel('被推动的锚点', fontproperties=cjk)
ax.set_ylabel('跟着移动的家具', fontproperties=cjk)
ax.set_title('归因：推 0.10–0.20 m 时家具框位移的中位数\n躺只喂床；坐主要喂椅；开柜喂柜与桌', fontsize=10.5,
             loc='left', fontproperties=cjk)
fig.colorbar(im, ax=ax, shrink=0.8).set_label('位移 (m)', fontproperties=cjk)

ax = axes[1]
pairs = [('lying', 'bed', '#55a868'), ('seated', 'chair', '#4c72b0'),
         ('cabinet', 'desk', '#dd8452'), ('cabinet', 'bed', '#8172b3')]
for c, o, col in pairs:
    sel = [r for r in rows if r['class'] == c and r[o] is not None]
    xs = np.array([r['delta'] for r in sel]); ys = np.array([r[o] for r in sel])
    order = np.argsort(xs)
    ax.plot(xs[order], ys[order], 'o-', color=col, lw=1.3, ms=5,
            label='%s → %s' % (dict(CL)[c], dict(OB)[o]))
ax.set_ylim(-0.06, 0.98)
ax.axhline(0, color='#999', lw=0.8); ax.axvline(0, color='#999', lw=0.8)
ax.plot([-0.25, 0.25], [0.25, 0.25], ls='--', color='#bbb', lw=1.0)
ax.text(0.16, 0.265, 'y = |Δ锚点|', fontsize=8, color='#999', fontproperties=cjk)
ax.set_xlabel('锚点被推的位移 (m)', fontproperties=cjk)
ax.set_ylabel('家具框移动 (m)', fontproperties=cjk)
ax.set_title('传导多数接近 1:1（坐→椅、开柜→桌），但会跨过离散边界跳变\n躺→床 在被推 0.2 m 时跳到 0.854 m；开柜→床 跳到 0.600 m', fontsize=10.5,
             loc='left', fontproperties=cjk)
ax.legend(prop=cjk, fontsize=8.5, loc='center right', framealpha=0.95); ax.grid(alpha=0.25)
fig.tight_layout()
out_p = os.path.normpath(os.path.join(H, '..', '..', 'output', 'layout-recon', 'attribution.png'))
fig.savefig(out_p, facecolor='white')
print('saved', out_p)
