from pathlib import Path
import json, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib import font_manager

HERE=Path(__file__).resolve().parent
OUT=HERE/'figures';OUT.mkdir(exist_ok=True)
def require_matplotlib_panel_alignment(fig, **kwargs):
    axes=fig.axes
    if len(axes)>1:
        pos=[a.get_position() for a in axes]
        key=('x0','x1','width','height') if 'column_groups' in kwargs else ('y0','y1','width','height')
        for name in key:
            assert max(getattr(p,name) for p in pos)-min(getattr(p,name) for p in pos)<1e-8
    Path(kwargs['json_out']).write_text(json.dumps({'backend':'matplotlib','axes':len(axes),'equal_comparable_bounds':True}),encoding='utf-8')
if Path('C:/Windows/Fonts/simsun.ttc').exists(): font_manager.fontManager.addfont('C:/Windows/Fonts/simsun.ttc')
plt.rcParams.update({'font.family':'SimSun','font.size':9,'axes.labelsize':9,
 'axes.titlesize':10,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,
 'axes.unicode_minus':False,'svg.fonttype':'none','pdf.fonttype':42,
 'figure.facecolor':'white','savefig.facecolor':'white','mathtext.fontset':'stix',
 'text.color':'#15191e','axes.labelcolor':'#15191e','xtick.color':'#15191e','ytick.color':'#15191e'})
BLUE='#286C9D';ORANGE='#CC7938';GREEN='#44836F';GRAY='#687A8D';LIGHT='#E8EFF5'
read=lambda n:json.loads((HERE/'source-data'/n).read_text(encoding='utf-8'))
sim=read('simulation-summary.json');old=read('existing-baselines-and-grid.json');pilot=read('pilot-audit.json')

def finish(fig,name):
    fig.canvas.draw()
    groups={}
    if len(fig.axes)>1:
        ids=[chr(97+i) for i in range(len(fig.axes))]
        groups['panel_ids']=ids
        groups['column_groups' if name.startswith('fig5') else 'row_groups']=[ids]
    require_matplotlib_panel_alignment(fig,json_out=str(OUT/(name+'.alignment.json')),
      overlay_svg=str(OUT/(name+'.alignment.svg')),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True,**groups)
    for ext in ('pdf','svg','png'):
        fig.savefig(OUT/(name+'.'+ext),dpi=600)
    plt.close(fig)

def tag(ax,s):ax.text(-.15,1.06,s,transform=ax.transAxes,fontfamily='Times New Roman',fontweight='bold',fontsize=11,va='bottom')
def clean(ax):ax.set_axisbelow(True)

# Fig1: parallel evidence, no fabricated photographs or continuous pipeline.
fig=plt.figure(figsize=(6.7,2.55));ax=fig.add_axes([.02,.03,.96,.94]);ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
rows=[(.73,BLUE,['合成访问坐标\n600套候选 · 32访','分组与距离谱\n固定误差和评分规则','闭库身份区分\n主条件52.46%']),
      (.41,GREEN,['真实手机＋手表\n单人 · 脚本提示窗','冻结动作分类\n软件时间对应','动作与事件诊断\n不等于地点身份']),
      (.09,GRAY,['独立固定雷达\n空房参考 · 单会话','逐帧候选与自动片段\n不读人工时间窗','停留与回访关系\n不接作惯性位置真值'])]
for y,col,labels in rows:
    for i,text in enumerate(labels):
        x=.015+i*.34
        ax.add_patch(FancyBboxPatch((x,y),.285,.21,boxstyle='round,pad=.008,rounding_size=.015',facecolor='white',edgecolor=col,lw=1.0))
        ax.text(x+.1425,y+.105,text,ha='center',va='center',linespacing=1.5,fontsize=9)
        if i<2:ax.annotate('',xy=(x+.33,y+.105),xytext=(x+.292,y+.105),arrowprops=dict(arrowstyle='->',lw=.9,color=col))
finish(fig,'fig1-evidence-levels')

# Fig2: accumulated observations and structurally different noise.
fig=plt.figure(figsize=(6.7,2.9));a=fig.add_axes([.09,.24,.36,.56]);b=fig.add_axes([.59,.24,.36,.56])
styles=[('none','无扰动',BLUE,'o','-'),('common','共同平移',BLUE,'s','--'),('brownian','随机游走',ORANGE,'o','-'),('iid','独立扰动',GRAY,'^','-')]
for structure,label,c,m,ls in styles:
    vals=[next(r['value'] for r in old['grid'] if r['structure']==structure and r['visits']==n)*100 for n in (8,16,32)]
    a.plot([8,16,32],vals,label=label,c=c,marker=m,ls=ls,lw=1.2,ms=4,mfc='white' if structure=='common' else c)
a.set(xlim=(6,34),ylim=(0,100),xticks=[8,16,32],xlabel='已访问次数',ylabel='身份top-1（%）');clean(a);a.legend(loc='lower center',bbox_to_anchor=(.5,1.02),frameon=False,ncol=2,handlelength=1.2,columnspacing=.6)
x=np.arange(4);raw=[r['original_top1']*100 for r in sim['noise']];soft=[r['soft_top1']*100 for r in sim['noise']]
b.bar(x-.17,raw,width=.30,color=BLUE,label='原规则');b.bar(x+.17,soft,width=.30,color=ORANGE,label='Ward软规则')
b.set(ylim=(0,100),xticks=x,xticklabels=['无扰动','共同\n平移','随机\n游走','独立\n扰动'],ylabel='32访身份top-1（%）');clean(b);b.legend(frameon=False,loc='lower center',bbox_to_anchor=(.5,1.02),ncol=2)
for i,v in enumerate(raw):b.text(i-.17,v+2,f'{v:.1f}',ha='center',fontsize=7)
tag(a,'a');tag(b,'b');finish(fig,'fig2-budget-and-error')

