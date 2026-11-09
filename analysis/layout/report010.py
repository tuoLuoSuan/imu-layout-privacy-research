"""Independent room-file aggregation, paired uncertainty and sampled frontier."""
import argparse,collections,csv,hashlib,json
from pathlib import Path
import numpy as np
from .activity_audit import bootstrap_means,paired_binary
from .fig_main_activity3d import interval


def summarize(rows,draws=5000):
    f=np.array([r['score']['f1'] if r['executable'] else 0. for r in rows]);hit=np.array([r['executable'] and r['score']['all_instances_hit'] for r in rows]);mean,lo,hi=interval(hit,True)
    ci=np.quantile(bootstrap_means(f,draws=draws),[.025,.975],axis=0).ravel().tolist()
    ledger=collections.Counter('all_centres_hit' if h else 'valid_output_wrong' if r['status']=='ok' else r['status'] for r,h in zip(rows,hit))
    per={c:{'tp':sum(r['score']['per_class'][c]['tp'] if r['executable'] else 0 for r in rows),'n':sum(r['score']['per_class'][c]['n_truth'] for r in rows)} for c in ['bed','desk','cab','chair']}
    for v in per.values():v['recall']=v['tp']/v['n']
    return {'n':len(rows),'whole':int(hit.sum()),'rate':mean,'wilson95':[lo,hi],'mean_f1':float(f.mean()),'f1_bootstrap95':ci,
      'f1_median':float(np.median(f)),'f1_zero':int((f==0).sum()),'f1_ge_0_9':int((f>=.9-1e-12).sum()),
      'whole_iou0_5':sum(r['whole_iou0_5'] for r in rows),'per_class':per,'failure_ledger':dict(ledger),
      'executable':sum(r['executable'] for r in rows),'fallback':sum(r.get('fallback_used',False) for r in rows),
      'median_nodes':float(np.median([r['search_nodes'] for r in rows])),'p90_nodes':float(np.quantile([r['search_nodes'] for r in rows],.9)),
      'median_elapsed_s':float(np.median([r['elapsed_s'] for r in rows])),'sum_elapsed_s':sum(r['elapsed_s'] for r in rows),
      'walk_m_median':float(np.median([r['walk_m'] for r in rows])),'unique_contacts_median':float(np.median([r['unique_contacts'] for r in rows]))}


def aggregate(source,out,expected,draws=5000):
    source,out=map(Path,(source,out));files=sorted((source/'rooms').glob('*.json'))
    if len(files)!=expected:raise ValueError(f'Frozen denominator{expected}, got{len(files)}')
    groups={};names=[];counts=[];rooms=[];digest=hashlib.sha256()
    for f in files:
        data=f.read_bytes();digest.update(data);d=json.loads(data);names.append(d['scene']);counts.append(sum(d['counts'].values()));seen=set();lookup={}
        for r in d['rows']:
            key=(r['policy'],r['coverage'],r['visits'])
            if key in seen:raise ValueError('Duplicate room-condition')
            seen.add(key);groups.setdefault(key,[]).append(r);lookup[key]=r
        rooms.append(lookup)
    if len(set(names))!=expected:raise ValueError('Duplicate room')
    summary=[]
    for key,rows in sorted(groups.items()):
        if len(rows)!=expected:raise ValueError('Missing cell')
        summary.append({'policy':key[0],'coverage':key[1],'visits':key[2],**summarize(rows,draws)})
    pairs=[]
    for c,n in sorted({(c,n) for p,c,n in groups}):
        ka=('post64_wall40k',c,n);kb=('depth_portfolio',c,n)
        if ka not in groups or kb not in groups:continue
        a=groups[ka];b=groups[kb];ha=np.array([r['executable'] and r['score']['all_instances_hit'] for r in a]);hb=np.array([r['executable'] and r['score']['all_instances_hit'] for r in b]);df=np.array([v['score']['f1']-u['score']['f1'] for u,v in zip(a,b)])
        ci=np.quantile(bootstrap_means(np.c_[hb.astype(float)-ha,df],draws=draws),[.025,.975],axis=0)
        pairs.append({'coverage':c,'visits':n,'a':'post64_wall40k','b':'depth_portfolio',**paired_binary(ha,hb),'whole_difference_bootstrap95':ci[:,0].tolist(),'f1_difference_bootstrap95':ci[:,1].tolist()})
    strata=[];primary=('depth_portfolio',1.,14)
    if primary in groups:
        for count in sorted(set(counts)):
            subset=[r for k,r in zip(counts,groups[primary]) if k==count];strata.append({'n_objects':count,**summarize(subset,draws)})
    points=[r for r in summary if r['policy']=='depth_portfolio' and r['rate']>=.8];pareto=[r for r in points if not any(q['coverage']<=r['coverage'] and q['visits']<=r['visits'] and (q['coverage']<r['coverage'] or q['visits']<r['visits']) for q in points)]
    full=sorted((r for r in summary if r['policy']=='depth_portfolio' and r['coverage']==1.),key=lambda r:r['visits'])
    result={'n':expected,'source_room_sha256':digest.hexdigest(),'uncertainty':'Whole: pointwise Wilson95%; F1 and paired differences: whole-room percentile bootstrap5000, seed611087; not simultaneous selected-frontier coverage','centre_endpoint':'Same-category one-to-one matching; all4..7 targets within0.5m, no extras/misses','footprint_endpoint':'Separate all-target IoU>=0.5 endpoint; not interchangeable with centre recovery','cells':summary,'paired':pairs,'count_strata':strata,
      'sampled_pareto80':[{'coverage':r['coverage'],'visits':r['visits'],'rate':r['rate'],'wilson95':r['wilson95']} for r in pareto],
      'full_coverage_first_point80':next((r['visits'] for r in full if r['rate']>=.8),None),'full_coverage_first_wilson_lower80':next((r['visits'] for r in full if r['wilson95'][0]>=.8),None),
      'threshold_scope':'Empirical sampled budget boundary of this controlled family/prior/estimator/protocol; not a guarantee for individual rooms or rawIMU',
      'distribution_primary':[{'scene':name,'n_objects':count,'f1':r[primary]['score']['f1'],'whole':r[primary]['score']['all_instances_hit'],'status':r[primary]['status']} for name,count,r in zip(names,counts,rooms)] if primary in groups else []}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=1),encoding='utf-8');print(json.dumps({'source':str(source),'n':expected,'paired':pairs,'frontier':result['sampled_pareto80']}),flush=True);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--expected',type=int,required=True);p.add_argument('--draws',type=int,default=5000);a=p.parse_args();aggregate(a.source,a.out,a.expected,a.draws)
