"""Frozen decoder controls on simple rooms, with explicit prior arms.

Reuses the original route/contact/continuous-region protocol. Omits the unrelated
finite-bank baseline to make the declared comparisons practical. No truth box
enters a decoder; truth is used only by the simulation generator and evaluator.
"""
import argparse,concurrent.futures,hashlib,json,time
from pathlib import Path
import numpy as np
from . import sim_eval as SE,activity_surface as AS
from .continuous_regions import object_region,contains_box
from .continuous_decode import decode
from .exp_walk_range import coverage_route,survey_prefixes

OBJECTS=('bed','desk','cab','chair')
COVERAGES=(0.,.70,.85,.95,1.)
VISITS=(0,2,5)
METHODS=('legacy','solid','family')


def evaluate_scene(task):
    source,out,cells,methods=task;source=Path(source);out=Path(out)
    scene=SE.load_scene(str(source));rows=[]
    if scene is None:raise ValueError('Unparseable source scene '+str(source))
    room=[scene['W'],scene['L']];dims={o:np.asarray(scene['gt'][o][2:])-scene['gt'][o][:2] for o in scene['gt']}
    try:
        episode=coverage_route(scene);ratio=len(episode['reachable_ids'])/len(episode['free_ids'])
        coverages=sorted(set(c for c,n in cells));prefixes=survey_prefixes(episode,[c/ratio for c in coverages])
        prefixes=dict(zip(coverages,prefixes))
        for cov,count in cells:
            prefix=prefixes[cov];path=prefix['path'] if cov>0 else np.empty((0,2))
            events=AS.event_sequence(scene,path,count,'dispersed')
            unique=sorted(set((e['object'],*e['pos']) for e in events));compact=[{'object':o,'pos':[x,y]} for o,x,y in unique]
            executable=bool(prefix['reached'] and len(events)==count)
            for method in methods:
                relation=.90 if method=='family' else None
                regions={o:object_region(room,dims[o],o,compact,path,path_margin=0.,walk_clearance_m=.15,desk_seat_max_distance=relation) for o in dims}
                truth_compatible=all(contains_box(regions[o],scene['gt'][o]) for o in regions)
                result=decode(room,regions,compact,path,solid_storage=method!='legacy',desk_seat_max_distance=relation)
                objects={}
                for o in OBJECTS:
                    b=result['boxes'].get(o);target=np.asarray(scene['gt'][o]);tc=(target[:2]+target[2:])/2
                    if b is None:objects[o]={'error_m':None,'radius_upper_m':None,'iou':0.};continue
                    p=(b[:2]+b[2:])/2;bounds=regions[o]['center_bounds_m'];radius=float(np.linalg.norm(np.maximum(abs(bounds[:2]-p),abs(bounds[2:]-p))))
                    objects[o]={'error_m':float(np.linalg.norm(p-tc)),'radius_upper_m':radius,'iou':SE.iou(b,target)}
                rows.append({'scene':scene['scene'],'method':method,'coverage':cov,'visits':count,'executable':executable,
                    'coverage_actual':prefix['coverage_free'] if cov>0 else 0.,'status':result['status'],'truth_compatible':truth_compatible,
                    'objects':objects,'boxes':{o:np.asarray(b).tolist() for o,b in result['boxes'].items()},
                    'contact_counts':{o:sum(e['object']==o for e in events) for o in OBJECTS}})
    except Exception as exc:
        # Failure is kept in the frozen denominator, never quietly filtered.
        rows=[{'scene':scene['scene'],'method':m,'coverage':c,'visits':n,'executable':False,
               'status':'evaluation_error','error':repr(exc),'objects':{}} for c,n in cells for m in methods]
    record={'scene':scene['scene'],'scene_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(record,separators=(',',':')),encoding='utf-8')
    return scene['scene'],len(rows)


def summarize(records,cells,methods):
    n=len(records);rows=[r for rec in records for r in rec['rows']];out=[]
    for method in methods:
        for cov,count in cells:
            part=[r for r in rows if r['method']==method and r['coverage']==cov and r['visits']==count]
            assert len(part)==n and len(set(r['scene'] for r in part))==n
            def ok(r,metric,cut):
                return r['executable'] and set(r['objects'])==set(OBJECTS) and all(
                    (o.get(metric) is not None and (o[metric]>=cut if metric=='iou' else o[metric]<=cut)) for o in r['objects'].values())
            rec={'method':method,'coverage':cov,'visits':count,'rooms':n,'executable':sum(r['executable'] for r in part),
                 'hits':sum(ok(r,'error_m',.5) for r in part),'all_iou_ge_05':sum(ok(r,'iou',.5) for r in part),
                 'all_radius_le_05':sum(ok(r,'radius_upper_m',.5) for r in part),'objects':{},
                 'truth_in_declared_outer_sets':sum(r.get('truth_compatible',False) for r in part),
                 'evaluation_errors':sum(r['status']=='evaluation_error' for r in part)}
            for obj in OBJECTS:
                errors=[r['objects'].get(obj,{}).get('error_m') for r in part];errors=[v for v in errors if v is not None]
                rec['objects'][obj]={'hits':sum(r['executable'] and r['objects'].get(obj,{}).get('error_m') is not None and r['objects'][obj]['error_m']<=.5 for r in part),
                    'median_error_m':float(np.median(errors)) if errors else None}
            out.append(rec)
    return out


def run(scenes,out,workers=6,limit=None,methods=METHODS,cells=None):
    files=sorted(Path(scenes).glob('FloorPlan*.json'));files=files[:limit] if limit else files
    cells=cells or ((0.,0),)+tuple((c,n) for c in COVERAGES if c>0 for n in VISITS)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    protocol={'n_rooms':len(files),'cells':cells,'methods':methods,'desk_seat_bound_m':.90,
        'source':'Explicit scene file list, frozen before decoding','source_scene_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'known_information':'Room box, exact nominal sizes and target classes; ideal trajectory/contact coordinates',
        'legacy':'Frozen original decoder, wall-shelf projection overlap permission',
        'solid':'Only add non-overlap of desk with floor-standing storage',
        'family':'Solid plus explicitly known seated-at-desk protocol, anchor-to-desk distance <=0.90m',
        'warning':'Controlled geometric experiment, not raw IMU and not a universal threshold'}
    protocol['source_code_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('continuous_decode.py'),Path(__file__).with_name('continuous_regions.py'),Path(AS.__file__)]}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=1),encoding='utf-8')
    tasks=[(str(p),str(out/'rooms'/(p.stem+'.json')),cells,methods) for p in files];start=time.time();done=0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for name,n in pool.map(evaluate_scene,tasks,chunksize=1):
            done+=1
            if done==1 or done%50==0:print(json.dumps({'done':done,'rooms':len(files),'seconds':round(time.time()-start,1)}),flush=True)
    records=[json.loads((out/'rooms'/(p.stem+'.json')).read_text(encoding='utf-8')) for p in files]
    summaries=summarize(records,cells,methods)
    result={'protocol':protocol,'seconds':time.time()-start,'summary':summaries}
    (out/'results.json').write_text(json.dumps(result,indent=1),encoding='utf-8');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scenes',required=True);p.add_argument('--out',required=True);p.add_argument('--workers',type=int,default=6);p.add_argument('--limit',type=int);p.add_argument('--methods',nargs='+',default=list(METHODS));p.add_argument('--single-cell',action='store_true');a=p.parse_args()
    r=run(a.scenes,a.out,a.workers,a.limit,tuple(a.methods),((.95,5),) if a.single_cell else None)
    print(json.dumps([{'method':s['method'],'coverage':s['coverage'],'visits':s['visits'],'hits':s['hits'],'rooms':s['rooms']} for s in r['summary']],indent=1))
