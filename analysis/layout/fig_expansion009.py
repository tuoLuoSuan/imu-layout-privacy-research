"""Static009 figures; measurements are never interpolated or forced monotone.

Source contracts:10000 ideal-geometric rooms,100 joint raw-signal episodes,
and one reused real case remain separate. PDF/SVG text stays editable.
"""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle
from .fig_main_activity3d import interval,pareto
from .activity_audit import bootstrap_means

BLUE='#386c8f';GOLD='#b47b27';GRAY='#8a949e';COLORS={'bed':'#5c80a5','desk':'#ae8349','cab':'#7e9b80','chair':'#9b799d'}
LABELS={'bed':'床','desk':'桌','cab':'储物','chair':'椅'}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def save(fig,out,stem,axes):
    from audit_panel_alignment import require_matplotlib_panel_alignment
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,axes=axes,json_out=out/(stem+'.alignment.json'),strict=True)
    fig.savefig(out/(stem+'.pdf'),facecolor='white')
    fig.savefig(out/(stem+'.svg'),facecolor='white')
    fig.savefig(out/(stem+'.png'),dpi=600,facecolor='white')
    plt.close(fig)


def header(fig,title,sub):
    fig.text(.09,.95,title,fontsize=11,weight='bold')
    fig.text(.09,.895,sub,fontsize=7.5,color='#4e5d68')


