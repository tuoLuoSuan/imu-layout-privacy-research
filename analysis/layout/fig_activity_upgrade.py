"""Static figures for room-level endpoints, distribution and estimator gap.

Contract: show activity-dependent whole-room recovery without conflating F1
with a success fraction. Statistical unit is a generated room. Python-only
exports, editable text, full source JSON and rendered alignment checks.
"""
import argparse,json,sys
from pathlib import Path
import numpy as np


def run(package,audit_tools):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.colors import Normalize
    sys.path.insert(0,str(audit_tools));from audit_panel_alignment import require_matplotlib_panel_alignment
    package=Path(package);out=package/'figures';out.mkdir(exist_ok=True)
    d=json.loads((package/'statistics/audit.json').read_text(encoding='utf-8'))
    upgrade=json.loads((package/'upgrade-summary.json').read_text(encoding='utf-8'))
    plt.rcParams.update({'font.family':['Arial','SimSun'],'font.size':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.unicode_minus':False})
    def save(fig,axes,name):
        fig.canvas.draw();require_matplotlib_panel_alignment(fig,axes=axes,json_out=out/(name+'.alignment.json'))
        fig.savefig(out/(name+'.png'),dpi=600,facecolor='white')
        fig.savefig(out/(name+'.pdf'),facecolor='white')
        fig.savefig(out/(name+'.svg'),facecolor='white')
        plt.close(fig)
    cells=[{**c,'f1_mean':c['f1']} for c in upgrade['cells']];xs=sorted({c['coverage']*100 for c in cells});ys=sorted({c['visits'] for c in cells});lookup={(c['coverage']*100,c['visits']):c for c in cells}
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,113/25.4));fig.subplots_adjust(left=.08,right=.89,bottom=.27,top=.78,wspace=.18)
    for ax,metric,title in zip(axes,['whole_rate','f1_mean'],['a  整屋全中：命中房数／1000','b  次端点：平均家具位置F1']):
        z=np.array([[lookup[x,y][metric]*100 if (x,y) in lookup else np.nan for x in xs] for y in ys]);cmap=plt.cm.viridis.copy();cmap.set_bad('#f0f2f5')
        im=ax.imshow(z,origin='lower',aspect='auto',vmin=0,vmax=100,cmap=cmap,interpolation='none')
        for j,y in enumerate(ys):
            for i,x in enumerate(xs):
                if (x,y) not in lookup:
                    # Explicit short segments keep the exported hatch geometry
                    # within each untested cell for backend-neutral PDF audits.
                    for offset in [-.75,-.5,-.25,0.,.25,.5,.75]:
                        lo=max(-.5,-.5-offset);hi=min(.5,.5-offset)
                        ax.plot([i+lo,i+hi],[j+lo+offset,j+hi+offset],color='#a6afb8',lw=.4)
                    continue
                q=lookup[x,y];text=str(q['whole_hits']) if metric=='whole_rate' else f"{q['f1_mean']*100:.1f}%"
                ax.text(i,j,text,ha='center',va='center',fontsize=6.1,color='white' if z[j,i]<65 else '#13283a')
        ax.set_xticks(range(len(xs)),[f'{x:g}' for x in xs]);ax.set_yticks(range(len(ys)),ys);ax.tick_params(length=0)
        ax.set_xlabel('行走覆盖目标 (%)');ax.set_ylabel('交互访次' if ax is axes[0] else '');ax.set_title(title,loc='left',fontsize=9,pad=11)
    ca=fig.add_axes([.92,.27,.014,.51]);fig.colorbar(im,cax=ca,ticks=[0,40,80,100])
    fig.text(.08,.94,'改进选点后的活动泄露：整屋全中与平均F1分开报告',fontsize=11)
    fig.text(.08,.875,'1000间受控规整房；床1件，桌／储物／椅各1–2件；中心容差0.5m。',fontsize=8)
    fig.text(.08,.16,'斜纹格未测试；各实测格分母固定1000。80%仅是F1展示参考，整屋未达80%。',fontsize=7.2)
    fig.text(.08,.09,'理想坐标、已知外框与家具清单；F1区间用房间bootstrap，整屋区间用Wilson。',fontsize=7.2)
    save(fig,list(axes),'main-heatmap')
    rows=d['distribution_best'];values=np.array([r['f1'] for r in rows]);ordered=np.sort(values)
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,108/25.4));fig.subplots_adjust(left=.09,right=.97,bottom=.26,top=.77,wspace=.25)
    axes[0].step(np.r_[0.,ordered],np.r_[0.,np.arange(1,len(values)+1)/len(values)]*100,where='post',color='#347886',lw=1.6)
    axes[0].axvline(values.mean(),color='#a87c35',ls='--',lw=.8);axes[0].set(xlim=(0,1.02),ylim=(0,102),xlabel='每房实例位置F1',ylabel='累计房间比例 (%)');axes[0].set_title('a  经验CDF：中位数为1.00',loc='left',fontsize=9)
    groups=[values==0,(values>0)&(values<.5),(values>=.5)&(values<.8),(values>=.8)&(values<.9),(values>=.9)&(values<1-1e-12),np.isclose(values,1.,rtol=0,atol=1e-12)]
    counts=np.array([int(x.sum()) for x in groups]);axes[1].bar(range(len(counts)),counts,color=['#8292a2']*5+['#347886'],width=.7)
    axes[1].set_xticks(range(len(counts)),['0','(0,.5)','[.5,.8)','[.8,.9)','[.9,1)','1'],fontsize=6.5);axes[1].set(ylabel='房间数',ylim=(0,650),xlabel='每房实例位置F1分组');axes[1].set_title('b  574间全中，32间为0',loc='left',fontsize=9)
    for i,n in enumerate(counts):axes[1].text(i,n+12,str(n),ha='center',va='bottom',fontsize=7)
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.text(.09,.94,'原006均值88.34%不表示每间房都错11.66%',fontsize=11)
    fig.text(.09,.865,'固定条件：100%覆盖／14次交互；1000间房，未按成败筛选。',fontsize=8)
    fig.text(.09,.15,'全中57.4% [54.3,60.4]；F1≥0.9同为57.4%（本批无只漏1件输出）。',fontsize=7.5)
    fig.text(.09,.08,'F1均值房间bootstrap95%区间约87.09–89.54%；0分含未出解，全部保留。',fontsize=7.5)
    save(fig,list(axes),'room-distribution')
    candidate=json.loads((package/'candidate-joint/summary.json').read_text(encoding='utf-8'))
    full=candidate['all']['full_proposals'];ret=candidate['all']['retained_proposals'];classes=['bed','desk','cab','chair'];labels=['床','桌','储物','椅']
    fig,ax=plt.subplots(figsize=(183/25.4,106/25.4));fig.subplots_adjust(left=.09,right=.97,bottom=.28,top=.77);x=np.arange(4);width=.24
    datasets=[([full[c]['tp']/full[c]['n_truth']*100 for c in classes],'完整候选的逐类oracle匹配','#b9c7d1'),
        ([ret[c]['tp']/ret[c]['n_truth']*100 for c in classes],'保留候选的逐类oracle匹配','#7fa3b4'),
        ([d['per_class_best'][c]['recall']*100 for c in classes],'实际选点召回','#347886')]
    for i,(v,label,col) in enumerate(datasets):ax.bar(x+(i-1)*width,v,width,label=label,color=col)
    ax.set_xticks(x,labels);ax.set(ylabel='实例召回 (%)',ylim=(0,108));ax.spines[['top','right']].set_visible(False);ax.legend(loc='lower center',bbox_to_anchor=(.5,-.36),ncol=1,frameon=False,fontsize=7)
    for i,c in enumerate(classes):ax.text(x[i]+width,d['per_class_best'][c]['recall']*100+2,f"{d['per_class_best'][c]['recall']*100:.1f}",ha='center',fontsize=7)
    fig.text(.09,.94,'桌的损失主要出现在选点之后，不能据此宣称信息上限',fontsize=11)
    fig.text(.09,.865,'评价端oracle在同一保留候选中找到913/1000间完整正确解；不属于部署成绩。',fontsize=8)
    fig.text(.09,.06,'oracle只用于评价诊断；逐类边缘匹配忽略联合兼容性，不是可部署成绩或整屋保证。',fontsize=7.2)
    save(fig,[ax],'proposal-gap')
    fig,ax=plt.subplots(figsize=(183/25.4,105/25.4));fig.subplots_adjust(left=.10,right=.96,bottom=.28,top=.77)
    pairs=[upgrade['spread_mechanism'][k] for k in ['outline|0.95|11','outline|1.0|14']];xx=np.arange(2);w=.28
    for i,(mode,label,color) in enumerate([('repeat','同点重复','#a2b3bf'),('dispersed','分散接触','#347886')]):
        means=np.array([p[mode]['whole_rate']*100 for p in pairs]);limits=np.array([p[mode]['whole_wilson_ci'] for p in pairs])*100
        ax.bar(xx+(i-.5)*w,means,w,color=color,label=label,yerr=np.array([means-limits[:,0],limits[:,1]-means]),capsize=3,error_kw={'lw':.8})
        for j,v in enumerate(means):ax.text(xx[j]+(i-.5)*w,v+5,f'{v:.1f}%',ha='center',fontsize=8)
    ax.set_xticks(xx,['95%覆盖／11次','100%覆盖／14次']);ax.set(ylabel='整屋全部命中 (%)',ylim=(0,100));ax.spines[['top','right']].set_visible(False);ax.legend(loc='upper left',frameon=False,fontsize=8)
    fig.text(.10,.94,'同样的交互次数，新增接触位置比重复更容易泄露布局',fontsize=11)
    fig.text(.10,.865,'固定outline估计器；每组1000间配对房间；路径、类别访次、尺寸和容差一致。',fontsize=8)
    fig.text(.10,.16,'100%／14次：分散接触增加23.1pp，配对bootstrap95%区间20.3–26.0pp。',fontsize=7.5)
    fig.text(.10,.09,'柱上误差线为Wilson95%区间；理想接触位置机制对照，不是已识别的真实IMU动作。',fontsize=7.3)
    save(fig,[ax],'spread-mechanism')
    # Numeric-coordinate3D appendices reuse the verified Python plotting path.
    from .fig_main_activity3d import pareto,static_plot
    display={'n_rooms':1000,'x':xs,'visits':ys,'views':{},'method':'outline','uncertainty':'Room bootstrap95% F1; Wilson95% whole-room; pointwise exploratory'}
    for metric in ['f1','layout']:
        a={key:[[None for x in xs] for y in ys] for key in ['z','lo','hi','hits']};a['n']=1000
        for j,y in enumerate(ys):
            for i,x in enumerate(xs):
                if (x,y) not in lookup:continue
                q=lookup[x,y];a['z'][j][i]=100*q['f1' if metric=='f1' else 'whole_rate'];lim=q['f1_bootstrap_ci' if metric=='f1' else 'whole_wilson_ci']
                a['lo'][j][i]=100*lim[0];a['hi'][j][i]=100*lim[1];a['hits'][j][i]=q['whole_hits']
        a['frontier80']=pareto(a['z'],xs,ys);display['views']['all|all|outline|'+metric]=a
    appendix=out/'appendix3d';appendix.mkdir(exist_ok=True);static_plot(display,appendix,audit_tools,method='outline')
    (appendix/'source-data.json').write_text(json.dumps(display,ensure_ascii=False,indent=1),encoding='utf-8')
    (out/'figure-source.json').write_text(json.dumps({'audit_source':'../statistics/audit.json','upgrade_source':'../upgrade-summary.json','candidate_source':'../candidate-joint/summary.json','distributions':counts.tolist(),'quantitative_grid':'unsmoothed categorical cells; untested hatched'},ensure_ascii=False,indent=1),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--audit-tools',required=True);a=p.parse_args();run(a.package,a.audit_tools)
