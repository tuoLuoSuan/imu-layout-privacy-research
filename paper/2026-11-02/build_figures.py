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
    axes=kwargs.get('axes',fig.axes);ids=kwargs.get('panel_ids',[str(i) for i in range(len(axes))]);pos=dict(zip(ids,[a.get_position() for a in axes]))
    for name,keys in [('row_groups',('y0','y1','width','height')),('column_groups',('x0','x1','width','height'))]:
        for group in kwargs.get(name,[]):
            for key in keys:
                vals=[getattr(pos[i],key) for i in group]
                assert max(vals)-min(vals)<1e-8,(group,key)
    Path(kwargs['json_out']).write_text(json.dumps({'comparable_groups_checked':True}),encoding='utf-8')

if Path('C:/Windows/Fonts/simsun.ttc').exists():font_manager.fontManager.addfont('C:/Windows/Fonts/simsun.ttc')
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
ci={r['condition']:r for r in read('score-intervals.json')['rows']}
act['label_names_zh']=['柜门交互','静止','躺下（过渡）','躺卧（持续）','坐下','起立','直立/坐姿','行走']
def interval(name):
    r=ci[name];v=r['rate']['value']*100;lo,hi=np.array(r['house_bootstrap95'])*100
    return v, np.array([[v-lo],[hi-v]])


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
spectra=[]
for h in examples['aliases']:
    p=np.array([s['xy'] for s in h['sites']]);i,j=np.triu_indices(len(p),1);d=np.sort(np.linalg.norm(p[i]-p[j],axis=1));d/=np.sqrt(np.mean(d*d));spectra.append(d)
delta=spectra[0]-spectra[1]
cc.plot(np.arange(1,len(delta)+1),delta,c=TEAL,marker='o',ms=3,lw=1)
cc.axhline(0,c=GRAY,ls='--',lw=.6)
cc.set(xlabel='排序后点对',ylabel='归一化谱差',xticks=[1,5,10],ylim=(-.01,.01),yticks=[-.01,0,.01])
cc.text(.5,.83,f'最大绝对差 {max(abs(delta)):.1e}',transform=cc.transAxes,ha='center',fontsize=8)
panel(cc,'c','别名谱差为零',x=-.37)
dd=fig.add_axes([.10,.12,.84,.19]);hist=read('alias-size-histogram.json')['classes']
dd.bar([r['size'] for r in hist],[r['classes'] for r in hist],width=.58,color=[GRAY if r['size']==1 else TEAL for r in hist])
for r in hist:dd.text(r['size'],r['classes']-80 if r['size']==1 else r['classes']+9,str(r['classes']),ha='center',fontsize=8,color='white' if r['size']==1 else INK)
dd.set(xlim=(.4,9.6),ylim=(0,480),xticks=range(1,10),yticks=[0,200,400],xlabel='每个等价类中的身份数',ylabel='等价类数')
dd.text(.99,.85,'421个单例类；71个多成员类包含179个身份',transform=dd.transAxes,ha='right',fontsize=8.5)
panel(dd,'d',x=-.07)
finish(fig,'fig1-evidence-levels',[aa,bb,cc,dd],['a','b','c','d'],rows=[['a','b']],reason='a/b share metric geometry and physical scale; c is a zero-difference spectrum diagnostic; d is the complete class-size distribution')

# 2. One frozen route explains the perturbation; all-house scores test its consequence.
fig=plt.figure(figsize=(7.2,6.3));mini=[]
view=examples['noise_example'];true=np.array(view['true_visits'])
colors=[TEAL,GRAY,ORANGE,BLUE];titles=['无扰动','共同平移','随机游走','独立扰动']
for i,(kind,title,col) in enumerate(zip(['none','common','brownian','iid'],titles,colors)):
    ax=fig.add_axes([.07+i*.235,.76,.18,.20]);mini.append(ax)
    obs=np.array(view['views'][kind]['observations']);cent=np.array(view['views'][kind]['group_representatives'])
    ax.scatter(*true.T,s=25,facecolors='none',edgecolors='#C1CCD1',lw=.8)
    ax.plot(*obs.T,c=col,lw=.55,alpha=.5);ax.scatter(*obs.T,s=4,c=col,alpha=.5)
    ax.scatter(*cent.T,s=21,c=col,edgecolors='white',lw=.5,zorder=4)
    ax.set(xlim=(-.4,8.6),ylim=(-2.7,4.5),xticks=[],yticks=[]);ax.set_aspect('equal',adjustable='box')
    for sp in ax.spines.values():sp.set_visible(False)
    ax.text(.5,1.16,title,transform=ax.transAxes,ha='center',fontsize=9)
    ax.plot([.2,2.2],[-1.8,-1.8],c=INK,lw=.9)
