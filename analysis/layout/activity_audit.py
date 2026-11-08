"""Post-review, room-level reanalysis of the unchanged 006 experiment.

No decoder, room eligibility or success tolerance changes. Bootstrap units
are rooms, with common resamples across paired conditions. These exploratory
intervals are pointwise, not simultaneous guarantees for a selected frontier.
"""
import argparse,csv,hashlib,json
from pathlib import Path
import numpy as np
from scipy.stats import binomtest
from .fig_main_activity3d import interval,pareto
from .multi_instance import load_native


def bootstrap_means(values,draws=10000,seed=611087,batch=64):
    a=np.asarray(values,float)
    if a.ndim==1:a=a[:,None]
    if not len(a) or not np.isfinite(a).all():raise ValueError('Finite room observations required')
    rng=np.random.default_rng(seed);out=np.empty((draws,a.shape[1]))
    for start in range(0,draws,batch):
        ids=rng.integers(0,len(a),size=(min(batch,draws-start),len(a)))
        out[start:start+len(ids)]=a[ids].mean(axis=1)
    return out


def paired_binary(a,b):
    a=np.asarray(a,bool);b=np.asarray(b,bool)
    if a.shape!=b.shape or not len(a):raise ValueError('Matched rooms required')
    a_only=int(np.sum(a&~b));b_only=int(np.sum(b&~a));n=a_only+b_only
    return {'n_rooms':len(a),'both':int(np.sum(a&b)),'a_only':a_only,'b_only':b_only,
        'neither':int(np.sum(~a&~b)),'b_minus_a':float(b.mean()-a.mean()),
        'mcnemar_exact_two_sided_p':float(binomtest(a_only,n,.5).pvalue) if n else 1.}


