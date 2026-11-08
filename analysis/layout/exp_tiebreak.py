"""How much of the point error is the tie-break rather than the evidence?

The joint beam ranks admissible layouts by an energy. For a furniture class with
no contact evidence the energy is flat, and production adds a small preference
for members near the supported centroid. This arm replaces that preference with
nothing and with random draws, on the same observations, to separate
"evidence does not decide" from "the ranking decided".
"""
import argparse
import json
from pathlib import Path
import numpy as np
from . import evidence_space as ES, sim_eval as SE, paths
from .activity_experiment import contact_targets
from .exp_walk_range import coverage_route, survey_prefixes

OBJECTS=('bed','desk','cab','chair')
TOL=.5
DRAWS=20


def infer_ta(room,banks,path,events,tie_break,rng=None):
    excluded=('desk','cab')
    selected={obj:bank[~ES._path_bad(bank,path,.08)] if obj in excluded else bank
              for obj,bank in banks.items()}
    return ES.infer(room,selected,[],events,False,True,None,padding=.20,
                    tie_break=tie_break,rng=rng)


def run(output,scene_limit=None,fraction=1.0,draws=DRAWS):
    files=sorted(Path(paths.THOR).glob('FloorPlan*.json'))
    scenes=[s for f in files if (s:=SE.load_scene(str(f)))]
    if scene_limit:scenes=scenes[:scene_limit]
    rows=[]
    for index,scene in enumerate(scenes):
        room=[scene['W'],scene['L']]
        dims={o:(b[2]-b[0],b[3]-b[1]) for o,b in scene['gt'].items()}
        banks=ES.make_bank(room,dims,spacing=.20)
        targets,_=contact_targets(scene,np.random.default_rng(19031+index))
        events=[{'object':o,'pos':p.tolist()} for o,p in targets.items() if p is not None]
        prefix=next(p for p in survey_prefixes(coverage_route(scene))
                    if p['target_reachable_fraction']==fraction)
        arms=[('centroid',None),('none',None)]+[('random',1000+d) for d in range(draws)]
        for arm,rng in arms:
            result=infer_ta(room,banks,prefix['path'],events,arm,rng)
            scores=ES.evaluate(result,scene['gt'],TOL)
            rows.append({'scene':scene['scene'],'arm':arm,'seed':rng,'status':result['status'],
                         'centre_error_m':scores['center_error_m'],
                         'hit':{o:(scores['center_error_m'][o] is not None and
                                   scores['center_error_m'][o]<=TOL) for o in OBJECTS},
                         'full_hit':scores['full_point_hit'],
                         'envelope_m':scores['center_diameter_upper_m']})
        print(scene['scene'],'done',flush=True)
    summary=[]
    for arm in ('centroid','none','random'):
        picked=[r for r in rows if r['arm']==arm]
        entry={'arm':arm,'n_rows':len(picked),'n_rooms':len({r['scene'] for r in picked})}
        for obj in OBJECTS:
            hits=[r['hit'][obj] for r in picked]
            errors=[r['centre_error_m'][obj] for r in picked if r['centre_error_m'][obj] is not None]
            entry[obj]={'hit_rate':float(np.mean(hits)),
                        'median_error_m':float(np.median(errors)) if errors else None,
                        'p90_error_m':float(np.percentile(errors,90)) if errors else None}
        entry['full_hit_rate']=float(np.mean([r['full_hit'] for r in picked]))
        summary.append(entry)
    record={'scope':'Same observations, different tie-break inside the frozen joint beam; geometric development set',
            'protocol':{'fraction':fraction,'draws':draws,'tolerance_m':TOL,
                        'arms':{'centroid':'production: 0.001 * distance from the supported centroid',
                                'none':'no preference, stable order only',
                                'random':'1e-6 * uniform draw, %d seeds'%draws},
                        'note':'random draws estimate the spread of the point estimate, not a better method'},
            'summary':summary,'rows':rows}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--scene-limit',type=int)
    a=p.parse_args();r=run(a.output,a.scene_limit)
    print(json.dumps([{'arm':s['arm'],**{o:s[o]['hit_rate'] for o in OBJECTS}} for s in r['summary']]))