fig.text(.07,.70,'比例尺均为2 m；线与小点为逐访观测，大点为组代表',fontsize=8.2,c=GRAY)
mini[0].text(-.27,1.16,'a',transform=mini[0].transAxes,fontweight='bold',fontfamily='Times New Roman',fontsize=12)
a=fig.add_axes([.10,.39,.35,.23]);b=fig.add_axes([.61,.39,.35,.23])
for kind,label,c,m,ls in [('none','无扰动',TEAL,'o','-'),('common','共同平移',GRAY,'s','--'),('brownian','随机游走',ORANGE,'o','-'),('iid','独立扰动',BLUE,'^','-')]:
    vals=[next(r['value'] for r in old['grid'] if r['structure']==kind and r['visits']==n)*100 for n in [8,16,32]]
    err=np.concatenate([interval(f'noise/{kind}/{n}')[1] for n in [8,16,32]],axis=1)
    a.errorbar([8,16,32],vals,yerr=err,c=c,marker=m,ls=ls,lw=1.1,ms=3.5,capsize=2,mfc='white' if kind=='common' else c,label=label)
a.set(xlim=(6,35),ylim=(0,100),xticks=[8,16,32],xlabel='已访问次数',ylabel='身份top-1（%）')
a.text(.03,.88,'无扰动＝共同平移',transform=a.transAxes,c=TEAL,fontsize=8.2);a.text(.05,.54,'随机游走',transform=a.transAxes,c=ORANGE,fontsize=8.2);a.text(.57,.12,'独立扰动',transform=a.transAxes,c=BLUE,fontsize=8.2)
raw=[x['original_top1']*100 for x in sim['noise']];soft=[x['soft_top1']*100 for x in sim['noise']]
for i,(r,s) in enumerate(zip(raw,soft)):
    b.plot([i-.13,i+.13],[r,s],c='#B5C3CA',lw=1.4)
    kind=['none','common','brownian','iid'][i]
    _,err=interval(f'noise/{kind}/32')
    b.errorbar(i-.13,r,yerr=err,fmt='o',ms=4,c=TEAL,capsize=2,label='原规则：95%区间' if i==0 else None)
    b.scatter(i+.13,s,s=26,c=ORANGE,marker='s',label='Ward软规则' if i==0 else None)
    b.text(i,r+8,f'{r:.2f}',ha='center',fontsize=8)
b.set(ylim=(0,100),xticks=range(4),xticklabels=['无扰动','共同\n平移','随机\n游走','独立\n扰动'],ylabel='32访身份top-1（%）')
b.legend(frameon=False,loc='upper right',fontsize=8)
panel(a,'b','访问积累',x=-.22);panel(b,'c','同分母规则复核',x=-.24)
d=fig.add_axes([.35,.105,.61,.16])
for y,name,label,col in [(2,'partial_metric','部分米制谱',GRAY),(1,'full_normalized','完整归一化谱',GRAY),(0,'partial_normalized','冻结部分归一化谱',TEAL)]:
    v,err=interval('strong/'+name);d.errorbar(v,y,xerr=err,fmt='o',c=col,capsize=2,ms=4,lw=1)
    d.text(v+6,y,f'{v:.2f}%',va='center',fontsize=8.5)
