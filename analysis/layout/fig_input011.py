"""Static011 figures. All32 records retained; oracle is explicitly labelled."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BLUE='#386c8f';GRAY='#909ca7';GOLD='#b47b27';PINK='#a56179'
COLORS={'bed':'#8faccd','desk':'#dfbd78','cab':'#a68fbd','chair':'#cb95a9'}
NAMES={'bed':'床','desk':'桌','cab':'储物','chair':'椅'}
ARMS=['old_raw_matched','new_raw','watch_absent','watch_clock10s','truth_pose_same_predicted_actions']
LABELS=['旧轨迹前端\n同一新解码器','新手机＋手表\n原始输入','新链去掉手表','手表错位10秒','真值位姿替换\n仅评价诊断']


def save(fig,out,name,axes):
    from audit_panel_alignment import require_matplotlib_panel_alignment
    fig.canvas.draw();require_matplotlib_panel_alignment(fig,axes=axes,json_out=out/(name+'.alignment.json'),strict=True)
    fig.savefig(out/(name+'.pdf'),facecolor='white')
    fig.savefig(out/(name+'.svg'),facecolor='white')
    fig.savefig(out/(name+'.png'),dpi=600,facecolor='white')
    plt.close(fig)


def header(fig,title,subtitle):
    fig.text(.10,.95,title,fontsize=10,weight='bold');fig.text(.10,.895,subtitle,fontsize=7,color='#4e5d68')


def comparison(p,out,audit):
    fig,ax=plt.subplots(figsize=(183/25.4,126/25.4));fig.subplots_adjust(left=.12,right=.95,bottom=.28,top=.79)
    for i,arm in enumerate(ARMS):
        r=audit['summary'][arm];y=100*r['rate'];lo,hi=np.array(r['wilson95'])*100
        ax.bar(i,y,.55,color=BLUE if arm=='new_raw' else GOLD if arm.startswith('truth') else GRAY)
        ax.errorbar(i,y,yerr=[[y-lo],[hi-y]],fmt='none',color='#203442',capsize=3,lw=.8)
        ax.text(i,hi+3,f"{r['whole']}/32",ha='center',fontsize=8)
    ax.set(ylim=(0,107),yticks=range(0,101,20),xticks=range(5),xticklabels=LABELS,ylabel='全部目标中心 ≤0.5 m 的录音 (%)');ax.tick_params(axis='x',labelsize=6.5)
    header(fig,'原始双设备 IMU 已驱动长链，但整屋恢复仍有明显损失','32条冻结新长记录 · 每条约10–15分钟 · 每房4–7件 · 同一候选上限128及方向/残差解码器')
    fig.text(.12,.17,'新链 vs 旧链：+18.75 pp；配对bootstrap95% [0,37.5]；McNemar p=0.109。',fontsize=7)
    fig.text(.12,.11,'手表仅提供柜门；去掉手表：−25.0 pp，配对p=0.0078。误差线为逐点Wilson95%。',fontsize=7)
    fig.text(.12,.05,'监督标定于同一合成生成族；强受控持法与家具先验；真值位姿臂不计入原始输入成绩。',fontsize=6.8)
    save(fig,out,'raw-input-controls',[ax])
    with (out/'raw-input-controls.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['arm','n','whole','rate','mean_f1','whole_iou0_5','wilson_low','wilson_high']);w.writeheader()
        for arm in ARMS:
            r=audit['summary'][arm];w.writerow({**{k:r[k] for k in ['n','whole','rate','mean_f1','whole_iou0_5']},'arm':arm,'wilson_low':r['wilson95'][0],'wilson_high':r['wilson95'][1]})


def trajectory(p,out,audit):
    fig,ax=plt.subplots(figsize=(183/25.4,116/25.4));fig.subplots_adjust(left=.12,right=.95,bottom=.26,top=.79)
    rows=audit['rows'];pairs=[]
    for scene in sorted({r['scene'] for r in rows}):
        a=next(r for r in rows if r['scene']==scene and r['arm']=='old_raw_matched');b=next(r for r in rows if r['scene']==scene and r['arm']=='new_raw');pairs.append([a['room_frame_ade_m'],b['room_frame_ade_m']]);ax.plot([0,1],pairs[-1],color='#b9c3c9',lw=.65,zorder=1)
    pairs=np.array(pairs);ax.scatter(np.zeros(len(pairs)),pairs[:,0],s=10,color=GRAY,zorder=2);ax.scatter(np.ones(len(pairs)),pairs[:,1],s=10,color=BLUE,zorder=2)
    for i in [0,1]:
        m=np.median(pairs[:,i]);ax.plot([i-.12,i+.12],[m,m],lw=2.5,color='#203442')
    ax.set(xlim=(-.5,1.6),ylim=(0,float(pairs.max())*1.08),xticks=[0,1],xticklabels=['旧轨迹＋同一新解码器','新轨迹＋同一新解码器'],ylabel='在所选房间坐标系下的全时段 ADE (m)')
    header(fig,'前端误差下降；保留每一条失败记录','每条线是一条配对长录音（n=32）；使用推断出的房间朝向，不用真值旋转做评价配准')
    fig.text(.12,.15,'相对初始规范ADE中位：0.403 → 0.178 m；所选房间坐标系：0.409 → 0.170 m。',fontsize=7)
    fig.text(.12,.09,'新增段位移监督模型＋同类未知接触点/面回访修正；全记录离线推断。',fontsize=7)
    fig.text(.12,.04,'未声称已修复RoNIN；本组旧前端是静止更新积分。跨真实房/自然持法尚未确认。',fontsize=6.8)
    save(fig,out,'trajectory-paired',[ax])


def example(p,out,native,audit):
    from . import multi_instance as M
    candidates=[r for r in audit['rows'] if r['arm']=='new_raw' and r['whole'] and r['n_objects']==7 and not next(q for q in audit['rows'] if q['scene']==r['scene'] and q['arm']=='old_raw_matched')['whole']]
    selected=sorted(candidates,key=lambda r:r['scene'])[0];name=selected['scene'];folder=p/'confirm32'/name;record=json.loads((folder/'results.json').read_text());scene=M.load_native(Path(native)/(name+'.json'));priors=json.loads((folder/'input/known-priors.json').read_text())
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,148/25.4));fig.subplots_adjust(left=.10,right=.95,bottom=.23,top=.80,wspace=.30)
    for ax,arm,title in zip(axes,['old_raw_matched','new_raw'],['a  旧轨迹输入','b  新轨迹输入']):
        r=next(r for r in record['rows'] if r['arm']==arm);est=np.load(folder/(arm+'-estimated.npz'));a=np.radians(r['prediction']['yaw_deg']);Q=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]]);path=(est['path']-est['path'][0])@Q.T+priors['start'];stride=max(1,len(path)//1500)
        ax.plot(path[::stride,0],path[::stride,1],color=BLUE,lw=.45,alpha=.6)
        for key,b in scene['gt'].items():ax.add_patch(Rectangle(b[:2],b[2]-b[0],b[3]-b[1],fill=False,ls='--',edgecolor='#203442',lw=.8,zorder=4))
        for key,b in r['prediction']['boxes'].items():
            ax.add_patch(Rectangle(b[:2],b[2]-b[0],b[3]-b[1],facecolor=COLORS[M.category(key)],edgecolor='#455767',lw=.6,alpha=.65))
        ax.add_patch(Rectangle((0,0),scene['W'],scene['L'],fill=False,lw=1.,color='#203442'));ax.set(xlim=(-.2,scene['W']+.2),ylim=(-.2,scene['L']+.2),xlabel='x (m)',ylabel='y (m)');ax.set_aspect('equal');ax.set_title(title+f"：{r['score']['tp']}/7",fontsize=8,loc='left',pad=10)
    header(fig,'七件房示例：原始 IMU 推断，不读取真值布局',name+' · 虚线仅作评价参考；实色为预测占地；两栏使用同一个方向/残差解码器')
    fig.legend([Rectangle((0,0),1,1,facecolor=COLORS[c]) for c in NAMES],[NAMES[c] for c in NAMES],ncol=4,loc='upper right',bbox_to_anchor=(.95,.875),fontsize=6.8)
    fig.text(.10,.14,'展示规则：新链全中、旧链未全中的七件房，按场景ID取首个；非随机代表性抽样。',fontsize=7)
    fig.text(.10,.085,'轨迹仅显示每约1/1500样点；推断与误差计算使用全时段。中心全中不代表轮廓全中。',fontsize=6.8)
    fig.text(.10,.04,'32条总体：新链17全中、9可行但错、6冲突/无提案；不排除失败房间。',fontsize=6.8)
    save(fig,out,'raw-seven-object-example',list(axes));(out/'example-provenance.json').write_text(json.dumps({'scene':name,'selection_rule':'First scene ID with7 objects, new all hit and old not all hit','display_decimation_only':True},indent=1))


def run(package,native,tools):
    sys.path.insert(0,str(tools));p=Path(package);out=p/'figures';out.mkdir(exist_ok=True);audit=json.loads((p/'confirm32/audit.json').read_text());plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','DejaVu Sans'],'font.size':7,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False});comparison(p,out,audit);trajectory(p,out,audit);example(p,out,native,audit)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--native',required=True);p.add_argument('--figure-tools',required=True);a=p.parse_args();run(a.package,a.native,a.figure_tools)
