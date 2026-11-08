"""Matched estimator ablation. Same observed path, contacts, proposals and budget.

Policies are chosen on development rooms only. Ground truth is used after
inference for scoring. Optional desk witnesses are diagnostics, not predictions.
"""
import argparse,concurrent.futures,json,time
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .selection_diagnostics import rerank_pools,desk_witness,minimum_cost_search
from .exp_walk_range import coverage_route,survey_prefixes


def one(task):
    source,observed,out,policies,cov,visits=task;source,observed,out=map(Path,(source,observed,out))
    sc=M.load_native(source);old=json.loads(observed.read_text(encoding='utf-8'));row=next(r for r in old['rows'] if r['method']=='generic' and r['coverage']==cov and r['visits']==visits)
    ep=coverage_route(sc);ratio=len(ep['reachable_ids'])/len(ep['free_ids']);prefix=survey_prefixes(ep,[cov/ratio])[0];path=prefix['path'] if cov else np.empty((0,2));cache={};captured={};rows=[]
    original=M._constraint_search
    for policy in policies:
        def select(inventory,pools,targets,counts):
            captured.update({k:v[0].copy() for k,v in pools.items()})
            solver=minimum_cost_search if policy=='outline_joint' else original
            return solver(inventory,rerank_pools(pools,[sc['W'],sc['L']],path,policy),targets,counts)
        M._constraint_search=select
        try:r=M.decode_instances([sc['W'],sc['L']],sc['inventory'],row['events'],path,proposal_cache=cache)
        finally:M._constraint_search=original
        full={key[0]:value[0] for key,value in cache.items()}
        witness=desk_witness(r['boxes'],full) if r['status']=='ok' else {'found':False}
        rows.append({'method':policy,'coverage':cov,'visits':visits,'executable':row['executable'],
            'status':r['status'],'search_nodes':r.get('search_nodes'),'score':M.score_instances(r['boxes'],sc['gt']),
            'candidate_objective_optimal':r.get('candidate_objective_optimal'),
            'boxes':{k:np.asarray(v).tolist() for k,v in r['boxes'].items()},'desk_witness':witness})
    record={'scene':sc['scene'],'split':sc['split'],'rows':rows};out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(record),encoding='utf-8');return record


def run(native,observations,out,policies,limit=None,workers=10,cov=1.,visits=14,split=None):
    native,observations,out=map(Path,(native,observations,out));files=sorted(native.glob('*.json'))
    if split:files=[f for f in files if M.load_native(f)['split']==split]
    files=files[:limit] if limit else files;rows=[];start=time.time()
    protocol={'policies':policies,'n_rooms':len(files),'coverage':cov,'visits':visits,'split':split,'selection':'Development-only policy choice; heldout policy must be frozen before running test','side_information_change':False,'candidate_limit':64,'search_node_limit':20000}
    out.mkdir(parents=True,exist_ok=True);(out/'protocol.json').write_text(json.dumps(protocol,indent=1),encoding='utf-8')
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(one,[(str(f),str(observations/f.name),str(out/'rooms'/f.name),policies,cov,visits) for f in files]):
            rows.append(r)
            if len(rows)%100==0:print(json.dumps({'done':len(rows),'elapsed_s':round(time.time()-start,1)}),flush=True)
    result={'protocol':protocol,'elapsed_s':time.time()-start,'summary':{}}
    for method in policies:
        for part in ['all','train','val','test']:
            selected=[q for r in rows if part=='all' or r['split']==part for q in r['rows'] if q['method']==method]
            if not selected:continue
            result['summary'][method+'|'+part]={'n_rooms':len(selected),'whole_hits':sum(r['score']['all_instances_hit'] and r['executable'] for r in selected),
                'f1':float(np.mean([r['score']['f1'] if r['executable'] else 0 for r in selected])),
                'desk_witness_rooms':sum('separation_m' in r['desk_witness'] for r in selected),
                'status_ok':sum(r['status']=='ok' for r in selected),
                'class_recall':{c:sum(r['score']['per_class'][c]['tp'] if r['executable'] else 0 for r in selected)/sum(r['score']['per_class'][c]['n_truth'] for r in selected) for c in ['bed','desk','cab','chair']}}
    (out/'summary.json').write_text(json.dumps(result,indent=1),encoding='utf-8');print(json.dumps(result,indent=1));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--observations',required=True);p.add_argument('--out',required=True);p.add_argument('--policies',nargs='+',default=['legacy','support_mean','outline']);p.add_argument('--limit',type=int);p.add_argument('--split');p.add_argument('--workers',type=int,default=10);p.add_argument('--coverage',type=float,default=1.);p.add_argument('--visits',type=int,default=14);a=p.parse_args();run(a.native,a.observations,a.out,a.policies,a.limit,a.workers,a.coverage,a.visits,a.split)
