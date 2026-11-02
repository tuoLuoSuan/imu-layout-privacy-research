"""Seven evidence-led plates at the manuscript's exact 160 mm final width.

Usage: python build_figures.py --language zh (or en), optionally --only STEM.
All inputs are frozen, derived source data. This entry point does not fit models
or recompute attack matching scores.
"""
from pathlib import Path
import argparse, json, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle, Polygon, ConnectionPatch
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter, NullLocator
from matplotlib.path import Path as GraphicPath
from matplotlib.transforms import Bbox

HERE=Path(__file__).resolve().parent
def require_matplotlib_panel_alignment(fig, **kwargs):
    axes=kwargs.get('axes',fig.axes);ids=kwargs.get('panel_ids',[str(i) for i in range(len(axes))]);pos=dict(zip(ids,[a.get_position() for a in axes]));width,height=fig.get_size_inches()*72
    for name,keys,scale in [('row_groups',('y0','y1','height'),height),('column_groups',('x0','x1','width'),width)]:
        for group in kwargs.get(name,[]):
            for key in keys:
                vals=[getattr(pos[i],key)*scale for i in group]
                assert max(vals)-min(vals)<=1.5,(group,key)
    Path(kwargs['json_out']).write_text(json.dumps({'comparable_groups_checked':True,'tolerance_pt':1.5}),encoding='utf-8')

parser=argparse.ArgumentParser()
parser.add_argument('--language',choices=['zh','en'],default='zh')
parser.add_argument('--only',nargs='*')
args=parser.parse_args();EN=args.language=='en'
OUT=HERE/('figures-en' if EN else 'figures');OUT.mkdir(exist_ok=True)
WIDTH_PT=160/25.4*72
WIDTH_IN=WIDTH_PT/72
INK='#24333D';TEAL='#0B7377';CLAY='#C4744C'
GRAY='#7F909B';DARK='#566C78';LIGHT='#BAC6CD';PALE='#E9EFF2';RULE='#D5DEE3'
for font in ['arial.ttf','arialbd.ttf','simsun.ttc']:
 p=Path('C:/Windows/Fonts')/font
 if p.exists():font_manager.fontManager.addfont(str(p))
plt.rcParams.update({'font.family':['Arial','SimSun'],'font.size':7.2,
 'axes.labelsize':7.2,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,
 'axes.unicode_minus':False,'text.color':INK,'axes.labelcolor':INK,
 'xtick.color':INK,'ytick.color':INK,'xtick.major.width':.6,'ytick.major.width':.6,
 'xtick.major.size':2.2,'ytick.major.size':2.2,'figure.facecolor':'white',
 'savefig.facecolor':'white','pdf.fonttype':42,'svg.fonttype':'none'})

def T(zh,en):return en if EN else zh
def read(name):return json.loads((HERE/'source-data'/name).read_text('utf-8'))
sim=read('simulation-summary.json');act=read('action-eight-summary.json')
ex=read('figure-examples.json');pilot=read('pilot-display.json')
station=read('station-permutation.json');sens=read('formal-gate-sensitivity.json')
ci={r['condition']:r for r in read('score-intervals.json')['rows']}
CHANCE=100/600;IDEAL=100*492/600
METHOD_KEYS=['oracle','complete','density','single','spectral','hdbscan']
METHOD_NAMES=[T('正确分组','True grouping'),T('完整连接','Complete linkage'),
 T('固定密度','Fixed density'),T('单连接','Single linkage'),T('谱配置','Spectral'), 'HDBSCAN']
ERR=dict(elinewidth=.7,capsize=1.8,capthick=.7)

def figure(height):return plt.figure(figsize=(WIDTH_IN,height))
def letter(ax,text,dx=-8,dy=5):
 if not hasattr(ax.figure,'_paper_letters'):ax.figure._paper_letters=[]
 ax.figure._paper_letters.append((ax,text,dx,dy))
def grid(ax,axis='y'):
 ax.grid(axis=axis,color=RULE,lw=.4,alpha=.65);ax.set_axisbelow(True)
def interval(key):
 r=ci[key];v=r['rate']['value']*100;lo,hi=np.array(r['house_bootstrap95'])*100
 return v,np.array([[v-lo],[hi-v]])
def point(ax,x,y,error=None,color=TEAL,marker='o',horizontal=True,**kw):
 options=dict(fmt=marker,ms=3.6,mec='white',mew=.45,color=color,zorder=4,**ERR)
 options.update(kw)
 return ax.errorbar(x,y,**({'xerr':error} if horizontal else {'yerr':error}),**options)
