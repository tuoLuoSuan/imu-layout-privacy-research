"""Matched spatial-event label controls; A already contains localisation."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from . import evidence_space as ES,sim_eval as SE,paths
from .activity_experiment import route_episode,prefix_episode


def cycle_labels(events,shift):
    names=('chair','cab','bed')
    if shift not in (1,2):raise ValueError('Use a class derangement')
    return [dict(e,object=names[(names.index(e['object'])+shift)%3]) for e in events]


def run(output,seed=17031,budgets=(32.,96.)):
    scenes=[s for f in sorted(Path(paths.THOR).glob('FloorPlan*.json')) if (s:=SE.load_scene(str(f)))]
    rows=[]
    for index,scene in enumerate(scenes):
        room=(scene['W'],scene['L']);banks=ES.make_bank(room,{o:(b[2]-b[0],b[3]-b[1]) for o,b in scene['gt'].items()})
        ep=route_episode(scene,'dispersed',seed+index)
        for budget in budgets:
            path,events=prefix_episode(ep,budget)
            variants=[('T',True,False,events),('A-spatial',False,True,events),('TA',True,True,events),
                      ('TA-cycle1',True,True,cycle_labels(events,1)),('TA-cycle2',True,True,cycle_labels(events,2))]
            for arm,use_path,use_actions,observed in variants:
                result=ES.infer(room,banks,path,observed,use_path,use_actions)
                rows.append({'scene':scene['scene'],'budget_m':budget,'arm':arm,'coverage':ES.spatial_coverage(path,room),
                     'path_sha256':hashlib.sha256(path.tobytes()).hexdigest(),
                     'event_positions_sha256':hashlib.sha256(np.asarray([e['pos'] for e in observed]).tobytes()).hexdigest(),
                     'scores':ES.evaluate(result,scene['gt']),
                     'event_counts':{o:sum(e['object']==o for e in observed) for o in ['bed','cab','chair']}})
        print(scene['scene'],'done',flush=True)
    summary=[]
    for budget in budgets:
        for arm in ['T','A-spatial','TA','TA-cycle1','TA-cycle2']:
            selected=[r for r in rows if r['arm']==arm and r['budget_m']==budget]
            summary.append({'budget_m':budget,'arm':arm,'n_rooms':len(selected),
               'success':{o:sum(r['scores']['center_error_m'][o] is not None and r['scores']['center_error_m'][o]<=.5 for r in selected)
                          for o in ['bed','desk','cab','chair']},
               'full_success':sum(r['scores']['full_point_hit'] for r in selected)})
    record={'scope':'Geometric oracle development; same path and anchor positions, class correspondence changed',
        'A':'Spatialised interactions with class and position; includes localisation evidence',
        'control':'Two fixed-point-free class cycles; event count/positions fixed, per-class counts can permute',
        'seed':seed,'scene_count':len(scenes),'rows':rows,'summary':summary}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8');return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--seed',type=int,default=17031)
    a=p.parse_args();run(a.output,a.seed)
