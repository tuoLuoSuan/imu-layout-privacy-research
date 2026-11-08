"""Outlier-order and event-duration randomised consistency diagnostic."""
import sys
from figure_style import *
rows=read("exp_consistency")
objects=["cab","chair","bed"]
fig,axes=plt.subplots(1,2,figsize=(6.3,3.1),layout="constrained")
for off,field,label,color in [(-.16,"detect","离群检出","#248a85"),(.16,"false_reject","真事件误拒","#cc873f")]:
    values=[100*np.mean([r[field] for r in rows if r["kind"]=="outlier" and r["obj"]==o]) for o in objects]
    axes[0].bar(np.arange(3)+off,values,.30,color=color,label=label)
axes[0].set(xticks=range(3),xticklabels=[NAMES[o] for o in objects],ylabel="重复条件的平均比例 (%)",ylim=(0,105))
axes[0].legend(prop=CJK,fontsize=7)
title(axes[0],"a 误检与误拒同时报告")
for off,field,label,color in [(-.16,"err_all","全部平均","#cc873f"),(.16,"err_filtered","过滤后平均","#248a85")]:
    values=[np.median([r[field] for r in rows if r["kind"]=="outlier" and r["obj"]==o]) for o in objects]
    axes[1].bar(np.arange(3)+off,values,.30,color=color,label=label)
axes[1].set(xticks=range(3),xticklabels=[NAMES[o] for o in objects],ylabel="锚点误差中位 (m)")
axes[1].set_ylim(0,max(r['err_all'] for r in rows if r['kind']=='outlier')*1.4)
axes[1].legend(prop=CJK,fontsize=7)
title(axes[1],"b 污染测量的描述性比较")
save(fig,sys.argv[1] if len(sys.argv)>1 else HERE/"../../output/layout-recon/filter.png",
     "几何模拟 %d 房；离群顺序和事件样本数随机化；无跨房确认" % len({r["scene"] for r in rows}))