def finish(fig,name,axes,ids,rows=(),cols=(),why=''):
 if args.only and name not in args.only:plt.close(fig);return
 fig.canvas.draw();w,h=fig.get_size_inches()*72;anchors=[]
 for ax,text,dx,dy in getattr(fig,'_paper_letters',[]):
  bb=ax.get_position();x=bb.x0+dx/w;y=bb.y1+dy/h
  fig.text(x,y,text,ha='left',va='bottom',fontsize=8,fontweight='bold',fontfamily='Arial')
  anchors.append(dict(text=text,x_pt=x*w,y_pt=y*h,dx_pt=dx,dy_pt=dy))
 fig.canvas.draw()
 require_matplotlib_panel_alignment(fig,axes=axes,panel_ids=ids,row_groups=list(rows),
  column_groups=list(cols),json_out=str(OUT/(name+'.alignment.json')),
  overlay_svg=str(OUT/(name+'.alignment.svg')),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(OUT/(name+'.pdf'),dpi=600)
 fig.savefig(OUT/(name+'.svg'),dpi=600)
 fig.savefig(OUT/(name+'.png'),dpi=600)
 fig.savefig(OUT/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
 meta=dict(language=args.language,width_mm=160,width_pt=float(w),height_pt=float(h),
  minimum_glyph_pt=7,panel_labels=anchors,comparable_rows=rows,comparable_columns=cols,
  interpretation=why,scoring_recomputed=False,model_fitting=False,
  color_roles={'teal':'retained primary analysis or frozen setting',
   'clay':'alternative reading or contrasting outcome','gray':'other conditions, devices and repeated records'})
 (OUT/(name+'.design.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 plt.close(fig)

# Axonometric data geometry, adapted from the structure-plus-evidence layout
# of published scientific plates; heights are schematic, never measurements.
def project(xy, z=0):
 xy=np.asarray(xy,float);return np.column_stack([.86*xy[:,0]-.48*xy[:,1],.32*xy[:,0]+.55*xy[:,1]+np.asarray(z)])
def prism(ax,rect,height,top='#F1F4F5',side='#C9D5DB',edge='#8397A2',base_z=0):
 x0,y0,x1,y1=rect;xy=np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])
 low=project(xy,base_z);high=project(xy,base_z+height)
 for i,j,col in [(0,1,side),(1,2,'#DFE6EA')]:
  ax.add_patch(Polygon(np.vstack([low[i],low[j],high[j],high[i]]),closed=True,fc=col,ec=edge,lw=.35))
 ax.add_patch(Polygon(high,closed=True,fc=top,ec=edge,lw=.4))
def room_scene(ax,house,route=None):
 rectangles=[r['rect'] for r in house['rooms']];allxy=np.array([[r[0],r[1]] for r in rectangles]+[[r[2],r[3]] for r in rectangles])
 x0,y0=allxy.min(axis=0);x1,y1=allxy.max(axis=0)
 prism(ax,[x0-.15,y0-.15,x1+.15,y1+.15],.18,top='#F6F8F9',side='#CBD6DC',base_z=-.18)
 for room in house['rooms']:
  rx0,ry0,rx1,ry1=room['rect']
  prism(ax,[rx0,ry1-.07,rx1,ry1],.85,top='#D7E1E6',side='#CBD8DE')
  prism(ax,[rx0,ry0,rx0+.07,ry1],.85,top='#DCE5E9',side='#C9D7DD')
 for item in sorted(house['objects'],key=lambda it:sum(it['rect'][1::2]),reverse=True):
  prism(ax,item['rect'],.34,top='#EDF2F4',side='#ACBEC8',edge='#8CA0AC')
 if route is not None:
  line=project(np.array(route),.04);ax.plot(*line.T,color=TEAL,lw=.8,alpha=.65,zorder=6)
 sites=np.array([r['xy'] for r in house['sites']]);points=project(sites,.07)
 ax.scatter(*points.T,c=TEAL,s=18,edgecolor='white',lw=.6,zorder=8)
 # Dashed ground-plane projections are geometric context, not a room estimate.
 corners=project(np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1]]))
 lo=corners.min(axis=0);hi=corners.max(axis=0)+[0,1]
 ax.set(xlim=(lo[0]-.5,hi[0]+.5),ylim=(lo[1]-.5,hi[1]+.5),xticks=[],yticks=[])
 ax.set_aspect('equal',adjustable='box');ax.axis('off')

# 1: one spatial illustration dominates, with a calibrated result panel below.
fig=figure(5.25)
house=ex['aliases'][0];route=ex['noise_example']['true_visits']
scene=fig.add_axes([.035,.555,.385,.245]);room_scene(scene,house,route)
sites=np.array([row['xy'] for row in house['sites']]);low=sites.min(axis=0)-[.7,.55];high=sites.max(axis=0)+[.8,.9]
focus=np.array([[low[0],low[1]],[high[0],low[1]],[high[0],high[1]],[low[0],high[1]]]);fp=project(focus)
scene.set(xlim=(fp[:,0].min()-.12,fp[:,0].max()+.12),ylim=(fp[:,1].min()-.1,fp[:,1].max()+.45))
def clip_polygon(vertices,xlim,ylim):
 vertices=[np.array(v,float) for v in vertices]
 for dim,bound,greater in [(0,xlim[0],True),(0,xlim[1],False),(1,ylim[0],True),(1,ylim[1],False)]:
  output=[]
  if not vertices:break
  previous=vertices[-1];pin=(previous[dim]>=bound) if greater else (previous[dim]<=bound)
  for current in vertices:
   cin=(current[dim]>=bound) if greater else (current[dim]<=bound)
   if cin!=pin:
    ratio=(bound-previous[dim])/(current[dim]-previous[dim]);output.append(previous+ratio*(current-previous))
   if cin:output.append(current)
   previous=current;pin=cin
  vertices=output
 return np.asarray(vertices)
for patch in list(scene.patches):
 if isinstance(patch,Polygon):
  clipped=clip_polygon(patch.get_xy(),scene.get_xlim(),scene.get_ylim())
  if len(clipped)>=3:patch.set_xy(clipped)
  else:patch.remove()
scene.text(.5,1.03,T('访问区域放大','Visited-region detail'),ha='center',transform=scene.transAxes,fontsize=7.5)
context=fig.add_axes([.045,.825,.125,.12]);room_scene(context,house)
context.add_patch(Polygon(fp,fill=False,ec=TEAL,lw=.8,ls=(0,(3,2))))
context.text(1.12,.65,T('完整候选全景','Whole candidate'),transform=context.transAxes,fontsize=7.2,va='center')
context.text(1.12,.30,T('虚框：下方放大区域','Outline: detail below'),transform=context.transAxes,fontsize=7,color=DARK,va='center')
fig.add_artist(ConnectionPatch(xyA=(fp[:,0].mean(),fp[:,1].min()),coordsA=context.transData,
 xyB=(.10,1.01),coordsB=scene.transAxes,color=LIGHT,lw=.6,ls=(0,(3,2)),clip_on=False))
