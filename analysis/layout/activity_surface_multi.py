"""Dense activity surface on the fixed variable-inventory room cohort.

Only the sampled activity budgets expand. Same decoder, contact protocol,
room inventory and class-wise matching as multi_threshold. Proposal memoization
is scoped to one room and one walk prefix and changes no numerical rule.
"""
import argparse,concurrent.futures,hashlib,json,time
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .exp_walk_range import coverage_route,survey_prefixes

COVERAGES=(.20,.40,.60,.75,.85,.95,1.)
VISITS=(0,2,5,8,11,14)
CELLS=((0.,0),)+tuple((c,n) for c in COVERAGES for n in VISITS)
METHODS=('generic','known_desk_protocol')


def one_room(task):
    source,out=map(Path,task);scene=M.load_native(source);rows=[]
    try:
        episode=coverage_route(scene);ratio=len(episode['reachable_ids'])/len(episode['free_ids'])
        covers=(0.,)+COVERAGES
        prefixes=dict(zip(covers,survey_prefixes(episode,[c/ratio for c in covers])))
        for cov in covers:
            prefix=prefixes[cov];path=prefix['path'] if cov else np.empty((0,2));cache={}
            for count in (VISITS if cov else (0,)):
                events=M.event_sequence(scene,path,count);executable=bool(prefix['reached'] and len(events)==count)
                for method in METHODS:
                    result=M.decode_instances([scene['W'],scene['L']],scene['inventory'],events,path,
                        known_desk_protocol=method!='generic',proposal_cache=cache)
                    rows.append({'scene':scene['scene'],'split':scene['split'],'counts':scene['counts'],
                        'coverage':cov,'visits':count,'method':method,'executable':executable,
                        'coverage_actual':float(prefix['coverage_free']) if cov else 0.,'walk_m':float(prefix['walk_m']) if cov else 0.,
                        'status':result['status'],'search_nodes':result.get('search_nodes'),
                        'events':events,'score':M.score_instances(result['boxes'],scene['gt']),
                        'boxes':{k:np.asarray(v).tolist() for k,v in result['boxes'].items()}})
    except Exception as exc:
        rows=[{'scene':scene['scene'],'split':scene['split'],'counts':scene['counts'],'coverage':c,'visits':n,
            'method':m,'executable':False,'status':'evaluation_error','error':repr(exc),
            'score':M.score_instances({},scene['gt'])} for c,n in CELLS for m in METHODS]
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'scene':scene['scene'],'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows},separators=(',',':')),encoding='utf-8')
    return scene['scene']


def run(native,out,workers=10,limit=None):
    files=sorted(Path(native).glob('*.json'));files=files[:limit] if limit else files
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    protocol={'n_rooms':len(files),'cells':CELLS,'coverages':(0.,)+COVERAGES,'visits':VISITS,'methods':METHODS,
        'source_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'inventory':'One bed; independently one/two desks, storage and chairs; eight patterns equally represented',
        'x':'Neighbourhood coverage of all body-clear floor;0.25m radius,0.15m body clearance',
        'y':'Visit budget; repeated same positions do not become independent information',
        'z_primary':'Mean per-room instance position F1, category-wise one-to-one centres within0.5m',
        'z_secondary':'Fraction of fixed rooms with every target instance correctly located, no extras or omissions',
        'side_information':'Room rectangle and exact target inventory/counts/sizes; semantic coordinates ideal, no true event-instance association',
        'reference_level':.8,'threshold_scope':'Exploratory reference level; sampled Pareto boundary, no extrapolation or monotonic smoothing',
        'uncertainty_unit':'Whole room; controlled generated seeds, not real-room population uncertainty',
        'source_code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(M.__file__)]}}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=1),encoding='utf-8');start=time.time();done=0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for name in pool.map(one_room,[(str(p),str(out/'rooms'/(p.stem+'.json'))) for p in files],chunksize=1):
            done+=1
            if done==1 or done%25==0:print(json.dumps({'done':done,'total':len(files),'elapsed_s':round(time.time()-start,1)}),flush=True)
    result={'protocol':protocol,'elapsed_s':time.time()-start,'n_room_files':done}
    (out/'run.json').write_text(json.dumps(result,indent=1),encoding='utf-8');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--workers',type=int,default=10);p.add_argument('--limit',type=int);a=p.parse_args();r=run(a.native,a.out,a.workers,a.limit);print(json.dumps({'rooms':r['n_room_files'],'seconds':r['elapsed_s']}))
