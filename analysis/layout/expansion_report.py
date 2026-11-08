"""Streaming room-level aggregation of1000 historical+4000 confirmation rooms.

Original observations and split labels remain intact. Primary inference is
on the4000 newly frozen seeds; the5000 surface is a descriptive combination.
All finite-search/acquisition states are retained and separately accounted.
"""
import argparse,collections,csv,hashlib,json
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from . import multi_instance as M,sim_eval as SE
from .activity_surface_multi import CELLS
from .activity_audit import bootstrap_means,paired_binary
from .fig_main_activity3d import interval,pareto
from .simple_rooms import rotate

CONDITIONS=[(float(c),int(n),'dispersed') for c,n in CELLS]+[(.95,11,'repeat'),(1.,14,'repeat')]
METHODS=['legacy','outline']


def footprint_all(pred,truth,threshold=.5):
    if not truth or len(pred)!=len(truth):return False
    for cls in {M.category(k) for k in truth}:
        ps=[v for k,v in pred.items() if M.category(k)==cls];ts=[v for k,v in truth.items() if M.category(k)==cls]
        if len(ps)!=len(ts):return False
        ious=np.array([[SE.iou(np.asarray(a),np.asarray(b)) for b in ts] for a in ps]);valid=ious>=threshold
        a,b=linear_sum_assignment((~valid)*(len(ps)+1)-ious*1e-5)
        if not valid[a,b].all():return False
    return True


def ledger_label(row):
    if row['status']=='native_or_evaluation_error':return 'acquisition_or_evaluation_error'
    if not row['executable']:return 'protocol_not_executable'
    if row['status']=='ok':return 'all_centres_hit' if row['score']['all_instances_hit'] else 'feasible_but_localization_wrong'
    return {'no_proposals':'proposal_missing','proposal_conflict':'retained_proposals_joint_conflict','search_budget_exhausted':'search_budget_exhausted'}.get(row['status'],'other_unresolved')


def canonical_geometry(scene):
    forms=[];W,L=scene['W'],scene['L']
    for k in range(4):
        entries=[]
        for name,b in scene['gt'].items():
            points=np.array([rotate(p,k,W,L) for p in [(b[0],b[1]),(b[0],b[3]),(b[2],b[1]),(b[2],b[3])]])
            entries.append([M.category(name),*np.round(np.r_[points.min(axis=0),points.max(axis=0)],6).tolist()])
        forms.append(json.dumps([round(L if k%2 else W,6),round(W if k%2 else L,6),sorted(entries)],separators=(',',':')))
    return hashlib.sha256(min(forms).encode()).hexdigest()


def original_record(repo,name):
    root=repo/'output/research-sync';a=json.loads((root/'2026-11-08-main-activity-3d-006/data/rooms'/name).read_text(encoding='utf-8'))
    b=json.loads((root/'2026-11-08-activity-upgrade-007/surface/rooms'/name).read_text(encoding='utf-8'))
    r=json.loads((root/'2026-11-08-activity-upgrade-007/repeat-control/rooms'/name).read_text(encoding='utf-8'))
    rows=[{**q,'method':'legacy','contact_mode':'dispersed'} for q in a['rows'] if q['method']=='generic']
    rows+=[{**q,'contact_mode':'dispersed'} for q in b['rows']]
    rows+=[q for q in r['rows'] if q['contact_mode']=='repeat']
    if a['scene']!=b['scene'] or a['scene']!=r['scene']:raise ValueError('Mismatched historical room')
    return {'scene':a['scene'],'split':a['rows'][0]['split'],'counts':a['rows'][0]['counts'],'rows':rows,'source_sha256':a['source_sha256']}


def summarize_subset(f1,whole,ids,draws=10000):
    values=f1[ids];samples=bootstrap_means(values,draws=draws);limits=np.quantile(samples,[.025,.975],axis=0);rows=[]
    for j,(method,condition) in enumerate((m,c) for m in METHODS for c in CONDITIONS):
        w,lo,hi=interval(whole[ids,j],True);c,n,mode=condition
        rows.append({'method':method,'coverage':c,'visits':n,'contact_mode':mode,'n_rooms':len(ids),
            'f1':float(values[:,j].mean()),'f1_bootstrap_ci':limits[:,j].tolist(),'whole_hits':int(whole[ids,j].sum()),
            'whole_rate':w,'whole_wilson_ci':[lo,hi]})
    return rows


