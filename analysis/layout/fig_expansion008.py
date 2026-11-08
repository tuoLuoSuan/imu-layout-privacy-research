"""Static5000-room evidence, untouched-seed confirmation and bridge failures.

Plot contract: distinguish full-position success, mean positionF1 and oracle
representability. Use actual sampled coordinates for3D, no smoothing, no
invented monotonicity; bootstrap/Wilson intervals are explicitly pointwise.
"""
import argparse,json,sys
from pathlib import Path
import numpy as np


def run(package,audit_tools,diagnostics_only=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    sys.path.insert(0,str(audit_tools));from audit_panel_alignment import require_matplotlib_panel_alignment
    from .fig_main_activity3d import pareto
    package=Path(package);out=package/'figures';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':['Arial','SimSun'],'font.size':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.unicode_minus':False})
    def save(fig,axes,name):
        fig.canvas.draw();require_matplotlib_panel_alignment(fig,axes=axes,json_out=out/(name+'.alignment.json'))
        fig.savefig(out/(name+'.png'),dpi=600,facecolor='white');fig.savefig(out/(name+'.pdf'),facecolor='white');fig.savefig(out/(name+'.svg'),facecolor='white');plt.close(fig)
    oracle=json.loads((package/'oracle-fixed1000/summary.json').read_text(encoding='utf-8'));witness={r['scene'] for r in oracle['rows'] if r['oracle_joint']['all_hit']}
    prior=package.parent/'2026-11-08-activity-upgrade-007/selection-full/rooms';counts=[]
    for method in ['legacy','outline']:
        selected=[]
        for f in sorted(prior.glob('*.json')):
            r=json.loads(f.read_text(encoding='utf-8'));q=next(x for x in r['rows'] if x['method']==method)
            if q['score']['all_instances_hit']:selected.append(r['scene'])
        if not set(selected)<=witness:raise ValueError('Oracle still contradicts deployment')
        counts.append([len(selected),len(witness)-len(selected),1000-len(witness)])
    fig,ax=plt.subplots(figsize=(183/25.4,104/25.4));fig.subplots_adjust(left=.12,right=.96,bottom=.27,top=.78);bottom=np.zeros(2)
    for j,(label,color) in enumerate([('实际全中','#347886'),('存在正确候选但未选中','#c29c65'),('本次未找到正确候选','#cbd4dc')]):
        values=np.array(counts)[:,j];ax.bar([0,1],values,bottom=bottom,width=.55,color=color,label=label)
        for i,v in enumerate(values):ax.text(i,bottom[i]+v/2 if v>=100 else bottom[i]+v+15,str(int(v)),ha='center',va='center' if v>=100 else 'bottom',fontsize=8)
        bottom+=values
    ax.set_xticks([0,1],['原部署选点','outline候选改进']);ax.set(ylabel='原1000间房的分账',ylim=(0,1100));ax.spines[['top','right']].set_visible(False)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.12),ncol=3,frameon=False,fontsize=7)
    fig.text(.10,.94,'同类匹配修复后：955个正确候选见证，25例矛盾全部消除',fontsize=11)
    fig.text(.10,.865,'评价端枚举同类置换；原913按编号绑定，漏掉可交换的家具对应。部署成绩不变。',fontsize=7.5)
    fig.text(.10,.08,'955是受限候选中的见证下界，非部署准确率或唯一可辨识比例；剩余45不称物理不可行。',fontsize=7.2)
    save(fig,[ax],'oracle-accounting')
    synth=json.loads((package/'synthetic-imu/results.json').read_text(encoding='utf-8'));groups=['original','dwell_0.45','dwell_0.75'];labels=['原36秒脚本','延长停留0.45','延长停留0.75']
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,109/25.4));fig.subplots_adjust(left=.10,right=.97,bottom=.28,top=.76,wspace=.26)
    for i,g in enumerate(groups):
        values=[r['frontend']['path_ratio'] for r in synth['rows'] if r['profile']==g];axes[0].scatter(np.full(len(values),i)+np.linspace(-.08,.08,len(values)),values,color='#347886',s=20)
    axes[0].axhline(1.,color='#a87c35',lw=.9,ls='--');axes[0].set_xticks(range(3),labels,fontsize=7);axes[0].set(ylabel='估计路程／真值人体路程',ylim=(0,1.15));axes[0].set_title('a  轨迹通道仍存在合成域偏差',loc='left',fontsize=9)
    classes=['walk','seated','lying','cabinet','other'];x=np.arange(5)
    for gi,g in enumerate(groups):
        samples=np.array([[r['actions'][c]['recall'] for c in classes] for r in synth['rows'] if r['profile']==g])*100;values=samples.mean(axis=0);color=['#8292a2','#347886','#bb925b'][gi]
        axes[1].errorbar(x,values,yerr=[values-samples.min(axis=0),samples.max(axis=0)-values],fmt='none',capsize=2,elinewidth=.5,ecolor=color)
        axes[1].plot(x,values,'o-',ms=3,lw=.8,label=labels[gi],color=color)
    axes[1].set_xticks(x,['走','坐','躺','柜','其他']);axes[1].set(ylabel='窗级召回 (%)',ylim=(0,105));axes[1].set_title('b  延长动作后仍有背景误识别',loc='left',fontsize=9);axes[1].legend(loc='upper right',frameon=False,fontsize=6.5)
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.text(.10,.94,'合成六轴IMU实际送入冻结模型：运动学9/9通过，整屋0/9全中',fontsize=10.5)
    fig.text(.10,.865,'1间程序化房、3种脚本×3次噪声重复；不把9次重复算9间房；未拟合轨迹尺度。',fontsize=7.5)
    fig.text(.10,.18,'右图：3次噪声重复均值及范围（非跨房区间）；真轨迹＋真动作也未整屋恢复。',fontsize=7.2)
    fig.text(.10,.13,'生成接触语义与生产床脚协议不兼容，不能把失败只归因于冻结前端。',fontsize=7.2)
    fig.text(.10,.07,'手机六轴桥接试验，不计入5000房几何成绩；未验证手机手表联合模拟。',fontsize=7.2)
    save(fig,list(axes),'synthetic-imu-bridge')
    if diagnostics_only:return
    d=json.loads((package/'summary5000.json').read_text(encoding='utf-8'));cell=[r for r in d['cells']['all5000'] if r['method']=='outline' and r['contact_mode']=='dispersed'];xs=sorted({r['coverage']*100 for r in cell});ys=sorted({r['visits'] for r in cell});lookup={(r['coverage']*100,r['visits']):r for r in cell}
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,113/25.4));fig.subplots_adjust(left=.08,right=.89,bottom=.27,top=.78,wspace=.18)
    for ax,metric,title in zip(axes,['whole_rate','f1'],['a  整屋位置全中：命中房数／5000','b  平均实例位置F1']):
        z=np.array([[lookup[x,y][metric]*100 if (x,y) in lookup else np.nan for x in xs] for y in ys]);cmap=plt.cm.viridis.copy();cmap.set_bad('#eff2f5');im=ax.imshow(z,origin='lower',aspect='auto',vmin=0,vmax=100,cmap=cmap,interpolation='none')
        for j,y in enumerate(ys):
            for i,x in enumerate(xs):
                if (x,y) not in lookup:
                    for off in [-.75,-.5,-.25,0,.25,.5,.75]:
                        lo=max(-.5,-.5-off);hi=min(.5,.5-off);ax.plot([i+lo,i+hi],[j+lo+off,j+hi+off],color='#a6afb8',lw=.4)
                    continue
                q=lookup[x,y];text=str(q['whole_hits']) if metric=='whole_rate' else f"{q['f1']*100:.1f}%";ax.text(i,j,text,ha='center',va='center',fontsize=6.1,color='white' if z[j,i]<65 else '#183044')
        ax.set_xticks(range(len(xs)),[f'{x:g}' for x in xs]);ax.set_yticks(range(len(ys)),ys);ax.tick_params(length=0);ax.set_xlabel('行走覆盖目标（离散档位 %）');ax.set_ylabel('交互访次' if ax is axes[0] else '');ax.set_title(title,loc='left',fontsize=8.5,pad=11)
    ca=fig.add_axes([.92,.27,.014,.51]);fig.colorbar(im,cax=ca,ticks=[0,40,80,100])
    fig.text(.08,.94,'5000间规整多实例房：活动覆盖与位置泄露',fontsize=11)
    fig.text(.08,.875,'1000历史房＋4000冻结新种子；床1件，桌／储物／椅各1–2件；中心容差0.5m。',fontsize=7.4)
    fig.text(.08,.16,'斜纹未测，格间不插值；固定分母5000。新种子确认与合并描述分开报告。',fontsize=7.3)
    fig.text(.08,.09,'理想轨迹和语义坐标、已知外框与清单；不是5000段原始IMU或5000间真实房。',fontsize=7.3)
    save(fig,list(axes),'activity-heatmap-5000')
    conf=[r for r in d['cells']['confirmation4000'] if r['coverage']==1. and r['visits']==14]
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,108/25.4));fig.subplots_adjust(left=.10,right=.97,bottom=.28,top=.77,wspace=.24)
    settings=[([next(r for r in conf if r['method']==m and r['contact_mode']=='dispersed') for m in ['legacy','outline']],['legacy','outline'],'a  4000新种子：冻结规则的确认'),
        ([next(r for r in conf if r['method']=='outline' and r['contact_mode']==mode) for mode in ['repeat','dispersed']],['同点重复','分散接触'],'b  同覆盖、同访次：空间证据对照')]
    for ax,(rows,labs,title) in zip(axes,settings):
        means=np.array([r['whole_rate']*100 for r in rows]);limits=np.array([r['whole_wilson_ci'] for r in rows])*100
        ax.bar([0,1],means,width=.56,color=['#a2b3bf','#347886'],yerr=[means-limits[:,0],limits[:,1]-means],capsize=3,error_kw={'lw':.8})
        for i,v in enumerate(means):ax.text(i,v+5,f'{v:.1f}%',ha='center',fontsize=8)
        ax.set_xticks([0,1],labs);ax.set(ylabel='整屋位置全中 (%)',ylim=(0,100));ax.spines[['top','right']].set_visible(False);ax.set_title(title,loc='left',fontsize=8.7)
    fig.text(.10,.94,'相同活动预算下，估计器与接触分布都影响实际恢复',fontsize=11)
    fig.text(.10,.865,'100%覆盖／14次；未用新增4000种子的结果选规则；同一生成族与资产库。',fontsize=7.5)
    p=d['paired']['confirmation4000'];m=d['mechanism']['confirmation4000']['outline|1.0|14']
    fig.text(.10,.16,f"新种子选点差值{p['b_minus_a']*100:+.1f}pp；分散接触差值{m['b_minus_a']*100:+.1f}pp；配对区间与检验见表。",fontsize=7.5)
    fig.text(.10,.08,'柱上为Wilson95%区间；主要确认检验只有左图固定条件，其他为次分析。',fontsize=7.4)
    save(fig,list(axes),'confirmation-and-spread')
    arrays=np.load(package/'paired-arrays5000.npz');keys=[json.loads(k) for k in arrays['keys']];target=[keys.index([m,1.,14,'dispersed']) for m in ['legacy','outline']];values=[arrays['f1'][:,j] for j in target]
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,108/25.4));fig.subplots_adjust(left=.10,right=.97,bottom=.27,top=.77,wspace=.25)
    for v,label,color in zip(values,['legacy','outline'],['#8292a2','#347886']):
        ordered=np.sort(v);axes[0].step(np.r_[0.,ordered],np.r_[0.,np.arange(1,len(v)+1)/len(v)]*100,where='post',lw=1.5,color=color,label=label)
    axes[0].set(xlabel='单房位置F1',ylabel='累计房间比例 (%)',xlim=(0,1.02),ylim=(0,102));axes[0].legend(frameon=False,fontsize=7,loc='upper left');axes[0].set_title('a  5000间逐房经验CDF',loc='left',fontsize=9)
    v=values[1];bins=[v==0,(v>0)&(v<.5),(v>=.5)&(v<.8),(v>=.8)&(v<.9),(v>=.9)&(v<1-1e-12),np.isclose(v,1.,atol=1e-12,rtol=0)];numbers=[int(b.sum()) for b in bins]
    axes[1].bar(range(6),numbers,color=['#a2b3bf']*5+['#347886'],width=.7);axes[1].set_xticks(range(6),['0','(0,.5)','[.5,.8)','[.8,.9)','[.9,1)','1'],fontsize=6.5);axes[1].set(xlabel='outline单房F1分组',ylabel='房间数',ylim=(0,max(numbers)*1.18));axes[1].set_title('b  单房恢复分布，未删除0分',loc='left',fontsize=9)
    for i,n in enumerate(numbers):axes[1].text(i,n+max(numbers)*.025,str(n),ha='center',fontsize=7)
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.text(.10,.94,'平均F1与整屋全中分开读：保留逐房分布',fontsize=11);fig.text(.10,.865,'100%覆盖／14次；5000间描述性合并，4000新种子确认另列。',fontsize=7.5)
    fig.text(.10,.16,'本批有解时输出完整清单，失败时零输出；F1≥0.9与F1=1的重合不推广到漏件模型。',fontsize=7.2)
    fig.text(.10,.08,'图中CDF与分组计数为实测分布；不是每间房都恰好达到平均恢复程度。',fontsize=7.3)
    save(fig,list(axes),'room-distribution-5000')
    for metric,stem,title in [('f1','activity-surface-f1-5000','5000房：覆盖 × 交互访次 → 平均位置F1'),('whole_rate','activity-surface-whole-5000','5000房：覆盖 × 交互访次 → 整屋位置全中')]:
        z=np.array([[lookup[x,y][metric]*100 if (x,y) in lookup else np.nan for x in xs] for y in ys]);xx,yy=np.meshgrid(xs,ys)
        fig=plt.figure(figsize=(183/25.4,145/25.4));ax=fig.add_subplot(111,projection='3d');fig.subplots_adjust(left=.02,right=.87,bottom=.23,top=.86)
        ax.plot_wireframe(xx,yy,z,color='#627d94',lw=.65,alpha=.65);ax.scatter(xx.ravel(),yy.ravel(),z.ravel(),c=z.ravel(),s=15,cmap='viridis',vmin=0,vmax=100,depthshade=False)
        for j,y in enumerate(ys):
            for i,x in enumerate(xs):
                if (x,y) in lookup:
                    ci=lookup[x,y]['f1_bootstrap_ci' if metric=='f1' else 'whole_wilson_ci'];ax.plot([x,x],[y,y],np.array(ci)*100,color='#536c80',lw=.5,alpha=.55)
        if metric=='f1':
            a,b=np.meshgrid([0.,100.],[0.,max(ys)]);ax.plot_surface(a,b,np.full_like(a,80),color='#c38a3f',alpha=.10,shade=False)
            frontier=pareto(z.tolist(),xs,ys);note='F1≥80%的已测预算前沿：'+'；'.join(f"{p['coverage']:g}%/{p['visits']}次" for p in frontier)
        else:note='本图只报所有家具中心同时命中的房间比例；不等于占地IoU或轮廓恢复。'
        ax.set(xlim=(0,100),ylim=(0,max(ys)),zlim=(0,100),xticks=[0,20,40,60,80,100],yticks=ys,zticks=[0,20,40,60,80,100])
        ax.set_xlabel('行走覆盖目标 (%)',labelpad=23);ax.set_ylabel('交互访次',labelpad=19);ax.set_zlabel('平均位置F1 (%)' if metric=='f1' else '整屋位置全中 (%)',labelpad=8);ax.view_init(elev=25,azim=-55);ax.set_box_aspect((1.3,1.,.85),zoom=.90)
        for axis in [ax.xaxis,ax.yaxis,ax.zaxis]:axis.pane.set_fill(False)
        ca=fig.add_axes([.90,.32,.015,.46]);fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0,100),cmap='viridis'),cax=ca,ticks=[0,40,80,100])
        fig.text(.075,.94,title,fontsize=11.5);fig.text(.075,.88,'1000历史房＋4000冻结新种子；1床、桌／储物／椅各1–2件；容差0.5m。',fontsize=7.7)
        fig.text(.075,.155,note,fontsize=7.7,color='#8d5c23');fig.text(.075,.105,'圆点为已测格；线仅连接测点；细竖线为逐点95%区间，不强制单调。',fontsize=7.7)
        fig.text(.075,.055,'给定外框和家具清单、理想位置与语义；几何条件结果，非原始IMU恢复阈值。',fontsize=7.7)
        save(fig,[ax],stem)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--audit-tools',required=True);p.add_argument('--diagnostics-only',action='store_true');a=p.parse_args();run(a.package,a.audit_tools,a.diagnostics_only)
