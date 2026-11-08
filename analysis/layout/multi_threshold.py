"""Variable-inventory regular rooms: explicit instance-aware geometric controls."""
import argparse,concurrent.futures,hashlib,json,time
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .exp_walk_range import coverage_route,survey_prefixes

CELLS=((0.,0),(.95,5),(.95,11),(1.,5),(1.,11))


def one_room(task):
    source,out,cells=task;scene=M.load_native(source);rows=[]
    try:
        episode=coverage_route(scene);ratio=len(episode['reachable_ids'])/len(episode['free_ids'])
        coverages=sorted({c for c,n in cells});prefixes=dict(zip(coverages,survey_prefixes(episode,[c/ratio for c in coverages])))
        for cov,count in cells:
            prefix=prefixes[cov];path=prefix['path'] if cov>0 else np.empty((0,2));events=M.event_sequence(scene,path,count)
            executable=bool(prefix['reached'] and len(events)==count)
            for method in ['generic','known_desk_protocol']:
                result=M.decode_instances([scene['W'],scene['L']],scene['inventory'],events,path,known_desk_protocol=method!='generic')
                score=M.score_instances(result['boxes'],scene['gt'])
                rows.append({'scene':scene['scene'],'split':scene['split'],'counts':scene['counts'],
                    'coverage':cov,'visits':count,'method':method,'executable':executable,'status':result['status'],
                    'events':events,'score':score,'boxes':{k:np.asarray(v).tolist() for k,v in result['boxes'].items()},
                    'candidate_counts':result.get('candidate_counts')})
    except Exception as exc:
        rows=[{'scene':scene['scene'],'split':scene['split'],'counts':scene['counts'],'coverage':c,'visits':n,
               'method':m,'executable':False,'status':'evaluation_error','error':repr(exc),
               'score':M.score_instances({},scene['gt'])} for c,n in cells for m in ['generic','known_desk_protocol']]
    result={'scene':scene['scene'],'source_sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),'rows':rows}
    Path(out).parent.mkdir(parents=True,exist_ok=True);Path(out).write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
    return scene['scene']


def summarize(records,cells):
    rows=[r for rec in records for r in rec['rows']];out=[]
    for split in ['all','train','val','test']:
        admitted=[r for r in rows if split=='all' or r['split']==split]
        for method in ['generic','known_desk_protocol']:
            for cov,count in cells:
                part=[r for r in admitted if r['method']==method and r['coverage']==cov and r['visits']==count]
                if not part:continue
                n=len(part);hits=sum(r['executable'] and r['status']=='ok' and r['score']['all_instances_hit'] for r in part)
                out.append({'split':split,'method':method,'coverage':cov,'visits':count,'rooms':n,'hits':hits,
                    'executable':sum(r['executable'] for r in part),'output_ok':sum(r['status']=='ok' for r in part),
                    'mean_instance_f1':float(np.mean([r['score']['f1'] if r['executable'] else 0. for r in part])),
                    'per_class':{c:{key:sum(r['score']['per_class'].get(c,{}).get(key,0) if r['executable'] else
                                  (sum(r['counts'].get(c,0) for _ in [0]) if key=='fn' else 0) for r in part)
                                     for key in ['tp','fp','fn']} for c in ['bed','desk','cab','chair']},
                    'evaluation_errors':sum(r['status']=='evaluation_error' for r in part)})
    return out


def run(native,out,workers=8,limit=None,full=True):
    files=sorted(Path(native).glob('*.json'));files=files[:limit] if limit else files
    cells=CELLS if full else ((1.,11),);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    protocol={'n_rooms':len(files),'cells':cells,'source_file_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'given_side_information':'Room rectangle plus inventory categories/counts/exact nominal sizes; not target positions or event-to-instance identity',
        'generic':'Physical non-overlap and class-only semantic events; bounded proposal/constraint search',
        'known_desk_protocol':'Same plus each observed sitting-at-desk anchor is within0.90m of at least one desk; association latent',
        'matching':'Category-wise one-to-one maximum centre matches, tolerance0.5m, extra and missing objects count',
        'coverage':'All body-clear floor;0.25m neighbourhood; ideal walk coordinates,0.15m clearance',
        'warning':'Own controlled regular rooms, not raw IMU, not a statistically calibrated uncertainty certificate',
        'source_code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(M.__file__)]}}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=1),encoding='utf-8')
    tasks=[(str(p),str(out/'rooms'/(p.stem+'.json')),cells) for p in files];start=time.time();done=0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for name in pool.map(one_room,tasks,chunksize=1):
            done+=1
            if done==1 or done%25==0:print(json.dumps({'done':done,'rooms':len(files),'seconds':round(time.time()-start,1)}),flush=True)
    records=[json.loads((out/'rooms'/(p.stem+'.json')).read_text(encoding='utf-8')) for p in files]
    result={'protocol':protocol,'seconds':time.time()-start,'summary':summarize(records,cells)}
    (out/'results.json').write_text(json.dumps(result,indent=1),encoding='utf-8');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--workers',type=int,default=8);p.add_argument('--limit',type=int);p.add_argument('--smoke',action='store_true');a=p.parse_args()
    r=run(a.native,a.out,a.workers,a.limit,not a.smoke);print(json.dumps([x for x in r['summary'] if x['split']=='all'],indent=1))