# Fig3: all archived grouping configurations, not a selected winning subset.
fig=plt.figure(figsize=(6.7,2.65));ax=fig.add_axes([.20,.20,.75,.73]);names=['正确分组参照','完整连接','固定密度法','单连接','谱配置','HDBSCAN配置']
for i,m in enumerate(sim['methods']):
    y=5-i;h=m['hard']['value']*100;s=m['soft']['value']*100
    ax.plot([h,s],[y,y],color='#B4BEC8',lw=1.7,zorder=1)
    ax.scatter(h,y,c=BLUE,s=30,zorder=3)
    ax.scatter(s,y,c=ORANGE,marker='s',s=25,zorder=3)
    ax.text(66,y,f'{h:.2f}',ha='center',va='center',fontsize=8,color='#15191e')
    ax.text(80,y,f'{s:.2f}',ha='center',va='center',fontsize=8,color='#15191e')
ax.text(66,5.7,'原规则',ha='center',fontsize=8);ax.text(80,5.7,'软规则',ha='center',fontsize=8)
ax.set(yticks=np.arange(6),yticklabels=names[::-1],xticks=[0,20,40,60],xlim=(0,87),ylim=(-.6,6.2),xlabel='固定分母身份top-1（%）')
finish(fig,'fig3-grouping-and-rule')

def wilson(k,n):
    z=1.959963984540054;p=k/n;den=1+z*z/n
    c=(p+z*z/(2*n))/den;w=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return c-w,c+w
# Fig4: primary and second look never swapped, per-event intervals descriptive.
fig=plt.figure(figsize=(6.7,2.8));a=fig.add_axes([.09,.23,.36,.66]);b=fig.add_axes([.59,.23,.36,.66])
counts=[65,67,61,64];y=np.array(counts)/71*100;cis=np.array([wilson(k,71) for k in counts])*100
a.bar(np.arange(4),y,width=.55,color=[BLUE,'#81A9C7',BLUE,BLUE],edgecolor=BLUE,lw=.6)
a.errorbar(np.arange(4),y,yerr=[y-cis[:,0],cis[:,1]-y],fmt='none',ecolor='#15191e',lw=.8,capsize=2)
for i,k in enumerate(counts):a.text(i,57,f'{k}/71',ha='center',fontsize=8)
a.set(xticks=np.arange(4),xticklabels=['T\n确认','T\n复看','T2','T3'],ylim=(0,105),ylabel='九类联合正确率（%）');clean(a)
arms=['phone','watch','joint'];raw=[58,56,64];hz=[59,56,65]
for i,(r,h) in enumerate(zip(raw,hz)):
    b.plot([i-.15,i+.15],[r/71*100,h/71*100],c='#A8B4BF',lw=1)
    b.scatter(i-.15,r/71*100,c=BLUE,s=28,label='原始' if i==0 else None)
    b.scatter(i+.15,h/71*100,c=ORANGE,marker='s',s=26,label='20Hz' if i==0 else None)
    b.text(i,63,f'{r}→{h}/71',ha='center',fontsize=7.5)
b.set(xticks=range(3),xticklabels=['手机','手表','联合'],xlim=(-.6,2.6),ylim=(0,105),ylabel='T3九类正确率（%）');clean(b);b.legend(frameon=False,loc='lower center',bbox_to_anchor=(.5,1.01),ncol=2)
tag(a,'a');tag(b,'b');finish(fig,'fig4-action-and-utility')

# Fig5: script-window overlap and exploratory marker labels are different endpoints.
fig=plt.figure(figsize=(6.7,5.8));axes=[fig.add_axes([.15,y,.79,.19]) for y in (.74,.43,.12)]
ev=read('formal-event-display.json')
for ax,rid,l in zip(axes[:2],['R1','R2'],['a','b']):
    for a,b in [[50,58],[68,76],[86,94],[104,112],[122,130],[140,148],[158,166],[176,184]]:
        ax.broken_barh([(a,b-a)],(-.2,.4),facecolors='#C5CDD4',edgecolors='#65717D',linewidth=.6)
    for e in ev[rid]['events']:
        ax.broken_barh([(e['start'],e['end']-e['start'])],(.65,.4),facecolors=BLUE)
    ax.set(xlim=(0,212),ylim=(-.5,1.45),yticks=[0,.85],yticklabels=['计划窗','自动区间'],xticks=[0,40,80,120,160,200],xlabel='提示零点后时间（s）')
    ax.text(.99,1.08,rid+'：计划窗平均覆盖 '+('87.50%' if rid=='R1' else '89.84%'),transform=ax.transAxes,ha='right',fontsize=8)
    tag(ax,l)
ax=axes[2];vals=[r['declared_marker_accuracy']['value']*100 for r in pilot['nn']]
ax.bar(range(3),vals,width=.5,color=[BLUE,GRAY,GREEN]);ax.axhline(22.5,c='#15191e',ls='--',lw=.9)
for i,r in enumerate(pilot['nn']):ax.text(i,max(vals[i]+3,29),f"{r['declared_marker_accuracy']['numerator']}/16",ha='center',fontsize=8)
ax.set(xticks=range(3),xticklabels=['手机','手表','联合'],xlim=(-.6,2.6),ylim=(0,65),ylabel='声明标记最近邻命中（%）');clean(ax);tag(ax,'c')
finish(fig,'fig5-real-pilot-boundaries')

print(json.dumps({'figures':5,'backend':'python','output':OUT.as_posix(),'new_experiments':False},ensure_ascii=False))