d.set(xlim=(0,100),ylim=(-.6,2.6),yticks=[0,1,2],yticklabels=['冻结部分归一化谱','完整归一化谱','部分米制谱'],xticks=[0,25,50,75,100],xlabel='32访身份top-1（%）· 同一随机游走条件、λ=0')
panel(d,'d','冻结主配置未超过两项强对照',x=-.50)
finish(fig,'fig2-budget-and-error',mini+[a,b,d],['a1','a2','a3','a4','b','c','d'],rows=[['a1','a2','a3','a4'],['b','c']],reason='a explains noise inputs, b/c share dimensions and house intervals; d compares three readings under the same 32-visit condition. Soft four-cell points have no saved per-house scores and are displayed as point estimates only.')

# 3. Ranking interaction plus the two distinct intermediate endpoints.
fig=plt.figure(figsize=(7.2,3.6));a=fig.add_axes([.19,.17,.37,.69]);b=fig.add_axes([.72,.60,.24,.25]);c=fig.add_axes([.72,.17,.24,.25])
names=['正确分组','完整连接','固定密度法','单连接','谱配置','HDBSCAN']
for i,row in enumerate(sim['methods']):
    y=5-i;h=row['hard']['value']*100;s=row['soft']['value']*100
    a.axhspan(y-.38,y+.38,color='#F3F6F7',zorder=0)
    a.plot([h,s],[y,y],c='#BCC8CE',lw=1.8)
    key=['oracle','complete','density','single','spectral','hdbscan'][i]
    a.errorbar(h,y,xerr=interval(f'group/{key}/hard')[1],fmt='o',ms=4,c=TEAL,capsize=2,zorder=3)
    a.errorbar(s,y,xerr=interval(f'group/{key}/soft')[1],fmt='s',ms=4,c=ORANGE,capsize=2,zorder=3)
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
a.set(xticks=range(8),xticklabels=[str(i) for i in range(1,9)],yticks=range(8),yticklabels=act['label_names_zh'],xlabel='预测类别（1–8与行序一致）');a.tick_params(axis='x',labelrotation=0)
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
    c.text(5,2-i,f"{row['accuracy']['numerator']}/71",va='center',fontsize=8)
c.set(yticks=[0,1,2],yticklabels=['手表','手机','联合'],xlim=(0,105),ylim=(-.6,2.6),xticks=[0,25,50,75,100],xlabel='正确率 / Wilson 95%区间（%）');panel(c,'c','设备对照',x=-.27)
for i,arm in enumerate(['phone','watch','joint']):
    row=act['utility'][arm];raw=row['raw']['value']*100;down=row['hz20']['value']*100
    d.plot([i-.10,i+.10],[raw,down],c='#B5C3CA',lw=1)
    d.scatter(i-.10,raw,c=GRAY,s=21,label='原始' if i==0 else None)
    d.scatter(i+.10,down,c=TEAL,marker='s',s=21,label='20 Hz手机' if i==0 else None)
    d.text(i,min(raw,down)-15,f"{row['raw']['numerator']}→{row['hz20']['numerator']}",ha='center',fontsize=8)
d.set(xlim=(-.5,2.5),ylim=(0,105),xticks=[0,1,2],xticklabels=['手机','手表','联合'],yticks=[0,25,50,75,100],ylabel='八类正确率（%）')
d.legend(frameon=False,loc='lower center',fontsize=8,ncol=2,handlelength=.8,columnspacing=.7)
panel(d,'d','同模型效用 · 联合p=0.5',x=-.27)
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
c.set(xlim=(0,212),ylim=(-.6,3.4),yticks=[-.22,.48,1.78,2.48],yticklabels=['计划','R2','计划','R1'],xticks=[0,40,80,120,160,200],xlabel='提示零点后时间（s）');panel(c,'c','计划窗与自动区间：R1 87.50%，R2 89.84%',x=-.10)
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
e.set(xlim=(-.5,2.5),ylim=(0,100),xticks=[0,1,2],xticklabels=['手机','手表','联合'],yticks=[0,25,50,75,100],ylabel='声明标记近邻命中（%）');panel(e,'e','声明标记的特征可分性',x=-.27)
finish(fig,'fig5-real-pilot-boundaries',[a,b,c,d,e],['a','b','c','d','e'],rows=[['d','e']],reason='a is metric geometry, b probability, c full-width event strip; d/e share bounds but differ in modality. Declared marker labels and nominal timing are not independent spatial truth.')

