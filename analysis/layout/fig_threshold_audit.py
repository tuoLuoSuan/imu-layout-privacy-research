"""Count-labelled sampled grid and numeric marginal curves; no surface fill."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
from . import exp_threshold_fine as F


def build(raw,out,audit_tools):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    sys.path.insert(0,str(audit_tools))
    from audit_panel_alignment import require_matplotlib_panel_alignment
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rows=json.loads(Path(raw).read_text(encoding='utf-8'))['rows']
    grids=[F.summarise(rows,F.NORMAL),F.summarise(rows,F.EXTENDED)]
    plt.rcParams.update({'font.family':['Arial','SimSun'],'font.size':8,
                         'pdf.fonttype':42,'svg.fonttype':'none','axes.unicode_minus':False})
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,104/25.4))
    fig.subplots_adjust(left=.075,right=.88,bottom=.29,top=.82,wspace=.20)
    records=[]
    for ai,(ax,grid,n) in enumerate(zip(axes,grids,[11,13])):
        z=np.array([[grid[f'dispersed|{c:.2f}|{v}']['hits']/n for c in F.COVERAGES] for v in F.VISITS])
        im=ax.imshow(z,origin='lower',vmin=0,vmax=1,cmap='Blues',aspect='auto',interpolation='none')
        for j,v in enumerate(F.VISITS):
            for i,c in enumerate(F.COVERAGES):
                cell=grid[f'dispersed|{c:.2f}|{v}'];censored=cell['censored']+cell['missing']
                if censored:ax.add_patch(Rectangle((i+.24,j+.22),.23,.23,facecolor='#f2f2f2',hatch='////',edgecolor='#7b8791',linewidth=0,rasterized=True))
                text=f"{cell['hits']}/{n}"+(f'\nc{censored}' if censored else '')
                ax.text(i,j,text,ha='center',va='center',fontsize=7,color='white' if z[j,i]>.65 else '#253544')
                records.append({'cohort':'restricted11' if ai==0 else 'geometry13','visits':v,'coverage':c,**cell})
        ax.set_xticks(range(len(F.COVERAGES)),[str(round(100*c)) for c in F.COVERAGES]);ax.set_yticks(range(len(F.VISITS)),F.VISITS)
        ax.set_xlabel('行走覆盖目标 (%)');ax.set_ylabel('独立交互次数' if ai==0 else '')
        ax.set_title(('A  受限开发集（11房）' if ai==0 else 'B  几何有效对照（13房）'),loc='left',fontsize=10,pad=12)
        for c,v,color in [(.95,5,'#d99520'),(.98,2,'#aa5577'),(.94,5,'#aa5577')]:
            i=F.COVERAGES.index(c);j=F.VISITS.index(v)
            for y in [j-.45,j+.45]:ax.plot([i-.44,i+.44],[y,y],color=color,lw=2,solid_capstyle='butt')
        ax.tick_params(length=0)
    ca=fig.add_axes([.905,.29,.015,.53]);fig.colorbar(im,cax=ca,ticks=[0,.5,1],format=lambda v,pos:f'{100*v:.0f}%')
    fig.text(.075,.94,'四件家具中心均 ≤0.5 m：每格标注命中／固定房间分母',fontsize=11)
    fig.text(.075,.17,'金线：95% / 5次。紫线：11房在≥80%达标线上的两个采样最小点。',fontsize=8)
    fig.text(.075,.115,'角部斜纹与 c：覆盖或交互不可执行；保守比例保留这些房间。列为离散测试档。',fontsize=8)
    fig.text(.075,.06,'理想坐标、给定外框与尺寸；开发集结果，非真实IMU总体阈值。无曲面插值。',fontsize=8)
    fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=out/'activity-heatmap.alignment.json')
    fig.savefig(out/'activity-heatmap.png',dpi=600,facecolor='white')
    fig.savefig(out/'activity-heatmap.pdf',facecolor='white')
    fig.savefig(out/'activity-heatmap.svg',facecolor='white')
    plt.close(fig)
    with (out/'activity-heatmap.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    fig,ax=plt.subplots(figsize=(183/25.4,90/25.4));fig.subplots_adjust(left=.10,right=.96,bottom=.27,top=.85)
    grid=grids[0]
    for policy,v,label,style in [('dispersed',2,'分散交互 2次','o-'),('dispersed',5,'分散交互 5次','s-'),('repeat',6,'同点重复 6次','^--')]:
        values=[100*grid[f'{policy}|{c:.2f}|{v}']['hits']/11 for c in F.COVERAGES]
        ax.plot(np.array(F.COVERAGES)*100,values,style,label=label,ms=4,lw=1.4)
    ax.axhline(80,color='#969da4',ls=':',lw=1);ax.set(ylim=(0,105),xlim=(84.5,100.5),xticks=[85,88,90,92,94,95,96,98,100],ylabel='四件中心达标比例 (%)',xlabel='行走覆盖目标 (%)')
    ax.legend(loc='upper left',ncol=3,fontsize=8);ax.set_title('同一11房、不同交互策略的已测覆盖响应',loc='left',pad=12)
    fig.text(.10,.08,'点为实测格值；连线只辅助阅读，不代表格间实验或单调性保证。每个点固定分母11。',fontsize=8)
    fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=out/'coverage-marginals.alignment.json')
    fig.savefig(out/'coverage-marginals.png',dpi=600,facecolor='white')
    fig.savefig(out/'coverage-marginals.pdf',facecolor='white')
    fig.savefig(out/'coverage-marginals.svg',facecolor='white')
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',required=True);p.add_argument('--out',required=True);p.add_argument('--audit-tools',required=True);a=p.parse_args();build(a.raw,a.out,a.audit_tools)
