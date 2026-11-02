"""Claim-led paper plates from frozen aggregates and explicit display examples."""
from pathlib import Path
import sys,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle,Polygon
from matplotlib.colors import LinearSegmentedColormap

HERE=Path(__file__).resolve().parent
OUT=HERE/'figures';OUT.mkdir(exist_ok=True)
def require_matplotlib_panel_alignment(fig, **kwargs):
    axes=kwargs.get('axes',fig.axes)
    ids=kwargs.get('panel_ids',[str(i) for i in range(len(axes))])
    positions=dict(zip(ids,[a.get_position() for a in axes]))
    for axis_name,keys in [('row_groups',('y0','y1','width','height')),('column_groups',('x0','x1','width','height'))]:
        for group in kwargs.get(axis_name,[]):
            for key in keys:
                values=[getattr(positions[i],key) for i in group]
                assert max(values)-min(values)<1e-8, (group,key)
    Path(kwargs['json_out']).write_text(json.dumps({'backend':'matplotlib','comparable_groups_checked':True}),encoding='utf-8')
if Path('C:/Windows/Fonts/simsun.ttc').exists(): font_manager.fontManager.addfont('C:/Windows/Fonts/simsun.ttc')
plt.rcParams.update({'font.family':['SimSun','Times New Roman','Arial'],'font.size':9.5,'axes.labelsize':9,
 'xtick.labelsize':8.5,'ytick.labelsize':8.5,'legend.fontsize':8.5,'axes.spines.top':False,
 'axes.spines.right':False,'axes.linewidth':.65,'axes.unicode_minus':False,
 'svg.fonttype':'none','pdf.fonttype':42,'figure.facecolor':'white','savefig.facecolor':'white',
 'text.color':'#202B34','axes.labelcolor':'#202B34','xtick.color':'#202B34','ytick.color':'#202B34'})
BLUE='#347C9B';TEAL='#26877D';ORANGE='#CE8654';GRAY='#8797A2';INK='#202B34';LIGHT='#E8EFF1'
read=lambda n:json.loads((HERE/'source-data'/n).read_text(encoding='utf-8'))
sim=read('simulation-summary.json');old=read('existing-baselines-and-grid.json')
act=read('action-eight-summary.json');examples=read('figure-examples.json')
pilot=read('pilot-audit.json');display=read('pilot-display.json')

def panel(ax,letter,title='',x=-.16):
    ax.text(x,1.08,letter,transform=ax.transAxes,fontfamily='Times New Roman',fontsize=12,fontweight='bold',va='bottom')
    if title:ax.text(0,1.08,title,transform=ax.transAxes,fontsize=9.5,va='bottom')
def finish(fig,name,axes,ids,rows=(),cols=(),reason=''):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,axes=axes,panel_ids=ids,row_groups=list(rows),column_groups=list(cols),
      json_out=str(OUT/(name+'.alignment.json')),overlay_svg=str(OUT/(name+'.alignment.svg')),
      tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
    (OUT/(name+'.design.json')).write_bytes(json.dumps({'comparable_rows':rows,'comparable_columns':cols,'intentional_heterogeneity':reason,'invented_data':False},ensure_ascii=False,indent=2).encode('utf-8'))
    fig.savefig(OUT/(name+'.pdf'),dpi=600,metadata={'Creator':'Matplotlib; frozen source data'})
    fig.savefig(OUT/(name+'.svg'),dpi=600,metadata={'Creator':'Matplotlib; frozen source data'})
    fig.savefig(OUT/(name+'.png'),dpi=600,metadata={'Creator':'Matplotlib; frozen source data'})
    fig.savefig(OUT/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    plt.close(fig)

# 1. What is represented? Two audited aliases and their shared distance spectrum.
fig=plt.figure(figsize=(7.2,4.4))
aa=fig.add_axes([.07,.43,.23,.48]);bb=fig.add_axes([.385,.43,.23,.48]);cc=fig.add_axes([.75,.47,.22,.36])
for ax,h,letter,name in zip([aa,bb],examples['aliases'],['a','b'],['办公室 T0319','教室 T0448']):
    for room in h['rooms']:
        x0,y0,x1,y1=room['rect'];ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,ec=GRAY,lw=1))
    for obj in h['objects']:
        x0,y0,x1,y1=obj['rect'];ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fc=LIGHT,ec='#C0CBD0',lw=.5))
    p=np.array([s['xy'] for s in h['sites']]);ax.scatter(*p.T,s=22,c=TEAL,zorder=4)
    ax.set(xlim=(-.4,9.4),ylim=(-.6,11.5),xticks=[0,4,8],yticks=[0,5,10],xlabel='x（m）')
    ax.set_aspect('equal',adjustable='box');panel(ax,letter,name,x=-.20)
