"""Single-room local perturbation sensitivity, not causal attribution."""
import sys
from figure_style import *
D=read("attribution")
fig,axes=plt.subplots(1,2,figsize=(6.3,3.1),layout="constrained")
classes=[("seated","坐"),("cabinet","柜"),("lying","躺")]
objects=["bed","desk","cab","chair"]
for j,obj in enumerate(objects):
    axes[0].plot(range(3),[D["summary"][c][obj] for c,_ in classes],"o-",markersize=3,color=COLORS[obj],label=NAMES[obj])
axes[0].set(xticks=range(3),xticklabels=[n for _,n in classes],ylabel="框边最大位移中位 (m)")
axes[0].legend(prop=CJK,fontsize=7)
title(axes[0],"a 各动作锚点的局部敏感性")
for axis,marker,color in [("x","o","#248a85"),("y","s","#cc873f")]:
    r=[r for r in D["rows"] if r["class"]=="cabinet" and r["axis"]==axis and r["desk"] is not None]
    axes[1].plot([v["delta"] for v in r],[v["desk"] for v in r],marker+"-",markersize=3,color=color,label="沿 "+axis+" 扰动")
axes[1].set(xlabel="柜锚点有符号扰动 (m)",ylabel="桌框最大边位移 (m)")
axes[1].legend(prop=CJK,fontsize=7)
title(axes[1],"b 桌对柜锚点的离散响应")
save(fig,sys.argv[1] if len(sys.argv)>1 else HERE/"../../output/layout-recon/attribution.png",
     "真实单房 n=1；每类 2 轴 × 4 扰动；描述性诊断，不是证据贡献量")