def source_csv(out,stem,rows):
    with (out/(stem+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
        keys=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def geometric(package,out):
    s=read(package/'summary10000.json');rows=[r for r in s['cells']['all10000'] if r['method']=='outline' and r['contact_mode']=='dispersed']
    source_csv(out,'geometry-core-source',rows)
    xs=sorted({r['coverage']*100 for r in rows});ns=sorted({r['visits'] for r in rows});look={(r['coverage']*100,r['visits']):r for r in rows}
    for metric,stem,title in [('f1','activity-f1-3d','活动范围 × 分散交互：家具位置恢复程度'),('whole_rate','activity-whole-3d','活动范围 × 分散交互：全部家具同时定位')]:
        z=np.array([[100*look[x,n][metric] if (x,n) in look else np.nan for x in xs] for n in ns]);x,y=np.meshgrid(xs,ns)
        fig=plt.figure(figsize=(183/25.4,150/25.4));ax=fig.add_subplot(111,projection='3d');fig.subplots_adjust(left=.02,right=.88,bottom=.23,top=.83)
        ax.plot_wireframe(x,y,z,color='#748c9e',lw=.65,alpha=.65)
        ax.scatter(x.ravel(),y.ravel(),z.ravel(),c=z.ravel(),s=16,cmap='viridis',vmin=0,vmax=100,depthshade=False)
        for r in rows:
            ci=r['f1_bootstrap_ci'] if metric=='f1' else r['whole_wilson_ci']
            ax.plot([r['coverage']*100]*2,[r['visits']]*2,np.array(ci)*100,color=BLUE,lw=.55,alpha=.55)
        front=pareto(z,xs,ns)
        for r in front:ax.scatter(r['coverage'],r['visits'],r['value'],s=42,facecolor='#e5ad50',edgecolor='#79531f',depthshade=False)
        ax.set(xlim=(0,100),ylim=(0,14),zlim=(0,100),xticks=[0,20,40,60,80,100],yticks=[0,2,5,8,11,14],zticks=[0,20,40,60,80,100])
        ax.set_xlabel('行走覆盖目标 (%)',labelpad=20);ax.set_ylabel('分散交互预算（次）',labelpad=16)
        ax.set_zlabel('实例位置 F1 (%)' if metric=='f1' else '全部中心达标房间 (%)',labelpad=9)
        ax.view_init(elev=25,azim=-55);ax.set_box_aspect((1.3,1.,.85),zoom=.9)
        for axis in [ax.xaxis,ax.yaxis,ax.zaxis]:axis.pane.set_fill(False)
        ca=fig.add_axes([.91,.32,.015,.43]);fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0,100),cmap='viridis'),cax=ca,ticks=[0,40,80,100])
        header(fig,title,'10,000 间生成单间 · 55,000 件家具 · 位置命中：同类一对一匹配，中心误差 ≤0.5 m')
        bound='；'.join(f"{r['coverage']:g}% / {r['visits']}次" for r in front) or '本图测点未达到80%'
        fig.text(.09,.16,'80%参考线的本图已测最小组合：'+bound,fontsize=7.5,color=GOLD)
        fig.text(.09,.11,'圆点为实测，连线仅引导阅读，竖线为95%区间；细网格与0–28次完整曲线另列。',fontsize=7.2)
        fig.text(.09,.06,'理想轨迹＋语义接触坐标，已知外框／数量／尺寸；本图不是原始IMU实验。',fontsize=7.2)
        save(fig,out,stem,[ax])
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,123/25.4));fig.subplots_adjust(left=.09,right=.90,bottom=.26,top=.77,wspace=.22)
    for ax,metric,title in zip(axes,['f1','whole_rate'],['a  平均实例位置 F1 (%)','b  全部中心达标（间）']):
        z=np.array([[100*look[x,n][metric] if (x,n) in look else np.nan for x in xs] for n in ns]);cmap=plt.cm.viridis.copy();cmap.set_bad('#edf0f3')
        im=ax.imshow(z,origin='lower',aspect='auto',vmin=0,vmax=100,cmap=cmap,interpolation='none')
        for j,n in enumerate(ns):
            for i,x in enumerate(xs):
                r=look.get((x,n));txt='—' if r is None else f"{100*r['f1']:.1f}" if metric=='f1' else str(r['whole_hits'])
                ax.text(i,j,txt,ha='center',va='center',fontsize=6.3,color='white' if r is not None and z[j,i]<65 else '#182a38')
        ax.set_xticks(range(len(xs)),[f'{v:g}' for v in xs]);ax.set_yticks(range(len(ns)),ns);ax.tick_params(length=0);ax.set_xlabel('覆盖目标 (%)')
        ax.set_title(title,loc='left',fontsize=8,pad=12)
    axes[0].set_ylabel('交互预算（次）');ca=fig.add_axes([.93,.26,.014,.51]);fig.colorbar(im,cax=ca,ticks=[0,40,80,100])
    header(fig,'恢复程度与整屋成功必须分开看','每格固定分母10,000间；未达到覆盖／交互预算的房间按失败计入。')
    fig.text(.09,.14,'横轴是明确标注的离散测点；灰格为未测组合。右图颜色为比例，格内为成功房间数。',fontsize=7.2)
    fig.text(.09,.08,'已知外框／数量／尺寸；位置端点不等于占地IoU。无平滑、无单调化、无成功房筛选。',fontsize=7.2)
    save(fig,out,'activity-heatmap',list(axes))
    a=np.load(package/'paired-arrays10000.npz');keys=[tuple(json.loads(k)) for k in a['keys']]
    fig,ax=plt.subplots(figsize=(183/25.4,110/25.4));fig.subplots_adjust(left=.12,right=.94,bottom=.25,top=.78)
    for method,color,label in [('legacy',GRAY,'原选择规则'),('outline',BLUE,'轮廓支持选择')]:
        v=np.sort(a['f1'][:,keys.index((method,1.,14,'dispersed'))]);ax.step(np.r_[0,v,1],np.r_[0,np.arange(1,len(v)+1)/len(v)*100,100],where='post',color=color,lw=1.8,label=label)
    ax.set(xlim=(0,1),ylim=(0,100),xlabel='单间家具位置 F1',ylabel='累计房间比例 (%)');ax.legend(loc='upper left',fontsize=8)
    header(fig,'平均90.43%背后，房间之间存在明显差异','100%覆盖／14次分散交互；中位F1=1，6470间全中，另有失败房间。')
    fig.text(.12,.12,'经验累积分布，每间房一个观测；未把10,000间的均值理解为每间房都达到相同精度。',fontsize=7.2)
    save(fig,out,'room-f1-cdf',[ax])