aa.set_ylabel('y（m）')
for h,col,ls in zip(examples['aliases'],[TEAL,ORANGE],['-','--']):
    p=np.array([s['xy'] for s in h['sites']]);i,j=np.triu_indices(len(p),1);d=np.sort(np.linalg.norm(p[i]-p[j],axis=1));d/=np.sqrt(np.mean(d*d))
    cc.plot(np.arange(1,len(d)+1),d,c=col,ls=ls,lw=1.5,label=h['house_id'])
cc.set(xlabel='排序后点对',ylabel='归一化距离',xticks=[1,5,10],ylim=(0,1.8));cc.legend(frameon=False,loc='lower right',fontsize=8)
panel(cc,'c','同谱，异身份',x=-.37)
dd=fig.add_axes([.04,.025,.94,.27]);dd.axis('off')
bands=[('合成身份','给定访问坐标 + 600候选','52.46% · 条件身份top-1',TEAL),
       ('真实活动','手机 + 手表 · 提示窗','八类活动判别 · 94.37%',BLUE),
       ('真实片段','固定雷达 / 两布局试点','自动片段与回访关系',GRAY)]
for y,(title,inp,end,col) in zip([.82,.48,.14],bands):
    dd.plot([0,.97],[y-.17,y-.17],c='#DDE5E9',lw=.6)
    dd.text(.01,y,title,c=col,va='center',fontsize=9.5,fontweight='bold');dd.text(.18,y,inp,va='center',fontsize=9)
    dd.annotate('',xy=(.65,y),xytext=(.59,y),arrowprops={'arrowstyle':'->','lw':.9,'color':col})
    dd.text(.68,y,end,va='center',fontsize=9)
dd.set(xlim=(0,1),ylim=(-.03,1))
finish(fig,'fig1-evidence-levels',[aa,bb,cc],['a','b','c'],rows=[['a','b']],reason='a/b share metric geometry and physical scale; c is a spectrum readout; bottom strip is evidence-scope annotation')

# 2. One frozen route explains the perturbation; all-house scores test its consequence.
fig=plt.figure(figsize=(7.2,4.9));mini=[]
view=examples['noise_example'];true=np.array(view['true_visits'])
colors=[TEAL,GRAY,ORANGE,BLUE];titles=['无扰动','共同平移','随机游走','独立扰动']
for i,(kind,title,col) in enumerate(zip(['none','common','brownian','iid'],titles,colors)):
    ax=fig.add_axes([.07+i*.235,.64,.18,.26]);mini.append(ax)
    obs=np.array(view['views'][kind]['observations']);cent=np.array(view['views'][kind]['group_representatives'])
    ax.scatter(*true.T,s=25,facecolors='none',edgecolors='#C1CCD1',lw=.8)
    ax.plot(*obs.T,c=col,lw=.55,alpha=.5);ax.scatter(*obs.T,s=4,c=col,alpha=.5)
    ax.scatter(*cent.T,s=21,c=col,edgecolors='white',lw=.5,zorder=4)
    ax.set(xlim=(-.4,8.6),ylim=(-2.7,4.5),xticks=[],yticks=[]);ax.set_aspect('equal',adjustable='box')
    for sp in ax.spines.values():sp.set_visible(False)
    ax.text(.5,1.16,title,transform=ax.transAxes,ha='center',fontsize=9)
    ax.plot([.2,2.2],[-1.8,-1.8],c=INK,lw=.9)
