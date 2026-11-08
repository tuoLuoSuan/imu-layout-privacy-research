"""Observed-object output policy; omitted objects are not latent variables."""
import sys
from figure_style import *
rows=read("partial")
subsets=["scl","sc","sl","cl","s","c","l"]
labels={"scl":"坐柜躺","sc":"坐柜","sl":"坐躺","cl":"柜躺","s":"坐","c":"柜","l":"躺"}
fig,axes=plt.subplots(1,2,figsize=(6.3,3.1),layout="constrained")
for j,obj in enumerate(["bed","desk","cab"]):
    values=[]
    for sub in subsets:
        e=[r["err"][obj] for r in rows if r["subset"]==sub and obj in r.get("err",{})]
        values.append(np.median(e) if e else np.nan)
    axes[0].plot(range(len(subsets)),values,"o-",markersize=3,color=COLORS[obj],label=NAMES[obj])
axes[0].set(xticks=range(len(subsets)),xticklabels=[labels[s] for s in subsets],ylabel="已输出物体中心误差中位 (m)")
axes[0].legend(prop=CJK,fontsize=7)
title(axes[0],"a 只输出有证据物体的策略")
base={r["scene"]:r for r in rows if r["subset"]=="scl"}
counts=[]
names=[]
for sub,removed in [("sc","躺"),("sl","柜"),("cl","坐")]:
    pairs=[(r,base[r["scene"]]) for r in rows if r["subset"]==sub and r["scene"] in base
           and "desk" in r.get("obj",{}) and "desk" in base[r["scene"]].get("obj",{})]
    counts.append(sum(max(abs(a-b) for a,b in zip(r["obj"]["desk"],b["obj"]["desk"]))>1e-9 for r,b in pairs) if pairs else np.nan)
    names.append("删"+removed+" (%d 对)" % len(pairs))
axes[1].bar(range(3),counts,color="#cc873f")
axes[1].set(xticks=range(3),xticklabels=names,ylabel="桌框改变的配对场景数")
title(axes[1],"b 框变化由当前缓存逐房计算")
save(fig,sys.argv[1] if len(sys.argv)>1 else HERE/"../../output/layout-recon/partial.png",
     "模拟 %d 房；无轨迹输入；缺事件也移除目标框，不能解释为纯证据消融" % len(base))
