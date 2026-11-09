"""Corrected matched comparisons; preserves DS's v3 and its original figures."""
import csv
from decimal import Decimal, ROUND_HALF_UP
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, 'D:/Application/Codex/skills/nature-figure/scripts')
from audit_panel_alignment import require_matplotlib_panel_alignment

OUT = Path(__file__).resolve().parent
plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'Arial'],
                     'pdf.fonttype': 42, 'svg.fonttype': 'none', 'font.size': 7,
                     'axes.spines.top': False, 'axes.spines.right': False})
BLUE, TEAL, GOLD, GRAY, INK = '#306b92', '#29988f', '#b78624', '#8b98a1', '#233c4b'
PANELS = [
 ('a', '接触落点干预', '同10,000房；100%覆盖 / 14次',
  [('同点重复',3978,10000,GRAY),('分散接触',6470,10000,BLUE)], '+24.92 pp；相同路线与访次'),
 ('b', '声明先验干预', '同1,000开发房；100%覆盖 / 14次',
  [('原候选方案',651,1000,GRAY),('桌墙间隙≤0.15 m',826,1000,TEAL)], '+17.50 pp；不是新增传感观测'),
 ('c', '有限解码干预', '同1,000确认房；相同节点上限',
  [('旧方案',851,1000,GRAY),('depth_portfolio',945,1000,GOLD)], '+9.40 pp；实际计算量不同'),
 ('d', '设备位姿替换诊断', '同32条记录；相同预测动作',
  [('原始手机＋手表',17,32,TEAL),('真值位姿替换',26,32,BLUE)], '+28.125 pp；条件诊断差，非上界'),
]


def wilson(k,n):
    p=k/n; z=1.959963984540054; den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    rad=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return 100*np.array([mid-rad,mid+rad])


fig, axes = plt.subplots(2,2,figsize=(183/25.4,146/25.4))
fig.subplots_adjust(left=.235,right=.97,bottom=.22,top=.80,wspace=1.02,hspace=1.15)
source=[]
for ax,(letter,title,sub,rows,effect) in zip(axes.flat,PANELS):
    for i,(label,k,n,col) in enumerate(rows):
        y=1-i; value=100*k/n; lo,hi=wilson(k,n)
        ax.errorbar(value,y,xerr=np.array([[value-lo],[hi-value]]),fmt='o',color=col,
                    markersize=4.4,elinewidth=1.05,capsize=2,zorder=3)
        display=(Decimal(k)*100/Decimal(n)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        ax.text(0,y+.24,f'{k:,}/{n:,} = {display}%',fontsize=6.4,color=col,va='bottom')
        source.append({'panel':letter,'arm':label,'success':k,'denominator':n,'percent':value,
                       'wilson_lower':lo,'wilson_upper':hi,'condition':sub})
    ax.set_yticks([1,0],labels=[r[0] for r in rows],fontsize=6.7)
    ax.tick_params(axis='y',length=0,pad=6)
    ax.set(xlim=(0,100),ylim=(-.48,1.64),xticks=[0,25,50,75,100])
    ax.tick_params(axis='x',labelsize=6.3,length=2.5,color=GRAY)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color(GRAY)
    ax.set_xlabel('整屋中心全中率（%）',fontsize=6.8,labelpad=3)
    ax.text(-.57,1.25,letter,transform=ax.transAxes,fontweight='bold',fontsize=10,color=INK)
    ax.text(-.43,1.25,title,transform=ax.transAxes,fontweight='bold',fontsize=8.2,color=INK)
    ax.text(-.43,1.075,sub,transform=ax.transAxes,fontsize=6.7,color=GRAY)
    ax.text(-.43,-.43,effect,transform=ax.transAxes,fontsize=6.6,color=INK)

fig.text(.03,.965,'位置泄露的条件测量：每项增益在各自配对集合内计算',fontsize=10.6,weight='bold',color=INK)
fig.text(.03,.917,'几何可恢复性、原始设备输入与真实复放分别报告；不把不同集合串成一条改进曲线。',fontsize=7.3,color=GRAY)
fig.text(.03,.105,'真实单房原生产链复放（n=1）',fontsize=7.5,weight='bold',color=INK)
fig.text(.03,.065,'床 0.112 m　桌 0.110 m　柜 0.093 m　椅 0.233 m；四件中心达标，不作为成功率估计。',fontsize=7,color=INK)
fig.text(.03,.022,'误差线为逐房/逐记录 Wilson 95% 区间。a–c为理想轨迹几何层；d为同生成域监督设备层。',fontsize=6.4,color=GRAY)
fig.canvas.draw()
require_matplotlib_panel_alignment(fig,json_out=OUT/'fig0-corrected.alignment.json',
                                  overlay_svg=OUT/'fig0-corrected.alignment.svg',strict=True)
fig.savefig(OUT/'fig0-corrected.pdf',facecolor='white')
fig.savefig(OUT/'fig0-corrected.svg',facecolor='white')
fig.savefig(OUT/'fig0-corrected.png',dpi=600,facecolor='white')
fig.savefig(OUT/'fig0-corrected.tiff',dpi=600,facecolor='white',pil_kwargs={'compression':'tiff_lzw'})
with (OUT/'fig0-corrected-source.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=source[0]);w.writeheader();w.writerows(source)
plt.close(fig)
