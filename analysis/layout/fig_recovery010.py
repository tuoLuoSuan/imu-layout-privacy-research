"""Static, source-backed010 figures; endpoints and input levels stay separate."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from .fig_main_activity3d import interval

BLUE='#386c8f';GRAY='#909ca7';GOLD='#b47b27'
COLORS={'bed':'#8faccd','desk':'#dfbd78','cab':'#a68fbd','chair':'#cb95a9'}
LABELS={'bed':'床','desk':'桌','cab':'储物','chair':'椅'}


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def save(fig,out,name,axes):
    from audit_panel_alignment import require_matplotlib_panel_alignment
    fig.canvas.draw();require_matplotlib_panel_alignment(fig,axes=axes,json_out=out/(name+'.alignment.json'),strict=True)
    fig.savefig(out/(name+'.pdf'),facecolor='white');fig.savefig(out/(name+'.svg'),facecolor='white')
    fig.savefig(out/(name+'.png'),dpi=600,facecolor='white');plt.close(fig)


def header(fig,title,subtitle):
    fig.text(.10,.95,title,fontsize=11,weight='bold');fig.text(.10,.895,subtitle,fontsize=7.5,color='#4e5d68')


def source(out,name,rows):
    with (out/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
        keys=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def geometry(p,out):
    s=read(p/'geometry-confirm1000/audit.json');rows=[r for r in s['cells'] if r['coverage']==1. and r['visits']==14 and r['policy'] in ['post64_wall40k','depth_portfolio']]
    source(out,'matched-geometry-source',rows);fig,ax=plt.subplots(figsize=(183/25.4,122/25.4));fig.subplots_adjust(left=.12,right=.95,bottom=.28,top=.78)
    for i,r in enumerate(rows):
        x=np.arange(3)+(i-.5)*.30;y=np.array([r['rate'],r['mean_f1'],r['whole_iou0_5']/r['n']])*100
        cis=[r['wilson95'],r['f1_bootstrap95'],interval([1]*r['whole_iou0_5']+[0]*(r['n']-r['whole_iou0_5']),True)[1:]];ci=np.array(cis)*100
        ax.bar(x,y,.28,color=BLUE if r['policy']=='depth_portfolio' else GRAY,label='新：墙面方向＋联合搜索＋失败回退' if r['policy']=='depth_portfolio' else '旧：截断后墙过滤（同4万节点上限）')
        ax.errorbar(x,y,yerr=np.c_[y-ci[:,0],ci[:,1]-y].T,fmt='none',color='#243847',lw=.8,capsize=2)
        for xx,yy in zip(x,y):ax.text(xx,yy+3,f'{yy:.1f}',ha='center',va='bottom',fontsize=8)
    ax.set(ylim=(0,110),yticks=[0,20,40,60,80,100],xticks=range(3),xticklabels=['全部中心 ≤0.5 m','平均实例位置 F1','全部占地 IoU ≥0.5'],ylabel='比例 / F1 (%)');ax.legend(loc='upper left',bbox_to_anchor=(-.03,1.23),fontsize=7)
    header(fig,'全屋位置恢复改善，家具轮廓仍未精确恢复','新种子确认：1,000 间 · 100%可达空地覆盖＋14次分散交互 · 同类一对一匹配')
    fig.text(.12,.17,'中心全中：851 → 945；配对增益 +9.4 pp，95% bootstrap [7.6, 11.3] pp。',fontsize=7.5)
    fig.text(.12,.11,'先验与搜索策略一起改变；预算上限匹配，实际搜索节点中位数 7 → 715.5。',fontsize=7.2)
    fig.text(.12,.05,'理想轨迹＋类别接触坐标，已知外框／数量／尺寸；误差线：Wilson或按房bootstrap95%。',fontsize=7.2)
    save(fig,out,'matched-geometry',[ax])


def raw_controls(p,out):
    a=read(p/'raw-final100-controls.json');raw=read(p/'raw-final100/summary.json')['summary'];labels=['仅手机','手机＋旧腕部模型','手机＋同一新腕部模型','去掉手表','手表错时10秒'];keys=['phone_only','old_real_only_watch','same_learned_watch','watch_absent','wrong_clock10s'];counts=[raw['phone_only']['all_hit']]+[a['rows'][k]['whole'] for k in keys[1:]]
    source(out,'raw-controls-source',[{'arm':k,'whole':n,'n':100} for k,n in zip(keys,counts)]);fig,ax=plt.subplots(figsize=(183/25.4,124/25.4));fig.subplots_adjust(left=.12,right=.95,bottom=.29,top=.77)
    for i,n in enumerate(counts):
        rate,lo,hi=interval([1]*n+[0]*(100-n),True);ax.bar(i,n,.57,color=BLUE if i==2 else GRAY);ax.errorbar(i,n,yerr=[[n-lo*100],[hi*100-n]],fmt='none',color='#243847',capsize=3,lw=.9);ax.text(i,max(n+10,hi*100+4),f'{n}/100',ha='center',fontsize=8)
    ax.set(ylim=(0,104),xticks=range(5),xticklabels=labels,ylabel='全部四件中心达标的录音 (%)');ax.tick_params(axis='x',labelsize=6.6)
    header(fig,'原始手机＋手表输入已跑通受控四件家具链路','冻结100条短合成录音 · 手机六轴120Hz／手表三轴16.7Hz · 手表无陀螺')
    fig.text(.12,.18,'新腕部模型联合端：80/100；F1=93.5%；误差线为按录音 Wilson95%。',fontsize=7.5)
    fig.text(.12,.12,'腕部专家在真实r1/r2＋20间合成开发房上训练；不是零样本迁移。柜门仅由手表提供。',fontsize=7.2)
    fig.text(.12,.06,'受控持法＋静止端点积分＋已知近墙起点；与一万间多实例几何实验分开报告。',fontsize=7.2)
    save(fig,out,'raw-joint-controls',[ax])


def real_case(p,out):
    r=read(p/'real-final/results.json');case=min(r['rows'],key=lambda x:abs(x['shift_s']));pred=case['prediction']['boxes'];truth={'bed':[1.17,1.96,2.695,4.045],'desk':[.05,1.05,.65,2.10],'cab':[.05,0,.65,1.05],'chair':[1.11,.92,1.55,1.36]}
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,140/25.4));fig.subplots_adjust(left=.10,right=.94,bottom=.24,top=.80,wspace=.32)
    for ax,boxes,title in zip(axes,[pred,truth],['a  手机＋手表推断','b  参考占地（仅评价）']):
        ax.add_patch(Rectangle((0,0),2.84,4.045,fill=False,lw=1.2,color='#203442'))
        for name,b in boxes.items():
            ax.add_patch(Rectangle(b[:2],b[2]-b[0],b[3]-b[1],facecolor=COLORS[name],edgecolor='#455767',lw=.7));ax.text((b[0]+b[2])/2,(b[1]+b[3])/2,LABELS[name],ha='center',va='center',fontsize=8)
        ax.plot([.437,1.212],[4.045,4.045],color='#5a8c70',lw=3);ax.plot(.825,3.845,'o',ms=3,color='#243847');ax.set(xlim=(-.1,2.94),ylim=(-.1,4.15),xticks=[0,1,2,2.84],yticks=[0,1,2,3,4],xlabel='x (m)',ylabel='y (m)');ax.set_aspect('equal');ax.set_title(title,fontsize=8,loc='left',pad=10)
    header(fig,'真实开发房仍能恢复出正确的家具位置','同一冻结手机模型＋同一新腕部模型；0秒及六档错时敏感性均为4/4')
    errors={m['class']:m['error_m'] for m in case['score']['matches']};text='；'.join(f'{LABELS[c]} {errors[c]:.3f} m' for c in ['bed','desk','cab','chair'])
    fig.text(.10,.15,'中心误差：'+text,fontsize=7.5);fig.text(.10,.09,'柜门事件只来自手表；软件时钟对齐，未获得物理同步证书。',fontsize=7.2);fig.text(.10,.04,'仅一间复用开发房，提供已知外框、起点、尺寸和家具关系；不代表跨真实房泛化。',fontsize=7.2)
    save(fig,out,'real-joint-case',list(axes))


def distribution(p,out):
    fig,ax=plt.subplots(figsize=(183/25.4,112/25.4));fig.subplots_adjust(left=.12,right=.94,bottom=.27,top=.79);data=[]
    for folder,color,label in [('historical10000',GRAY,'历史10,000间'),('geometry-confirm1000',BLUE,'新种子1,000间')]:
        a=read(p/folder/'audit.json');d=a['distribution_primary'];v=np.sort([r['f1'] for r in d]);ax.step(np.r_[0,v,1],np.r_[0,np.arange(1,len(v)+1)/len(v)*100,100],where='post',color=color,lw=1.7,label=label)
        data.extend({'cohort':folder,**r} for r in d)
    ax.set(xlim=(0,1),ylim=(0,101),xlabel='每间房的实例位置 F1',ylabel='累计房间比例 (%)');ax.legend(fontsize=8,loc='upper left');header(fig,'平均值之外：逐房分布保留失败尾部','同一新估计器，100%覆盖＋14次；每间房一个统计单位，不剔除失败')
    fig.text(.12,.15,'两组均以F1=1为中位数；全中率分别92.36%和94.5%，其余房间并非均匀差一点。',fontsize=7.2);fig.text(.12,.08,'历史样本与新种子确认分开；相同生成族和资产，不代表自然住宅总体。',fontsize=7.2);source(out,'room-f1-cdf-source',data);save(fig,out,'room-f1-cdf',[ax])


def matched_coverage(p,out):
    f=p/'matched-coverage/summary.json'
    if not f.exists():return
    a=read(f);keys=['a_95walk_95contacts','b_100walk_95contacts','c_100walk_100contacts'];counts=[a['arms'][k]['whole'] for k in keys];fig,ax=plt.subplots(figsize=(183/25.4,121/25.4));fig.subplots_adjust(left=.12,right=.94,bottom=.28,top=.78)
    for i,n in enumerate(counts):
        mean,lo,hi=interval([1]*n+[0]*(1000-n),True);ax.bar(i,n/10,.56,color=[GRAY,BLUE,GOLD][i]);ax.errorbar(i,n/10,yerr=[[n/10-lo*100],[hi*100-n/10]],fmt='none',color='#243847',capsize=3,lw=.8);ax.text(i,hi*100+3,f'{n}/1000',ha='center',fontsize=8)
    ax.set(ylim=(0,110),yticks=range(0,101,20),xticks=range(3),xticklabels=['A：95%走路\n95%时接触','B：100%走路\n接触坐标完全固定为A','C：100%走路\n100%时接触'],ylabel='全部中心达标房间 (%)');header(fig,'最后5%覆盖本身带来信息：固定接触的配对验证','1000间，同14访次、先验、估计器；A→B仅增加步行证据，B→C才改变接触位置')
    fig.text(.12,.17,'A→B：+16.7 pp [14.3, 19.1]；B→C：+2.3 pp [1.4, 3.3]。',fontsize=8)
    fig.text(.12,.10,'柱误差线Wilson95%；增益区间为按房配对bootstrap95%；固定顺序分解，不是时间轨迹。',fontsize=7.2)
    fig.text(.12,.04,'观察主曲线后增加的机制诊断；未将接触可达性变化全部归因于走路。',fontsize=7.2);source(out,'matched-coverage-source',[{'arm':k,**a['arms'][k]} for k in keys]);save(fig,out,'matched-coverage',[ax])


def activity(p,out):
    f=p/'activity-confirm1000/audit.json'
    if not f.exists():return
    a=read(f);rows=a['cells'];source(out,'activity-source',rows);xs=[0,20,40,60,75,85,95,100];ns=[0,2,5,8,11,14];lookup={(round(r['coverage']*100),r['visits']):r for r in rows}
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,126/25.4));fig.subplots_adjust(left=.10,right=.90,bottom=.26,top=.78,wspace=.25)
    for ax,key,title in zip(axes,['rate','mean_f1'],['a  整屋中心全中（间/1000）','b  平均实例位置 F1 (%)']):
        z=np.array([[100*lookup[x,n][key] if (x,n) in lookup else np.nan for x in xs] for n in ns]);cmap=plt.cm.viridis.copy();cmap.set_bad('#edf0f3');im=ax.imshow(z,origin='lower',aspect='auto',vmin=0,vmax=100,cmap=cmap,interpolation='none')
        for j,n in enumerate(ns):
            for i,x in enumerate(xs):
                r=lookup.get((x,n));txt='未测' if r is None else str(r['whole']) if key=='rate' else f"{100*r[key]:.1f}";ax.text(i,j,txt,ha='center',va='center',fontsize=6.3,color='white' if np.isfinite(z[j,i]) and z[j,i]<65 else '#182a38')
        ax.set_xticks(range(len(xs)),xs);ax.set_yticks(range(len(ns)),ns);ax.tick_params(length=0);ax.set_xlabel('覆盖目标 (%)：离散测点');ax.set_title(title,fontsize=8,loc='left',pad=12)
    axes[0].set_ylabel('分散交互预算（次）');ca=fig.add_axes([.93,.26,.014,.52]);fig.colorbar(im,cax=ca,ticks=[0,40,80,100]);header(fig,'活动范围 × 交互：恢复边界随证据和先验改变','新种子确认1,000间；每格固定分母；不可执行按失败计；主端点为4–7件全部中心≤0.5m')
    fig.text(.10,.15,'已知外框／数量／尺寸＋桌墙面先验；理想坐标与语义事件，不是原始IMU曲面。',fontsize=7.2);fig.text(.10,.09,'同点重复不等于分散交互；未测格不补零，全部格不平滑、不强制单调。',fontsize=7.2);fig.text(.10,.04,'完整源表含0–20次逐整数的100%覆盖结果及按房不确定性。',fontsize=7.2);save(fig,out,'activity-heatmap',list(axes))
    # Measured points at their true numerical positions. Wire connections are
    # visual guides, never fitted continuous response or certified boundaries.
    fig=plt.figure(figsize=(183/25.4,150/25.4));ax=fig.add_subplot(111,projection='3d');fig.subplots_adjust(left=.02,right=.89,bottom=.24,top=.83)
    wire_ns=[0,2,5,8,11,14];X,Y=np.meshgrid(xs,wire_ns);Z=np.array([[100*lookup[x,n]['rate'] if (x,n) in lookup else np.nan for x in xs] for n in wire_ns]);ax.plot_wireframe(X,Y,Z,color='#7994a4',lw=.55,alpha=.6)
    x=np.array([r['coverage']*100 for r in rows]);y=np.array([r['visits'] for r in rows]);z=np.array([r['rate']*100 for r in rows]);ax.scatter(x,y,z,c=z,cmap='viridis',vmin=0,vmax=100,s=14,depthshade=False)
    for r in rows:
        ax.plot([r['coverage']*100]*2,[r['visits']]*2,np.array(r['wilson95'])*100,color=BLUE,lw=.4,alpha=.55)
    ax.set(xlim=(0,100),ylim=(0,20),zlim=(0,100),xticks=[0,20,40,60,80,100],yticks=[0,5,10,15,20],zticks=[0,20,40,60,80,100]);ax.set_xlabel('可达空地覆盖目标 (%)',labelpad=18);ax.set_ylabel('分散交互预算（次）',labelpad=26);ax.set_zlabel('整屋中心全中 (%)',labelpad=9);ax.view_init(elev=25,azim=-55);ax.set_box_aspect((1.3,1,.85),zoom=.9)
    for axis in [ax.xaxis,ax.yaxis,ax.zaxis]:axis.pane.set_fill(False)
    header(fig,'活动范围 × 分散交互 → 整屋位置恢复','1,000间新种子；圆点为实测、竖线为Wilson95%；轴按真实数值间距绘制')
    fig.text(.10,.16,'连线只引导阅读；不补未测格、不插值墙面、不强制单调。',fontsize=7.2);fig.text(.10,.10,'条件：矩形房、已知外框／清单／尺寸、桌墙面先验；理想轨迹＋类别接触。',fontsize=7.2);fig.text(.10,.04,'原始双设备输入与真实开发房结果单列，不能把本图当作一万条IMU端到端成绩。',fontsize=7.2);save(fig,out,'activity-3d',[ax])
    full=sorted((r for r in rows if r['coverage']==1.),key=lambda r:r['visits']);fig,ax=plt.subplots(figsize=(183/25.4,120/25.4));fig.subplots_adjust(left=.12,right=.94,bottom=.27,top=.79)
    for key,ci,color,label in [('rate','wilson95',BLUE,'全部中心达标'),('mean_f1','f1_bootstrap95',GOLD,'平均位置F1')]:
        x=np.array([r['visits'] for r in full]);y=np.array([r[key] for r in full])*100;b=np.array([r[ci] for r in full])*100;ax.plot(x,y,'o-',color=color,ms=3,lw=1.3,label=label);ax.fill_between(x,b[:,0],b[:,1],color=color,alpha=.15,lw=0)
    ax.axhline(80,color=GRAY,ls='--',lw=.8);ax.set(xlim=(0,20),ylim=(0,103),xticks=range(0,21,2),xlabel='分散交互预算（逐整数测量）',ylabel='恢复程度 / 整屋成功 (%)');ax.legend(fontsize=8,loc='lower right');header(fig,'100%覆盖：最小已测预算与置信下界分别报告','同一1,000间新种子；不得把协议中的访次当作独立测量次数')
    fig.text(.12,.16,f"点估计首次≥80%：{a['full_coverage_first_point80']}次；Wilson下界首次≥80%：{a['full_coverage_first_wilson_lower80']}次。",fontsize=8)
    fig.text(.12,.10,'区间为逐点95%，对扫描后挑选的最小预算没有同时覆盖保证。',fontsize=7.2);fig.text(.12,.04,'第14次是储物访问；同一椅反复坐点不增加空间跨度；具体机制按事件坐标核验。',fontsize=7.2);save(fig,out,'full-coverage-threshold',[ax])


def run(package,skills):
    sys.path.insert(0,str(skills));plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],'pdf.fonttype':42,'svg.fonttype':'none','font.size':7,'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False})
    p=Path(package);out=p/'figures';out.mkdir(exist_ok=True);geometry(p,out);raw_controls(p,out);real_case(p,out);distribution(p,out);matched_coverage(p,out);activity(p,out)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--figure-tools',required=True);a=p.parse_args();run(a.package,a.figure_tools)