# 0. Separate evidence lanes, with no implied measured end-to-end edge.
fig=plt.figure(figsize=(7.2,3.5));a=fig.add_axes([.02,.02,.96,.94]);a.axis('off')
for x,title in [(.145,'观测输入'),(.49,'处理'),(.835,'评价属性')]:a.text(x,.96,title,ha='center',fontsize=10,fontweight='bold')
lanes=[(.73,BLUE,['手机 + 手表原始记录','冻结窗特征与分类器','八类动作 · 67/71']),(.45,GRAY,['雷达 / 两布局真实记录','候选与访问片段分析','回访关系 / 计划窗覆盖']),(.17,TEAL,['给定访问坐标 + 指定噪声','分组 → 距离谱 → 闭库匹配','600身份 · top-1 52.46%'])]
for y,col,labels in lanes:
    for x,txt in zip([.015,.36,.705],labels):
        a.add_patch(Rectangle((x,y-.085),.27,.17,fc=col+'14',ec=col,lw=.9))
        a.text(x+.135,y,txt,ha='center',va='center',fontsize=8.5)
    for x in [.285,.63]:a.annotate('',xy=(x+.07,y),xytext=(x+.01,y),arrowprops={'arrowstyle':'->','color':col,'lw':1})
a.text(.5,-.025,'三行分别提供模块与条件测量；第三行坐标并非前两行端到端生成',ha='center',fontsize=8.5,color=INK)
a.set(xlim=(0,1),ylim=(-.06,1.02))
finish(fig,'fig0-threat-and-evidence',[a],['scope'],reason='Three evidence lanes are intentionally disconnected; radar is a reference module, not an inertial attacker sensor. Synthetic score assumes correct grouping and lambda 0.0003.')

# 6. Every reported setting, including event-count and coverage variation.
sens=read('formal-gate-sensitivity.json');fig=plt.figure(figsize=(7.2,4.1));axes=[];ids=[]
for row,rid in enumerate(['R1','R2']):
    for col,gap in enumerate([0.,.5]):
        ax=fig.add_axes([.13+col*.46,.59-row*.44,.34,.27]);axes.append(ax);ids.append(rid+str(gap))
        arr=np.array([[next(r[rid]['mean_frac'] for r in sens if r['thr']==t and r['min_dwell']==d and r['merge_gap']==gap) for t in [.3,.4,.5,.6,.7]] for d in [2,3,4]])
        ax.imshow(arr,cmap=LinearSegmentedColormap.from_list('coverage',['#FFFFFF','#D4E7E3',TEAL]),vmin=.6,vmax=1,aspect='auto')
        for ii in range(3):
            for jj in range(5):ax.text(jj,ii,f'{arr[ii,jj]*100:.1f}',ha='center',va='center',fontsize=9,color=INK)
        if gap==0:ax.add_patch(Rectangle((-.47,1.53),.94,.94,fill=False,ec=ORANGE,lw=2))
        ax.set(xticks=range(5),xticklabels=['0.3','0.4','0.5','0.6','0.7'],yticks=range(3),yticklabels=['2','3','4'],xlabel='行走概率阈值',ylabel='最短时长（s）')
        panel(ax,chr(97+row*2+col),f'{rid} · 合并间隙{gap:g} s',x=-.25)
finish(fig,'fig6-event-gate-sensitivity',axes,ids,rows=[[ids[0],ids[1]],[ids[2],ids[3]]],cols=[[ids[0],ids[2]],[ids[1],ids[3]]],reason='All 30 settings are shown for each record; text and colour are rounded mean planned-window coverage, not detection accuracy. Orange outline is the development-selected conservative tie-break, not a held-out optimum.')

print(json.dumps({'figures':7,'primary_action_task':'T3 eight-class','new_experiments':False,'new_model_fitting':False,'backend':'python'},ensure_ascii=False))