fig.text(.07,.59,'比例尺均为2 m；线与小点为逐访观测，大点为组代表',fontsize=8.2,c=GRAY)
mini[0].text(-.27,1.16,'a',transform=mini[0].transAxes,fontweight='bold',fontfamily='Times New Roman',fontsize=12)
a=fig.add_axes([.10,.15,.35,.33]);b=fig.add_axes([.61,.15,.35,.33])
for kind,label,c,m,ls in [('none','无扰动',TEAL,'o','-'),('common','共同平移',GRAY,'s','--'),('brownian','随机游走',ORANGE,'o','-'),('iid','独立扰动',BLUE,'^','-')]:
    vals=[next(r['value'] for r in old['grid'] if r['structure']==kind and r['visits']==n)*100 for n in [8,16,32]]
    a.plot([8,16,32],vals,c=c,marker=m,ls=ls,lw=1.3,ms=4,mfc='white' if kind=='common' else c,label=label)
a.set(xlim=(6,35),ylim=(0,100),xticks=[8,16,32],xlabel='已访问次数',ylabel='身份top-1（%）')
a.legend(loc='upper left',bbox_to_anchor=(-.04,1.02),ncol=2,frameon=False,fontsize=8.2,columnspacing=.7,handlelength=1)
raw=[x['original_top1']*100 for x in sim['noise']];soft=[x['soft_top1']*100 for x in sim['noise']]
for i,(r,s) in enumerate(zip(raw,soft)):
    b.plot([i-.13,i+.13],[r,s],c='#B5C3CA',lw=1.4)
    b.scatter(i-.13,r,s=28,c=TEAL,label='原规则' if i==0 else None)
    b.scatter(i+.13,s,s=26,c=ORANGE,marker='s',label='Ward软规则' if i==0 else None)
    b.text(i,r+6,f'{r:.2f}',ha='center',fontsize=8)
b.set(ylim=(0,100),xticks=range(4),xticklabels=['无扰动','共同\n平移','随机\n游走','独立\n扰动'],ylabel='32访身份top-1（%）')
b.legend(frameon=False,loc='upper right',fontsize=8)
panel(a,'b','访问积累',x=-.22);panel(b,'c','同分母规则复核',x=-.24)
finish(fig,'fig2-budget-and-error',mini+[a,b],['a1','a2','a3','a4','b','c'],rows=[['a1','a2','a3','a4'],['b','c']],reason='route illustration and aggregate score plots use different physical scales; only panels within their rows are comparable')

# 3. Ranking interaction plus the two distinct intermediate endpoints.
fig=plt.figure(figsize=(7.2,3.6));a=fig.add_axes([.19,.17,.37,.69]);b=fig.add_axes([.72,.60,.24,.25]);c=fig.add_axes([.72,.17,.24,.25])
names=['正确分组','完整连接','固定密度法','单连接','谱配置','HDBSCAN']
for i,row in enumerate(sim['methods']):
    y=5-i;h=row['hard']['value']*100;s=row['soft']['value']*100
    a.axhspan(y-.38,y+.38,color='#F3F6F7',zorder=0)
    a.plot([h,s],[y,y],c='#BCC8CE',lw=1.8)
    a.scatter(h,y,s=32,c=TEAL,zorder=3);a.scatter(s,y,s=29,c=ORANGE,marker='s',zorder=3)
    a.text(66,y,f'{h:.2f}',ha='right',va='center',fontsize=8.2)
    a.text(82,y,f'{s:.2f}',ha='right',va='center',fontsize=8.2)
