"""Separate desk-centre bearing ORACLE sensitivity; measured arm unavailable.

True directions are generated only in the evaluator and explicitly granted
to these extra-input arms. They never enter the generic5000-room experiment
and are not claimed to be phone/body facing estimates.
"""
import argparse,concurrent.futures,json,time
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .selection_diagnostics import rerank_pools
from .exp_walk_range import coverage_route,survey_prefixes


def add_bearings(pools,targets,bearings,cone_deg=45.,max_distance=.9):
    extended=list(targets)+[{'object':'desk_relation','pos':b['pos']} for b in bearings];out={}
    if len(extended)>60:raise ValueError('Direction target budget exceeded')
    for b in bearings:
        if set(b)!={'pos','bearing'}:raise ValueError('Only position and direction allowed; no instance identity')
    for name,(boxes,masks,energy) in pools.items():
        masks=masks.copy()
        if M.category(name)=='desk':
            for j,b in enumerate(bearings):
                point=np.asarray(b['pos']);outside=np.maximum(boxes[:,:2]-point,point-boxes[:,2:]).clip(min=0)
                keep=np.linalg.norm(outside,axis=1)<=max_distance+1e-8
                if b['bearing'] is not None:
                    h=np.asarray(b['bearing'],float)
                    if h.shape!=(2,) or not np.isfinite(h).all() or not np.isclose(np.linalg.norm(h),1.):raise ValueError('Unit direction required')
                    v=(boxes[:,:2]+boxes[:,2:])/2-point;norm=np.linalg.norm(v,axis=1)
                    cosine=np.divide(v@h,norm,out=np.ones(len(v)),where=norm>1e-9)
                    keep&=cosine>=np.cos(np.radians(cone_deg))-1e-8
                masks|=keep.astype(np.uint64)*np.uint64(1<<(len(targets)+j))
        out[name]=(boxes,masks,energy)
    return out,extended


def one(task):
    native,observations,out=map(Path,task);scene=M.load_native(native);raw=json.loads(native.read_text(encoding='utf-8'))
    rec=json.loads(observations.read_text(encoding='utf-8'));row=next(r for r in rec['rows'] if r['method']=='generic' and r['coverage']==1. and r['visits']==14)
    ep=coverage_route(scene);ratio=len(ep['reachable_ids'])/len(ep['free_ids']);path=survey_prefixes(ep,[1/ratio])[0]['path'];base=[]
    association=raw['selection']['chair_to_desk_truth_only']
    for point in sorted({tuple(e['pos']) for e in row['events'] if e['object']=='chair'}):
        chair=min((k for k in scene['gt'] if M.category(k)=='chair'),key=lambda k:np.linalg.norm((scene['gt'][k][:2]+scene['gt'][k][2:])/2-point))
        box=scene['gt'][association[chair]];v=(box[:2]+box[2:])/2-point;v=v/np.linalg.norm(v)
        base.append({'pos':list(point),'bearing':v.tolist()})
    rng=np.random.default_rng(61300000+int(scene['scene'].split('-')[-1]));common=float(rng.normal());cache={};original=M._constraint_search;rows=[]
    for method,sigma in [('no_extra_channel',None),('distance_only',None),('oracle_bearing_sigma0',0.),('oracle_bearing_sigma20',20.),('oracle_bearing_sigma40',40.)]:
        bearings=[]
        for b in base:
            if method=='no_extra_channel':continue
            h=None
            if sigma is not None:
                a=np.radians(common*sigma);c,s=np.cos(a),np.sin(a);h=(np.array([[c,-s],[s,c]])@np.asarray(b['bearing'])).tolist()
            bearings.append({'pos':b['pos'],'bearing':h})
        def select(inventory,pools,targets,counts):
            ranked=rerank_pools(pools,[scene['W'],scene['L']],path,'outline');ranked,extended=add_bearings(ranked,targets,bearings)
            return original(inventory,ranked,extended,counts)
        M._constraint_search=select
        try:r=M.decode_instances([scene['W'],scene['L']],scene['inventory'],row['events'],path,proposal_cache=cache)
        finally:M._constraint_search=original
        rows.append({'method':method,'status':r['status'],'score':M.score_instances(r['boxes'],scene['gt']),'bearings':bearings})
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'scene':scene['scene'],'rows':rows}),encoding='utf-8');return rows


def run(native,observations,out,workers=10):
    native,observations,out=map(Path,(native,observations,out));files=sorted(native.glob('*.json'));allrows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for rows in pool.map(one,[(str(f),str(observations/f.name),str(out/'rooms'/f.name)) for f in files]):allrows.extend(rows)
    summary={}
    for method in sorted({r['method'] for r in allrows}):
        rows=[r for r in allrows if r['method']==method];summary[method]={'n_rooms':len(rows),'whole_hits':sum(r['score']['all_instances_hit'] for r in rows),'f1':float(np.mean([r['score']['f1'] for r in rows])),
            'desk_recall':sum(r['score']['per_class']['desk']['tp'] for r in rows)/sum(r['score']['per_class']['desk']['n_truth'] for r in rows)}
    result={'scope':__doc__,'condition':'100%/14 on original1000 development rooms; same retained proposals and outline estimator','cone_deg':45.,'max_distance_m':.9,'noise':'One common zero-mean Gaussian yaw error per room, matched draw across sigma; not independent repeated measurements','measured_arm':{'status':'unavailable','reason':'No independently validated body-facing estimate; never substituted with truth'},'summary':summary}
    out.mkdir(parents=True,exist_ok=True);(out/'results.json').write_text(json.dumps(result,indent=1),encoding='utf-8');print(json.dumps(result,indent=1));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--observations',required=True);p.add_argument('--out',required=True);p.add_argument('--workers',type=int,default=10);a=p.parse_args();run(a.native,a.observations,a.out,a.workers)
