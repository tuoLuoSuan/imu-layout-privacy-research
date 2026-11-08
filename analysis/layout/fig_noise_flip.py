"""Perturbation stability against the base solution, not truth accuracy."""
import sys
from figure_style import *
D=read("noise_flip"); rows=D["rows"]
sigmas=sorted({r["sigma"] for r in rows})
fig,axes=plt.subplots(1,2,figsize=(6.3,3.1),layout="constrained")
for obj in NAMES:
    values=[]
    for sigma in sigmas:
        r=[r for r in rows if r["obj"]==obj and r["sigma"]==sigma]
        values.append(100*np.mean([v["fail"] or (v["disp"] is not None and v["disp"]>.5) for v in r]))
    axes[0].plot(sigmas,values,"o-",markersize=3,color=COLORS[obj],label=NAMES[obj])
axes[0].set(xlabel="每轴高斯标准差 (m)",ylabel="无解或位移 > 0.5 m (%)",ylim=(0,105))
axes[0].legend(prop=CJK,fontsize=7)
title(axes[0],"a 含无解的复合不稳定率")
values=[r["disp"] for r in rows if r["sigma"]==.10 and r["disp"] is not None]
axes[1].hist(values,bins=20,color="#248a85")
axes[1].axvline(.5,linestyle=":",linewidth=.8,color="#cc873f")
axes[1].set(xlabel="相对无噪解的位移 (m)",ylabel="成功输出的物体行数")
title(axes[1],"b 标准差 0.10 m 时的位移")
save(fig,sys.argv[1] if len(sys.argv)>1 else HERE/"../../output/layout-recon/noise.png",
     "几何模拟；%d 次求解、%d 次无解；有解也可能偏离真值" % (D["solves"],D["fails"]))
