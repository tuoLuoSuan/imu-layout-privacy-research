# 图：证据累积是「对象局部」的 —— 加别类的动作对本物件毫无帮助；
# 真实房间里哪条事件是临界的（删掉它区间就变宽）。
import io, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

HERE = os.path.dirname(os.path.abspath(__file__))
cjk = fm.FontProperties(fname=r'C:/Windows/Fonts/msyh.ttc')
D = json.load(io.open(os.path.join(HERE, 'evidence_accum.json'), encoding='utf-8'))
NAME = {'cab': '柜', 'chair': '椅', 'bed': '床'}
OWN = {'cab': 'cabinet', 'chair': 'seated', 'bed': 'lying'}
OBJS = ('cab', 'chair', 'bed')

fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.2), dpi=150)

# 左：iTHOR 逐物件，无证据 / 只有本类 / 三类全给
ax = axes[0]
subs = D['thor']['subsets']
def med(sub, obj):
    return [s for s in subs if s['subset'] == sub][0]['per_object'][obj]['width_median']
xs = np.arange(len(OBJS)); w = 0.26
vals = {'none': [med([], o) for o in OBJS],
        'own': [med([OWN[o]], o) for o in OBJS],
        'all': [med(['seated', 'cabinet', 'lying'], o) for o in OBJS]}
for i, (k, lab, col) in enumerate([('none', '没有任何动作', '#b0b0b0'),
                                   ('own', '只有本类动作', '#4c72b0'),
                                   ('all', '三类动作全给', '#55a868')]):
    ax.bar(xs + (i - 1) * w, vals[k], w, label=lab, color=col)
    for j, v in enumerate(vals[k]):
        ax.text(j + (i - 1) * w, v + 0.05, '%.2f' % v, ha='center', fontsize=8, fontproperties=cjk)
ax.set_xticks(xs); ax.set_xticklabels([NAME[o] for o in OBJS], fontproperties=cjk)
ax.set_ylabel('残余宽度中位 (m)', fontproperties=cjk)
ax.set_title('AI2-THOR 15 场景 90 个轴参数：证据是对象局部的\n'
             '加上别类的动作，本物件宽度一点没变（蓝与绿逐项相同）', fontsize=11, loc='left', fontproperties=cjk)
ax.legend(fontsize=8.5, prop=cjk); ax.grid(axis='y', alpha=0.25)

# 右：真实房间，U 档 vs 贴墙先验档，全保留 vs 删掉本类事件
ax = axes[1]
base_u = D['real']['u_prior']['per_object']
base_b = [s for s in D['real']['subsets'] if s['classes_active'] == ['cabinet', 'lying', 'seated']][0]['per_object']
loo = {(r['removed'][0], r['removed'][1]): r for r in D['real']['leave_one_out']}
own_loo = {}
for o in OBJS:
    cls = OWN[o]
    own_loo[o] = loo[(cls, 0)]
xs = np.arange(len(OBJS) * 2)
labels = []
for i, o in enumerate(OBJS):
    labels += [NAME[o] + '\nU档', NAME[o] + '\n贴墙先验']
base = [base_u[o]['width_median'] for o in OBJS] + [base_b[o]['width_median'] for o in OBJS]
drop = [own_loo[o]['u']['per_object'][o]['width_median'] for o in OBJS] + \
       [own_loo[o]['box']['per_object'][o]['width_median'] for o in OBJS]
order = [0, 2, 4, 1, 3, 5]
ax.bar(np.arange(6) - 0.18, [base[i] for i in order], 0.36, label='全部事件保留', color='#55a868')
ax.bar(np.arange(6) + 0.18, [drop[i] for i in order], 0.36, label='删掉本类事件', color='#c44e52')
for i, k in enumerate(order):
    ax.text(i - 0.18, base[k] + 0.05, '%.2f' % base[k], ha='center', fontsize=8, fontproperties=cjk)
    ax.text(i + 0.18, drop[k] + 0.05, '%.2f' % drop[k], ha='center', fontsize=8, fontproperties=cjk)
ax.set_xticks(np.arange(6)); ax.set_xticklabels(labels, fontproperties=cjk, fontsize=8.5)
ax.set_ylabel('残余宽度 (m)', fontproperties=cjk)
ax.set_title('s-59d570ee：删掉本类事件，只有本物件变宽\n'
             '贴墙先验档里柜/床已被墙钉到 0.10 m，事件对它们是冗余的', fontsize=11, loc='left', fontproperties=cjk)
ax.legend(fontsize=8.5, prop=cjk); ax.grid(axis='y', alpha=0.25)

fig.suptitle('证据累积与临界事件：每条交互只喂自己那件家具', fontsize=12.5, fontproperties=cjk)
fig.tight_layout(rect=[0, 0, 1, 0.94])
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'output', 'layout-recon', 'evidence-accum.png')
fig.savefig(out, facecolor='white')
print('saved', os.path.abspath(out))
