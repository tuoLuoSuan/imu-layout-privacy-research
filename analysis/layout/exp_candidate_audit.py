"""Evaluation-only proposal/selection diagnostic, never a deployable oracle.

True positions only measure support after the truth-free decoder returns.
Marginal matching bounds ignore cross-object compatibility and are therefore
optimistic proposal ceilings, not guaranteed achievable joint layouts.
"""
import argparse,concurrent.futures,json,time
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from . import multi_instance as M
from .exp_walk_range import coverage_route,survey_prefixes


def proposal_bound(pools,truth,tolerance=.5):
    out={}
    for cls in ['bed','desk','cab','chair']:
        ps=[(k,np.asarray(v,float).reshape(-1,4)) for k,v in pools.items() if M.category(k)==cls]
        ts=[np.asarray(v) for k,v in truth.items() if M.category(k)==cls]
        distances=np.full((len(ps),len(ts)),np.inf)
        for i,(name,boxes) in enumerate(ps):
            if not len(boxes):continue
            centres=(boxes[:,:2]+boxes[:,2:])/2
            for j,box in enumerate(ts):distances[i,j]=np.linalg.norm(centres-(box[:2]+box[2:])/2,axis=1).min()
        hits=0
        if len(ps) and len(ts):
            valid=distances<=tolerance;a,b=linear_sum_assignment((~valid)*(len(ps)+len(ts)+1)+np.minimum(distances,100)*1e-5)
            hits=int(valid[a,b].sum())
        out[cls]={'tp':hits,'n_truth':len(ts),'n_inventory':len(ps),'minimum_error_m':np.min(distances,axis=0).tolist() if len(ps) else [None]*len(ts)}
    out['marginal_all_classes']=all(v['tp']==v['n_truth'] for k,v in out.items() if k!='marginal_all_classes')
    return out


def one(task):
    native,out,observations=map(Path,task);sc=M.load_native(native)
    old=json.loads(observations.read_text(encoding='utf-8'));row=next(r for r in old['rows'] if r['method']=='generic' and r['coverage']==1 and r['visits']==14)
    ep=coverage_route(sc);ratio=len(ep['reachable_ids'])/len(ep['free_ids']);path=survey_prefixes(ep,[1/ratio])[0]['path']
    cache={};captured={};oracle_joint={};original=M._constraint_search
    def observe(inventory,pools,targets,counts):
        captured.update({k:v[0].copy() for k,v in pools.items()})
        # Evaluation-only existence check: constrain each known-size inventory
        # slot to the vicinity of its ground-truth counterpart, then require
        # the same event coverage and physical compatibility as the real CSP.
        restricted={}
        for name,(boxes,masks,energy) in pools.items():
            truth=np.asarray(sc['gt'][name]);centre=(truth[:2]+truth[2:])/2
            keep=np.linalg.norm((boxes[:,:2]+boxes[:,2:])/2-centre,axis=1)<=.5
            restricted[name]=(boxes[keep],masks[keep],energy[keep])
        if all(len(v[0]) for v in restricted.values()):
            check=original(inventory,restricted,targets,counts)
            oracle_joint.update(status=check['status'],all_hit=M.score_instances(check['boxes'],sc['gt'])['all_instances_hit'])
        else:oracle_joint.update(status='no_oracle_nearby_proposal',all_hit=False)
        return original(inventory,pools,targets,counts)
    M._constraint_search=observe
    try:result=M.decode_instances([sc['W'],sc['L']],sc['inventory'],row['events'],path,proposal_cache=cache)
    finally:M._constraint_search=original
    full={key[0]:value[0] for key,value in cache.items()}
    record={'scene':sc['scene'],'split':sc['split'],'n_objects':len(sc['gt']),
        'status':result['status'],'replayed_score':M.score_instances(result['boxes'],sc['gt']),
        'same_output':result['status']==row['status'] and all(np.array_equal(np.asarray(v),np.asarray(row['boxes'].get(k))) for k,v in result['boxes'].items()),
        'full_proposals':proposal_bound(full,sc['gt']),'retained_proposals':proposal_bound(captured,sc['gt']),
        'oracle_joint':oracle_joint,
        'counts_full':{k:len(v) for k,v in full.items()},'counts_retained':{k:len(v) for k,v in captured.items()}}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(record),encoding='utf-8');return record


def run(native,observations,out,limit=None,workers=10):
    native,observations,out=map(Path,(native,observations,out));files=sorted(native.glob('*.json'));files=files[:limit] if limit else files
    start=time.time();rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(one,[(str(f),str(out/'rooms'/f.name),str(observations/f.name)) for f in files]):
            rows.append(r)
            if len(rows)%50==0:print(json.dumps({'done':len(rows),'elapsed_s':round(time.time()-start,1)}),flush=True)
    result={'scope':__doc__,'n_rooms':len(rows),'replay_differences':sum(not r['same_output'] for r in rows),'rows':rows}
    for split in ['all','train','val','test']:
        selected=[r for r in rows if split=='all' or r['split']==split]
        if not selected:continue
        summary={'n_rooms':len(selected),'oracle_joint_hits':sum(r['oracle_joint'].get('all_hit',False) for r in selected)}
        for stage in ['full_proposals','retained_proposals']:
            summary[stage]={c:{'tp':sum(r[stage][c]['tp'] for r in selected),'n_truth':sum(r[stage][c]['n_truth'] for r in selected)} for c in ['bed','desk','cab','chair']}
            summary[stage]['marginal_whole_hits']=sum(r[stage]['marginal_all_classes'] for r in selected)
        result[split]=summary
    out.mkdir(parents=True,exist_ok=True);(out/'summary.json').write_text(json.dumps(result,indent=1),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=1));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--observations',required=True);p.add_argument('--out',required=True);p.add_argument('--limit',type=int);p.add_argument('--workers',type=int,default=10);a=p.parse_args();run(a.native,a.observations,a.out,a.limit,a.workers)
