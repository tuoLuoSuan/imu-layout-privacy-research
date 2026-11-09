"""Combine immutable008 arrays with5000 new frozen native-room evaluations."""
import argparse,collections,csv,hashlib,json
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .expansion_report import METHODS,CONDITIONS,paired_summary,summarize_subset,ledger_label,footprint_all,canonical_geometry
from .activity_audit import bootstrap_means
from .fig_main_activity3d import interval,pareto
from .threshold009 import sources,CELLS as FINE_CELLS
from .dense_visits009 import VISITS as DENSE_VISITS


def merge_threshold_records(records,scene,source_sha256,expected_cells):
    rows={}
    for record in records:
        if record['scene']!=scene or record['source_sha256']!=source_sha256:
            raise ValueError('Threshold room/source mismatch')
        for row in record['rows']:
            key=(float(row['coverage']),int(row['visits']))
            if key in rows:raise ValueError('Duplicate threshold budget')
            rows[key]=row
    if set(rows)!=set(expected_cells):raise ValueError('Missing/unexpected threshold budget')
    return rows


def full_coverage_threshold(rows,max_visits=28):
    full=sorted([r for r in rows if r['coverage']==1.],key=lambda r:r['visits'])
    if [r['visits'] for r in full]!=list(range(max_visits+1)):
        raise ValueError('Full-coverage threshold requires every integer budget')
    first=lambda field:next((r for r in full if field(r)>=.8),None)
    whole=first(lambda r:r['whole_rate'])
    return {'max_tested_visits':max_visits,'rows':full,
            'first_empirical_whole80':whole,
            'first_whole_lower_ci80':first(lambda r:r['whole_wilson_ci'][0]),
            'first_mean_f1_80':first(lambda r:r['f1']),
            'first_f1_lower_ci80':first(lambda r:r['f1_bootstrap_ci'][0]),
            'whole_passes_every_later_count':bool(whole is not None and all(r['whole_rate']>=.8 for r in full if r['visits']>=whole['visits'])),
            'scope':'Integer count minimum at100% coverage within0..max_tested_visits only; no monotonic or universal guarantee'}