def thresholds(package,out):
    f=package/'thresholds10000.json'
    if not f.exists():return
    s=read(f)['cohorts']['all10000'];rows=s['full_coverage']['rows'];source_csv(out,'threshold-source',s['rows'])
    fig,ax=plt.subplots(figsize=(183/25.4,119/25.4));fig.subplots_adjust(left=.12,right=.94,bottom=.28,top=.78)
    for metric,ci,color,label in [('f1','f1_bootstrap_ci',BLUE,'平均位置F1'),('whole_rate','whole_wilson_ci',GOLD,'全部中心达标比例')]:
        x=np.array([r['visits'] for r in rows]);y=np.array([r[metric] for r in rows])*100;bounds=np.array([r[ci] for r in rows])*100
        ax.plot(x,y,'o-',color=color,ms=3,lw=1.4,label=label);ax.fill_between(x,bounds[:,0],bounds[:,1],color=color,alpha=.15,lw=0)
    ax.axhline(80,color=GRAY,lw=.8,ls='--');ax.set(xlim=(0,28),ylim=(0,102),xticks=range(0,29,2),xlabel='交互预算（每个整数均已测试）',ylabel='恢复程度 / 成功比例 (%)');ax.legend(loc='lower right',fontsize=8)
    header(fig,'走遍可达区域后，增加交互还能带来多少信息？','覆盖目标100%；10,000间；同一条路线、相同估计器，0–28次逐一测试。')
    first=s['full_coverage']['first_empirical_whole80'];msg=f"整屋80%首次实测达到：{first['visits']}次" if first else '整屋80%：在0–28次的已测范围内未达到'
    fig.text(.12,.16,msg,fontsize=8,color=GOLD)
    fig.text(.12,.10,'阴影：F1按房bootstrap95%区间，整屋比例Wilson95%区间；不强制曲线单调。',fontsize=7.2)
    save(fig,out,'full-coverage-counts',[ax])
    xs=[90,92,94,95,96,98,100];ns=[6,7,8,9,10,11,14];lookup={(round(r['coverage']*100,6),r['visits']):r for r in s['rows']}
    z=np.array([[100*lookup[x,n]['f1'] if (x,n) in lookup else np.nan for x in xs] for n in ns]);fig,ax=plt.subplots(figsize=(183/25.4,126/25.4));fig.subplots_adjust(left=.14,right=.86,bottom=.25,top=.78)
    cmap=plt.cm.viridis.copy();cmap.set_bad('#edf0f3');im=ax.imshow(z,origin='lower',aspect='auto',cmap=cmap,vmin=0,vmax=100,interpolation='none')
    for j,n in enumerate(ns):
        for i,x in enumerate(xs):
            value=z[j,i];ax.text(i,j,'—' if not np.isfinite(value) else f'{value:.2f}',ha='center',va='center',fontsize=7,color='white' if np.isfinite(value) and value<65 else '#182a38')
    ax.set(xticks=range(len(xs)),xticklabels=xs,yticks=range(len(ns)),yticklabels=ns,xlabel='覆盖目标 (%)',ylabel='交互预算（次）');ax.tick_params(length=0)
    ca=fig.add_axes([.90,.25,.014,.53]);fig.colorbar(im,cax=ca,ticks=[0,40,80,100]);header(fig,'80%位置F1附近：保留未测格，不填出一堵墙','每格10,000间；这里只放边界附近已测预算，数值为平均实例位置F1 (%)。')
    fig.text(.14,.14,'灰格为未测组合；不插值。完整0–28次的100%覆盖曲线另列。',fontsize=7.2)
    fig.text(.14,.08,'80%是展示参考线；F1越线不表示80%的房间全部家具定位成功。',fontsize=7.2)
    save(fig,out,'threshold-fine-zoom',[ax])