a_frame=fig.add_axes([.045,.555,.85,.39],frameon=False)
a_frame.patch.set_visible(False);a_frame.axis('off');letter(a_frame,'a')
fig.text(.055,.515,T('青点：站位　连线：访问先后次序','Teal: sites   Lines: visit order'),fontsize=7.2)
obsax=fig.add_axes([.475,.65,.17,.22]);v=ex['noise_example']['views']['brownian'];obs=np.array(v['observations']);cent=np.array(v['group_representatives'])
obsax.plot(*obs.T,c=LIGHT,lw=.55,zorder=1);obsax.scatter(*obs.T,s=5,c=GRAY,alpha=.7,zorder=2)
for i,j in zip(*np.triu_indices(len(cent),1)):obsax.plot(*cent[[i,j]].T,c='#B8CFD1',lw=.5,zorder=2)
obsax.scatter(*cent.T,s=19,c=TEAL,edgecolor='white',lw=.6,zorder=3)
obsax.axis('off');obsax.set_aspect('equal',adjustable='box')
obsax.text(.5,1.08,T('32次观测 → 组代表','32 observations → representatives'),ha='center',transform=obsax.transAxes,fontsize=7.2)
mat=fig.add_axes([.755,.765,.135,.135]);ix,iy=np.triu_indices(len(cent),1);dist=np.linalg.norm(cent[:,None]-cent[None,:],axis=-1)
map_=LinearSegmentedColormap.from_list('geometry_matrix',['#EFF5F5','#A9CBCF',TEAL])
mat.imshow(dist,cmap=map_,interpolation='nearest',aspect='auto');mat.set(xticks=[],yticks=[])
for spine in mat.spines.values():spine.set_visible(False)
mat.text(.5,1.12,T('两两距离','Pairwise distances'),ha='center',transform=mat.transAxes,fontsize=7.2)
spec=fig.add_axes([.745,.575,.15,.105]);spectrum=np.sort(dist[ix,iy]);spectrum/=np.sqrt(np.mean(spectrum*spectrum))
spec.plot(np.linspace(0,1,len(spectrum)),spectrum,c=TEAL,lw=1);spec.scatter(np.linspace(0,1,len(spectrum)),spectrum,s=6,c=TEAL)
spec.set(xticks=[],yticks=[]);spec.spines[['top','right']].set_visible(False)
spec.text(.5,-.30,T('归一化距离谱','Normalized spectrum'),ha='center',transform=spec.transAxes,fontsize=7.2)
for x0,x1 in [(.417,.465),(.665,.72)]:
 fig.add_artist(plt.annotate('',xy=(0,0))) if False else None
 fig.text((x0+x1)/2,.735,'→',fontsize=11,ha='center',va='center',color=GRAY)

b=fig.add_axes([.38,.13,.51,.285])
rows=[(3,T('无扰 / 共同平移 · λ=0','None / common shift · λ=0'),'noise/none/32',False),
 (2,T('冻结主条件 · λ=0.0003','Frozen main setting · λ=0.0003'),'group/oracle/hard',True),
 (1,T('随机游走 · λ=0','Brownian walk · λ=0'),'noise/brownian/32',False),
 (0,T('独立扰动 · λ=0','IID noise · λ=0'),'noise/iid/32',False)]
for y,label,key,main in rows:
 value,error=interval(key);b.plot([.1,100],[y,y],c=PALE,lw=.5,zorder=0)
 point(b,value,y,error,color=TEAL if main else GRAY,ms=4.1 if main else 3.5)
 b.text(1.13,y,f'{value:.1f}',ha='right',va='center',transform=b.get_yaxis_transform(),fontsize=7.8,color=TEAL if main else DARK,fontweight='bold' if main else 'normal')
b.set_xscale('log');b.set(xlim=(.1,100),ylim=(-.55,3.9),yticks=[r[0] for r in rows],yticklabels=[r[1] for r in rows],xticks=[.1,1,10,100],xlabel=T('身份 top-1（%，对数轴）','Identity top-1 (%, log scale)'))
b.xaxis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:g}'));b.xaxis.set_minor_locator(NullLocator());b.spines['left'].set_visible(False);b.tick_params(axis='y',length=0,pad=6)
for tick,row in zip(b.get_yticklabels(),rows):
 if row[3]:tick.set_color(TEAL);tick.set_fontweight('bold')
b.axvline(CHANCE,c=DARK,lw=.6,ls=(0,(4,2)),zorder=0);b.axvline(IDEAL,c=CLAY,lw=.6,ls=(0,(4,2)),zorder=0)
b.text(CHANCE,4.06,T('机会 1/600','Chance 1/600'),va='bottom',fontsize=7,color=DARK)
b.text(IDEAL,4.06,T('理想 492/600','Ideal 492/600'),ha='right',va='bottom',fontsize=7,color=CLAY)
letter(b,'b')
finish(fig,'fig1-threat-model',[b],['b'],why='Quantitative panel b is accompanied by an original structure-led illustration a; the conceptual axes are not comparable numerical plot areas. Every visible structure uses the pre-existing frozen T0319 geometry and first route; the main scene is an explicitly marked zoom of the visited region and the thumbnail retains the full candidate extent. All visit sites and all 32 visits remain visible in the detail; no coordinates or observations are excluded. The axonometric object heights are illustration only and are not 3D measurements or matcher inputs. Matrix and normalized spectrum use the saved noisy group representatives. Four outcome rows carry their own lambda labels, all share true grouping; no unlabelled mixed-condition leaderboard. The two reference lines are analytic and conditional. All panel-label anchors use physical points.')