a.text(66,5.65,'原规则',ha='right',fontsize=8,c=TEAL);a.text(82,5.65,'软规则',ha='right',fontsize=8,c=ORANGE)
a.set(yticks=range(6),yticklabels=names[::-1],xlim=(0,86),ylim=(-.6,6.1),xticks=[0,20,40,60],xlabel='固定分母身份top-1（%）');panel(a,'a','规则改变得分与排序',x=-.44)
qual=[100,1107/2400*100,494/2400*100];ys=np.arange(3)
b.barh(ys,qual,color=[GRAY,TEAL,BLUE],height=.45)
for i,v in enumerate(qual):b.text(min(v+2,66),i,['100.00%','46.13%','20.58%'][i],va='center',fontsize=8.2,color='white' if v>95 else INK)
b.set(yticks=ys,yticklabels=['正确','完整','密度'],xlim=(0,104),xticks=[0,50,100],xlabel='原规则真值资格（%）');b.invert_yaxis();panel(b,'b',x=-.35)
for i,row in enumerate(sim['methods']):
    x=row['pair_recall']['value']*100;y=row['pair_precision']['value']*100
    label_xy=[(101,86),(67,92),(51,95),(93,68),(93,41),(81,65)][i]
    c.scatter(x,y,c=TEAL if i<3 else ORANGE,s=24);c.annotate(str(i+1),(x,y),xytext=label_xy,textcoords='data',fontsize=8.2)
c.set(xlim=(45,105),ylim=(20,110),xticks=[50,75,100],yticks=[25,50,75,100],xlabel='配对召回（%）',ylabel='配对精度（%）');panel(c,'c',x=-.35)
finish(fig,'fig3-grouping-and-rule',[a,b,c],['a','b','c'],cols=[['b','c']],reason='a is a six-row hero; b/c share plot bounds, but measure different intermediate endpoints. Numeric point keys in c follow a top-to-bottom.')

# 4. Eight-class action task: the main success and the complete remaining failure.
fig=plt.figure(figsize=(7.2,5.4));a=fig.add_axes([.12,.47,.35,.43]);b=fig.add_axes([.66,.47,.27,.43])
cm=np.array(act['arms']['joint']['confusion']);norm=cm/cm.sum(axis=1)[:,None]
cmap=LinearSegmentedColormap.from_list('paper_teal',['#FFFFFF','#DBEFEC',TEAL])
a.imshow(norm,cmap=cmap,vmin=0,vmax=1,aspect='auto',interpolation='nearest')
for i in range(8):
    for j in range(8):
        if cm[i,j]:a.text(j,i,str(cm[i,j]),ha='center',va='center',fontsize=9,color='white' if norm[i,j]>.7 else INK)
a.set(xticks=range(8),xticklabels=act['label_names_zh'],yticks=range(8),yticklabels=act['label_names_zh'],xlabel='预测类别',ylabel='脚本声明类别');a.tick_params(axis='x',labelrotation=60)
panel(a,'a','联合67/71 · 94.37%',x=-.27)
rec=np.array([[x['recall']['value'] for x in act['arms'][arm]['per_class']] for arm in ['phone','watch','joint']]).T
b.imshow(rec,cmap=cmap,vmin=0,vmax=1,aspect='auto',interpolation='nearest')
for i in range(8):
    for j in range(3):b.text(j,i,f'{rec[i,j]*100:.0f}',ha='center',va='center',fontsize=8.5,color='white' if rec[i,j]>.7 else INK)
b.set(xticks=[0,1,2],xticklabels=['手机','手表','联合'],yticks=range(8),yticklabels=[]);b.tick_params(axis='y',length=0)
panel(b,'b','逐类召回（%）',x=-.27)
for ax in [a,b]:
    ax.set_xticks(np.arange(len(ax.get_xticks()))-.5,minor=True);ax.set_yticks(np.arange(8)-.5,minor=True);ax.grid(which='minor',c='white',lw=.8);ax.tick_params(which='minor',length=0)