def raw_joint(package,out):
    control=read(package/'joint-watch-controls100.json');raw=read(package/'joint-confirmation100/summary.json');prefix=read(package/'joint-prefix100/summary.json')
    fine=package/'joint-prefix-fine100/summary.json'
    if fine.exists():
        extra=read(fine);by={r['scene']:r for r in extra['rows']}
        if len(by)!=100 or set(by)!={r['scene'] for r in prefix['rows']}:raise ValueError('Raw prefix room mismatch')
        prefix['cells']=sorted(prefix['cells']+extra['cells'],key=lambda r:r['fraction'])
        prefix['rows']=[{**r,'rows':r['rows']+by[r['scene']]['rows']} for r in prefix['rows']]
    arms=[('真实训练RF → 模拟',raw['summary']['joint_learned_watch']['all_hit'],GRAY),('模拟域手表规则',control['summary']['correct_watch']['whole_hits'],BLUE),('同一规则，手表错开10秒',control['summary']['clock_shift_10s']['whole_hits'],GOLD),('同一规则，去掉手表',control['summary']['watch_absent']['whole_hits'],GRAY),('真轨迹＋真动作（诊断）',raw['summary']['truth_pose_truth_actions']['all_hit'],'#bdc8ce')]
    fig,ax=plt.subplots(figsize=(183/25.4,124/25.4));fig.subplots_adjust(left=.36,right=.94,bottom=.27,top=.78)
    data=[]
    for j,(label,count,color) in enumerate(arms):
        rate,lo,hi=interval([True]*count+[False]*(100-count),True);ax.barh(j,rate*100,color=color,height=.53);ax.errorbar(rate*100,j,xerr=[[max(0.,100*(rate-lo))],[max(0.,100*(hi-rate))]],fmt='none',color='#253b4b',capsize=3,lw=.8);ax.text(104,j,f'{count}/100',va='center',fontsize=8)
        data.append({'arm':label,'hits':count,'n_rooms':100,'wilson_lo':lo,'wilson_hi':hi})
    ax.set(xlim=(0,120),xticks=[0,20,40,60,80,100],yticks=range(len(arms)),yticklabels=[r[0] for r in arms],xlabel='四件家具中心全部 ≤0.5 m (%)');ax.invert_yaxis()
    header(fig,'手表的柜门通道确实进入了原始输入链','100间四件家具房；手机六轴120Hz＋手表三轴加速度16.7Hz；理想共同模拟时钟。')
    fig.text(.09,.16,'85%为探索性的模拟域规则结果；预先冻结的真实训练RF迁移失败，不能把两者合并。',fontsize=7.2)
    fig.text(.09,.10,'已知近墙起点、固定姿态方向协议；前端为静止端点校正积分，条件强于万房几何实验。',fontsize=7.2)
    save(fig,out,'watch-controls',[ax]);source_csv(out,'watch-controls-source',data)
    fig,ax=plt.subplots(figsize=(183/25.4,126/25.4));fig.subplots_adjust(left=.12,right=.94,bottom=.29,top=.78)
    rows=prefix['cells'];x=np.array([r['fraction']*100 for r in rows]);whole=np.array([r['whole_rate']*100 for r in rows]);ci=np.array([r['whole_wilson_ci'] for r in rows])*100
    fv=np.array([[next(r for r in case['rows'] if r['fraction']==f)['f1'] for f in [r['fraction'] for r in rows]] for case in prefix['rows']]);fc=np.quantile(bootstrap_means(fv),[.025,.975],axis=0)*100
    ax.plot(x,whole,'o-',color=BLUE,lw=1.5,ms=4,label='全部中心达标比例');ax.fill_between(x,ci[:,0],ci[:,1],color=BLUE,alpha=.15,lw=0)
    ax.plot(x,fv.mean(axis=0)*100,'s-',color=GOLD,lw=1.2,ms=3,label='平均实例F1');ax.fill_between(x,fc[0],fc[1],color=GOLD,alpha=.12,lw=0)
    ax.axhline(80,ls='--',color=GRAY,lw=.8);ax.set(xlim=(48,102),ylim=(0,104),xticks=[50,60,65,70,75,80,90,100],xlabel='每条预定脚本已观察的比例 (%)',ylabel='恢复程度 / 成功比例 (%)');ax.legend(loc='lower right',fontsize=8)
    header(fig,'先截断原始手机和手表数据，再恢复布局','同一批100间，模拟域手表规则；每个预算都先删除未来事件行和手机交付行。')
    fig.text(.12,.18,'75%预算：84/100，95%区间75.6–89.9%；中位时长59.1秒、中位覆盖19.9%。',fontsize=7.2)
    fig.text(.12,.12,'这是本协议的首个80%实测格；中位数不能拼成“覆盖20%＋3类交互”的充分条件。',fontsize=7.2)
    fig.text(.12,.06,'静止端点到达后才回填该段位移；非连续在线定位。与万房几何曲面不共用阈值。',fontsize=7.2)
    save(fig,out,'raw-joint-prefix',[ax]);source_csv(out,'raw-prefix-source',rows)