def paired_summary(f1,whole,ids,j0,j1):
    result=paired_binary(whole[ids,j0],whole[ids,j1]);differences=np.c_[whole[ids,j1].astype(float)-whole[ids,j0],f1[ids,j1]-f1[ids,j0]]
    ci=np.quantile(bootstrap_means(differences),[.025,.975],axis=0)
    result.update(whole_difference_bootstrap_ci=ci[:,0].tolist(),f1_difference=float(differences[:,1].mean()),f1_difference_bootstrap_ci=ci[:,1].tolist());return result


def run(package,repo,draws=10000):
    package,repo=map(Path,(package,repo));oldroot=repo/'output/research-sync/2026-11-08-procthor-rescue-005/multi'
    old=json.loads((oldroot/'manifest.json').read_text(encoding='utf-8'));new=json.loads((package/'new4000/manifest.json').read_text(encoding='utf-8'))
    selections=old['rows']+new['rows'];names=[r['house_id'] for r in selections]
    if len(names)!=5000 or len(set(names))!=5000:raise ValueError('Exactly5000 unique frozen rooms required')
    if not all((package/'new4000/evaluation/rooms'/(s['house_id']+'.json')).exists() for s in new['rows']):raise ValueError('Wait until all4000 confirmation rooms finish')
    keys=[(m,*c) for m in METHODS for c in CONDITIONS];lookup={k:i for i,k in enumerate(keys)};N=len(names);K=len(keys)
    f1=np.empty((N,K));whole=np.zeros((N,K),bool);unique=np.zeros((N,K));foot=np.zeros((N,2),bool);best={m:[] for m in METHODS};meta=[];fingerprints=[];sources=[]
    for i,sel in enumerate(selections):
        name=sel['house_id'];isnew=i>=1000
        native=(package/'new4000/native' if isnew else oldroot/'native')/(name+'.json');record=json.loads((package/'new4000/evaluation/rooms'/(name+'.json')).read_text(encoding='utf-8')) if isnew else original_record(repo,name+'.json')
        if record['scene']!=name or record['source_sha256']!=hashlib.sha256(native.read_bytes()).hexdigest():raise ValueError('Room/source identity changed')
        rows={(q['method'],q['coverage'],q['visits'],q['contact_mode']):q for q in record['rows']}
        if set(rows)!=set(keys) or len(record['rows'])!=len(keys):raise ValueError('Missing/duplicate room-condition row')
        scene=M.load_native(native) if record.get('native_valid',True) else None
        if scene:fingerprints.append(canonical_geometry(scene))
        area=scene['W']*scene['L'] if scene else None
        meta.append({'scene':name,'split':record['split'],'cohort':'confirmation4000' if isnew else 'historical1000','n_objects':sum(record['counts'].values()),'area_m2':area})
        for key,j in lookup.items():
            q=rows[key];f1[i,j]=q['score']['f1'] if q['executable'] else 0.;whole[i,j]=q['executable'] and q['status']=='ok' and q['score']['all_instances_hit'];unique[i,j]=len({(e['object'],*e['pos']) for e in q['events']})
        for mi,m in enumerate(METHODS):
            q=rows[m,1.,14,'dispersed'];best[m].append(q)
            if scene:foot[i,mi]=q['executable'] and footprint_all(q['boxes'],scene['gt'])
        sources.append({'scene':name,'native_sha256':record['source_sha256'],'cohort':meta[-1]['cohort']})
        if (i+1)%500==0:print(json.dumps({'aggregated':i+1,'total':N}),flush=True)
    out={'date_local':'2026-11-09','n_rooms':N,'n_instances':sum(r['n_objects'] for r in meta),'source_labels':'1000 historical+4000 previously unexamined frozen new seeds of the same controlled family',
        'unique_geometry_up_to_cardinal_rotation':len(set(fingerprints)),'valid_native_rooms':len(fingerprints),'source_index':sources,'bootstrap_draws':draws,'cells':{},'paired':{},'mechanism':{},'best':{},'counts':[]}
    primary_j=[lookup[m,1.,14,'dispersed'] for m in METHODS]
    for cohort,ids in [('all5000',list(range(N))),('historical1000',list(range(1000))),('confirmation4000',list(range(1000,N)))]:
        out['cells'][cohort]=summarize_subset(f1,whole,ids,draws)
        out['paired'][cohort]=paired_summary(f1,whole,ids,*primary_j)
        out['mechanism'][cohort]={}
        for c,n in [( .95,11),(1.,14)]:
            for m in METHODS:
                a=lookup[m,c,n,'repeat'];b=lookup[m,c,n,'dispersed']
                out['mechanism'][cohort][f'{m}|{c}|{n}']={**paired_summary(f1,whole,ids,a,b),'repeat_whole_hits':int(whole[ids,a].sum()),'dispersed_whole_hits':int(whole[ids,b].sum()),'repeat_unique_contacts_mean':float(unique[ids,a].mean()),'dispersed_unique_contacts_mean':float(unique[ids,b].mean())}
        out['best'][cohort]={}
        for mi,m in enumerate(METHODS):
            j=primary_j[mi];ledger=dict(collections.Counter(ledger_label(best[m][i]) for i in ids))
            assert sum(ledger.values())==len(ids)
            classes={c:{'tp':sum(best[m][i]['score']['per_class'][c]['tp'] if best[m][i]['executable'] else 0 for i in ids),'n_truth':sum(best[m][i]['score']['per_class'][c]['n_truth'] for i in ids)} for c in ['bed','desk','cab','chair']}
            for v in classes.values():v['recall']=v['tp']/v['n_truth']
            out['best'][cohort][m]={'n_rooms':len(ids),'f1_equal1':int(np.sum(np.isclose(f1[ids,j],1.,atol=1e-12,rtol=0))),'f1_ge_0_9':int(np.sum(f1[ids,j]>=.9)),'f1_median':float(np.median(f1[ids,j])),'whole_iou0_5_hits':int(foot[ids,mi].sum()),'failure_ledger':ledger,'classes':classes}
    for count in [4,5,6,7]:
        ids=[i for i,r in enumerate(meta) if r['n_objects']==count];areas=[meta[i]['area_m2'] for i in ids if meta[i]['area_m2'] is not None]
        out['counts'].append({'objects':count,'n_rooms':len(ids),'area_median_m2':float(np.median(areas)),'legacy_f1':float(f1[ids,primary_j[0]].mean()),'outline_f1':float(f1[ids,primary_j[1]].mean()),'legacy_whole_hits':int(whole[ids,primary_j[0]].sum()),'outline_whole_hits':int(whole[ids,primary_j[1]].sum())})
    decision=out['paired']['confirmation4000'];out['primary_confirmation_passed']=bool(decision['b_minus_a']>0 and decision['mcnemar_exact_two_sided_p']<.05)
    out['scope']='Conditional geometric position leakage, known room/counts/sizes and ideal class contact locations. Not5000 real rooms or rawIMU trials. New seeds confirm within-generator performance, not cross-family/real-world generalization.'
    distribution=[{**r,'legacy_f1':float(f1[i,primary_j[0]]),'outline_f1':float(f1[i,primary_j[1]]),'legacy_whole':bool(whole[i,primary_j[0]]),'outline_whole':bool(whole[i,primary_j[1]])} for i,r in enumerate(meta)]
    (package/'summary5000.json').write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding='utf-8')
    for name,rows in [('per-room5000',distribution),('count-strata5000',out['counts'])]:
        with (package/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    np.savez_compressed(package/'paired-arrays5000.npz',f1=f1,whole=whole,footprint=foot,unique_contacts=unique,keys=np.asarray([json.dumps(k) for k in keys]),scene=np.asarray(names))
    print(json.dumps({'n_rooms':N,'n_instances':out['n_instances'],'primary':decision,'confirmation_passed':out['primary_confirmation_passed'],'all_best':out['best']['all5000']},ensure_ascii=False,indent=1));return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--repo',default='.');p.add_argument('--draws',type=int,default=10000);a=p.parse_args();run(a.package,a.repo,a.draws)