c=fig.add_axes([.12,.10,.35,.19]);d=fig.add_axes([.62,.10,.35,.19])
cols=[TEAL,BLUE,GRAY]
for i,(arm,col) in enumerate(zip(['joint','phone','watch'],cols)):
    row=act['arms'][arm];v=row['accuracy']['value']*100;lo,hi=np.array(row['wilson95'])*100
    c.errorbar(v,2-i,xerr=[[v-lo],[hi-v]],fmt='o',c=col,capsize=2,lw=1.1,ms=5)
    c.text(102,2-i,f"{row['accuracy']['numerator']}/71",va='center',fontsize=8)
c.set(yticks=[0,1,2],yticklabels=['手表','手机','联合'],xlim=(70,101),ylim=(-.6,2.6),xticks=[70,80,90,100],xlabel='正确率 / Wilson 95%区间（%）');panel(c,'c','设备对照',x=-.27)
for arm,col,dx in [('phone',BLUE,-.08),('watch',GRAY,0),('joint',TEAL,.08)]:
    row=act['utility'][arm];ys=[row['raw']['value']*100,row['hz20']['value']*100]
    d.plot([0+dx,1+dx],ys,c=col,marker='o',ms=4,lw=1.2)
    d.text(-.12,ys[0],str(row['raw']['numerator']),ha='right',va='center',fontsize=8,c=col)
    label_y=ys[1]+({'phone':-1.4,'watch':1.0,'joint':0}[arm])
    d.text(1.15,label_y,str(row['hz20']['numerator'])+'/71',ha='left',va='center',fontsize=8,c=col)
d.set(xlim=(-.5,1.7),ylim=(80,101),xticks=[0,1],xticklabels=['原始','20 Hz手机'],yticks=[80,90,100],ylabel='八类正确率（%）');panel(d,'d','同模型效用检查',x=-.27)
finish(fig,'fig4-action-and-utility',[a,b,c,d],['a','b','c','d'],rows=[['c','d']],reason='a is an 8x8 confusion hero and b an 8x3 device-recall matrix; same row order/height, intentionally different widths. c/d share final plot area.')

# 5. Measured marker geometry, actual output sequence and the unverified identity gap.
fig=plt.figure(figsize=(7.2,5.6));a=fig.add_axes([.08,.68,.27,.24]);b=fig.add_axes([.52,.68,.43,.24])
d12=2.03;x0=(.91**2+d12**2-1.50**2)/(2*d12);y0=np.sqrt(.91**2-x0*x0);x3=(1.18**2+d12**2-1.02**2)/(2*d12);y3=-np.sqrt(1.18**2-x3*x3)
p=np.array([[x0,y0],[0,0],[d12,0],[x3,y3]])
for idx,col in [(0,TEAL),(3,ORANGE)]:
    q=p[[1,idx,2]];a.add_patch(Polygon(q,fc=col,alpha=.10,ec='none'));a.plot(*np.vstack([q,q[0]]).T,c=col,lw=1)
a.scatter(*p.T,c=[TEAL,GRAY,GRAY,ORANGE],s=28,zorder=4)
for i,off in enumerate([(0,7),(-8,-13),(8,-13),(0,-13)]):a.annotate('P'+str(i),p[i],xytext=off,textcoords='offset points',ha='center',fontsize=8)
a.text(1.015,-.08,'2.03 m',ha='center',va='top',fontsize=8.2)
a.set(xlim=(-.2,2.25),ylim=(-.75,1.05),xticks=[],yticks=[]);a.set_aspect('equal',adjustable='box');a.axis('off');panel(a,'a','两布局标记重建',x=-.16)
for rid,col in [('R1',TEAL),('R2',ORANGE)]:
    series=display['events'][rid]['series'];b.plot([x['s'] for x in series],[x['p_walk_phone'] for x in series],c=col,lw=.8,label=rid)
