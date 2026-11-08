"""Measured effects and the distinction between accuracy and resolution."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({'font.family':['Arial','SimSun'],'font.size':7.3,'axes.titlesize':8.,
 'axes.labelsize':7.3,'xtick.labelsize':7.3,'ytick.labelsize':7.3,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,
 'pdf.fonttype':42,'svg.fonttype':'none','legend.frameon':False})


def make(data,out,audit_scripts):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if audit_scripts:
        sys.path.insert(0,str(audit_scripts))
        from audit_panel_alignment import require_matplotlib_panel_alignment
    def save(fig,name):
        fig.canvas.draw()
        if audit_scripts:
            require_matplotlib_panel_alignment(fig,json_out=out/(name+'.alignment.json'),strict=True,tolerance_pt=1.5)
        fig.savefig(out/(name+'.pdf'),facecolor='white')
        fig.savefig(out/(name+'.svg'),facecolor='white')
        fig.savefig(out/(name+'.png'),dpi=300,facecolor='white')
        plt.close(fig)
    spans=[0.,.25,.5,.75,1.,1.5]
    fig,ax=plt.subplots(figsize=(6.3,3.15))
    fig.subplots_adjust(left=.12,right=.975,bottom=.30,top=.85)
    for label,key,color,style in [('Central contacts','central_seed1','#9A9FA2',':'),
                                 ('Offset contacts, seed 1','offset_seed1','#247B83','-'),
                                 ('Offset contacts, seed 2','offset_seed2','#667EAA','--')]:
        selected=[data['contact_scans'][key]['summary'][f'bed:{s:.2f}'] for s in spans]
        ax.plot(spans,[r['hit_rate'] for r in selected],label=label,color=color,ls=style,lw=1.5,marker='o',ms=3)
    ax.plot(spans,[0.]*len(spans),color='#B17C49',lw=1.4,ls='-.',label='Radius <=0.50 m (all three)')
    ax.axhline(.8,color='#C3C5C7',lw=.7,ls='--')
    ax.set(xlim=(0,1.5),ylim=(-.04,1.04),xticks=[0,.5,1.,1.5],yticks=[0,.5,.8,1.],
           xlabel='Bed-contact span along the long axis (m)',ylabel='Fraction of 14 development rooms')
    ax.legend(loc='upper left',bbox_to_anchor=(-.01,-.30),ncols=2,columnspacing=1.3,handlelength=2.)
    fig.text(.12,.95,'Accurate points can precede a narrow feasible region',fontsize=8.,fontweight='bold')
    save(fig,'stage2-span-frontiers')

    fig,axes=plt.subplots(1,2,figsize=(6.3,3.15))
    fig.subplots_adjust(left=.09,right=.975,bottom=.30,top=.82,wspace=.34)
    labels=['Full','One bed\nanchor','Mean\nrepeated','No bed\nevent']
    matched=data['paired_ablation'];n=matched['collapse:bed']['n_scene_budgets']
    values=[matched['collapse:bed']['full_successes'],matched['single:bed']['edited_successes'],
            matched['collapse:bed']['edited_successes'],matched['drop:bed']['edited_successes']]
    axes[0].bar(range(4),np.array(values)/n,width=.64,color=['#247B83','#667EAA','#B17C49','#B4B9BC'])
    axes[0].set(xticks=range(4),xticklabels=labels,ylim=(0,1.05),yticks=[0,.5,1.],ylabel='Bed success fraction')
    axes[0].set_title('a  Matched scene-prefix pairs',loc='left',fontweight='bold',pad=8)
    arms=['TA','TA-cycle1','TA-cycle2'];colors=['#247B83','#9BA8B1','#BEC5CB'];x=np.arange(3)
    for j,(arm,c) in enumerate(zip(arms,colors)):
        row=next(r for r in data['semantics']['summary'] if r['budget_m']==96. and r['arm']==arm)
        axes[1].bar(x+(j-1)*.24,[row['success'][o]/row['n_rooms'] for o in ['bed','cab','chair']],
                    width=.22,color=c,label=['Correct classes','Cycle 1','Cycle 2'][j])
    axes[1].set(xticks=x,xticklabels=['Bed','Storage','Chair'],ylim=(0,1.05),yticks=[0,.5,1.],ylabel='Success fraction')
    axes[1].set_title('b  Same path and anchor positions',loc='left',fontweight='bold',pad=8)
    handles,legend_labels=axes[1].get_legend_handles_labels()
    fig.legend(handles,legend_labels,loc='lower center',bbox_to_anchor=(.52,.015),ncols=3,columnspacing=1.6,handlelength=1.3)
    fig.text(.5,.95,'Spatialised interaction evidence matters in this decoder',ha='center',fontsize=8.)
    fig.text(.09,.15,'a: 23 pairs / 14 rooms; b: 14 rooms at 96 m; geometry-level observations',fontsize=7.3)
    save(fig,'stage2-matched-evidence')

    fig,axes=plt.subplots(1,2,figsize=(6.3,3.15))
    fig.subplots_adjust(left=.10,right=.975,bottom=.25,top=.82,wspace=.34)
    for key,color,style in [('seed1','#247B83','-'),('seed2','#667EAA','--')]:
        rows=data['continuous_bed_resolution'][key]['summary']
        x=[r['spread_fraction'] for r in rows]
        axes[0].plot(x,[r['median_radius_upper_m'] for r in rows],color=color,ls=style,lw=1.5,marker='o',ms=2.6,label=key.replace('seed','Seed '))
        axes[1].plot(x,[r['success_rate'] for r in rows],color=color,ls=style,lw=1.5,marker='o',ms=2.6)
    axes[0].axhline(.5,color='#B17C49',ls=':',lw=.8)
    axes[1].axhline(.8,color='#B17C49',ls=':',lw=.8)
    axes[0].set(ylim=(0,1.4),yticks=[0,.5,1.],ylabel='Median conditional radius (m)')
    axes[1].set(ylim=(-.03,1.05),yticks=[0,.5,.8,1.],ylabel='Fraction with radius <=0.50 m')
    for ax in axes:ax.set(xlim=(0,1),xticks=[0,.5,.9,1.],xlabel='Contact span / bed extent (both axes)')
    axes[0].set_title('a  Continuous position envelope',loc='left',fontweight='bold',pad=8)
    axes[1].set_title('b  Conditional grid threshold: 0.90',loc='left',fontweight='bold',pad=8)
    axes[0].legend(loc='lower left')
    fig.text(.5,.95,'Three ideal bed contacts; known room and bed dimensions',ha='center',fontsize=8.)
    fig.text(.10,.045,'14 development rooms; 0.20 m padding; centre estimate, not a complete-layout threshold')
    save(fig,'stage2-continuous-bed-resolution')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',default=str(Path(__file__).with_name('stage2-results.json')))
    p.add_argument('--output',required=True);p.add_argument('--audit-scripts');a=p.parse_args()
    make(json.loads(Path(a.results).read_text(encoding='utf-8')),a.output,a.audit_scripts)
