# 图：锚点噪声 → 布局翻转率；以及翻转是双峰的。
import io, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
H = os.path.dirname(os.path.abspath(__file__))
cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
rows = json.load(io.open(os.path.join(H, 'noise_flip.json'), encoding='utf-8'))
SIG = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30)
OB = [('bed', '床', '#4c72b0'), ('desk', '桌', '#dd8452'), ('cab', '柜', '#55a868'), ('chair', '椅', '#c44e52')]

fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.8), dpi=150)
ax = axes[0]
for k, nm, col in OB:
    ys = []
    for s in SIG:
        sel = [r for r in rows if r['sigma'] == s and r['obj'] == k and r['disp'] is not None]
        ys.append(100 * np.mean([r['disp'] > 0.5 for r in sel]) if sel else np.nan)
    ax.plot(SIG, ys, 'o-', color=col, lw=1.6, ms=6, label=nm)
allf = []
for s in SIG:
    sel = [r for r in rows if r['sigma'] == s]
    allf.append(100 * np.mean([r['fail'] or (r['disp'] is not None and r['disp'] > 0.5) for r in sel]))
ax.plot(SIG, allf, 'k--', lw=1.4, label='全部合并')
ax.set_xlabel('锚点位置噪声 sigma (m)', fontproperties=cjk)
ax.set_ylabel('翻转率（家具框位移 > 0.5 m） (%)', fontproperties=cjk)
ax.set_title('锚点只要偏 5 cm，桌就有 20% 的概率被放到另一处\n要把翻转率压到 10% 以下，锚点误差得 <= 5 cm', fontsize=10.5,
             loc='left', fontproperties=cjk)
ax.grid(alpha=0.25); ax.legend(prop=cjk, fontsize=9)

ax = axes[1]
d = np.array([r['disp'] for r in rows if r['sigma'] == 0.10 and r['disp'] is not None])
bins = np.concatenate([np.linspace(0, 0.5, 21), np.linspace(0.5, 3.2, 22)])
ax.hist(np.clip(d, 0, 3.2), bins=bins, color='#4c72b0', alpha=0.85)
ax.set_yscale('log')
ax.set_xlabel('家具框位移 (m)，sigma = 0.10 m', fontproperties=cjk)
ax.set_ylabel('样本数（对数轴）', fontproperties=cjk)
ax.axvline(0.5, color='#c44e52', lw=1.2, ls='--')
ax.text(0.55, ax.get_ylim()[1] * 0.35, '0.5 m', color='#c44e52', fontsize=9, fontproperties=cjk)
ax.set_title('位移是双峰的：多数贴 0，少数跳到 1–3 m\n0.4–0.6 m 之间几乎没有样本——所以「平均误差」会掩盖失效', fontsize=10.5,
             loc='left', fontproperties=cjk)
ax.grid(alpha=0.25, which='both')
fig.tight_layout()
out_p = os.path.normpath(os.path.join(H, '..', '..', 'output', 'layout-recon', 'noise-flip.png'))
fig.savefig(out_p, facecolor='white')
print('saved', out_p)
