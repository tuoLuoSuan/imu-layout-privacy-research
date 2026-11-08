"""Conditional intervals and aggregation on one corrected-clock recording."""
import sys
from figure_style import *
import identifiability as ID
import paths
session=sys.argv[1] if len(sys.argv)>1 else paths.SESSION
out=sys.argv[2] if len(sys.argv)>2 else HERE/"../../output/layout-recon/ident.png"
ref={"bed":(1.17,1.96,2.695,4.045),"desk":(.05,1.05,.65,2.10),
     "cab":(.05,0,.65,1.05),"chair":(1.11,.92,1.55,1.36)}
result=ID.analyze(session,truth=ref); objects=["cab","chair","bed"]
fig,axes=plt.subplots(1,2,figsize=(6.3,3.1),layout="constrained")
for off,kind,label,color in [(-.16,"width","条件宽度","#248a85"),(.16,"error","中心误差","#cc873f")]:
    values=[]
    for obj in objects:
        r=next(r for r in result["rows"] if r["object"]==obj)
        values.append(max(r["axes"][a]["width_m"] for a in ("x","y")) if kind=="width" else r.get("error_m",np.nan))
    axes[0].bar(np.arange(3)+off,values,.30,color=color,label=label)
axes[0].set(xticks=range(3),xticklabels=[NAMES[o] for o in objects],ylabel="长度 (m)")
axes[0].legend(prop=CJK,fontsize=7)
title(axes[0],"a 给定模式的范围与真实误差")
data=read("exp_average")
rounddata=next(iter(data["sessions"].values()))
for j,(key,label,color) in enumerate([("first_event","首次","#888888"),("all_averaged","平均","#cc873f"),("consistency","过滤","#248a85")]):
    values=[rounddata[key]["errors"][o]["center_m"] for o in ["cab","desk"]]
    axes[1].bar(np.arange(2)+(j-1)*.24,values,.23,color=color,label=label)
axes[1].set(xticks=[0,1],xticklabels=["柜","桌"],ylabel="家具中心误差 (m)")
axes[1].legend(prop=CJK,fontsize=7)
title(axes[1],"b 同段预测事件的聚合诊断")
save(fig,out,"真实 n=1；墙、朝向与邻接框固定；条件区间不是全模式置信区间")
