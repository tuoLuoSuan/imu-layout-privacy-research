"""Fixed outline estimator and matched repeated-location mechanism control.

The006 trajectories, inventory and matching endpoint remain unchanged. This
runner can regenerate class-only dispersed/repeated contacts at equal visit
counts. It does not treat each revisit as an independent room or observation.
"""
import argparse,concurrent.futures,hashlib,json,time
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .activity_surface_multi import CELLS
from .exp_walk_range import coverage_route,survey_prefixes
from .selection_diagnostics import rerank_pools


def one(task):
    source,observations,out,cells,methods,modes=task;source,observations,out=map(Path,(source,observations,out))
    sc=M.load_native(source);old=json.loads(observations.read_text(encoding='utf-8'))
    lookup={(r['coverage'],r['visits']):r for r in old['rows'] if r['method']=='generic'}
    ep=coverage_route(sc);ratio=len(ep['reachable_ids'])/len(ep['free_ids']);covs=sorted({c for c,n in cells})
    prefixes=dict(zip(covs,survey_prefixes(ep,[c/ratio for c in covs])));rows=[];original=M._constraint_search
    for cov in covs:
        path=prefixes[cov]['path'] if cov else np.empty((0,2));cache={}
        for c,n in cells:
            if c!=cov:continue
            oldrow=lookup[c,n]
            for mode in modes:
                events=M.event_sequence(sc,path,n,mode=mode)
                if mode=='dispersed' and events!=oldrow['events']:raise ValueError('Dispersed observations changed')
                for policy in methods:
                    def select(inventory,pools,targets,counts):
                        return original(inventory,rerank_pools(pools,[sc['W'],sc['L']],path,policy),targets,counts)
                    M._constraint_search=select
                    try:r=M.decode_instances([sc['W'],sc['L']],sc['inventory'],events,path,proposal_cache=cache)
                    finally:M._constraint_search=original
                    rows.append({'scene':sc['scene'],'split':sc['split'],'counts':sc['counts'],
                        'coverage':c,'visits':n,'method':policy,'contact_mode':mode,
                        'executable':bool(prefixes[c]['reached'] and len(events)==n),
                        'coverage_actual':oldrow['coverage_actual'],'walk_m':oldrow['walk_m'],
                        'status':r['status'],'search_nodes':r.get('search_nodes'),'events':events,
                        'score':M.score_instances(r['boxes'],sc['gt']),
                        'boxes':{k:np.asarray(v).tolist() for k,v in r['boxes'].items()}})
    record={'scene':sc['scene'],'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(record,separators=(',',':')),encoding='utf-8');return record


def run(native,observations,out,control=False,workers=10,limit=None):
    native,observations,out=map(Path,(native,observations,out));files=sorted(native.glob('*.json'));files=files[:limit] if limit else files
    cells=[(.95,11),(1.,14)] if control else list(CELLS)
    methods=['legacy','outline'] if control else ['outline'];modes=['repeat','dispersed'] if control else ['dispersed']
    protocol={'n_rooms':len(files),'cells':cells,'methods':methods,'contact_modes':modes,
        'comparison':'Same path, class visit counts, inventory and candidate/search cap; only contact locations or fixed estimator ranking differ',
        'side_information':'Ideal trajectory and class contacts; given rectangle/inventory/sizes; not rawIMU',
        'primary':'All instances matched within0.5m, no extras/misses','secondary':'Room-average position F1',
        'source_code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(M.__file__),Path(__file__).with_name('selection_diagnostics.py')]}}
    out.mkdir(parents=True,exist_ok=True);(out/'protocol.json').write_text(json.dumps(protocol,indent=1),encoding='utf-8')
    start=time.time();done=0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for record in pool.map(one,[(str(f),str(observations/f.name),str(out/'rooms'/f.name),cells,methods,modes) for f in files],chunksize=1):
            done+=1
            if done==1 or done%50==0:print(json.dumps({'done':done,'total':len(files),'elapsed_s':round(time.time()-start,1)}),flush=True)
    result={'n_rooms':done,'elapsed_s':time.time()-start,'protocol':protocol};(out/'run.json').write_text(json.dumps(result,indent=1),encoding='utf-8');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--observations',required=True);p.add_argument('--out',required=True);p.add_argument('--control',action='store_true');p.add_argument('--limit',type=int);p.add_argument('--workers',type=int,default=10);a=p.parse_args();r=run(a.native,a.observations,a.out,a.control,a.workers,a.limit);print(json.dumps({'rooms':r['n_rooms'],'elapsed_s':r['elapsed_s']}))
