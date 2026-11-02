"""Evidence-led manuscript figures. Inputs are frozen aggregates, not raw trials.

Usage: python build_figures.py --language zh (or en)
"""
from pathlib import Path
import argparse,json,math,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle,Circle,Ellipse,Polygon,PathPatch,FancyBboxPatch
from matplotlib.path import Path as MPath
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import PercentFormatter

HERE=Path(__file__).resolve().parent
def require_matplotlib_panel_alignment(fig, **kwargs):
    axes=kwargs.get('axes',fig.axes);ids=kwargs.get('panel_ids',[str(i) for i in range(len(axes))]);pos=dict(zip(ids,[a.get_position() for a in axes]));width,height=fig.get_size_inches()*72
    for name,keys,scale in [('row_groups',('y0','y1','height'),height),('column_groups',('x0','x1','width'),width)]:
        for group in kwargs.get(name,[]):
            for key in keys:
                vals=[getattr(pos[i],key)*scale for i in group]
                assert max(vals)-min(vals)<=1.5,(group,key)
    Path(kwargs['json_out']).write_text(json.dumps({'comparable_groups_checked':True,'tolerance_pt':1.5}),encoding='utf-8')

parser=argparse.ArgumentParser();parser.add_argument('--language',choices=['zh','en'],default='zh');parser.add_argument('--only',nargs='*',help='Optional figure stems to export');args=parser.parse_args()
EN=args.language=='en'
OUT=HERE/('figures-en' if EN else 'figures');OUT.mkdir(exist_ok=True)
def T(zh,en):return en if EN else zh
def read(n):return json.loads((HERE/'source-data'/n).read_text('utf-8'))
sim=read('simulation-summary.json');act=read('action-eight-summary.json');ex=read('figure-examples.json');pilot=read('pilot-display.json')
ci={r['condition']:r for r in read('score-intervals.json')['rows']}
station=read('station-permutation.json')
INK='#172D3A';TEAL='#087F83';BLUE='#467EAC';AMBER='#D7854F';GRAY='#7A8C9A';PALE='#EDF1F4';GRID='#D9E2E8'
if Path('C:/Windows/Fonts/simsun.ttc').exists():font_manager.fontManager.addfont('C:/Windows/Fonts/simsun.ttc')
plt.rcParams.update({'font.family':['Arial','SimSun'],'font.size':9,
 'axes.labelsize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':7.8,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,'axes.unicode_minus':False,
 'text.color':INK,'axes.labelcolor':INK,'xtick.color':INK,'ytick.color':INK,
 'figure.facecolor':'white','savefig.facecolor':'white','pdf.fonttype':42,'svg.fonttype':'none'})
def letter(ax,s,x=-.13,y=1.055):ax.text(x,y,s,transform=ax.transAxes,fontfamily='Arial',fontweight='bold',fontsize=10,va='bottom')
def lightgrid(ax,axis='y'):ax.grid(axis=axis,color=GRID,lw=.45,zorder=0);ax.set_axisbelow(True)
def getci(k):
 r=ci[k];v=r['rate']['value']*100;lo,hi=np.array(r['house_bootstrap95'])*100
 return v,np.array([[v-lo],[hi-v]])
