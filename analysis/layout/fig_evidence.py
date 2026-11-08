"""Conditional interval accounting; frames are fixed, not re-estimated."""
import sys
from figure_style import *
D = read("evidence_accum")
fig, axes = plt.subplots(1, 2, figsize=(6.3, 3.1), layout="constrained")
objects = ["cab", "chair", "bed"]
own = {"cab": "cabinet", "chair": "seated", "bed": "lying"}
subsets = D["thor"]["subsets"]
x = np.arange(3)
for offset, mode, label, color in [(-.24, "none", "无动作", "#aaaaaa"),
                                  (0, "own", "本类动作", "#cc873f"),
                                  (.24, "all", "三类动作", "#248a85")]:
    values=[]
    for obj in objects:
        keys=[] if mode=="none" else ([own[obj]] if mode=="own" else ["seated","cabinet","lying"])
        values.append(next(r for r in subsets if r["subset"]==keys)["per_object"][obj]["width_median"])
    axes[0].bar(x+offset, values, .23, color=color, label=label)
axes[0].set(xticks=x, xticklabels=[NAMES[o] for o in objects], ylabel="残余宽度中位 (m)")
axes[0].legend(prop=CJK, fontsize=7)
title(axes[0], "a 条件模型中的对象局部性")
base=D["real"]["u_prior"]["per_object"]
drop={(r["removed"][0],r["removed"][1]):r for r in D["real"]["leave_one_out"]}
for offset, key, color, label in [(-.16, "base", "#248a85", "保留事件"),(.16,"drop","#cc873f","删本类事件")]:
    values=[base[o]["width_median"] if key=="base" else drop[(own[o],0)]["u"]["per_object"][o]["width_median"] for o in objects]
    axes[1].bar(x+offset, values, .30, color=color, label=label)
axes[1].set(xticks=x, xticklabels=[NAMES[o] for o in objects], ylabel="U 档残余宽度 (m)")
axes[1].legend(prop=CJK, fontsize=7)
title(axes[1], "b 真实单房的固定模式诊断")
save(fig, sys.argv[1] if len(sys.argv)>1 else HERE/"../../output/layout-recon/evidence.png",
     "条件区间：模拟 %d 房、%d 轴；真实 n=1；柱为描述性中位" % (D["thor"]["n_scenes"],D["thor"]["n_axes"]))