# 2: one paired geometric example, followed by the entire class distribution.
fig=figure(2.85);a0=fig.add_axes([.035,.18,.245,.69]);a1=fig.add_axes([.315,.18,.245,.69]);b=fig.add_axes([.71,.23,.235,.61])
for ax,house in zip([a0,a1],ex['aliases']):room_scene(ax,house)
lims=np.array([a0.get_xlim()+a0.get_ylim(),a1.get_xlim()+a1.get_ylim()]);xlim=(lims[:,0].min(),lims[:,1].max());ylim=(lims[:,2].min()-.9,lims[:,3].max())
for ax,label in [(a0,'T0319'),(a1,'T0448')]:
 ax.set(xlim=xlim,ylim=ylim);ax.text(.5,1.02,label,ha='center',transform=ax.transAxes,fontsize=7.5)
base_x=xlim[0]+.3;base_y=ylim[0]+.15
bar=project(np.array([[0,0],[2,0]]));a0.plot(base_x+bar[:,0],base_y+bar[:,1],c=INK,lw=.7)
a0.annotate(T('2 m（x方向）','2 m (x direction)'),(base_x+bar[:,0].mean(),base_y+bar[:,1].mean()),xytext=(0,-9),textcoords='offset points',ha='center',va='top',fontsize=7)
letter(a0,'a')
hist=read('alias-size-histogram.json')['classes'];sizes=[r['size'] for r in hist];freq=[r['classes'] for r in hist]
b.scatter(freq,sizes,s=17,c=GRAY,zorder=3)
for n,k in zip(freq,sizes):b.annotate(str(n),(n,k),xytext=(4,0),textcoords='offset points',va='center',fontsize=7)
b.set_xscale('log');b.set(xlim=(.7,1400),ylim=(9.7,.3),xticks=[1,10,100,1000],yticks=[1,3,5,9],
 xlabel=T('等价类数（对数）','Class count (log)'),ylabel=T('每类身份数','Identities per class'))
b.xaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:g}'));b.xaxis.set_minor_locator(NullLocator())
fig.text(.71,.055,T('大小7、8：0类','Sizes 7 and 8: zero classes'),fontsize=7,color=DARK)
letter(b,'b')
finish(fig,'fig2-representation',[a0,a1,b],['a0','a1','b'],rows=[['a0','a1']],why='a is a same-scale, same-projection axonometric pair of frozen 2D synthetic layouts. Extrusion heights are illustrative and are not measured room geometry; spectra use original 2D coordinates. b retains all 492 classes. Zero-frequency categories have no log coordinate and are noted outside the axes; no pseudo-zero dot is drawn. The paired illustration axes intentionally differ from the count panel.')

