"""Room-level summaries for the fixed estimator and spatial-spread control."""
import argparse,csv,json
from pathlib import Path
import numpy as np
from .activity_audit import bootstrap_means,paired_binary
from .fig_main_activity3d import interval,pareto


def load_rows(directory):
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(Path(directory).glob('*.json'))]


def matched(a,b):
    x=np.array([r['score']['all_instances_hit'] and r['executable'] for r in a]);y=np.array([r['score']['all_instances_hit'] and r['executable'] for r in b]);d=paired_binary(x,y)
    diff=bootstrap_means(y.astype(float)-x.astype(float));d['difference_bootstrap_ci']=np.quantile(diff[:,0],[.025,.975]).tolist();return d


def summarize(rows):
    values=np.array([r['score']['f1'] if r['executable'] else 0. for r in rows]);w=np.array([r['executable'] and r['status']=='ok' and r['score']['all_instances_hit'] for r in rows])
    mean,lo,hi=interval(w,True);ci=np.quantile(bootstrap_means(values)[:,0],[.025,.975])
    return {'n_rooms':len(rows),'f1':float(values.mean()),'f1_bootstrap_ci':ci.tolist(),'whole_hits':int(w.sum()),
        'whole_rate':mean,'whole_wilson_ci':[lo,hi],'f1_median':float(np.median(values)),
        'f1_one':int(np.sum(np.isclose(values,1.,rtol=0,atol=1e-12))),'f1_ge_0_9':int(np.sum(values>=.9)),
        'f1_zero':int(np.sum(values==0.)),'output_ok':sum(r['status']=='ok' for r in rows),
        'distinct_contact_mean':float(np.mean([len({(e['object'],*e['pos']) for e in r['events']}) for r in rows])) if all('events' in r for r in rows) else None,
        'recall':{c:sum(r['score']['per_class'][c]['tp'] if r['executable'] else 0 for r in rows)/sum(r['score']['per_class'][c]['n_truth'] for r in rows) for c in ['bed','desk','cab','chair']}}


def run(package):
    package=Path(package);surface=load_rows(package/'surface/rooms');control=load_rows(package/'repeat-control/rooms')
    best=load_rows(package/'selection-full/rooms');n=len(surface)
    if n!=1000 or len(control)!=n or len(best)!=n:raise ValueError('All1000 rooms must finish')
    groups={};cells=[]
    for r in surface:
        for q in r['rows']:groups.setdefault((q['coverage'],q['visits']),[]).append(q)
    # Common whole-room resamples across all cells preserve pairing.
    keys=sorted(groups);values=np.array([[r['score']['f1'] if r['executable'] else 0. for r in groups[k]] for k in keys]).T
    ci=np.quantile(bootstrap_means(values),[.025,.975],axis=0)
    for j,key in enumerate(keys):
        rows=groups[key];w=np.array([r['executable'] and r['status']=='ok' and r['score']['all_instances_hit'] for r in rows]);rate,lo,hi=interval(w,True)
        cells.append({'coverage':key[0],'visits':key[1],'n_rooms':len(rows),'f1':float(values[:,j].mean()),'f1_bootstrap_ci':ci[:,j].tolist(),
            'whole_hits':int(w.sum()),'whole_rate':rate,'whole_wilson_ci':[lo,hi],
            'output_ok':sum(r['status']=='ok' for r in rows),'executable':sum(r['executable'] for r in rows),
            'walk_m_median':float(np.median([r['walk_m'] for r in rows])),'distinct_contact_mean':float(np.mean([len({(e['object'],*e['pos']) for e in r['events']}) for r in rows]))})
    comparison={}
    for split in ['all','train','val','test']:
        selected=[r for r in best if split=='all' or r['split']==split];by={m:[next(q for q in r['rows'] if q['method']==m) for r in selected] for m in ['legacy','outline']}
        comparison[split]={'legacy':summarize(by['legacy']),'outline':summarize(by['outline']),'paired':matched(by['legacy'],by['outline'])}
    mechanism={};class_count_mismatches=0
    for cov,count in [( .95,11),(1.,14)]:
        for policy in ['legacy','outline']:
            by={mode:[next(q for q in r['rows'] if q['method']==policy and q['contact_mode']==mode and q['coverage']==cov and q['visits']==count) for r in control] for mode in ['repeat','dispersed']}
            for a,b in zip(by['repeat'],by['dispersed']):
                class_count_mismatches+=sorted(e['object'] for e in a['events'])!=sorted(e['object'] for e in b['events'])
            mechanism[f'{policy}|{cov}|{count}']={'repeat':summarize(by['repeat']),'dispersed':summarize(by['dispersed']),'paired':matched(by['repeat'],by['dispersed'])}
    xs=sorted({c['coverage']*100 for c in cells});ys=sorted({c['visits'] for c in cells});look={(c['coverage']*100,c['visits']):c for c in cells}
    z=[[look[x,y]['f1']*100 if (x,y) in look else None for x in xs] for y in ys]
    lower=[[look[x,y]['f1_bootstrap_ci'][0]*100 if (x,y) in look else None for x in xs] for y in ys]
    result={'date_local':'2026-11-09','n_rooms':n,'cells':cells,'best_condition_comparison':comparison,'spread_mechanism':mechanism,
        'contact_class_count_mismatches':class_count_mismatches,'f1_reference80_frontier':pareto(z,xs,ys,80),
        'f1_reference80_lowerCI_frontier':pareto(lower,xs,ys,80),'primary_whole80_reached':any(c['whole_rate']>=.8 for c in cells),
        'scope':'Controlled geometry; known room/inventory; ideal class positions; unchanged tolerance0.5m. Exploratory post-review estimator ablation.'}
    (package/'upgrade-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8')
    csvrows=[{**{k:v for k,v in c.items() if not isinstance(v,list)},'f1_ci_lo':c['f1_bootstrap_ci'][0],'f1_ci_hi':c['f1_bootstrap_ci'][1],'whole_ci_lo':c['whole_wilson_ci'][0],'whole_ci_hi':c['whole_wilson_ci'][1]} for c in cells]
    with (package/'upgrade-cells.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
    print(json.dumps({k:v for k,v in result.items() if k not in ['cells','spread_mechanism']},ensure_ascii=False,indent=1));print(json.dumps(mechanism,indent=1));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);a=p.parse_args();run(a.package)
