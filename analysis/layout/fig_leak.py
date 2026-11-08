"""Ideal containment intervals; span is imposed, not a measured IMU coverage."""
import sys
from figure_style import *
import leakage_curve as LC
import paths
root=sys.argv[1] if len(sys.argv)>1 else paths.THOR
out=sys.argv[2] if len(sys.argv)>2 else HERE/"../../output/layout-recon/leak.png"
rows=LC.params(root); rows=[r for r in rows if not r.get("geom_bad")]
spans=np.arange(0,2.61,.1)
fig,axes=plt.subplots(1,2,figsize=(6.3,3.1),layout="constrained")
for tol,col in [(.5,"#248a85"),(1.0,"#cc873f")]:
    values=[100*LC.share_exceed(rows,float(s),tol,"U") for s in spans]
    axes[0].plot(spans,values,color=col,label="容差 %.1f m"%tol)
axes[0].set(xlabel="指定的接触跨度 (m)",ylabel="期望宽度超过容差的轴比例 (%)",ylim=(0,105))
axes[0].legend(prop=CJK,fontsize=7)
title(axes[0],"a 简化包含模型中的跨度曲线")
cats=[c for c in LC.CATS if any(r["cat"]==c for r in rows)]
values=[np.median(LC.residual([r for r in rows if r["cat"]==c],0.0,"U")) for c in cats]
axes[1].barh(range(len(cats)),values,color="#888888")
axes[1].set(yticks=range(len(cats)),yticklabels=cats,xlabel="零跨度的期望宽度中位 (m)")
title(axes[1],"b 类别尺寸与先验的影响")
save(fig,out,"几何机制：%d 场景、%d 轴；未加入 IMU 噪声，不是现实活动阈值" % (len({r["scene"] for r in rows}),len(rows)))
