"""Final-size figures for conditional activity leakage; no interpolated thresholds."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from .activity_diagnostics import ambiguity_witness

COLORS={'bed':'#247B83','desk':'#B17C49','cab':'#806997','chair':'#667EAA'}
plt.rcParams.update({'font.family':['Arial','SimSun'],'font.size':7.3,'axes.titlesize':8.,
 'axes.labelsize':7.3,'xtick.labelsize':7.3,'ytick.labelsize':7.3,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,
 'pdf.fonttype':42,'svg.fonttype':'none','legend.frameon':False})


def make(record,out,audit_scripts=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if audit_scripts:
        sys.path.insert(0,str(audit_scripts))
        from audit_panel_alignment import require_matplotlib_panel_alignment
    def save(fig,name):
        fig.canvas.draw()
        if audit_scripts:
            require_matplotlib_panel_alignment(fig,json_out=out/(name+'.alignment.json'),
                                               tolerance_pt=1.5,strict=True)
        fig.savefig(out/(name+'.pdf'),facecolor='white')
        fig.savefig(out/(name+'.svg'),facecolor='white')
        fig.savefig(out/(name+'.png'),dpi=300,facecolor='white')
        plt.close(fig)

    # a/b show two complete, static worlds with identical observable motion.
    witness=ambiguity_witness();path=witness['walk']
    fig,axes=plt.subplots(1,2,figsize=(6.3,3.15))
    fig.subplots_adjust(left=.09,right=.975,bottom=.17,top=.86,wspace=.30)
    for i,(ax,key) in enumerate(zip(axes,['first','second'])):
        for obj,b in witness[key].items():
            ax.add_patch(Rectangle(b[:2],b[2]-b[0],b[3]-b[1],facecolor=COLORS[obj],alpha=.35,
                                    edgecolor=COLORS[obj],linewidth=.8))
        ax.plot(path[:,0],path[:,1],color='#454B50',lw=.55,alpha=.75)
        b=witness[key]['cab'];ax.text((b[0]+b[2])/2,(b[1]+b[3])/2,'Cab',ha='center',va='center')
        ax.set(xlim=(0,4),ylim=(0,4),xlabel='x (m)',ylabel='y (m)',xticks=[0,2,4],yticks=[0,2,4])
        ax.set_aspect('equal');ax.set_title(chr(97+i)+'  Layout '+str(i+1),loc='left',fontweight='bold',pad=7)
    fig.text(.5,.95,'Same motion; cabinet centres differ by 1.40 m',ha='center',fontsize=8.)
    fig.text(.5,.025,'Coverage 67.6%  |  path radius 0.25 m  |  obstacle clearance 0.15 m',ha='center')
    save(fig,'activity-ambiguity')

    # Compare algorithmic availability and coverage, without claiming population risk.
    rows=record['fine_prefix_rows'];t=[r['T'] for r in rows]
    fig,axes=plt.subplots(1,2,figsize=(6.3,2.8))
    fig.subplots_adjust(left=.09,right=.975,bottom=.24,top=.82,wspace=.36)
    axes[0].step(t,[len(r['err']) for r in rows],where='post',color='#247B83',lw=1.8)
    axes[0].scatter([36.75,37.],[3,4],color='#247B83',s=15,zorder=3)
    axes[0].set(ylim=(2.8,4.2),yticks=[3,4],ylabel='Furniture emitted',xlabel='Available raw IMU (s)')
    axes[1].plot(t,[100*r['estimated_prefix_coverage'] for r in rows],color='#667EAA',lw=1.8)
    axes[1].set(ylim=(32,35),yticks=[32,33,34,35],ylabel='Estimated coverage (%)',xlabel='Available raw IMU (s)')
    for ax in axes:ax.set(xticks=[35,37,40],xlim=(35,40))
    for i,ax in enumerate(axes):ax.set_title(chr(97+i)+'  '+['New lying evidence','No coverage increase'][i],loc='left',fontweight='bold',pad=8)
    fig.text(.5,.94,'One development recording: first joint pass at 37.0 s',ha='center',fontsize=8.)
    fig.text(.5,.035,'Centre error <=0.50 m for each item; previous tested prefix 36.75 s fails',ha='center')
    save(fig,'activity-real-trigger')

    # Isolate observed effects and instability in a matched geometric benchmark.
    fig,axes=plt.subplots(1,2,figsize=(6.3,3.15))
    fig.subplots_adjust(left=.09,right=.975,bottom=.30,top=.83,wspace=.34)
    for label,policy,col,style in [('Local repeat','local_repeat','#879196','--'),('Dispersed','dispersed','#247B83','-')]:
        s=[r for r in record['experiments']['development']['summary'] if r['arm']=='TA-U' and r['policy']==policy]
        axes[0].plot([r['budget_m'] for r in s],[r['per_object_success']['bed'] for r in s],label=label,color=col,ls=style,lw=1.6,marker='o',ms=2.7)
    for label,run,col,style in [('Original','development','#247B83','-'),('New route','new_route_seed','#667EAA','--'),
                              ('Common offset','matched_noise','#B17C49',':')]:
        s=[r for r in record['experiments'][run]['summary'] if r['arm']=='TA-U' and r['policy']=='dispersed']
        axes[1].plot([r['budget_m'] for r in s],[r['success_rate'] for r in s],label=label,color=col,ls=style,lw=1.6,marker='o',ms=2.7)
    for i,ax in enumerate(axes):
        ax.set(xlim=(0,96),ylim=(-.03,1.05),xticks=[0,32,64,96],yticks=[0,.5,1],
               xlabel='Walking budget (m)',ylabel='Development-room success fraction')
        ax.axhline(.8,color='#B7BABC',ls=(0,(3,3)),lw=.6)
        ax.legend(loc='upper left',bbox_to_anchor=(0,-.31),ncols=2,fontsize=7.3,handlelength=1.4,columnspacing=1.)
        ax.set_title(chr(97+i)+'  '+['Bed: spatially diverse contact','All four: no stable threshold'][i],loc='left',fontweight='bold',pad=8)
    fig.text(.5,.95,'Fixed furniture, 14 development rooms; geometry-level observations',ha='center',fontsize=8.)
    save(fig,'activity-frontier')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',default=str(Path(__file__).with_name('activity-results.json')))
    p.add_argument('--output',required=True);p.add_argument('--audit-scripts');a=p.parse_args()
    make(json.loads(Path(a.results).read_text(encoding='utf-8')),a.output,a.audit_scripts)
