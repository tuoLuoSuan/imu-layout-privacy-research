"""Frozen paired evaluation on newly generated rooms; no development tuning.

Each room shares route, contact sequence and proposals across legacy/outline.
Whole-room independence is preserved across90 conditions. Native acquisition
and finite-search failures remain in the frozen denominator.
"""
import hashlib,json
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .activity_surface_multi import CELLS
from .exp_walk_range import coverage_route,survey_prefixes
from .selection_diagnostics import rerank_pools

POLICIES=('legacy','outline')
REPEAT_CELLS=((.95,11),(1.,14))


def empty_score(counts):
    return {'tp':0,'fp':0,'fn':sum(counts.values()),'f1':0.,'all_instances_hit':False,
        'matches':[],'per_class':{c:{'tp':0,'fp':0,'fn':n,'n_truth':n,'n_pred':0} for c,n in counts.items()}}


def evaluate_room(task):
    source,out=map(Path,task);native=json.loads(source.read_text(encoding='utf-8'));sel=native['selection'];rows=[]
    conditions=[(c,n,'dispersed') for c,n in CELLS]+[(c,n,'repeat') for c,n in REPEAT_CELLS]
    try:
        scene=M.load_native(source);room=[scene['W'],scene['L']]
        if any(np.any(np.asarray(b)[2:]<=np.asarray(b)[:2]) or np.any(np.asarray(b)[:2]<-1e-4) or np.any(np.asarray(b)[2:]>np.asarray(room)+1e-4) for b in scene['gt'].values()):raise ValueError('Invalid native geometry')
        ep=coverage_route(scene);ratio=len(ep['reachable_ids'])/len(ep['free_ids']);coverages=sorted({c for c,n in CELLS})
        prefixes=dict(zip(coverages,survey_prefixes(ep,[c/ratio for c in coverages])));original=M._constraint_search
        for cov in coverages:
            prefix=prefixes[cov];path=prefix['path'] if cov else np.empty((0,2));cache={}
            for c,n,mode in conditions:
                if c!=cov:continue
                events=M.event_sequence(scene,path,n,mode=mode)
                for policy in POLICIES:
                    def select(inventory,pools,targets,counts):return original(inventory,rerank_pools(pools,room,path,policy),targets,counts)
                    M._constraint_search=select
                    try:result=M.decode_instances(room,scene['inventory'],events,path,proposal_cache=cache)
                    finally:M._constraint_search=original
                    rows.append({'coverage':c,'visits':n,'contact_mode':mode,'method':policy,
                        'executable':bool(prefix['reached'] and len(events)==n),'coverage_actual':float(prefix['coverage_free']) if cov else 0.,
                        'walk_m':float(prefix['walk_m']) if cov else 0.,'events':events,'status':result['status'],
                        'search_nodes':result.get('search_nodes'),'score':M.score_instances(result['boxes'],scene['gt']),
                        'boxes':{k:np.asarray(v).tolist() for k,v in result['boxes'].items()}})
        record={'scene':scene['scene'],'split':scene['split'],'counts':scene['counts'],'room':room,'rows':rows,'native_valid':True}
    except Exception as exc:
        # This path is explicit acquisition/evaluation failure, not a discarded room.
        counts=sel['counts'];rows=[{'coverage':c,'visits':n,'contact_mode':mode,'method':policy,'executable':False,
            'status':'native_or_evaluation_error','error':type(exc).__name__+': '+str(exc),'events':[],
            'score':empty_score(counts),'boxes':{}} for c,n,mode in conditions for policy in POLICIES]
        record={'scene':sel['house_id'],'split':sel['source_split'],'counts':counts,'rows':rows,'native_valid':False}
    record['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(record,separators=(',',':')),encoding='utf-8');tmp.replace(out)
    return {'scene':record['scene'],'native_valid':record['native_valid'],'rows':len(rows)}
