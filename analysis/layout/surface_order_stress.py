"""Stress the frozen 95%/6-visit development candidate on another survey order.
Same rooms, so this is route-order stress, never independent-room confirmation.
"""
import argparse,json
from pathlib import Path
import numpy as np
from . import sim_eval as SE,paths
from .activity_surface import event_sequence
from .continuous_regions import object_region,contains_box
from .continuous_decode import decode
from .exp_diagnose import sweep_route
from .exp_walk_range import survey_prefixes


def run(output):
    rows=[];invalid=[]
    for f in sorted(Path(paths.THOR).glob('FloorPlan*.json')):
        scene=SE.load_scene(str(f))
        if not scene:continue
        dims={o:np.asarray(b[2:])-b[:2] for o,b in scene['gt'].items()}
        if any(min(v)<=0 for v in dims.values()):invalid.append(scene['scene']);continue
        episode=sweep_route(scene);ratio=len(episode['reachable_ids'])/len(episode['free_ids'])
        prefixes=survey_prefixes(episode,[c/ratio for c in [.95,.98,1.]])
        for target,prefix in zip([.95,.98,1.],prefixes):
            path=prefix['path'];cache={}
            for visits in [6,9,12]:
                events=event_sequence(scene,path,visits,'dispersed')
                unique=tuple(sorted(set((e['object'],*e['pos']) for e in events)))
                if unique not in cache:
                    compact=[{'object':o,'pos':[x,y]} for o,x,y in unique]
                    regions={o:object_region([scene['W'],scene['L']],size,o,compact,path,path_margin=0.,walk_clearance_m=.15) for o,size in dims.items()}
                    assert all(contains_box(regions[o],scene['gt'][o]) for o in regions)
                    result=decode([scene['W'],scene['L']],regions,compact,path)
                    err={o:None for o in dims}
                    for o,b in result['boxes'].items():
                        true=np.asarray(scene['gt'][o]);err[o]=float(np.linalg.norm((b[:2]+b[2:]-true[:2]-true[2:])/2))
                    cache[unique]=(result,err)
                result,err=cache[unique]
                executable=prefix['reached'] and len(events)==visits
                rows.append({'scene':scene['scene'],'coverage_target':target,'visits':visits,
                    'coverage_free':prefix['coverage_free'],'walk_m':prefix['walk_m'],'executable':executable,
                    'status':result['status'],'centre_errors_m':err,
                    'success':executable and all(v is not None and v<=.5 for v in err.values())})
        print(scene['scene'],'route-order stress done',flush=True)
    summary=[]
    for c in [.95,.98,1.]:
        for n in [6,9,12]:
            picked=[r for r in rows if r['coverage_target']==c and r['visits']==n]
            summary.append({'coverage_target':c,'visits':n,'rooms':len(picked),
                'successes':sum(r['success'] for r in picked),'rate_lower':sum(r['success'] for r in picked)/len(picked),
                'censored':sum(not r['executable'] for r in picked)})
    record={'scope':'Same-development-room route-order stress of previously frozen95%/6 candidate; not independent confirmation',
        'protocol':{'coverage':[.95,.98,1.],'visits':[6,9,12],'target_error_m':.5,'success_rate_target':.8},
        'invalid_geometry':invalid,'candidate_survives':all(r['rate_lower']>=.8 for r in summary),
        'summary':summary,'rows':rows}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8');return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();r=run(a.output)
    print(json.dumps({'candidate_survives':r['candidate_survives'],'summary':r['summary']}))
