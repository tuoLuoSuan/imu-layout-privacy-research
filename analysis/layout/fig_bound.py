# 图：预测残余宽度 vs 实测误差（place 后端，与主表同一条）。
import io, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
H = os.path.dirname(os.path.abspath(__file__))
cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
rows = [r for r in json.load(io.open(os.path.join(H, 'pred_vs_actual.json'), encoding='utf-8'))
        if r['backend'] == 'place']
P = np.array([r['pred'] for r in rows]); M = np.array([r['meas'] for r in rows])
WO = np.array([r['wall_ok'] for r in rows])
bad = M > P + 1e-9
COL = {'bed': '#4c72b0', 'desk': '#dd8452', 'cab': '#55a868', 'chair': '#c44e52'}
NAME = {'bed': '床', 'desk': '桌', 'cab': '柜', 'chair': '椅'}

fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.1), dpi=150, gridspec_kw={'width_ratios': [1.25, 1]})
ax = axes[0]
lo, hi = 0.02, 6.0
ax.plot([lo, hi], [lo, hi], color='#888', lw=1.2, ls='--')
ax.text(2.3, 3.4, '上界 y = x', fontsize=9, color='#666', rotation=30, fontproperties=cjk)
for k, c in COL.items():
    sel = [i for i, r in enumerate(rows) if r['obj'] == k and not bad[i]]
    vio = [i for i, r in enumerate(rows) if r['obj'] == k and bad[i]]
    ax.scatter(P[sel], np.maximum(M[sel], 0.02), s=48, color=c, label=NAME[k], alpha=0.85,
               edgecolor='white', linewidth=0.6)
    ax.scatter(P[vio], M[vio], s=95, facecolor='none', edgecolor=c, linewidth=1.6, marker='D')
ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlim(lo, hi); ax.set_ylim(0.02, hi)
ax.set_xlabel('预测残余宽度 (m，对数轴)', fontproperties=cjk)
ax.set_ylabel('实测中心误差 (m，对数轴)', fontproperties=cjk)
ax.set_title('上界成立 %d/%d = %.0f%%；但它是松的\n预测中位 %.2f m，实测中位 %.2f m；%.0f%% 的样本实测不到预测的一半' % (
    int((~bad).sum()), len(M), 100 * np.mean(~bad), np.median(P), np.median(M),
    100 * np.mean(M <= 0.5 * P)), fontsize=10.5, loc='left', fontproperties=cjk)
ax.grid(alpha=0.25, which='both')
h, l = ax.get_legend_handles_labels()
ax.legend(h, l, prop=cjk, fontsize=8.5, loc='lower right', title='实心：守住上界  空心菱形：越界',
          title_fontproperties=cjk)

ax = axes[1]
groups = [('墙判对', WO), ('墙判错', ~WO)]
xs = np.arange(len(groups))
wid = 0.34
w_cnt = [int((~bad[g]).sum()) for _, g in groups]
v_cnt = [int(bad[g].sum()) for _, g in groups]
ax.bar(xs - wid / 2, w_cnt, wid, color='#9ec9e8', label='实测 <= 预测')
ax.bar(xs + wid / 2, v_cnt, wid, color='#c44e52', label='越界')
for i, (nm, g) in enumerate(groups):
    ax.text(xs[i] - wid / 2, w_cnt[i] + 0.8, '%d' % w_cnt[i], ha='center', fontsize=9.5)
    ax.text(xs[i] + wid / 2, v_cnt[i] + 0.8, '%d' % v_cnt[i], ha='center', fontsize=9.5)
    mw = np.median(M[g & ~bad]) if (g & ~bad).any() else 0.0
    mv = np.median(M[g & bad]) if (g & bad).any() else 0.0
    ax.text(xs[i], -4.2, '守住中位 %.2f m\n越界中位 %.2f m' % (mw, mv), ha='center', fontsize=8.5,
            fontproperties=cjk, color='#444')
ax.set_xticks(xs); ax.set_xticklabels([g[0] for g in groups], fontproperties=cjk)
ax.set_xlim(-0.6, 1.6); ax.set_ylim(-8, 52)
ax.set_ylabel('样本数', fontproperties=cjk)
ax.set_title('越界集中在哪里：墙判错只有 %d 次，却贡献了 %d 次越界\n越界的 9 条误差中位 1.88 m，守住的 50 条中位 0.00 m' % (
    int((~WO).sum()), int(bad[~WO].sum())), fontsize=10.5, loc='left', fontproperties=cjk)
ax.axhline(0, color='#999', lw=0.8)
ax.legend(prop=cjk, fontsize=9, loc='upper right')
ax.grid(axis='y', alpha=0.25)

fig.tight_layout()
out_p = os.path.normpath(os.path.join(H, '..', '..', 'output', 'layout-recon', 'bound-check.png'))
fig.savefig(out_p, facecolor='white')
print('saved', out_p, 'n=%d within=%d' % (len(rows), int((~bad).sum())))
