"""Measured activity matrix -> offline interactive 3D and static scientific preview.

Contract: show activity-coverage x visit-count response without forced monotonicity.
One static quantitative panel,183mm wide,>=8pt editable text,14 development-room
denominator. The plotted partial-recovery endpoint is separate from full layout
success and from a conditional continuous geometric certificate.
"""
import argparse,json,sys,shutil
from pathlib import Path
import numpy as np
from .activity_surface import threshold_frontier


def display_data(record):
    xs=list(record['protocol']['coverage_targets']);ns=list(record['protocol']['independent_visits'])
    scope=json.loads(Path(__file__).with_name('normal-room-scope.json').read_text(encoding='utf-8'))
    included=set(scope['included_rooms'])
    out={'x':[100*v for v in xs],'counts':ns,'data':{},'quality':record['quality_issues'],
         'normal_scope':scope,'cohort_sizes':{}}
    for cohort in ['normal','extended']:
     admitted=[r for r in record['rows'] if r['status']!='invalid_geometry' and (cohort=='extended' or r['scene'] in included)]
     n=len(set(r['scene'] for r in admitted));out['cohort_sizes'][cohort]=n
     for policy in ['repeat','dispersed']:
      for tol in [.5,1.]:
       for method in ['joint','continuous','finite']:
        for metric in ['objects','layout','certificate','bed','desk','cab','chair']:
            z=np.zeros((len(ns),len(xs)));avail=np.zeros_like(z);roomcov=np.zeros_like(z)
            for j,count in enumerate(ns):
              for i,x in enumerate(xs):
                rows=[r for r in admitted if r['policy']==policy and r['visits']==count and r['coverage_target']==x]
                values=[]
                for r in rows:
                    objects=r['objects'];values_obj=[];radii=[]
                    for obj in ['bed','desk','cab','chair']:
                        o=objects.get(obj,{})
                        err=o.get('joint_error_m' if method=='joint' else 'continuous_midpoint_error_m' if method=='continuous' else 'center_error_m')
                        radius=o.get('joint_radius_upper_m' if method=='joint' else 'continuous_midpoint_radius_m' if method=='continuous' else 'radius_upper_m')
                        values_obj.append(bool(r['executable'] and err is not None and err<=tol))
                        radii.append(bool(r['executable'] and radius is not None and radius<=tol))
                    value=np.mean(values_obj) if metric=='objects' else all(values_obj) if metric=='layout' else all(radii) if metric=='certificate' else values_obj[['bed','desk','cab','chair'].index(metric)]
                    values.append(value)
                z[j,i]=np.mean(values);avail[j,i]=sum(r['executable'] for r in rows)
                roomcov[j,i]=np.median([r['coverage_room'] for r in rows if 'coverage_room' in r])
            key='|'.join([cohort,policy,str(tol),method,metric])
            out['data'][key]={'z':(100*z).tolist(),'available':avail.tolist(),'room_coverage':(100*roomcov).tolist(),
                             'frontier':threshold_frontier(z,xs,ns)}
    return out