def finish(fig,name,axes,ids,rows=(),cols=(),why=''):
 if args.only and name not in args.only:plt.close(fig);return
 fig.canvas.draw()
 require_matplotlib_panel_alignment(fig,axes=axes,panel_ids=ids,row_groups=list(rows),column_groups=list(cols),json_out=str(OUT/(name+'.alignment.json')),overlay_svg=str(OUT/(name+'.alignment.svg')),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(OUT/(name+'.pdf'),dpi=600)
 fig.savefig(OUT/(name+'.svg'),dpi=600)
 fig.savefig(OUT/(name+'.png'),dpi=600)
 fig.savefig(OUT/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
 (OUT/(name+'.design.json')).write_bytes((json.dumps(dict(language=args.language,comparable_rows=rows,comparable_columns=cols,exception_reason=why,scoring_recomputed=False),ensure_ascii=False,indent=2)+'\n').encode())
 plt.close(fig)

# Figure 1: device, evidence, representation and endpoint have distinct forms.
fig=plt.figure(figsize=(7.2,3.35));ax=fig.add_axes([.015,.035,.97,.93]);ax.axis('off');ax.set(xlim=(0,1),ylim=(0,1))
ax.add_patch(FancyBboxPatch((.005,.13),.255,.78,boxstyle='round,pad=.007,rounding_size=.025',facecolor='#F0F5FA',edgecolor='none'))
ax.add_patch(FancyBboxPatch((.295,.32),.695,.59,boxstyle='round,pad=.007,rounding_size=.025',facecolor='#EDF6F3',edgecolor='none'))
ax.text(.025,.94,T('实测模块','Measured modules'),fontsize=9.5,fontweight='bold');ax.text(.315,.94,T('给定坐标的条件身份测量','Conditional identity from supplied coordinates'),fontsize=9.5,fontweight='bold')
def roundbox(x,y,w,h,r,fc,ec=INK,lw=.8):
 box=FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0,rounding_size={r}',facecolor=fc,edgecolor=ec,lw=lw);ax.add_patch(box);return box
# Device silhouettes are vector schematics, with no invented sensor traces.
roundbox(.035,.43,.083,.37,.012,'#C7D1DA',GRAY,.7);roundbox(.031,.435,.083,.37,.012,'#182B3B',INK,.8);roundbox(.036,.447,.073,.345,.009,'#FAFCFD','#8897A4',.4)
roundbox(.059,.771,.026,.006,.003,'#93A4B1','none',0);ax.add_patch(Rectangle((.028,.69),.003,.055,fc=GRAY,ec='none'));ax.add_patch(Rectangle((.028,.62),.003,.035,fc=GRAY,ec='none'))
roundbox(.154,.405,.046,.417,.014,'#CFDAE1',GRAY,.6);roundbox(.145,.535,.064,.165,.014,'#B2C2CE',GRAY,.65);roundbox(.142,.542,.064,.165,.014,'#263B4B',INK,.7);roundbox(.147,.554,.054,.141,.010,'#FAFCFD','#8BA0AC',.45);ax.add_patch(Rectangle((.207,.605),.006,.026,fc=GRAY,ec='none'))
for yy in [.437,.462,.487]:roundbox(.174,yy,.006,.008,.002,'#97A9B7','none',0)
for x,y,w,h,col in [(.073,.603,.022,.052,BLUE),(.174,.616,.016,.035,AMBER)]:
 ax.annotate('',xy=(x+w,y),xytext=(x,y),arrowprops=dict(arrowstyle='-|>',lw=.65,color=col,mutation_scale=4));ax.annotate('',xy=(x,y+h),xytext=(x,y),arrowprops=dict(arrowstyle='-|>',lw=.65,color=col,mutation_scale=4));ax.plot([x,x-w*.6],[y,y-h*.5],c=col,lw=.65)
ax.text(.073,.48,'IMU',ha='center',fontsize=7,c=BLUE);ax.text(.174,.565,'IMU',ha='center',fontsize=6.3,c=AMBER)
ax.text(.073,.367,T('手机','Phone'),ha='center',fontsize=8.3);ax.text(.176,.367,T('手表','Watch'),ha='center',fontsize=8.3)
ax.text(.025,.255,T('八类活动','Eight-class activity'),fontsize=8.2,c=BLUE);ax.text(.235,.255,'67/71',ha='right',fontsize=10,fontweight='bold',c=BLUE)
# Radar is a separate measured module, not a phone/watch input channel.
ax.add_patch(Rectangle((.037,.147),.043,.032,fc='#BDC9D1',ec=GRAY,lw=.6))
ax.add_patch(Ellipse((.0585,.178),.043,.014,fc='#334F5C',ec=INK,lw=.55))
ax.add_patch(Ellipse((.0585,.181),.027,.007,fc='#8FC0BE',ec='none'))
ax.plot([.0585,.0585],[.147,.126],c=GRAY,lw=.7)
ax.plot([.045,.072],[.126,.126],c=GRAY,lw=.7)
ax.text(.098,.152,T('雷达 · 8片段','Radar · 8 episodes'),fontsize=8.0,c=GRAY)
v=ex['noise_example']['views']['brownian'];pts=np.array(v['observations']);cent=np.array(v['group_representatives']);q=(pts-pts.min(axis=0))/np.ptp(pts,axis=0)
ax.plot(.33+q[:,0]*.115,.47+q[:,1]*.27,c=BLUE,lw=.4,alpha=.35);ax.scatter(.33+q[:,0]*.115,.47+q[:,1]*.27,s=6,c=BLUE,edgecolor='white',lw=.2)
ax.text(.39,.82,T('访问坐标','Visit coordinates'),ha='center',fontsize=8.4);ax.text(.39,.375,'32 '+T('次访问','visits'),ha='center',fontsize=7.8)
g=(cent-cent.min(axis=0))/np.maximum(np.ptp(cent,axis=0),1e-9);gx=.535+g[:,0]*.09;gy=.49+g[:,1]*.23
for i,j in zip(*np.triu_indices(len(g),1)):ax.plot([gx[i],gx[j]],[gy[i],gy[j]],c='#94B6B3',lw=.5,alpha=.65)
ax.scatter(gx,gy,s=20,c=TEAL,edgecolor='white',lw=.6,zorder=3);ax.text(.58,.82,T('组代表几何','Group geometry'),ha='center',fontsize=8.4)
ix,iy=np.triu_indices(len(cent),1);ds=np.sort(np.linalg.norm(cent[ix]-cent[iy],axis=1));ds/=np.sqrt(np.mean(ds*ds));z=(ds-ds.min())/np.ptp(ds)
ax.plot(np.linspace(.70,.785,len(ds)),.49+z*.23,c=TEAL,lw=1.4);ax.scatter(np.linspace(.70,.785,len(ds)),.49+z*.23,s=6,c=TEAL,edgecolor='white',lw=.2);ax.text(.742,.82,T('归一化距离谱','Normalized spectrum'),ha='center',fontsize=8.3)
for x0,label in [(.457,T('分组','Group')),(.636,T('距离','Distances')),(.797,T('排名','Rank'))]:
 ax.annotate('',xy=(x0+.058,.60),xytext=(x0,.60),arrowprops=dict(arrowstyle='->',lw=.95,color=INK));ax.text(x0+.029,.68,label,ha='center',fontsize=7.8)
for shift in [.014,.007,0]:roundbox(.877+shift,.465+shift,.085,.26,.004,'white','#A2B8C2',.5)
for yy,txt in zip([.68,.63,.58,.505],['1','2','…','600']):ax.text(.918,yy,txt,ha='center',fontsize=7.7)
ax.text(.919,.82,T('候选目录','Catalog'),ha='center',fontsize=8.4)
ax.text(.315,.21,T('可见','Visible'),c=TEAL,fontweight='bold',fontsize=8.3);ax.text(.425,.21,T('二维坐标 · 顺序 · 600候选','2D coordinates · order · 600 candidates'),fontsize=8.2)
ax.text(.315,.105,T('自动臂未知','Auto-arm lacks'),c=GRAY,fontweight='bold',fontsize=8.3);ax.text(.45,.105,T('原点 · 绝对朝向 · 真实分区','Origin · absolute heading · true partition'),fontsize=8.2)
finish(fig,'fig1-threat-model',[ax],['scope'],why='Single conceptual canvas, with separately scoped measured and coordinate-given lanes. Phone, watch and radar silhouettes are original vector schematics. Frozen coordinates generate point, geometry and spectrum glyphs. Numerical identity outcomes are reported in the quantitative figures rather than a suspended schematic readout.')

# Figure 2: aliases are an instance; the full distribution carries the scale.
fig=plt.figure(figsize=(7.2,2.9));a=fig.add_axes([.065,.17,.23,.72]);b=fig.add_axes([.375,.17,.23,.72]);c=fig.add_axes([.685,.17,.23,.72])
for aa,h,s in zip([a,b],ex['aliases'],['a','b']):
 for room in h['rooms']:
  x0,y0,x1,y1=room['rect'];aa.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,ec=GRAY,lw=.8))
 for item in h['objects']:
  x0,y0,x1,y1=item['rect'];aa.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fc=PALE,ec='#CDD9DF',lw=.5))
 p=np.array([s['xy'] for s in h['sites']]);aa.scatter(*p.T,c=TEAL,s=24,edgecolor='white',lw=.6,zorder=4)
 aa.set(xlim=(-.4,9.4),ylim=(-.6,11.5),xticks=[0,4,8],yticks=[0,5,10],xlabel='x (m)');aa.set_aspect('equal',adjustable='box');letter(aa,s,x=-.22)