def run(data,native,out,draws=10000):
    data,native,out=map(Path,(data,native,out));out.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((data/'protocol.json').read_text(encoding='utf-8'))
    records=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((data/'rooms').glob('*.json'))]
    if len(records)!=protocol['n_rooms']:raise ValueError('Fixed denominator changed')
    scenes=[load_native(native/(r['scene']+'.json')) for r in records]
    keys=[(m,float(c),int(n)) for m in protocol['methods'] for c,n in protocol['cells']]
    f1=np.empty((len(records),len(keys)));whole=np.zeros_like(f1,dtype=bool);lookup=[];best=[]
    for i,r in enumerate(records):
        rows={(q['method'],float(q['coverage']),int(q['visits'])):q for q in r['rows']}
        if len(rows)!=len(keys):raise ValueError('Missing or duplicate room condition')
        lookup.append(rows)
        for j,key in enumerate(keys):
            q=rows[key];f1[i,j]=q['score']['f1'] if q['executable'] else 0.
            whole[i,j]=q['executable'] and q['status']=='ok' and q['score']['all_instances_hit']
        best.append(rows['generic',1.,14])
    samples=bootstrap_means(f1,draws=draws);limits=np.quantile(samples,[.025,.975],axis=0)
    summaries=[]
    for j,(method,cov,visits) in enumerate(keys):
        q=[d[method,cov,visits] for d in lookup];w,lo,hi=interval(whole[:,j],True)
        summaries.append({'method':method,'coverage':cov,'visits':visits,'n_rooms':len(records),
            'f1_mean':float(f1[:,j].mean()),'f1_bootstrap_lo':float(limits[0,j]),'f1_bootstrap_hi':float(limits[1,j]),
            'f1_median':float(np.median(f1[:,j])),'f1_equal_one':int(np.sum(np.isclose(f1[:,j],1.,rtol=0,atol=1e-12))),
            'f1_ge_0_9':int(np.sum(f1[:,j]>=.9-1e-12)),'f1_zero':int(np.sum(f1[:,j]==0)),
            'whole_hits':int(whole[:,j].sum()),'whole_rate':w,'whole_wilson_lo':lo,'whole_wilson_hi':hi,
            'executable':sum(r['executable'] for r in q),'output_ok':sum(r['status']=='ok' for r in q),
            'coverage_actual_median':float(np.median([r['coverage_actual'] for r in q])),
            'walk_m_median':float(np.median([r['walk_m'] for r in q])),
            'distinct_contacts_median':float(np.median([len({(e['object'],*e['pos']) for e in r['events']}) for r in q]))})
    a=keys.index(('generic',1.,14));b=keys.index(('known_desk_protocol',1.,14));paired=paired_binary(whole[:,a],whole[:,b])
    paired['method_a']='generic';paired['method_b']='known_desk_protocol'
    diff=bootstrap_means(np.c_[whole[:,b].astype(float)-whole[:,a],f1[:,b]-f1[:,a]],draws=draws)
    paired['whole_difference_bootstrap_ci']=np.quantile(diff[:,0],[.025,.975]).tolist()
    paired['f1_b_minus_a']=float(np.mean(f1[:,b]-f1[:,a]));paired['f1_difference_bootstrap_ci']=np.quantile(diff[:,1],[.025,.975]).tolist()
    strata=[]
    for count in [4,5,6,7]:
        ids=[i for i,s in enumerate(scenes) if len(s['gt'])==count];areas=[scenes[i]['W']*scenes[i]['L'] for i in ids]
        strata.append({'n_objects':count,'n_rooms':len(ids),'area_median_m2':float(np.median(areas)),
            'area_q25_m2':float(np.quantile(areas,.25)),'area_q75_m2':float(np.quantile(areas,.75)),
            'f1':float(f1[ids,a].mean()),'whole_hits':int(whole[ids,a].sum())})
    per={}
    for cls in ['bed','desk','cab','chair']:
        tp=sum(r['score']['per_class'][cls]['tp'] if r['executable'] else 0 for r in best)
        n=sum(r['score']['per_class'][cls]['n_truth'] for r in best)
        per[cls]={'tp':tp,'n_truth':n,'recall':tp/n}
    # Conditional bottleneck: a diagnostic, not success after deleting desks.
    non_desk=sum(r['executable'] and r['status']=='ok' and all(r['score']['per_class'][c]['fn']==r['score']['per_class'][c]['fp']==0 for c in ['bed','cab','chair']) for r in best)
    per['non_desk_joint']={'hits':non_desk,'n_rooms':len(best),'role':'Diagnostic only; original all-target endpoint remains unchanged'}
    distribution=[{'scene':r['scene'],'split':scenes[i]['split'],'n_objects':len(scenes[i]['gt']),
        'area_m2':scenes[i]['W']*scenes[i]['L'],'f1':float(f1[i,a]),'whole':bool(whole[i,a]),
        'status':best[i]['status'],'known_f1':float(f1[i,b]),'known_whole':bool(whole[i,b])} for i,r in enumerate(records)]
    result={'n_rooms':len(records),'draws':draws,'seed':611087,'bootstrap':'Percentile95%, ordinary whole-room bootstrap, matched resamples; pointwise exploratory intervals',
        'primary':'All target instances correctly matched within0.5m, no extras or misses','secondary':'Mean per-room instance position F1',
        'reporting_revision':'Post-review endpoint hierarchy, not pre-registration of the unchanged006 run',
        'reference80':'F1 display reference only; whole-layout80% not attained',
        'source_protocol_sha256':hashlib.sha256((data/'protocol.json').read_bytes()).hexdigest(),
        'cells':summaries,'paired_prior':paired,'count_strata':strata,'per_class_best':per,'distribution_best':distribution}
    (out/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8')
    for name,rows in [('cells',summaries),('distribution',distribution),('count-strata',strata)]:
        with (out/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:result[k] for k in ['n_rooms','paired_prior','count_strata','per_class_best']},ensure_ascii=False,indent=1))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--draws',type=int,default=10000);a=p.parse_args();run(a.data,a.native,a.out,a.draws)