HTML=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>活动范围与布局泄露</title><script src="plotly.min.js"></script><style>
*{box-sizing:border-box}body{margin:0;background:#f6f7f8;color:#202b34;font:15px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif}
main{max-width:1400px;margin:auto;padding:28px 32px}header p{margin:4px 0;color:#61717b}h1{font-size:30px;line-height:1.3;margin:8px 0 12px;font-weight:650}small,.tag{font-size:12px}.tag{color:#177e78;letter-spacing:1px}
.notice{background:#fff6df;border-left:3px solid #b08434;padding:12px 16px;margin:20px 0;color:#735825}.controls{display:flex;gap:15px;flex-wrap:wrap;margin:16px 0 22px}label{font-size:12px;color:#63717b}select{display:block;background:white;border:1px solid #d9e0e4;border-radius:7px;padding:9px 30px 9px 10px;color:#243842;font:14px inherit}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:20px}#plot{height:650px;background:white;border-radius:10px}.card{background:#fff;padding:20px;border:1px solid #e3e8eb;border-radius:10px;margin-bottom:16px}.card h2{font-size:16px;margin:0 0 8px}.card p{font-size:13px;margin:6px 0;color:#596a75}.big{font-size:26px;color:#177e78;font-weight:650}.note{font-size:12px;color:#687780;margin-top:16px}.details{margin-top:20px;display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.details strong{font-size:14px}.details p{font-size:13px}.legendline{display:inline-block;width:20px;border-top:2px dashed #b08434;margin-right:6px;vertical-align:middle}@media(max-width:850px){main{padding:16px}.layout,.details{grid-template-columns:1fr}#plot{height:530px}}
</style><main><header><span class="tag">主实验 · 几何开发版</span><h1>活动到什么程度，布局开始可恢复？</h1><p>可拖动旋转，悬停查看每个测试网格点。主图采用固定名单的11间受限普通单间；可切换13间扩展对照。已知外框与家具名义尺寸。</p></header>
<div class="notice">当前是理想轨迹与动作位置的几何模拟，不是原始 IMU 多房验证。曲面保留原始波动，没有强行做成单调上升。</div>
<div class="controls"><label>适用域<select id="cohort"><option value="normal">普通单间（固定11房）</option><option value="extended">扩展场景对照（13房）</option></select></label><label>交互方式<select id="policy"><option value="dispersed">在可达家具上换位置交互</option><option value="repeat">反复在同一位置交互</option></select></label>
<label>Z轴指标<select id="metric"><option value="layout">整屋恢复成功率</option><option value="objects">平均家具恢复率</option><option value="bed">床位置恢复率</option><option value="desk">桌位置恢复率</option><option value="cab">柜／架位置恢复率</option><option value="chair">椅位置恢复率</option></select></label>
<label>中心位置容差<select id="tol"><option value="0.5">0.5 m（主标准）</option><option value="1.0">1.0 m（宽松敏感性）</option></select></label>
<label>中心估计方法<select id="method"><option value="joint">连续候选联合重建</option><option value="continuous">连续位置范围中心（诊断对照）</option><option value="finite">网格候选重建（对照）</option></select></label></div>
<div class="layout"><div><div id="plot"></div><p class="note">X：全部可行走空地的覆盖目标，半径0.25m；家具占地另计。Y：独立访次，不是重叠动作窗。曲面连接仅帮助读图；圆点才是测试值。</p></div>
<aside><div class="card"><h2>整屋阈值</h2><div id="threshold" class="big"></div><p id="thresholdnote"></p></div><div class="card"><h2>当前指标</h2><p id="meaning"></p><p><span class="legendline"></span>80%经验达标线</p><p id="maxvalue"></p></div><div class="card"><h2>分母与证据</h2><p id="cohortnote"></p><p>外框、目标类别和尺寸均给定；动作类别与坐标理想已知，行走人体净距假设0.15m。</p></div></aside></div>
<div class="details"><div class="card"><strong>范围不是累计路程</strong><p>在同一区域来回走会增加路程，不一定扩大空间覆盖。本图用覆盖比例，整间房覆盖的中位值可在每个点悬停查看。</p></div><div class="card"><strong>次数需要和位置一起读</strong><p>在同一家具同一位置精确重复，不会增加新的几何约束。两种交互方式用于检验次数背后的空间分布作用。</p></div><div class="card"><strong>整屋与部分恢复分开</strong><p>平均家具恢复率=被定位到容差内的家具比例。整屋成功要求床、桌、柜、椅在同一个输出里全部满足容差。</p></div></div></main>
<script>const D=__DATA__;
const el=id=>document.getElementById(id);let camera={eye:{x:1.65,y:-1.9,z:1.2}};
const names={objects:'平均家具恢复率',layout:'整屋恢复成功率',certificate:'整屋条件几何证书产出',bed:'床位置恢复率',desk:'桌位置恢复率',cab:'柜／架位置恢复率',chair:'椅位置恢复率'};
function draw(){let cohort=el('cohort').value,nrooms=D.cohort_sizes[cohort];let p=el('policy').value,t=el('tol').value,m=el('method').value,k=el('metric').value;let a=D.data[[cohort,p,t,m,k].join('|')];let full=D.data[[cohort,p,t,m,'layout'].join('|')];
let custom=a.z.map((row,j)=>row.map((z,i)=>[a.available[j][i],a.room_coverage[j][i]]));
let traces=[{type:'surface',x:D.x,y:D.counts,z:a.z,colorscale:[[0,'#eef3f2'],[.35,'#a7cdc6'],[.7,'#378f86'],[1,'#155e59']],cmin:0,cmax:100,opacity:.94,showscale:true,colorbar:{title:{text:'比例 (%)'},len:.7},customdata:custom,hovertemplate:'可行走空地覆盖目标 %{x:.0f}%<br>独立交互 %{y} 次<br>当前指标 %{z:.1f}%<br>可执行房间 %{customdata[0]}/'+nrooms+'<br>整间房附近覆盖中位 %{customdata[1]:.1f}%<extra></extra>',contours:{z:{show:true,usecolormap:true,highlightcolor:'#155e59',project:{z:false}}}}];
let xx=[],yy=[],zz=[];a.z.forEach((row,j)=>row.forEach((z,i)=>{xx.push(D.x[i]);yy.push(D.counts[j]);zz.push(z)}));traces.push({type:'scatter3d',mode:'markers',x:xx,y:yy,z:zz,marker:{size:2,color:'#155e59'},hoverinfo:'skip',showlegend:false});
if(k==='layout' && full.frontier.length){let f=full.frontier[0],xx=f.coverage_target*100,yy=f.visits,zi=a.z[D.counts.indexOf(yy)][D.x.indexOf(xx)];traces.push({type:'scatter3d',x:[xx],y:[yy],z:[zi],mode:'markers+text',text:['开发边界'],textposition:'top center',marker:{size:6,color:'#b08434'},showlegend:false,hovertemplate:'覆盖目标 '+xx+'% / '+yy+'次<extra>开发条件边界</extra>'});}
traces.push({type:'surface',x:[0,100],y:[0,18],z:[[80,80],[80,80]],opacity:.10,colorscale:[[0,'#be9d52'],[1,'#be9d52']],showscale:false,hoverinfo:'skip'});
Plotly.react('plot',traces,{margin:{l:0,r:12,t:20,b:0},paper_bgcolor:'#fff',font:{family:'Arial,Microsoft YaHei,sans-serif',color:'#344952'},scene:{camera,xaxis:{title:{text:'可行走空地覆盖目标 (%)'},range:[0,100],tickvals:[0,25,50,75,100]},yaxis:{title:{text:'独立交互次数'},tickvals:[0,3,6,9,12,18]},zaxis:{title:{text:names[k]+' (%)'},range:[0,100]},aspectratio:{x:1.2,y:1,z:.8}},uirevision:'keep'}, {responsive:true,displaylogo:false});
let f=full.frontier;el('threshold').textContent=f.length?'发现开发条件边界':'尚未发现';el('thresholdnote').textContent=f.length?f.map(v=>`${Math.round(v.coverage_target*100)}%覆盖 / ${v.visits}次交互`).join('；'):'当前设置没有达到“至少80%有效房间整屋成功，且后续两档覆盖和两档访次仍达标”的开发边界。';
el('meaning').textContent=k==='objects'?'每房四件家具中，中心落入容差内的比例，再对全部房间平均。它不能替代整屋恢复成功率。':k==='certificate'?'全部四件的连续位置范围都能给出所选容差内的条件误差界。它依赖误差、尺寸和语义假设，未做统计校准。':k==='layout'?'同一输出中床、桌、柜、椅中心全部落入容差内的房间比例。':'对应单类家具中心落入容差内的房间比例；不是整屋阈值。';
el('cohortnote').textContent=cohort==='normal'?'本轮受限开发集11房。按用户要求固定剔除：零厚度柜框、空地不连通、柜操作面模型不适用。名单在开发诊断后收窄，尚非独立验证。':'13个几何有效场景；零厚度柜框坏输入另存。无法达到覆盖或请求交互的条件作删失，图上报保守达标比例。';
el('maxvalue').textContent='当前曲面最高值 '+Math.max(...a.z.flat()).toFixed(1)+'%。整屋曲面最高值 '+Math.max(...full.z.flat()).toFixed(1)+'%。';}
['cohort','policy','tol','method','metric'].forEach(id=>el(id).addEventListener('change',draw));draw();window.ACTIVITY_DATA=D;
</script></html>'''


def build(data_path,out,plotly_js=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    record=json.loads(Path(data_path).read_text(encoding='utf-8'));display=display_data(record)
    (out/'activity-surface.html').write_text(HTML.replace('__DATA__',json.dumps(display,ensure_ascii=False)),encoding='utf-8')
    if plotly_js and Path(plotly_js).resolve()!=(out/'plotly.min.js').resolve():shutil.copy2(plotly_js,out/'plotly.min.js')
    (out/'surface-display-data.json').write_text(json.dumps(display,ensure_ascii=False,indent=1),encoding='utf-8')
    return display


def static_plot(display,out,alignment_tools=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    if alignment_tools:sys.path.insert(0,str(alignment_tools))
    from audit_panel_alignment import require_matplotlib_panel_alignment
    plt.rcParams.update({'font.family':['Arial','SimSun'],'font.size':8,'axes.titlesize':10,
                         'pdf.fonttype':42,'svg.fonttype':'none','axes.unicode_minus':False})
    fig=plt.figure(figsize=(183/25.4,125/25.4))
    ax=fig.add_subplot(111,projection='3d')
    x,y=np.meshgrid(display['x'],display['counts'])
    z=np.asarray(display['data']['normal|dispersed|0.5|joint|layout']['z'])
    ax.plot_surface(x,y,z,cmap='viridis',vmin=0,vmax=100,linewidth=.35,edgecolor='#b9c8c5',alpha=.92,antialiased=True)
    ax.scatter(x.ravel(),y.ravel(),z.ravel(),s=6,color='#1c615b',depthshade=False)
    ax.set(xlim=(0,100),ylim=(0,18),zlim=(0,100),xticks=[0,25,50,75,100],yticks=[0,3,6,9,12,18],zticks=[0,25,50,75,100])
    ax.set_xlabel('行走覆盖目标 (% 可行走空地)',labelpad=22)
    ax.set_ylabel('独立交互次数',labelpad=23)
    ax.set_zlabel('整屋恢复成功率 (%)',labelpad=8)
    ax.view_init(elev=25,azim=-58)
    for axis in [ax.xaxis,ax.yaxis,ax.zaxis]:axis.pane.set_fill(False)
    ax.set_title('覆盖范围 × 交互次数：整屋恢复响应面',pad=18)
    f=display['data']['normal|dispersed|0.5|joint|layout']['frontier']
    boundary='未发现稳定开发边界' if not f else '开发边界：覆盖目标≥%g%%，独立交互≥%d次（当前网格）'%(f[0]['coverage_target']*100,f[0]['visits'])
    fig.text(.09,.105,boundary,fontsize=8,color='#8a6521')
    fig.text(.09,.065,'11 间受限普通单间；四件中心均≤0.5 m；连续候选联合重建。',fontsize=8)
    fig.text(.09,.025,'按用户要求固定适用域；开发后名单收窄，尚非独立验证或真实IMU阈值。',fontsize=8,color='#735825')
    fig.subplots_adjust(left=.04,right=.93,bottom=.23,top=.88)
    ax.set_box_aspect((1.25,1.,.9),zoom=.92)
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=Path(out)/'activity-surface.alignment.json')
    fig.savefig(Path(out)/'activity-surface.png',dpi=300,facecolor='white')
    fig.savefig(Path(out)/'activity-surface.pdf',facecolor='white')
    fig.savefig(Path(out)/'activity-surface.svg',facecolor='white')
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--out',required=True)
    p.add_argument('--plotly-js');p.add_argument('--alignment-tools')
    a=p.parse_args();d=build(a.data,a.out,a.plotly_js)
    if a.alignment_tools:static_plot(d,a.out,a.alignment_tools)