a.set_ylabel('y (m)')
hist=read('alias-size-histogram.json')['classes'];freq={r['size']:r['classes'] for r in hist}
for k in range(1,10):
 n=freq.get(k,0)
 if n:c.scatter(k,n,color=GRAY if k==1 else TEAL,s=24,zorder=3);c.text(k,n*1.30,str(n),ha='center',fontsize=8)
 else:c.text(k,.44,'0',ha='center',fontsize=7.5,color=GRAY)
c.set_yscale('log');c.set(xlim=(.4,9.6),ylim=(.35,1100),xticks=[1,3,5,7,9],yticks=[1,10,100],yticklabels=['1','10','100'],xlabel=T('类内身份数','Identities per class'),ylabel=T('等价类数（对数）','Classes (log scale)'));letter(c,'c',x=-.22)
fig.canvas.draw();box=a.get_position();c.set_position([.685,box.y0,.23,box.height])
finish(fig,'fig2-representation',[a,b,c],['a','b','c'],rows=[['a','b','c']],why='a/b share physical scale. c uses log-count point positions, not bar lengths; empty sizes 7/8 are annotated 0 below the positive-count region. All three final plot areas have the same width and height.')

# Figure 3: compact example/control/benchmark chain; bands expose uncertainty.
fig=plt.figure(figsize=(7.2,4.45));mini=[]
view=ex['noise_example'];true=np.array(view['true_visits']);kinds=['none','common','brownian','iid'];colors=[TEAL,GRAY,AMBER,BLUE]
allp=np.vstack([true]+[np.array(view['views'][k]['observations']) for k in kinds]);lo=allp.min(axis=0)-.6;hi=allp.max(axis=0)+.6
for j,(kind,col) in enumerate(zip(kinds,colors)):
 aa=fig.add_axes([.075+(j%2)*.18,.76-(j//2)*.18,.15,.145]);mini.append(aa)
 obs=np.array(view['views'][kind]['observations']);cent=np.array(view['views'][kind]['group_representatives'])
 aa.scatter(*true.T,s=17,facecolor='none',edgecolor='#B7C6CF',lw=.6);aa.plot(*obs.T,c=col,lw=.45,alpha=.5);aa.scatter(*obs.T,s=3,c=col,alpha=.5);aa.scatter(*cent.T,s=16,c=col,edgecolor='white',lw=.4,zorder=4)
 aa.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),xticks=[],yticks=[]);aa.set_aspect('equal',adjustable='box');aa.axis('off');aa.text(.01,.94,'a'+str(j+1),transform=aa.transAxes,fontsize=8,fontweight='bold',fontfamily='Arial')
 aa.plot([lo[0]+.3,lo[0]+2.3],[lo[1]+.4,lo[1]+.4],c=INK,lw=.8)
b=fig.add_axes([.59,.61,.36,.29]);c=fig.add_axes([.10,.17,.34,.28]);d=fig.add_axes([.66,.17,.29,.28])
for kind,label,col,marker in [('none',T('无扰动/平移','None / common'),TEAL,'o'),('brownian',T('随机游走','Brownian'),AMBER,'s'),('iid',T('独立扰动','IID'),BLUE,'^')]:
 rr=[ci[f'noise/{kind}/{n}'] for n in [8,16,32]];v=np.array([r['rate']['value'] for r in rr])*100;l=np.array([r['house_bootstrap95'] for r in rr])*100
 b.fill_between([8,16,32],l[:,0],l[:,1],color=col,alpha=.23,lw=0);b.errorbar([8,16,32],v,yerr=np.array([v-l[:,0],l[:,1]-v]),c=col,marker=marker,ms=3.5,lw=1.1,capsize=2,label=label)
b.set(xlim=(6,34),ylim=(0,105),xticks=[8,16,32],yticks=[0,25,50,75,100],xlabel=T('访问次数','Visits'),ylabel=T('身份top-1（%）','Identity top-1 (%)'));lightgrid(b);b.legend(loc='lower center',bbox_to_anchor=(.5,1.04),ncol=3,frameon=False,fontsize=7.2,columnspacing=.7,handlelength=1.1);letter(b,'b',x=-.19)
for i,r in enumerate(sim['noise']):
 h=r['original_top1']*100;s=r['soft_top1']*100
 c.plot([i-.13,i+.13],[h,s],c='#B9C8D0',lw=1.3);c.errorbar(i-.13,h,yerr=getci(f'noise/{kinds[i]}/32')[1],fmt='o',ms=4,c=TEAL,capsize=2,label=T('原规则','Original') if i==0 else None);c.scatter(i+.13,s,c=AMBER,marker='s',s=18,label=T('Ward软规则','Ward-soft') if i==0 else None)
 c.text(i,max(h,s)+10,f'{h:.1f}/{s:.1f}',ha='center',fontsize=7.6,c=INK)
c.set(xlim=(-.45,3.45),ylim=(0,110),xticks=range(4),xticklabels=[T('无扰动','None'),T('共同平移','Common'),T('随机游走','Brownian'),T('独立扰动','IID')],yticks=[0,25,50,75,100],ylabel=T('32访身份top-1（%）','32-visit top-1 (%)'));c.tick_params(axis='x',labelsize=7.5);c.legend(loc='upper center',bbox_to_anchor=(.5,1.19),frameon=False,ncol=2,fontsize=7.3,handlelength=.8,columnspacing=.7);letter(c,'c',x=-.20)
for yy,name,label,col in [(2,'partial_metric',T('部分米制谱','Metric subset'),GRAY),(1,'full_normalized',T('完整归一谱','Full normalized'),GRAY),(0,'partial_normalized',T('冻结子谱','Frozen subset'),TEAL)]:
 v,e=getci('strong/'+name);d.errorbar(v,yy,xerr=e,fmt='o',c=col,ms=4,capsize=2,lw=1);d.text(v+5,yy,f'{v:.1f}',va='center',fontsize=8)
d.set(xlim=(0,75),ylim=(-.6,2.6),xticks=[0,25,50,75],yticks=[0,1,2],yticklabels=[T('冻结子谱','Frozen subset'),T('完整归一谱','Full normalized'),T('部分米制谱','Metric subset')],xlabel=T('身份top-1（%）','Identity top-1 (%)'));letter(d,'d',x=-.42)
finish(fig,'fig3-noise-and-budget',mini+[b,c,d],['a1','a2','a3','a4','b','c','d'],rows=[['a1','a2'],['a3','a4'],['c','d']],cols=[['a1','a3'],['a2','a4']],why='a1-a4 are equal-scale illustration insets; b/c/d use different variables. c/d have different spans deliberately: c needs four conditions, d needs three long row labels. Only bottom/top edges and heights are comparable; unequal widths are intentional.')

# Figure 4: paired rule outcomes; qualification and fidelity remain separate.
fig=plt.figure(figsize=(7.2,3.65));a=fig.add_axes([.16,.16,.41,.74]);b=fig.add_axes([.75,.72,.22,.18]);c=fig.add_axes([.75,.16,.095,.38]);d=fig.add_axes([.885,.16,.095,.38])
names=[T('正确分组','True grouping'),T('完整连接','Complete'),T('固定密度','Fixed density'),T('单连接','Single'),T('谱配置','Spectral'),T('HDBSCAN','HDBSCAN')]
for i,row in enumerate(sim['methods']):
 y=5-i;key=['oracle','complete','density','single','spectral','hdbscan'][i];h=row['hard']['value']*100;s=row['soft']['value']*100
 a.plot([h,s],[y+.09,y-.09],c='#B9C7CE',lw=1.1)
 for v,rule,col,marker,dy in [(h,'hard',TEAL,'o',.09),(s,'soft',AMBER,'s',-.09)]:a.errorbar(v,y+dy,xerr=getci(f'group/{key}/{rule}')[1],fmt=marker,ms=4.2,c=col,capsize=2,lw=1,label=(T('原规则','Original') if rule=='hard' else T('Ward软规则','Ward-soft')) if i==0 else None)
a.set(xlim=(-1,65),ylim=(-.6,5.7),xticks=[0,20,40,60],yticks=range(6),yticklabels=names[::-1],xlabel=T('固定分母身份top-1（%）','Fixed-denominator identity top-1 (%)'));a.legend(loc='upper center',bbox_to_anchor=(.5,1.11),ncol=2,frameon=False,fontsize=8,handlelength=1);letter(a,'a',x=-.28)
for yy,v,txt in [(2,100,'2400/2400'),(1,1107/24,'1107/2400'),(0,494/24,'494/2400')]:
 b.barh(yy,v,height=.34,color=GRAY);b.text(v+3,yy,txt,va='center',fontsize=7.3)
b.set(xlim=(0,170),ylim=(-.6,2.6),xticks=[0,50,100],yticks=[0,1,2],yticklabels=[T('密度','Density'),T('完整','Complete'),T('正确','True')],xlabel=T('真值资格（%）','True-candidate eligibility (%)'));letter(b,'b',x=-.4)
for i,row in enumerate(sim['methods']):
 y=5-i;c.scatter(row['pair_recall']['value']*100,y,c=BLUE,marker='o',s=17);d.scatter(row['pair_precision']['value']*100,y,facecolor='white',edgecolor=GRAY,marker='s',s=17,lw=.8)
for aa,label,letter_ in [(c,T('召回（%）','Recall (%)'),'c'),(d,T('精度（%）','Precision (%)'),'d')]:
 aa.set(xlim=(-3,105),ylim=(-.6,5.7),xticks=[0,100],yticks=range(6),yticklabels=names[::-1] if aa is c else ['']*6,xlabel=label);aa.tick_params(axis='both',labelsize=7.2);aa.xaxis.label.set_size(7.5);letter(aa,letter_,x=-.35)
zoom=fig.add_axes([.205,.76,.15,.10]);zoom.spines[['top','right','left']].set_visible(False)
for rule,col,marker,y in [('hard',TEAL,'o',.16),('soft',AMBER,'s',-.16)]:
 val,err=getci(f'group/spectral/{rule}');zoom.errorbar(val,y,xerr=err,fmt=marker,ms=2.5,c=col,capsize=2,lw=1,zorder=3)
zoom.set(xlim=(0,3),ylim=(-.45,.45),xticks=[0,1,2,3],yticks=[]);zoom.tick_params(axis='x',labelsize=6.5,pad=1,length=2)
zoom.text(.5,1.18,T('谱配置局部 / %','Spectral detail / %'),ha='center',transform=zoom.transAxes,fontsize=7)
finish(fig,'fig4-grouping-and-rules',[a,b,c,d],['a','b','c','d'],rows=[['c','d']],why='a is the paired outcome hero, with all twelve house-bootstrap intervals. Its spectral-only inset makes the small intervals visible. b is eligibility; c/d are separate recall/precision axes with equal dimensions and no connecting line between distinct quantities. The inset is a magnified view of existing values, not a new analysis.')

# Figure 5: one confusion hero, segment heterogeneity, and a true delta axis.
fig=plt.figure(figsize=(7.2,4.0));a=fig.add_axes([.145,.30,.43,.64]);b=fig.add_axes([.75,.61,.21,.30]);c=fig.add_axes([.75,.20,.21,.22])
cm=np.array(act['arms']['joint']['confusion']);norm=cm/cm.sum(axis=1)[:,None];cmap=LinearSegmentedColormap.from_list('activity',['#E6F0F0',TEAL]);cmap.set_bad('#EBEFF2')
im=a.imshow(np.ma.masked_where(cm==0,norm),cmap=cmap,vmin=0,vmax=1,aspect='auto',interpolation='nearest')
for i in range(8):
 for j in range(8):
  if cm[i,j]:a.text(j,i,str(cm[i,j]),ha='center',va='center',fontsize=9,color='white' if norm[i,j]>.65 else INK)
longzh=['柜门交互','静止','躺下（过渡）','躺卧（持续）','坐下','起立','直立/坐姿','行走'];shortzh=['柜门','静止','躺下','躺卧','坐下','起立','直立/坐姿','行走'];longen=['Cabinet','Idle','Lie down','Lying','Sit down','Stand up','Upright†','Walk'];names=longen if EN else longzh
a.set(xticks=range(8),xticklabels=['Cabinet','Idle','Lie down','Lying','Sit down','Stand up','Upright','Walk'] if EN else shortzh,yticks=range(8),yticklabels=[n+f'  n={int(cm[i].sum())}' for i,n in enumerate(names)]);a.tick_params(axis='x',labelrotation=60,labelsize=7.3)
for tx in a.get_xticklabels():tx.set_ha('right');tx.set_rotation_mode('anchor')
a.set_xticks(np.arange(9)-.5,minor=True);a.set_yticks(np.arange(9)-.5,minor=True);a.grid(which='minor',color='white',lw=.7);a.tick_params(which='minor',length=0);letter(a,'a',x=-.20,y=1.01)
cbax=fig.add_axes([.145,.115,.43,.020]);cb=fig.colorbar(im,cax=cbax,orientation='horizontal',ticks=[0,.5,1]);cb.ax.set_xticklabels(['0','50','100']);cb.set_label(T('行归一化比例（%）；格内为事件数','Row-normalized proportion (%); cell labels are counts'),fontsize=7.8,labelpad=1)
parts={r['part']:r['accuracy'] for r in act['arms']['joint']['per_part']}
for i,part in enumerate(['T-G1a','T-G1b','T-G2a','T-G2b','T-Ba','T-Bb']):
 r=parts[part];y=5-i;v=r['value']*100;b.scatter(v,y,s=24,c=AMBER if '-B' in part else BLUE);b.text(109,y,f"{r['numerator']}/{r['denominator']}",va='center',fontsize=7.2,clip_on=False)
b.set_position([.75,.61,.18,.30])
b.set(xlim=(0,105),ylim=(-.6,5.6),xticks=[0,50,100],yticks=range(6),yticklabels=['Bb','Ba','G2b','G2a','G1b','G1a'],xlabel=T('分段准确率（%）','Per-session accuracy (%)'));letter(b,'b',x=-.30)
b.scatter([],[],s=16,c=BLUE,label=T('地面 G','Floor G'));b.scatter([],[],s=16,c=AMBER,label=T('床上 B','Bed B'));b.legend(loc='lower center',bbox_to_anchor=(.62,1.03),frameon=False,ncol=2,fontsize=7.0,columnspacing=.6,handlelength=.5)
c.set_position([.75,.20,.18,.22])
for i,(arm,col) in enumerate([('phone',BLUE),('watch',GRAY),('joint',TEAL)]):
 r=act['utility'][arm];v=100*(r['hz20']['value']-r['raw']['value']);y=2-i;c.plot([0,v],[y,y],c=col,lw=1.6);c.scatter(v,y,s=25,c=col);c.text(v+.18,y,f'{v:+.1f}',va='center',fontsize=8)
c.axvline(0,c=GRAY,lw=.65,ls='--');c.set(xlim=(-.4,4.2),ylim=(-.6,2.6),xticks=[0,1,2,3,4],yticks=[0,1,2],yticklabels=[T('联合','Joint'),T('手表','Watch'),T('手机','Phone')],xlabel=T('20Hz处理变化（百分点）','Change after 20 Hz (pp)'));letter(c,'c',x=-.30)
finish(fig,'fig5-action-and-utility',[a,b,c],['a','b','c'],cols=[['b','c']],why='a is the full 8-class confusion matrix with support and a colorbar; b/c share column edges but differ in height; b adds session heterogeneity rather than repeating per-class recall; c shows paired changes, not a truncated percentage axis. Colorbar is intentionally excluded from panel groups.')

# Figure 6: real inputs -> complete intervals -> exploratory marker diagnostic.
fig=plt.figure(figsize=(7.2,5.2));a=fig.add_axes([.055,.69,.28,.25]);table=fig.add_axes([.345,.67,.13,.27]);b=fig.add_axes([.60,.69,.35,.25]);c=fig.add_axes([.17,.395,.78,.15]);d=fig.add_axes([.14,.075,.31,.19]);e=fig.add_axes([.67,.075,.28,.19])
d12=2.03;x0=(.91**2+d12**2-1.5**2)/(2*d12);y0=np.sqrt(.91**2-x0*x0);x3=(1.18**2+d12**2-1.02**2)/(2*d12);y3=-np.sqrt(1.18**2-x3*x3);p=np.array([[x0,y0],[0,0],[d12,0],[x3,y3]])
for k,col in [(0,TEAL),(3,AMBER)]:
 q=p[[1,k,2]];a.add_patch(Polygon(q,fc=col,alpha=.08,ec='none'));a.plot(*np.vstack([q,q[0]]).T,c=col,lw=1)
a.plot(*p[[0,3]].T,c=GRAY,ls=':',lw=.8);a.scatter(*p.T,c=[TEAL,GRAY,GRAY,AMBER],s=28,edgecolor='white',lw=.6,zorder=4)
for i,off in enumerate([(0,7),(-7,-11),(7,-11),(0,-12)]):a.annotate('P'+str(i),p[i],xytext=off,textcoords='offset points',ha='center',fontsize=8)
a.set(xlim=(-.2,2.25),ylim=(-.72,1.0),xticks=[],yticks=[]);a.set_aspect('equal',adjustable='box');a.axis('off');letter(a,'a',x=-.08)
table.axis('off');table.text(0,1,T('实测 / cm','Measured / cm'),fontsize=7.7)
for i,(pair,value) in enumerate(pilot['geometry']['inputs_cm'].items()):table.text(0,.84-i*.145,pair.replace('P','')+f'  {value}'+('†' if pair=='P0-P3' else ''),fontsize=7.8)
for rid,col,ls in [('R1',TEAL,'-'),('R2',AMBER,'--')]:
 ser=pilot['events'][rid]['series'];b.plot([r['s'] for r in ser],[r['p_walk_phone'] for r in ser],c=col,ls=ls,lw=.8,label=rid)
b.axhline(.3,c=GRAY,ls=':',lw=.7,label=T('门限0.3','Threshold 0.3'));b.set(xlim=(0,210),ylim=(0,1.05),xticks=[0,70,140,210],yticks=[0,.5,1],xlabel=T('时间（s）','Time (s)'),ylabel=T('行走概率','P(walk)'));b.legend(loc='upper center',bbox_to_anchor=(.5,1.18),frameon=False,ncol=3,handlelength=1.2,columnspacing=.8,fontsize=7.4);letter(b,'b',x=-.22)
windows=np.array([[50,58],[68,76],[86,94],[104,112],[122,130],[140,148],[158,166],[176,184]])
for y,rid,col in [(1,'R1',TEAL),(0,'R2',AMBER)]:
 for st,en in windows:
  c.broken_barh([(st,en-st)],(y-.13,.26),facecolors=PALE,edgecolors=GRAY,lw=.3)
  for ev in pilot['events'][rid]['events']:
   low=max(st,ev['start']);high=min(en,ev['end'])
   if high>low:c.broken_barh([(low,high-low)],(y-.13,.26),facecolors=col,edgecolors='none')
 for ev in pilot['events'][rid]['events']:c.plot([ev['start'],ev['end']],[y+.29,y+.29],c=col,lw=1.5,solid_capstyle='butt')
 for j,(st,en) in enumerate(windows):c.text((st+en)/2,y,'ACBACBAC'[j],ha='center',va='center',fontsize=7.5,color='white')
c.set(xlim=(0,210),ylim=(-.3,1.55),yticks=[0,1],yticklabels=['R2 89.8%','R1 87.5%'],xticks=[0,40,80,120,160,210],xlabel=T('时间（s）','Time (s)'));letter(c,'c',x=-.14)
vis=pilot['feature_distances']['visits'];order=sorted(range(16),key=lambda i:(vis[i]['declared_marker'],i));dm=np.array(pilot['feature_distances']['matrices']['joint'])[np.ix_(order,order)];np.fill_diagonal(dm,np.nan);vm=5*np.ceil(np.nanmax(dm)/5)
dc=LinearSegmentedColormap.from_list('spatial_teal',['#EDF2F4','#C1DEE0','#78AFB1','#2C858C','#164C59']);dc.set_bad('#DDE3E7');im=d.imshow(np.ma.masked_invalid(dm),cmap=dc,vmin=0,vmax=vm,aspect='auto',interpolation='nearest');ticks=[]
for marker in ['P0','P1','P2','P3']:
 ix=[j for j,i in enumerate(order) if vis[i]['declared_marker']==marker];ticks.append((np.mean(ix),marker))
 if max(ix)<15:d.axhline(max(ix)+.5,c='white',lw=.8);d.axvline(max(ix)+.5,c='white',lw=.8)
d.set(xticks=[v for v,s in ticks],xticklabels=[s for v,s in ticks],yticks=[v for v,s in ticks],yticklabels=[s for v,s in ticks]);letter(d,'d',x=-.22)
cbax=fig.add_axes([.47,.075,.012,.19]);cb=fig.colorbar(im,cax=cbax,ticks=[0,vm/2,vm]);cb.ax.tick_params(labelsize=7.3);cb.set_label(T('标准化特征距离','Standardized distance'),fontsize=7.5,labelpad=1)
for i,row in enumerate(station['rows']):
 y=2-i;lo,hi=row['null_hit_quantiles95'];obs=row['observed']['numerator'];col=[BLUE,GRAY,TEAL][i]
 e.plot([lo,hi],[y,y],c='#CED8DE',lw=5,solid_capstyle='round');e.scatter(row['null_mean']['value']*16,y,c=GRAY,s=14,zorder=3);e.scatter(obs,y,c=col,s=29,edgecolor='white',lw=.5,zorder=4);e.text(obs,y+.31,f'{obs}/16',ha='center',fontsize=7.8)
e.set(xlim=(-.5,16),ylim=(-.5,2.8),xticks=[0,4,8,12,16],yticks=[0,1,2],yticklabels=[T('联合','Joint'),T('手表','Watch'),T('手机','Phone')],xlabel=T('声明标记命中数 / 16','Declared-marker hits / 16'));letter(e,'e',x=-.23)
finish(fig,'fig6-real-pilot',[a,b,c,d,e],['a','b','c','d','e'],rows=[['d','e']],why='a has equal metric scale; its six-edge table and d colorbar are subordinate insets. b is probability, c the complete event stream, d/e share row edges, measuring distances and a fixed-count permutation reference respectively. No shared data scale is implied between these modalities.')

# Figure 7: coverage stability and event-count variation are different endpoints.
sens=read('formal-gate-sensitivity.json');fig=plt.figure(figsize=(7.2,2.55));a=fig.add_axes([.11,.24,.35,.66]);b=fig.add_axes([.60,.24,.35,.66]);thresholds=[.3,.4,.5,.6,.7]
for rid,col,marker in [('R1',TEAL,'o'),('R2',AMBER,'s')]:
 vals=[];low=[];high=[];chosen=[]
 for th in thresholds:
  same=[r[rid]['mean_frac'] for r in sens if r['thr']==th];assert len(same)==6 and len(set(same))==1;vals.append(same[0]*100)
  counts=[r[rid]['events_total'] for r in sens if r['thr']==th];low.append(min(counts));high.append(max(counts));chosen.append(next(r[rid]['events_total'] for r in sens if r['thr']==th and r['min_dwell']==4 and r['merge_gap']==0))
 a.plot(thresholds,vals,c=col,marker=marker,lw=1.4,ms=4);a.scatter(.3,vals[0],s=60,facecolor='white',edgecolor=col,lw=1.3,zorder=5,marker=marker);a.text(.73,vals[-1]+(-1.2 if rid=='R1' else .35),rid,va='center',c=col,fontsize=8)
 offset=-.006 if rid=='R1' else .006;x=np.array(thresholds)+offset
 b.errorbar(x,chosen,yerr=[np.array(chosen)-low,np.array(high)-chosen],fmt=marker,c=col,lw=1.2,ms=3.5,capsize=3,label=rid)
 b.plot(x,chosen,c=col,lw=.7,ls='-' if rid=='R1' else '--',drawstyle='steps-mid')
a.set(xlim=(.275,.79),ylim=(80,100),xticks=thresholds,yticks=[80,85,90,95,100],xlabel=T('行走概率阈值','Walk-probability threshold'),ylabel=T('平均计划窗覆盖（%）','Mean coverage (%)'));lightgrid(a);letter(a,'a',x=-.20)
b.set(xlim=(.275,.79),ylim=(0,12),xticks=thresholds,yticks=[0,4,8,10,12],xlabel=T('行走概率阈值','Walk-probability threshold'),ylabel=T('全段自动事件数','Full-record event count'));lightgrid(b);letter(b,'b',x=-.20)
b.legend(loc='lower right',frameon=False,ncol=2,fontsize=7.8,handlelength=.9)
finish(fig,'fig7-gate-sensitivity',[a,b],['a','b'],rows=[['a','b']],why='a retains all coincident coverage readouts. b shows the min-max count range of six settings per threshold and the 4-second/zero-gap slice as points; ranges are setting variation, not confidence intervals. Horizontal offsets only prevent overlap. Full 30-setting data retained; a has a declared 80-100% range, b starts at zero.')
print(json.dumps({'figures':7,'language':args.language,'new_scoring':False,'new_model_fitting':False},ensure_ascii=False))
