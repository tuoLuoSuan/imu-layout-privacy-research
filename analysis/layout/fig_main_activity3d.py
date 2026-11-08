"""Source-backed 3D activity response, explicit metrics and sampled boundaries."""
import argparse,csv,hashlib,json,math,shutil,sys
from pathlib import Path
import numpy as np

METRICS={'f1':'实例位置F1','layout':'全屋全部定位成功率','bed':'床位置F1',
         'desk':'桌位置F1','cab':'储物位置F1','chair':'椅位置F1'}


def pareto(z,xs,ns,level=80):
    passed=[{'coverage':x,'visits':n,'value':float(z[j][i])} for j,n in enumerate(ns) for i,x in enumerate(xs)
            if z[j][i] is not None and math.isfinite(z[j][i]) and z[j][i]>=level]
    return [p for p in passed if not any(q['coverage']<=p['coverage'] and q['visits']<=p['visits'] and
              (q['coverage']<p['coverage'] or q['visits']<p['visits']) for q in passed)]


def interval(values,binary=False):
    values=np.asarray(values,float);n=len(values);mean=float(values.mean())
    if binary:
        den=1+1.96**2/n;centre=(mean+1.96**2/(2*n))/den
        half=1.96*math.sqrt(mean*(1-mean)/n+1.96**2/(4*n*n))/den
        return mean,max(0.,centre-half),min(1.,centre+half)
    if n<2:return mean,0.,1.
    half=1.96*float(values.std(ddof=1))/math.sqrt(n)
    return mean,max(0.,mean-half),min(1.,mean+half)


def prepare(records,protocol):
    if len(records)!=protocol['n_rooms']:raise ValueError('Fixed room denominator changed')
    names=[r['scene'] for r in records]
    if len(names)!=len(set(names)):raise ValueError('Duplicate room')
    cells=[tuple(c) for c in protocol['cells']];methods=list(protocol.get('methods',['generic','known_desk_protocol']))
    xs=sorted({float(c)*100 for c,n in cells});ns=sorted({int(n) for c,n in cells});look={c:i for i,c in enumerate(cells)}
    values={m:{k:np.full((len(records),len(cells)),np.nan) for k in METRICS} for m in methods}
    available={m:np.zeros((len(records),len(cells)),bool) for m in methods}
    output={m:np.zeros((len(records),len(cells)),bool) for m in methods};unique={m:np.zeros((len(records),len(cells))) for m in methods}
    meta=[]
    for i,rec in enumerate(records):
        if not rec['rows']:raise ValueError('Room without observations')
        first=rec['rows'][0];meta.append({'scene':rec['scene'],'split':first['split'],'count':sum(first['counts'].values()),'counts':first['counts']})
        seen=set()
        for row in rec['rows']:
            c=(float(row['coverage']),int(row['visits']));method=row['method'];key=(method,c)
            if method not in methods or c not in look:continue
            if key in seen:raise ValueError('Duplicate room-condition row')
            seen.add(key);j=look[c];ex=bool(row['executable']);available[method][i,j]=ex;output[method][i,j]=row['status']=='ok'
            score=row['score'];values[method]['f1'][i,j]=float(score['f1']) if ex else 0.
            values[method]['layout'][i,j]=float(ex and row['status']=='ok' and score['all_instances_hit'])
            for k in ['bed','desk','cab','chair']:
                s=score['per_class'].get(k,{});tp=s.get('tp',0);den=2*tp+s.get('fp',0)+s.get('fn',0)
                values[method][k][i,j]=2*tp/den if ex and den else 0.
            unique[method][i,j]=len(set((e['object'],*e['pos']) for e in row.get('events',[])))
        if len(seen)!=len(methods)*len(cells):raise ValueError('Missing room-condition row')
    views={};cohorts={};splits={}
    for cohort in ['all','4','5','6','7']:
        for split in ['all','train','val','test']:
            ids=[i for i,m in enumerate(meta) if (cohort=='all' or m['count']==int(cohort)) and (split=='all' or m['split']==split)]
            if not ids:continue
            cohorts[cohort]=sum(cohort=='all' or m['count']==int(cohort) for m in meta);splits[split]=sum(split=='all' or m['split']==split for m in meta)
            for method in methods:
                for metric in METRICS:
                    a={k:[[None for x in xs] for n in ns] for k in ['z','lo','hi','available','output','hits','unique','lower','upper_missing']}
                    for (cov,count),j in look.items():
                        yi=ns.index(count);xi=xs.index(round(cov*100,8));v=values[method][metric][ids,j]
                        if not np.isfinite(v).all():raise ValueError('Non-finite metric')
                        mean,lo,hi=interval(v,metric=='layout');av=int(available[method][ids,j].sum());censored=len(ids)-av
                        a['z'][yi][xi]=100*mean if av else None
                        a['lower'][yi][xi]=100*mean;a['upper_missing'][yi][xi]=min(100.,100*(mean+censored/len(ids)))
                        a['lo'][yi][xi]=100*lo;a['hi'][yi][xi]=100*hi
                        a['available'][yi][xi]=av;a['output'][yi][xi]=int(output[method][ids,j].sum())
                        a['hits'][yi][xi]=int(values[method]['layout'][ids,j].sum());a['unique'][yi][xi]=float(unique[method][ids,j].mean())
                    a.update(n=len(ids),frontier80=pareto(a['z'],xs,ns),conservative_frontier80=pareto(a['lo'],xs,ns))
                    views['|'.join([cohort,split,method,metric])]=a
    return {'x':xs,'visits':ns,'views':views,'methods':methods,'metrics':METRICS,'cohorts':cohorts,'splits':splits,
        'n_rooms':len(records),'n_objects':sum(m['count'] for m in meta),'tested_cells':len(cells),'protocol':protocol,
        'uncertainty':'Whole-room normal-approximation95% interval for mean F1; Wilson95% interval for all-room success. Controlled generated seeds only.',
        'scope':'Ideal trajectory and class coordinates, known room and inventory; not raw IMU or a universal leakage threshold'}


