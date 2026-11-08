"""Oracle-width diagnostic; no calibrated runtime upper-bound claim."""
import sys
from figure_style import *
rows=[r for r in read("pred_vs_actual") if r["backend"]=="place"]
fig,axes=plt.subplots(1,2,figsize=(6.3,3.1),layout="constrained")
limit=max(max(r["pred"],r["meas"]) for r in rows)*1.08
axes[0].plot([0,limit],[0,limit],":",color="#888",linewidth=.8)
for obj in NAMES:
    r=[r for r in rows if r["obj"]==obj]
    axes[0].scatter([v["pred"] for v in r],[v["meas"] for v in r],s=12,color=COLORS[obj],label=NAMES[obj])
axes[0].set(xlabel="oracle 几何宽度 (m)",ylabel="最大轴中心误差 (m)",xlim=(0,limit),ylim=(0,limit))
axes[0].legend(prop=CJK,fontsize=7)
title(axes[0],"a 宽度与误差并非同一端点")
for j,(wall,name) in enumerate([(True,"墙判对"),(False,"墙判错")]):
    r=[r for r in rows if r["wall_ok"]==wall]
    for off,failed,color in [(-.16,False,"#248a85"),(.16,True,"#cc873f")]:
        n=sum((v["meas"]>v["pred"]+1e-9)==failed for v in r)
        axes[1].bar(j+off,n,.30,color=color,label=("误差 ≤ 宽度" if not failed else "误差 > 宽度") if j==0 else None)
axes[1].set(xticks=[0,1],xticklabels=["墙判对","墙判错"],ylabel="已输出物体数")
axes[1].legend(prop=CJK,fontsize=7)
title(axes[1],"b 描述性分层，不作风险校准")
save(fig,sys.argv[1] if len(sys.argv)>1 else HERE/"../../output/layout-recon/bound.png",
     "place 后端；%d 房、%d 已输出物体；oracle 输入，未输出物体不在此图" % (len({r["scene"] for r in rows}),len(rows)))