# 3: illustrative error geometry, budget, a rule control, and stronger readings.
fig=figure(4.4);mini=[];view=ex['noise_example'];true=np.array(view['true_visits'])
kinds=['none','common','brownian','iid'];allpts=np.vstack([true]+[np.array(view['views'][k]['observations']) for k in kinds])
lo=allpts.min(axis=0)-.6;hi=allpts.max(axis=0)+.6
for j,kind in enumerate(kinds):
 ax=fig.add_axes([.055+(j%2)*.205,.75-(j//2)*.18,.175,.14]);mini.append(ax)
 col=TEAL if kind=='brownian' else GRAY;obs=np.array(view['views'][kind]['observations']);cent=np.array(view['views'][kind]['group_representatives'])
 ax.scatter(*true.T,s=12,facecolor='none',edgecolor=LIGHT,lw=.5);ax.plot(*obs.T,color=col,lw=.45,alpha=.7)
 ax.scatter(*obs.T,s=3,color=col,alpha=.5);ax.scatter(*cent.T,s=13,color=col,edgecolor='white',lw=.4,zorder=4)
 ax.set(xlim=(lo[0],hi[0]),ylim=(lo[1],hi[1]),xticks=[],yticks=[]);ax.set_aspect('equal',adjustable='box');ax.axis('off')
 ax.text(.5,1.0,[T('无扰动','None'),T('共同平移','Common shift'),T('随机游走','Brownian'),T('独立扰动','IID')][j],ha='center',transform=ax.transAxes,fontsize=7)
 if j==0:
  ax.plot([lo[0]+.3,lo[0]+2.3],[lo[1]+.4,lo[1]+.4],c=INK,lw=.7)
  ax.text(lo[0]+1.3,lo[1]-1.1,'2 m',ha='center',fontsize=7,clip_on=False)
letter(mini[0],'a')
b=fig.add_axes([.60,.63,.34,.28]);c=fig.add_axes([.12,.14,.34,.29]);d=fig.add_axes([.60,.14,.34,.29])
for kind,label,col,ls in [('none',T('无扰 / 平移','None/shift'),GRAY,'--'),('brownian',T('随机游走','Brownian'),TEAL,'-'),('iid',T('独立扰动','IID'),DARK,':')]:
 rr=[ci[f'noise/{kind}/{n}'] for n in [8,16,32]];v=np.array([r['rate']['value'] for r in rr])*100;bounds=np.array([r['house_bootstrap95'] for r in rr])*100
 b.fill_between([8,16,32],bounds[:,0],bounds[:,1],color=col,alpha=.13,lw=0)
 b.errorbar([8,16,32],v,yerr=[v-bounds[:,0],bounds[:,1]-v],color=col,lw=1,ls=ls,marker='o',ms=3,**ERR)
 b.text(33.3,v[-1],label,va='center',fontsize=7,color=col)
b.set(xlim=(6,45),ylim=(0,100),xticks=[8,16,32],yticks=[0,50,100],xlabel=T('访问次数','Visits'),ylabel=T('身份 top-1（%）','Identity top-1 (%)'));grid(b);letter(b,'b')
for y,i,label in [(2,0,T('无扰 / 平移','None/shift')),(1,2,T('随机游走','Brownian')),(0,3,T('独立扰动','IID'))]:
 row=sim['noise'][i];hard=row['original_top1']*100;soft=row['soft_top1']*100
 c.plot([hard,soft],[y+.08,y-.08],color=LIGHT,lw=.7)
 point(c,hard,y+.08,interval(f'noise/{kinds[i]}/32')[1],color=TEAL)
 point(c,soft,y-.08,color=CLAY,marker='s')
c.set(xlim=(-2,102),ylim=(-.5,2.6),yticks=[0,1,2],yticklabels=[T('独立扰动','IID'),T('随机游走','Brownian'),T('无扰 / 平移','None/shift')],
 xticks=[0,50,100],xlabel=T('32访身份 top-1（%）','32-visit identity top-1 (%)'))
c.plot([],[],'o',ms=3.6,c=TEAL,label=T('原规则','Original'));c.plot([],[],'s',ms=3.6,c=CLAY,label=T('软规则','Ward-soft'))
c.legend(loc='lower center',bbox_to_anchor=(.5,1.03),ncol=2,frameon=False,columnspacing=1,handlelength=.6);letter(c,'c')
strongs=[('partial_normalized',T('归一子谱','Subset\nnormalized'),TEAL),('full_normalized',T('完整谱','Full\nnormalized'),GRAY),('partial_metric',T('米制子谱','Subset\nmetric'),CLAY)]
for x,(key,label,col) in enumerate(strongs):
 val,err=interval('strong/'+key);point(d,x,val,err,color=col,horizontal=False)
 d.text(x,val+5,f'{val:.1f}',ha='center',fontsize=7.3)
d.set(xlim=(-.5,2.5),ylim=(0,80),xticks=range(3),xticklabels=[r[1] for r in strongs],yticks=[0,40,80],ylabel=T('身份 top-1（%）','Identity top-1 (%)'));letter(d,'d')
finish(fig,'fig3-noise-and-budget',mini+[b,c,d],['a1','a2','a3','a4','b','c','d'],rows=[['a1','a2'],['a3','a4'],['c','d']],cols=[['a1','a3'],['a2','a4']],why='Four distinct evidence roles: one frozen route under four processes, prefix budget, rule control, stronger geometric readings. The scale bar appears once for equal-scale insets. b directly labels lines. c combines the identical none/common controls and retains the soft-rule point-only limitation. All quantitative conditions use saved scores, 2400 routes, true grouping and lambda=0.')

# 4: wide primary outcome; eligibility and geometric relationship diagnostics.
fig=figure(4.4);a=fig.add_axes([.28,.54,.66,.38]);b=fig.add_axes([.16,.13,.30,.25]);c=fig.add_axes([.64,.13,.30,.25])
for i,row in enumerate(sim['methods']):
 y=5-i;hv,he=interval(f'group/{METHOD_KEYS[i]}/hard');sv,se=interval(f'group/{METHOD_KEYS[i]}/soft')
 a.plot([hv,sv],[y+.12,y-.12],c=LIGHT,lw=.7)
 point(a,hv,y+.12,he,color=TEAL);point(a,sv,y-.12,se,color=CLAY,marker='s')
a.set(xlim=(-1,65),ylim=(-.5,5.6),xticks=[0,20,40,60],yticks=range(6),yticklabels=METHOD_NAMES[::-1],xlabel=T('固定分母身份 top-1（%）','Fixed-denominator identity top-1 (%)'))
a.plot([],[],'o',c=TEAL,ms=3.6,label=T('原规则','Original'));a.plot([],[],'s',c=CLAY,ms=3.6,label=T('Ward软规则','Ward-soft'))
a.legend(loc='lower center',bbox_to_anchor=(.53,1.02),ncol=2,frameon=False,handlelength=.7);letter(a,'a')
for y,val,label in [(2,100,'2400/2400'),(1,1107/24,'1107/2400'),(0,494/24,'494/2400')]:
 b.barh(y,val,height=.50,color=GRAY);b.text(val+2,y,label,va='center',fontsize=7,color=DARK)
b.set(xlim=(0,145),ylim=(-.6,2.6),xticks=[0,50,100],yticks=[0,1,2],yticklabels=[T('密度','Density'),T('完整','Complete'),T('正确','True')],xlabel=T('真值候选资格（%）','True-candidate eligibility (%)'));letter(b,'b')
label_pos=[(35,103),(3,94),(3,75),(65,59),(54,27),(3,46)]
for i,row in enumerate(sim['methods']):
 x=row['pair_recall']['value']*100;y=row['pair_precision']['value']*100
 c.scatter(x,y,s=16,c=GRAY,edgecolor='white',lw=.4,zorder=3)
 c.annotate(METHOD_NAMES[i],(x,y),xytext=label_pos[i],textcoords='data',fontsize=7,
  ha='left',va='center',arrowprops=dict(arrowstyle='-',lw=.45,color=LIGHT,shrinkA=2,shrinkB=3))
c.set(xlim=(0,105),ylim=(0,111),xticks=[0,50,100],yticks=[0,50,100],xlabel=T('同地配对召回（%）','Pair recall (%)'),ylabel=T('精度（%）','Precision (%)'));letter(c,'c')
finish(fig,'fig4-grouping-and-rules',[a,b,c],['a','b','c'],rows=[['b','c']],why='The wide outcome panel retains all twelve original confidence intervals without duplicating a spectral inset. The lower panels separate candidate eligibility from precision/recall; c is a bivariate diagnostic, not a line joining different metrics. Same coordinates, catalog and 2400-route denominator; Brownian sigma=.5, lambda=.0003, with the recorded soft-branch exception.')

# 5: a confusion hero, counts of errors, and counts changed by the utility arm.
fig=figure(3.85);a=fig.add_axes([.235,.27,.40,.64]);b=fig.add_axes([.81,.59,.15,.31]);c=fig.add_axes([.81,.15,.15,.22])
cm=np.array(act['arms']['joint']['confusion']);norm=cm/cm.sum(axis=1)[:,None]
cmap=LinearSegmentedColormap.from_list('retained_activity',['#E2EEEE',TEAL]);cmap.set_bad('#EDF1F3')
im=a.imshow(np.ma.masked_where(cm==0,norm),cmap=cmap,vmin=0,vmax=1,aspect='auto',interpolation='nearest')
for i in range(8):
 for j in range(8):
  if cm[i,j]:a.text(j,i,str(cm[i,j]),ha='center',va='center',fontsize=8,color='white' if norm[i,j]>.65 else INK)
longzh=['柜门交互','静止','躺下（过渡）','躺卧（持续）','坐下','起立','直立/坐姿','行走'];shortzh=['柜门','静止','躺下','躺卧','坐下','起立','直立/坐姿','行走']
longen=['Cabinet','Idle','Lie down','Lying','Sit down','Stand up','Upright†','Walk']
a.set(xticks=range(8),xticklabels=longen if EN else shortzh,yticks=range(8),
 yticklabels=[f'{n} ({int(cm[i].sum())})' for i,n in enumerate(longen if EN else longzh)])
a.tick_params(axis='x',labelrotation=55)
for tx in a.get_xticklabels():tx.set_ha('right');tx.set_rotation_mode('anchor')
a.set_xticks(np.arange(9)-.5,minor=True);a.set_yticks(np.arange(9)-.5,minor=True);a.grid(which='minor',c='white',lw=.6);a.tick_params(which='minor',length=0);letter(a,'a')
cbax=fig.add_axes([.659,.27,.012,.64]);cb=fig.colorbar(im,cax=cbax,ticks=[0,.5,1]);cb.ax.set_yticklabels(['0','50','100']);cb.set_label(T('行比例（%）','Row proportion (%)'),fontsize=7,labelpad=1)
parts={r['part']:r['accuracy'] for r in act['arms']['joint']['per_part']}
for i,part in enumerate(['T-G1a','T-G1b','T-G2a','T-G2b','T-Ba','T-Bb']):
 r=parts[part];y=5-i;errors=r['denominator']-r['numerator']
 if errors:b.barh(y,errors,height=.5,color=CLAY)
 else:b.plot(0,y,'o',ms=3,mfc='white',mec=GRAY,mew=.7,clip_on=False)
b.set(xlim=(0,3.5),ylim=(-.6,5.6),xticks=[0,1,2,3],yticks=range(6),
 yticklabels=[f'{n} ({parts["T-"+n]["denominator"]})' for n in ['Bb','Ba','G2b','G2a','G1b','G1a']],xlabel=T('错误窗数','Errors'));letter(b,'b')
for y,arm in [(2,'phone'),(1,'watch'),(0,'joint')]:
 row=act['utility'][arm];delta=row['hz20']['numerator']-row['raw']['numerator'];col=TEAL if arm=='joint' else GRAY
 if delta:
  c.plot([0,delta],[y,y],c=col,lw=1);c.plot(delta,y,'o',c=col,ms=3.6);c.text(delta+.13,y,f'+{delta}',va='center',fontsize=7)
 else:c.text(.08,y,T('未变','Unchanged'),va='center',fontsize=7,color=GRAY)
c.set(xlim=(0,2.8),ylim=(-.6,2.6),xticks=[0,1,2],yticks=[0,1,2],yticklabels=[T('联合','Joint'),T('手表','Watch'),T('手机','Phone')],xlabel=T('正确窗变化','Change in correct'));letter(c,'c')
finish(fig,'fig5-action-and-utility',[a,b,c],['a','b','c'],cols=[['b','c']],why='The frozen joint eight-class confusion is the hero. b encodes error counts on a zero-based count axis and retains each session support, rather than magnifying near-ceiling percentages. c encodes paired changes in correct counts, denominator 71, and explicitly writes unchanged instead of a zero-length bar. The colorbar is adjacent to the matrix; device identity is written, not assigned a hue.')

# 6: geometry and probability, then full interval tracks and marker diagnostics.
fig=figure(5.55);a=fig.add_axes([.075,.73,.32,.22]);b0=fig.add_axes([.59,.86,.35,.09]);b1=fig.add_axes([.59,.73,.35,.09]);c=fig.add_axes([.205,.405,.735,.22]);d=fig.add_axes([.15,.08,.31,.20]);e=fig.add_axes([.70,.08,.24,.20])
base=2.03;x0=(.91**2+base**2-1.5**2)/(2*base);y0=np.sqrt(.91**2-x0*x0);x3=(1.18**2+base**2-1.02**2)/(2*base);y3=-np.sqrt(1.18**2-x3*x3);pts=np.array([[x0,y0],[0,0],[base,0],[x3,y3]])
plane=np.array([[-.50,-1.0],[2.6,-1.0],[2.6,1.25],[-.50,1.25]])
plane_base=project(plane,-.07);plane_top=project(plane)
a.add_patch(Polygon(np.vstack([plane_base[0],plane_base[1],plane_top[1],plane_top[0]]),fc='#CCD9E0',ec='none'))
a.add_patch(Polygon(plane_top,fc='#F0F4F6',ec='none'))
pp=project(pts)
for k,col,ls in [(0,TEAL,'-'),(3,DARK,'--')]:
 q=pp[[1,k,2]];a.plot(*np.vstack([q,q[0]]).T,c=col,lw=.9,ls=ls)
a.plot(*pp[[0,3]].T,c=CLAY,lw=.7,ls=':');a.scatter(*pp.T,c=[TEAL,DARK,DARK,DARK],s=22,edgecolor='white',lw=.55,zorder=4)
for i,offset in enumerate([(0,9),(-12,1),(12,1),(0,-12)]):a.annotate('P'+str(i),pp[i],xytext=offset,textcoords='offset points',ha='center',va='center',fontsize=7)
# Place edge labels against final physical geometry; never across an edge.
allpp=np.vstack([plane_top,plane_base]);low=allpp.min(axis=0);high=allpp.max(axis=0)
a.set(xlim=(low[0]-.15,high[0]+.15),ylim=(low[1]-.15,high[1]+.15),xticks=[],yticks=[]);a.set_aspect('equal',adjustable='box');a.axis('off')
fig.canvas.draw()
occupied=[text.get_window_extent(fig.canvas.get_renderer()).padded(1.5*fig.dpi/72) for text in a.texts]
segments=[]
for line in a.lines:
 points=a.transData.transform(line.get_xydata());segments.extend(zip(points[:-1],points[1:]))
def crosses_rectangle(start,end,bb):
 dx,dy=end-start;lower=0.;upper=1.
 for v,q in [(-dx,start[0]-bb.x0),(dx,bb.x1-start[0]),(-dy,start[1]-bb.y0),(dy,bb.y1-start[1])]:
  if abs(v)<1e-12:
   if q<0:return False
  else:
   t=q/v
   if v<0:lower=max(lower,t)
   else:upper=min(upper,t)
   if lower>upper:return False
 return True
edge_specs=[(0,1,2,'91'),(0,2,1,'150'),(1,3,2,'118'),(2,3,1,'102'),(1,2,0,'203'),(0,3,1,'119†')]
for i,j,k,label in edge_specs:
 midpoint=(pp[i]+pp[j])/2;dv=a.transData.transform(midpoint)-a.transData.transform((pp[i]+pp[j]+pp[k])/3)
 dv=dv/max(np.linalg.norm(dv),1e-9);placed=False
 for radius in [9,13,17,21,25,29,33]:
  if placed:break
  for angle in [0,25,-25,50,-50,90,-90,180]:
   theta=np.deg2rad(angle);offset=radius*np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])@dv
   text=a.annotate(label,midpoint,xytext=offset,textcoords='offset points',ha='center',va='center',fontsize=7,color=CLAY if '†' in label else DARK)
   fig.canvas.draw();bb=text.get_window_extent(fig.canvas.get_renderer()).padded(1.4*fig.dpi/72)
   blocked=any(crosses_rectangle(start,end,bb) for start,end in segments) or any(bb.overlaps(box) for box in occupied)
   if not blocked:
    occupied.append(bb);placed=True;break
   text.remove()
 if not placed:raise RuntimeError('No uncluttered edge-label position: '+label)
allpp=np.vstack([plane_top,plane_base]);low=allpp.min(axis=0);high=allpp.max(axis=0)
a.set(xlim=(low[0]-.15,high[0]+.15),ylim=(low[1]-.15,high[1]+.15),xticks=[],yticks=[]);a.set_aspect('equal',adjustable='box');a.axis('off');letter(a,'a')
fig.text(.075,.682,T('cm · †119实测 / 113.2重建','cm · †119 measured / 113.2 fitted'),fontsize=7,color=DARK)
for ax,rid in [(b0,'R1'),(b1,'R2')]:
 series=pilot['events'][rid]['series'];ax.plot([r['s'] for r in series],[r['p_walk_phone'] for r in series],c=DARK,lw=.7)
 ax.axhline(.3,c=TEAL,lw=.6,ls=(0,(4,2)));ax.set(xlim=(0,210),ylim=(0,1.06),yticks=[0,1],xticks=[0,70,140,210],ylabel=rid)
 if ax is b0:ax.tick_params(axis='x',labelbottom=False)
 else:ax.set_xlabel(T('时间（s）','Time (s)'))
letter(b0,'b')
windows=np.array([[50,58],[68,76],[86,94],[104,112],[122,130],[140,148],[158,166],[176,184]])
for yp,ya,rid in [(3,2,'R1'),(1,0,'R2')]:
 for j,(start,end) in enumerate(windows):
  c.broken_barh([(start,end-start)],(yp-.28,.56),facecolors=PALE,edgecolors=GRAY,lw=.4)
  c.text((start+end)/2,yp,'ACBACBAC'[j],ha='center',va='center',fontsize=7)
 for event in pilot['events'][rid]['events']:
  c.broken_barh([(event['start'],event['end']-event['start'])],(ya-.28,.56),facecolors=LIGHT,edgecolors='none')
  for start,end in windows:
   low=max(start,event['start']);high=min(end,event['end'])
   if high>low:c.broken_barh([(low,high-low)],(ya-.28,.56),facecolors=TEAL,edgecolors='none')
c.set(xlim=(0,210),ylim=(-.5,3.6),yticks=[0,1,2,3],
 yticklabels=[T('R2 输出 89.8%','R2 output 89.8%'),T('R2 计划','R2 planned'),T('R1 输出 87.5%','R1 output 87.5%'),T('R1 计划','R1 planned')],
 xticks=[0,40,80,120,160,210],xlabel=T('时间（s）','Time (s)'))
c.plot([],[],lw=4,c=LIGHT,label=T('自动区间','Automatic'));c.plot([],[],lw=4,c=TEAL,label=T('窗内重叠','Overlap'))
c.legend(loc='lower right',bbox_to_anchor=(1,1.02),ncol=2,frameon=False,handlelength=1.3);letter(c,'c')
vis=pilot['feature_distances']['visits'];order=sorted(range(16),key=lambda i:(vis[i]['declared_marker'],i));dm=np.array(pilot['feature_distances']['matrices']['joint'])[np.ix_(order,order)];np.fill_diagonal(dm,np.nan);vm=5*np.ceil(np.nanmax(dm)/5)
cmap=LinearSegmentedColormap.from_list('primary_distances',['#EEF3F4','#B9D8DA','#70AAAE','#0B7377','#174A51']);cmap.set_bad('#DDE5E9')
im=d.imshow(np.ma.masked_invalid(dm),cmap=cmap,vmin=0,vmax=vm,aspect='auto',interpolation='nearest');ticks=[]
for i in range(16):d.plot([i-.16,i+.16],[i,i],c=GRAY,lw=.5)
nearest=next(row['nearest'] for row in station['rows'] if row['arm']=='joint');inverse={original:new for new,original in enumerate(order)}
for original in range(16):d.scatter(inverse[nearest[original]],inverse[original],s=12,facecolor='none',edgecolor='#253D49',lw=.55,zorder=4)
for marker in ['P0','P1','P2','P3']:
 ix=[j for j,i in enumerate(order) if vis[i]['declared_marker']==marker];ticks.append((np.mean(ix),marker))
 if max(ix)<15:d.axhline(max(ix)+.5,c='white',lw=.6);d.axvline(max(ix)+.5,c='white',lw=.6)
d.set(xticks=[x for x,_ in ticks],xticklabels=[s for _,s in ticks],yticks=[x for x,_ in ticks],yticklabels=[s for _,s in ticks]);letter(d,'d')
cbax=fig.add_axes([.48,.08,.012,.20]);cb=fig.colorbar(im,cax=cbax,ticks=[0,vm/2,vm]);cb.set_label(T('特征距离','Feature distance'),fontsize=7,labelpad=1)
for i,row in enumerate(station['rows']):
 y=2-i;low,high=row['null_hit_quantiles95'];obs=row['observed']['numerator'];col=TEAL if row['arm']=='joint' else DARK
 e.plot([low,high],[y,y],c=PALE,lw=5,solid_capstyle='round');e.scatter(row['null_mean']['value']*16,y,c=GRAY,s=12,zorder=3)
 e.scatter(obs,y,c=col,s=22,edgecolor='white',lw=.4,zorder=4);e.text(obs,y+.32,f'{obs}/16',ha='center',fontsize=7)
e.set(xlim=(-.5,16),ylim=(-.5,2.85),xticks=[0,8,16],yticks=[0,1,2],yticklabels=[T('联合','Joint'),T('手表','Watch'),T('手机','Phone')],xlabel=T('标记命中 / 16','Marker hits / 16'));letter(e,'e')
finish(fig,'fig6-real-pilot',[a,b0,b1,c,d,e],['a','b0','b1','c','d','e'],rows=[['d','e']],cols=[['b0','b1']],why='The oblique plane is a coordinate reference, not a room boundary. Six measured lengths are labelled on the reconstructed planar geometry; the dagger marks the inconsistent cross-edge. Probabilities are separate round tracks, never shifted in time. Planned and automatic intervals have separate rows, preserving all out-of-window output; teal consistently encodes overlap under the frozen setting in both rounds. Gray dashes mask self-distance. Hollow circles show the existing frozen joint nearest-neighbor indices, without selecting new neighbors. e retains an exploratory null-distribution range, not a hit-rate confidence interval. Unequal bottom widths are deliberate for matrix versus three-row diagnostic.')

# 7: stability of one criterion does not imply stable interval counts.
fig=figure(2.6);a=fig.add_axes([.12,.25,.34,.62]);b=fig.add_axes([.60,.25,.34,.62]);thresholds=[.3,.4,.5,.6,.7]
for rid,col,ls in [('R1',DARK,'-'),('R2',GRAY,'--')]:
 values=[];lower=[];upper=[];selected=[]
 for threshold in thresholds:
  same=[r[rid]['mean_frac'] for r in sens if r['thr']==threshold];assert len(same)==6 and len(set(same))==1;values.append(same[0]*100)
  counts=[r[rid]['events_total'] for r in sens if r['thr']==threshold];lower.append(min(counts));upper.append(max(counts))
  selected.append(next(r[rid]['events_total'] for r in sens if r['thr']==threshold and r['min_dwell']==4 and r['merge_gap']==0))
 a.plot(thresholds,values,color=col,ls=ls,marker='o',ms=3.2,lw=1)
 a.scatter(.3,values[0],s=36,facecolor='white',edgecolor=TEAL,lw=1,zorder=5)
 a.text(.73,values[-1]+(-.6 if rid=='R1' else .1),rid,c=col,va='center',fontsize=7)
 x=np.array(thresholds)+(-.006 if rid=='R1' else .006)
 b.errorbar(x,selected,yerr=[np.array(selected)-lower,np.array(upper)-selected],fmt='o',ms=3,color=col,**ERR)
 b.plot(x,selected,color=col,lw=1,ls=ls,drawstyle='steps-mid')
 end_y=10.5 if rid=='R1' else 7.4
 b.annotate(rid,(x[-1],selected[-1]),xytext=(.73,end_y),ha='left',va='center',fontsize=7,color=col,
  arrowprops=dict(arrowstyle='-',lw=.5,color=col,shrinkA=2,shrinkB=3))
a.annotate(T('冻结0.3','Frozen 0.3'),(.3,87.5),xytext=(.35,81.6),fontsize=7,color=TEAL,
 arrowprops=dict(arrowstyle='-',color=TEAL,lw=.55,shrinkA=2,shrinkB=3))
a.set(xlim=(.275,.79),ylim=(80,100),xticks=thresholds,yticks=[80,90,100],xlabel=T('行走概率阈值','Walk-probability threshold'),ylabel=T('平均计划窗覆盖（%）','Mean planned-window coverage (%)'));grid(a);letter(a,'a')
b.set(xlim=(.275,.79),ylim=(0,12),xticks=thresholds,yticks=[0,4,8,12],xlabel=T('行走概率阈值','Walk-probability threshold'),ylabel=T('全段自动事件数','Full-record event count'));grid(b);letter(b,'b')
finish(fig,'fig7-gate-sensitivity',[a,b],['a','b'],rows=[['a','b']],why='Rounds are repeated records in gray, not treatment/control colors. Teal open circles and the callout identify the frozen threshold. Coverage has a declared 80-100% axis; counts start at zero. Error bars show the six-setting min-max range, not statistical uncertainty. Direct labels use leaders where the selected count traces coincide; no observed value is moved vertically.')
print(json.dumps({'figures':7,'language':args.language,'width_mm':160,'new_scoring':False,'new_model_fitting':False},ensure_ascii=False))