def load(data):
    data=Path(data);protocol=json.loads((data/'protocol.json').read_text(encoding='utf-8'))
    files=sorted((data/'rooms').glob('*.json'));records=[json.loads(p.read_text(encoding='utf-8')) for p in files]
    result=prepare(records,protocol);result['source_data_sha256']=hashlib.sha256((data/'protocol.json').read_bytes()).hexdigest();return result


def build(data,out,plotly_js):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);display=load(data)
    (out/'source-data.json').write_text(json.dumps(display,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    template=Path(__file__).with_name('activity3d.html').read_text(encoding='utf-8')
    (out/'index.html').write_text(template.replace('__DATA__',json.dumps(display,ensure_ascii=False,separators=(',',':'),allow_nan=False)),encoding='utf-8')
    shutil.copy2(plotly_js,out/'plotly.min.js')
    fields=['cohort','split','method','metric','coverage_percent','visits','n_rooms','mean_percent','ci_lo','ci_hi','executable','whole_room_hits','distinct_contacts_mean']
    with (out/'source-data.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for key,a in display['views'].items():
            cohort,split,method,metric=key.split('|')
            for j,n in enumerate(display['visits']):
                for i,x in enumerate(display['x']):
                    if a['lower'][j][i] is None:continue
                    w.writerow(dict(zip(fields,[cohort,split,method,metric,x,n,a['n'],a['lower'][j][i],a['lo'][j][i],a['hi'][j][i],a['available'][j][i],a['hits'][j][i],a['unique'][j][i]])))
    return display


def static_plot(d,out,audit_tools,method='generic'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    sys.path.insert(0,str(audit_tools));from audit_panel_alignment import require_matplotlib_panel_alignment
    out=Path(out);plt.rcParams.update({'font.family':['Arial','SimSun'],'font.size':8,'pdf.fonttype':42,'svg.fonttype':'none','axes.unicode_minus':False})
    for metric,stem,title in [('f1','main-activity-3d','活动覆盖 × 交互积累：家具位置恢复程度'),('layout','whole-layout-3d','活动覆盖 × 交互积累：全部实例同时达标')]:
        a=d['views']['all|all|'+method+'|'+metric];x,y=np.meshgrid(d['x'],d['visits']);z=np.array([[np.nan if v is None else v for v in row] for row in a['z']])
        fig=plt.figure(figsize=(183/25.4,145/25.4));ax=fig.add_subplot(111,projection='3d')
        fig.subplots_adjust(left=.02,right=.87,bottom=.23,top=.86)
        ax.plot_wireframe(x,y,z,color='#627d94',lw=.65,alpha=.65)
        ax.scatter(x.ravel(),y.ravel(),z.ravel(),c=z.ravel(),s=15,cmap='viridis',vmin=0,vmax=100,depthshade=False,zorder=6)
        for j,n in enumerate(d['visits']):
            for i,cov in enumerate(d['x']):
                if a['z'][j][i] is not None:ax.plot([cov,cov],[n,n],[a['lo'][j][i],a['hi'][j][i]],color='#536c80',lw=.5,alpha=.55)
        xx,yy=np.meshgrid([0.,100.],[0.,max(d['visits'])]);ax.plot_surface(xx,yy,np.full_like(xx,80.),color='#c38a3f',alpha=.10,shade=False)
        for p in a['frontier80']:ax.scatter([p['coverage']],[p['visits']],[p['value']],s=40,facecolor='#e0a23b',edgecolor='#774d17',depthshade=False)
        ax.set(xlim=(0,100),ylim=(0,max(d['visits'])),zlim=(0,100),xticks=[0,20,40,60,80,100],yticks=d['visits'],zticks=[0,20,40,60,80,100])
        ax.set_xlabel('行走覆盖目标 (%)',labelpad=23);ax.set_ylabel('交互访次',labelpad=19);ax.set_zlabel(('实例位置F1 (%)' if metric=='f1' else '全部实例达标房间 (%)'),labelpad=8)
        ax.view_init(elev=25,azim=-55);ax.set_box_aspect((1.3,1.,.85),zoom=.90)
        for axis in [ax.xaxis,ax.yaxis,ax.zaxis]:axis.pane.set_fill(False)
        ca=fig.add_axes([.90,.32,.015,.46]);fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0,100),cmap='viridis'),cax=ca,ticks=[0,40,80,100])
        fig.text(.075,.94,title,fontsize=12)
        fig.text(.075,.88,f"{d['n_rooms']} 间规整单间 · 床1件，桌／储物／椅各1–2件 · 同类一对一匹配≤0.5m",fontsize=8)
        boundary='；'.join(f"{p['coverage']:g}%/{p['visits']}次" for p in a['frontier80']) or '当前网格未达到80%参考线'
        fig.text(.075,.155,'80%参考线的已测最小组合：'+boundary,fontsize=8,color='#8d5c23')
        fig.text(.075,.105,'圆点为实测；线仅连接测点；细竖线为按房95%区间。未强制单调，格间未测试。',fontsize=8)
        fig.text(.075,.055,'理想轨迹与语义坐标；已知外框、数量和尺寸。生成协议内的条件结果，非原始IMU阈值。',fontsize=8)
        fig.canvas.draw();require_matplotlib_panel_alignment(fig,axes=[ax],json_out=out/(stem+'.alignment.json'))
        fig.savefig(out/(stem+'.png'),dpi=600,facecolor='white');fig.savefig(out/(stem+'.pdf'),facecolor='white');fig.savefig(out/(stem+'.svg'),facecolor='white');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(183/25.4,116/25.4));fig.subplots_adjust(left=.08,right=.89,bottom=.25,top=.78,wspace=.18)
    for ax,metric,title in zip(axes,['f1','layout'],['a  恢复程度：按房实例位置F1','b  全屋成功：命中／1000间']):
        a=d['views']['all|all|'+method+'|'+metric];z=np.array([[np.nan if v is None else v for v in r] for r in a['z']])
        cmap=plt.cm.viridis.copy();cmap.set_bad('#eef1f5');im=ax.imshow(z,origin='lower',aspect='auto',vmin=0,vmax=100,cmap=cmap,interpolation='none')
        for j,n in enumerate(d['visits']):
            for i,x in enumerate(d['x']):
                v=a['z'][j][i];text='—' if v is None else (f"{a['hits'][j][i]}\n/ {a['n']}" if metric=='layout' else f'{v:.1f}%')
                ax.text(i,j,text,ha='center',va='center',fontsize=6.5,color='white' if v is not None and v<65 else '#1d2e3f')
        ax.set_xticks(range(len(d['x'])),[f'{x:g}' for x in d['x']]);ax.set_yticks(range(len(d['visits'])),d['visits']);ax.tick_params(length=0)
        ax.set_xlabel('行走覆盖目标 (%)');ax.set_ylabel('交互访次' if metric=='f1' else '');ax.set_title(title,loc='left',fontsize=9,pad=12)
    ca=fig.add_axes([.92,.25,.015,.53]);fig.colorbar(im,cax=ca,ticks=[0,40,80,100])
    fig.text(.08,.94,'同一1000间房：恢复了多少家具，与整屋是否全部恢复',fontsize=11)
    fig.text(.08,.875,'同类一对一匹配，中心误差≤0.5m；4–7件家具，不按成功率筛房。',fontsize=8)
    fig.text(.08,.145,'灰格为未测试或无可执行条件，不能解释成定位成功率0%。',fontsize=8)
    fig.text(.08,.09,'理想坐标、已知外框和家具清单；95%区间与全部数值见随附CSV。',fontsize=8)
    fig.canvas.draw();require_matplotlib_panel_alignment(fig,axes=list(axes),json_out=out/'activity-heatmap.alignment.json')
    fig.savefig(out/'activity-heatmap.png',dpi=600,facecolor='white');fig.savefig(out/'activity-heatmap.pdf',facecolor='white');fig.savefig(out/'activity-heatmap.svg',facecolor='white');plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--out',required=True);p.add_argument('--plotly-js',required=True);p.add_argument('--audit-tools');a=p.parse_args();d=build(a.data,a.out,a.plotly_js)
    if a.audit_tools:static_plot(d,a.out,a.audit_tools)
    print(json.dumps({'rooms':d['n_rooms'],'cells':d['tested_cells'],'objects':d['n_objects']}))
