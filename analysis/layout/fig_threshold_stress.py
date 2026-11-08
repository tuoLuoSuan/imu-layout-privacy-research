"""Fixed activity span under perturbation; mean and all 14 room-level values."""
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


def make(data,output,audit_scripts=None):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if audit_scripts:
        sys.path.insert(0,str(audit_scripts))
        from audit_panel_alignment import require_matplotlib_panel_alignment
    def room_values(scenario,budget):
        return [r['allowed_share'] for r in data['per_room'] if r['spread_fraction']==.9
                  and r['scenario']==scenario and r['max_bad_events']==budget]
    fig,axes=plt.subplots(1,2,figsize=(6.3,3.30))
    fig.subplots_adjust(left=.09,right=.975,bottom=.33,top=.82,wspace=.34)
    for x,scenario,color in zip(range(3),['clean','common_0.10','contraction_0.10'],['#A4ADB2','#A4ADB2','#B17C49']):
        values=room_values(scenario,0)
        axes[0].bar(x,np.mean(values),width=.65,color=color,alpha=.7)
        axes[0].scatter(x+np.linspace(-.14,.14,len(values)),values,s=7,color='#4B5358',alpha=.7,zorder=3)
    axes[0].set(xticks=range(3),xticklabels=['Clean','Common\n0.10 m','Contraction\n0.10 m'])
    scenarios=['false_positive','repeated_middle_false_positive','repeated_endpoints_false_positive']
    for j,(budget,color,label) in enumerate([(0,'#A4ADB2','All contacts'),(1,'#247B83','Allow one bad event')]):
        for x,scenario in enumerate(scenarios):
            values=room_values(scenario,budget);pos=x+(j-.5)*.32
            axes[1].bar(pos,np.mean(values),width=.29,color=color,alpha=.7,label=label if x==0 else None)
            axes[1].scatter(pos+np.linspace(-.08,.08,len(values)),values,s=6,color=color,alpha=.85,zorder=3)
    axes[1].set(xticks=range(3),xticklabels=['3 visits','4: middle\nrepeated','4: endpoints\nrepeated'])
    for ax in axes:ax.set(ylim=(0,1.06),yticks=[0,.5,1.],ylabel='Share meeting radius <=0.50 m')
    axes[0].set_title('a  Same span, different position errors',loc='left',fontweight='bold',pad=8)
    axes[1].set_title('b  One added false event',loc='left',fontweight='bold',pad=8)
    handles,labels=axes[1].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.53,.01),ncols=2,handlelength=1.3)
    fig.text(.5,.95,'Fixed 90% true bed-contact span; 0.20 m padding',ha='center',fontsize=8.)
    fig.text(.09,.15,'Bars: mean of 14 development rooms; dots: each room; geometric stress cases')
    fig.canvas.draw()
    if audit_scripts:require_matplotlib_panel_alignment(fig,json_out=output.with_suffix('.alignment.json'),strict=True,tolerance_pt=1.5)
    fig.savefig(output.with_suffix('.pdf'),facecolor='white')
    fig.savefig(output.with_suffix('.svg'),facecolor='white')
    fig.savefig(output.with_suffix('.png'),facecolor='white',dpi=300)
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',default=str(Path(__file__).with_name('threshold-stress-results.json')))
    p.add_argument('--output',required=True);p.add_argument('--audit-scripts');a=p.parse_args()
    make(json.loads(Path(a.results).read_text(encoding='utf-8')),a.output,a.audit_scripts)