b.axhline(.3,c=GRAY,ls='--',lw=.7);b.set(xlim=(0,210),ylim=(0,1.05),xticks=[0,60,120,180],yticks=[0,.5,1],xlabel='提示零点后时间（s）',ylabel='P（行走）');b.legend(frameon=False,loc='lower right',bbox_to_anchor=(1.,1.08),ncol=2,fontsize=8.2);panel(b,'b','冻结手机门的完整输出',x=-.20)
c=fig.add_axes([.12,.38,.83,.19]);windows=np.array([[50,58],[68,76],[86,94],[104,112],[122,130],[140,148],[158,166],[176,184]])
for y,rid,col in [(2.2,'R1',TEAL),(.2,'R2',ORANGE)]:
    for st,en in windows:c.broken_barh([(st,en-st)],(y-.62,.40),facecolors='#D3DCE1',edgecolors='none')
    for e in display['events'][rid]['events']:c.broken_barh([(e['start'],e['end']-e['start'])],(y,.55),facecolors=col)
for i,(st,en) in enumerate(windows):c.text((st+en)/2,3.03,'ACBACBAC'[i],ha='center',fontsize=8)
c.set(xlim=(0,212),ylim=(-.6,3.4),yticks=[-.22,.48,1.78,2.48],yticklabels=['计划','R2','计划','R1'],xticks=[0,40,80,120,160,200],xlabel='提示零点后时间（s）');panel(c,'c','计划窗与完整自动区间',x=-.10)
d=fig.add_axes([.12,.07,.35,.19]);e=fig.add_axes([.62,.07,.35,.19])
vis=display['feature_distances']['visits'];order=sorted(range(16),key=lambda i:(vis[i]['declared_marker'],i));dm=np.array(display['feature_distances']['matrices']['joint'])[np.ix_(order,order)];np.fill_diagonal(dm,np.nan)
d.imshow(dm,cmap='cividis',interpolation='nearest',aspect='auto',vmin=0,vmax=25)
starts=[]
for mark in ['P0','P1','P2','P3']:
    where=[k for k,i in enumerate(order) if vis[i]['declared_marker']==mark];starts.append((np.mean(where),mark))
    if max(where)<15:d.axhline(max(where)+.5,c='white',lw=.6);d.axvline(max(where)+.5,c='white',lw=.6)
d.set(xticks=[x for x,s in starts],xticklabels=[s for x,s in starts],yticks=[x for x,s in starts],yticklabels=[s for x,s in starts]);panel(d,'d','联合特征距离（0–25）',x=-.27)
for i,row in enumerate(pilot['nn']):
    v=row['declared_marker_accuracy']['value']*100;e.scatter(i,v,s=40,c=[BLUE,GRAY,TEAL][i]);e.text(i,v+6,f"{row['declared_marker_accuracy']['numerator']}/16",ha='center',fontsize=8)
e.axhline(22.5,c=GRAY,ls='--',lw=.8);e.text(2.45,22.5,'22.5%',ha='right',va='bottom',fontsize=8.2)
e.set(xlim=(-.5,2.5),ylim=(0,70),xticks=[0,1,2],xticklabels=['手机','手表','联合'],yticks=[0,25,50],ylabel='声明标记近邻命中（%）');panel(e,'e','声明标记的特征可分性',x=-.27)
finish(fig,'fig5-real-pilot-boundaries',[a,b,c,d,e],['a','b','c','d','e'],rows=[['d','e']],reason='a is metric geometry, b probability, c full-width event strip; d/e share bounds but differ in modality. Declared marker labels and nominal timing are not independent spatial truth.')
print(json.dumps({'figures':5,'primary_action_task':'T3 eight-class','new_experiments':False,'new_model_fitting':False,'backend':'python'},ensure_ascii=False))