def run(repo,package,draws=10000):
    repo,package=map(Path,(repo,package));previous=repo/'output/research-sync/2026-11-09-expansion-imu-008'
    old=json.loads((previous/'summary5000.json').read_text(encoding='utf-8'));arr=np.load(previous/'paired-arrays5000.npz');keys=[json.loads(k) for k in arr['keys']];lookup={tuple(k):i for i,k in enumerate(keys)}
    N,K=10000,len(keys);f1=np.zeros((N,K));whole=np.zeros((N,K),bool);unique=np.zeros((N,K));foot=np.zeros((N,2),bool)
    f1[:5000]=arr['f1'];whole[:5000]=arr['whole'];unique[:5000]=arr['unique_contacts'];foot[:5000]=arr['footprint'];names=list(arr['scene']);source_index=list(old['source_index']);meta=[];fingerprints=[];best={m:[] for m in METHODS}
    with (previous/'per-room5000.csv').open(encoding='utf-8-sig',newline='') as file:
        for r in csv.DictReader(file):meta.append({'scene':r['scene'],'n_objects':int(r['n_objects']),'area_m2':float(r['area_m2']),'cohort':'historical5000'})
    native=sources(repo,package)
    if not all((package/'new5000/evaluation/rooms'/p.name).exists() for p in native[5000:]):raise ValueError('Wait for every new5000 result; no denominator reduction')
    for i,p in enumerate(native):
        sc=M.load_native(p);fingerprints.append(canonical_geometry(sc))
        if i<5000:continue
        q=json.loads((package/'new5000/evaluation/rooms'/p.name).read_text(encoding='utf-8'));assert q['source_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
        rows={(r['method'],r['coverage'],r['visits'],r['contact_mode']):r for r in q['rows']};assert len(q['rows'])==K and set(rows)==set(lookup)
        for key,j in lookup.items():
            r=rows[key];f1[i,j]=r['score']['f1'] if r['executable'] else 0.;whole[i,j]=r['executable'] and r['score']['all_instances_hit'];unique[i,j]=len({(e['object'],*e['pos']) for e in r['events']})
        for mi,m in enumerate(METHODS):
            r=rows[m,1.,14,'dispersed'];best[m].append(r);foot[i,mi]=r['executable'] and footprint_all(r['boxes'],sc['gt'])
        names.append(q['scene']);meta.append({'scene':q['scene'],'n_objects':sum(q['counts'].values()),'area_m2':sc['W']*sc['L'],'cohort':'confirmation5000'})
        source_index.append({'scene':q['scene'],'native_sha256':q['source_sha256'],'cohort':'confirmation5000'})
        if (i+1)%500==0:print(json.dumps({'aggregation':i+1}),flush=True)
    assert len(names)==N and len(set(names))==N
    result={'date_local':'2026-11-09','n_rooms':N,'n_instances':sum(r['n_objects'] for r in meta),'unique_geometry_up_to_cardinal_rotation':len(set(fingerprints)),'source_index':source_index,'cells':{},'paired':{},'mechanism':{},'best':{},'counts':[],'scope':'Controlled native-engine geometry, not10000 rawIMU trials; new5000 same-family confirmation'}
    primary=[lookup[m,1.,14,'dispersed'] for m in METHODS]
    for cohort,ids in [('all10000',list(range(N))),('confirmation5000',list(range(5000,N)))]:
        result['cells'][cohort]=summarize_subset(f1,whole,ids,draws)
        result['paired'][cohort]=paired_summary(f1,whole,ids,*primary);result['mechanism'][cohort]={};result['best'][cohort]={}
        for c,n in [(.95,11),(1.,14)]:
            for m in METHODS:
                a=lookup[m,c,n,'repeat'];b=lookup[m,c,n,'dispersed'];result['mechanism'][cohort][f'{m}|{c}|{n}']={**paired_summary(f1,whole,ids,a,b),'repeat_whole_hits':int(whole[ids,a].sum()),'dispersed_whole_hits':int(whole[ids,b].sum()),'repeat_unique_contacts_mean':float(unique[ids,a].mean()),'dispersed_unique_contacts_mean':float(unique[ids,b].mean())}
        for mi,m in enumerate(METHODS):
            ledger=collections.Counter(ledger_label(r) for r in best[m]);classes={c:{'tp':sum(r['score']['per_class'][c]['tp'] for r in best[m]),'n_truth':sum(r['score']['per_class'][c]['n_truth'] for r in best[m])} for c in ['bed','desk','cab','chair']}
            if cohort=='all10000':
                ledger.update(old['best']['all5000'][m]['failure_ledger'])
                for c,v in classes.items():
                    for k in ['tp','n_truth']:v[k]+=old['best']['all5000'][m]['classes'][c][k]
            for v in classes.values():v['recall']=v['tp']/v['n_truth']
            j=primary[mi];result['best'][cohort][m]={'failure_ledger':dict(ledger),'classes':classes,'whole_iou0_5_hits':int(foot[ids,mi].sum()),'f1_equal1':int(np.sum(np.isclose(f1[ids,j],1.,atol=1e-12,rtol=0))),'f1_ge_0_9':int(np.sum(f1[ids,j]>=.9)),'f1_median':float(np.median(f1[ids,j]))}
            assert sum(ledger.values())==len(ids)
    for count in [4,5,6,7]:
        ids=[i for i,r in enumerate(meta) if r['n_objects']==count]
        result['counts'].append({'n_objects':count,'n_rooms':len(ids),'area_median_m2':float(np.median([meta[i]['area_m2'] for i in ids])),'outline_f1':float(f1[ids,primary[1]].mean()),'outline_whole_hits':int(whole[ids,primary[1]].sum())})
    (package/'summary10000.json').write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8')
    np.savez_compressed(package/'paired-arrays10000.npz',f1=f1,whole=whole,footprint=foot,unique_contacts=unique,keys=np.array([json.dumps(k) for k in keys]),scene=np.array(names))
    with (package/'per-room10000.csv').open('w',encoding='utf-8-sig',newline='') as file:
        rows=[{**r,'outline_f1':float(f1[i,primary[1]]),'outline_whole':bool(whole[i,primary[1]])} for i,r in enumerate(meta)];w=csv.DictWriter(file,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({'new5000':result['paired']['confirmation5000'],'best':result['best']['all10000']},ensure_ascii=False),flush=True)
    return result


def fine_summary(package,draws=10000):
    package=Path(package);base=json.loads((package/'summary10000.json').read_text(encoding='utf-8'));names=[r['scene'] for r in base['source_index']]
    cells=FINE_CELLS+[(1.,n) for n in DENSE_VISITS]
    f1=np.zeros((10000,len(cells)));whole=np.zeros_like(f1,dtype=bool);executable=np.zeros_like(whole);output_ok=np.zeros_like(whole)
    for i,name in enumerate(names):
        paths=[package/folder/'rooms'/(name+'.json') for folder in ['fine-grid','dense-visits']]
        if not all(p.exists() for p in paths):raise ValueError('Fine/dense-grid denominator incomplete')
        q=merge_threshold_records([json.loads(p.read_text(encoding='utf-8')) for p in paths],name,base['source_index'][i]['native_sha256'],cells)
        for j,key in enumerate(cells):
            f1[i,j]=q[key]['f1'];whole[i,j]=q[key]['whole'];executable[i,j]=q[key]['executable'];output_ok[i,j]=q[key]['status']=='ok'
    out={'n_rooms':10000,'scope':'Additional frozen sampled budgets; no continuous or universal certificate; full-coverage counts0..28 complete','cohorts':{}}
    for cohort,ids in [('all10000',list(range(10000))),('confirmation5000',list(range(5000,10000)))]:
        ci=np.quantile(bootstrap_means(f1[ids],draws=draws),[.025,.975],axis=0);rows=[]
        for j,(c,n) in enumerate(cells):
            rate,lo,hi=interval(whole[ids,j],True);rows.append({'coverage':c,'visits':n,'f1':float(f1[ids,j].mean()),'f1_bootstrap_ci':ci[:,j].tolist(),'whole_hits':int(whole[ids,j].sum()),'whole_rate':rate,'whole_wilson_ci':[lo,hi],'n_rooms':len(ids),'executable':int(executable[ids,j].sum()),'output_ok':int(output_ok[ids,j].sum())})
        rows+=[r for r in base['cells'][cohort] if r['method']=='outline' and r['contact_mode']=='dispersed'];xs=sorted({r['coverage']*100 for r in rows});ys=sorted({r['visits'] for r in rows});lookup={(r['coverage']*100,r['visits']):r for r in rows}
        front={metric:pareto([[lookup[x,n][metric]*100 if (x,n) in lookup else float('nan') for x in xs] for n in ys],xs,ys) for metric in ['f1','whole_rate']}
        front['f1_lower_ci']=pareto([[lookup[x,n]['f1_bootstrap_ci'][0]*100 if (x,n) in lookup else float('nan') for x in xs] for n in ys],xs,ys)
        out['cohorts'][cohort]={'rows':rows,'frontiers':front,'highest_whole_rate':max(r['whole_rate'] for r in rows),'full_coverage':full_coverage_threshold(rows)}
    (package/'thresholds10000.json').write_text(json.dumps(out,indent=1),encoding='utf-8');np.savez_compressed(package/'fine-arrays10000.npz',f1=f1,whole=whole,executable=executable,output_ok=output_ok,keys=np.array(cells));print(json.dumps({k:v['frontiers'] for k,v in out['cohorts'].items()}),flush=True);return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',default='.');p.add_argument('--package',required=True);p.add_argument('--fine-only',action='store_true');a=p.parse_args()
    fine_summary(a.package) if a.fine_only else run(a.repo,a.package)
