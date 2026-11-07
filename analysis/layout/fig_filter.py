# 图：一致性过滤值不值——检出率、误拒率，以及它把锚点误差压低多少。
import io, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
H = os.path.dirname(os.path.abspath(__file__))
cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
rec = json.load(io.open(os.path.join(H, 'exp_consistency.json'), encoding='utf-8'))
gen = [r for r in rec if r['kind'] == 'genuine']; out = [r for r in rec if r['kind'] == 'outlier']
OBJ = [('cab', '柜'), ('chair', '椅'), ('bed', '床')]

det = [100 * np.mean([r['detect'] for r in out if r['obj'] == o]) for o, _ in OBJ]
fr_out = [100 * np.mean([r['false_reject'] for r in out if r['obj'] == o]) for o, _ in OBJ]
fr_gen = [100 * np.mean([r['false_reject'] for r in gen if r['obj'] == o]) for o, _ in OBJ]
e_all = [np.median([r['err_all'] for r in out if r['obj'] == o]) for o, _ in OBJ]
e_flt = [np.median([r['err_filtered'] for r in out if r['obj'] == o]) for o, _ in OBJ]

fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.9), dpi=150)
ax = axes[0]
xs = np.arange(len(OBJ)); w = 0.36
ax.bar(xs - w / 2, det, w, color='#55a868', label='离群事件被拒（检出率）')
ax.bar(xs + w / 2, [100 - v for v in fr_out], w, color='#9ec9e8', label='真事件被留下（1 − 误拒率）')
for i in range(len(OBJ)):
    ax.text(xs[i] - w / 2, det[i] + 2, '%.0f%%' % det[i], ha='center', fontsize=9)
    ax.text(xs[i] + w / 2, 100 - fr_out[i] + 2, '%.1f%%' % (100 - fr_out[i]), ha='center', fontsize=9)
ax.set_xticks(xs); ax.set_xticklabels([n for _, n in OBJ], fontproperties=cjk)
ax.set_ylim(0, 118); ax.set_ylabel('百分比 (%)', fontproperties=cjk)
ax.set_title('阈值随物体对角缩放，所以床最弱\n柜/椅 85% 检出；床只有 30%——2.5 m 的对角让「任何位置都算一致」', fontsize=10.5, loc='left', fontproperties=cjk)
ax.legend(prop=cjk, fontsize=9, loc='lower left'); ax.grid(axis='y', alpha=0.25)

ax = axes[1]
ax.bar(xs - w / 2, e_all, w, color='#c44e52', label='把同类事件全平均')
ax.bar(xs + w / 2, e_flt, w, color='#4c72b0', label='一致性过滤后再平均')
for i in range(len(OBJ)):
    ax.text(xs[i] - w / 2, e_all[i] + 0.02, '%.2f' % e_all[i], ha='center', fontsize=9)
    ax.text(xs[i] + w / 2, e_flt[i] + 0.02, '%.2f' % e_flt[i], ha='center', fontsize=9)
ax.set_xticks(xs); ax.set_xticklabels([n for _, n in OBJ], fontproperties=cjk)
ax.set_ylabel('锚点误差中位 (m)', fontproperties=cjk)
ax.set_title('一个离群事件就够把锚点拉走\n平均 0.62–0.63 m，过滤后 0.15–0.18 m（床 0.43 m，因检出率低）', fontsize=10.5, loc='left', fontproperties=cjk)
ax.set_ylim(0, 0.86)
ax.legend(prop=cjk, fontsize=8.5, loc='upper center', ncol=2, framealpha=0.95)
ax.grid(axis='y', alpha=0.25)

fig.tight_layout()
out_p = os.path.normpath(os.path.join(H, '..', '..', 'output', 'layout-recon', 'consistency-filter.png'))
fig.savefig(out_p, facecolor='white')
print('saved', out_p)