def real_case(package,out):
    s=read(package/'real-joint-fresh/results.json');r=next(r for r in s['rows'] if r['shift_s']==0);truth={'bed':[1.17,1.96,2.695,4.045],'desk':[.05,1.05,.65,2.1],'cab':[.05,0,.65,1.05],'chair':[1.11,.92,1.55,1.36]}
    fig,ax=plt.subplots(figsize=(135/25.4,170/25.4));fig.subplots_adjust(left=.13,right=.92,bottom=.24,top=.83)
    ax.add_patch(Rectangle((0,0),2.84,4.045,fill=False,edgecolor='#253b4b',lw=1.5))
    for name,b in truth.items():ax.add_patch(Rectangle(b[:2],b[2]-b[0],b[3]-b[1],fill=False,ls='--',edgecolor=COLORS[name],lw=1.2))
    for name,b in r['prediction']['boxes'].items():
        ax.add_patch(Rectangle(b[:2],b[2]-b[0],b[3]-b[1],facecolor=COLORS[name],alpha=.20,edgecolor=COLORS[name],lw=1.4))
        centre=np.array([(b[0]+b[2])/2,(b[1]+b[3])/2]);labelpos=centre if name!='chair' else centre+[.65,.12]
        ax.text(*labelpos,LABELS[name],ha='center',va='center',fontsize=9,color='#253b4b')
        if name=='chair':ax.plot([b[2]+.03,labelpos[0]-.12],[centre[1],labelpos[1]],color=COLORS[name],lw=.7)
    a=np.load(package/'real-fresh/ronin-xy.npy');p=a[:,1:3];angle=np.radians(r['prediction']['rot_deg']);R=np.array([[np.cos(angle),np.sin(angle)],[-np.sin(angle),np.cos(angle)]]);q=(p-p[0])@R+np.array([.825,3.845]);ax.plot(q[:,0],q[:,1],color=BLUE,lw=.7,alpha=.6)
    ax.plot([.437,1.212],[4.045,4.045],color='white',lw=3);ax.plot(.825,3.845,'o',color='#202f3b',ms=4);ax.set(xlim=(-.15,3.),ylim=(-.1,4.25),xlabel='x (m)',ylabel='y (m)',aspect='equal')
    fig.text(.10,.945,'真实手机＋手表：原始数据重新跑通',fontsize=10,weight='bold');fig.text(.10,.90,'实线填色为预测，虚线为参考；柜门仅由手表识别。',fontsize=7.5)
    errors={m['class']:m['error_m'] for m in r['score']['matches']};fig.text(.10,.17,'中心误差：床 %.3f／桌 %.3f／柜 %.3f／椅 %.3f m'%tuple(errors[k] for k in ['bed','desk','cab','chair']),fontsize=7.2)
    fig.text(.10,.115,'同一房间的受控案例；手机RoNIN轨迹与008基线逐点相同。',fontsize=7.2)
    fig.text(.10,.06,'软件时钟对齐，物理同步未验；不是跨房留出，也不是精确占地恢复。',fontsize=7.2)
    save(fig,out,'real-joint-layout',[ax])


def run(package,audit_tools):
    package=Path(package);out=package/'figures';out.mkdir(exist_ok=True);sys.path.insert(0,str(audit_tools))
    plt.rcParams.update({'font.family':['Arial','Microsoft YaHei','SimSun'],'font.size':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False})
    geometric(package,out);thresholds(package,out);raw_joint(package,out);real_case(package,out)
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--audit-tools',required=True);a=p.parse_args();run(a.package,a.audit_tools)
