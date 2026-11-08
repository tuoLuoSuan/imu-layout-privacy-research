"""Hold contacts fixed, expand walked area: a geometric development control.

The generator may read truth to plan a reachable survey. The decoder only sees
known room/target sizes, fixed available contacts and walk samples. This is not IMU.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from . import evidence_space as ES, sim_eval as SE, paths
from .activity_experiment import contact_targets

FRACTIONS=(0.,.10,.25,.40,.55,.70,.85,.95,1.)


def coverage_route(scene,spacing=.20,body_clearance=.15):
    room=np.array([scene['W'],scene['L']])
    xs=np.linspace(body_clearance,room[0]-body_clearance,max(2,int(np.ceil(room[0]/spacing))))
    ys=np.linspace(body_clearance,room[1]-body_clearance,max(2,int(np.ceil(room[1]/spacing))))
    xx,yy=np.meshgrid(xs,ys);points=np.c_[xx.ravel(),yy.ravel()]
    blocked=np.zeros(len(points),bool)
    boxes=list(scene['gt'].values())
    for box in boxes:
        b=np.asarray(box)
        blocked|=np.all((points>b[:2]-body_clearance)&(points<b[2:]+body_clearance),axis=1)
    free=np.flatnonzero(~blocked)
    if not len(free):raise ValueError('No body-clear floor centre in rectangle approximation')
    start=int(free[np.linalg.norm(points[free]-scene['S'],axis=1).argmin()])
    nx=len(xs);ny=len(ys)
    def neighbours(i):
        y,x=divmod(i,nx)
        for dy,dx in [(0,1),(1,0),(0,-1),(-1,0)]:
            cy,cx=y+dy,x+dx
            if not (0<=cy<ny and 0<=cx<nx):continue
            j=cy*nx+cx
            if blocked[j]:continue
            # Nodes alone do not guarantee a segment avoids a thin object.
            a=points[i];b=points[j];valid=True
            for box in boxes:
                lo=np.asarray(box[:2])-body_clearance;hi=np.asarray(box[2:])+body_clearance
                axis=0 if dy==0 else 1;other=1-axis
                if lo[other]<a[other]<hi[other] and min(max(a[axis],b[axis]),hi[axis])>max(min(a[axis],b[axis]),lo[axis]):
                    valid=False;break
            if valid:yield j
    # Deterministic nested depth-first walk, including return edges (actual distance).
    visited={start};stack=[(start,iter(neighbours(start)))];route=[start]
    while stack:
        current,it=stack[-1]
        nxt=next(it,None)
        if nxt is None:
            stack.pop()
            if stack:route.append(stack[-1][0])
        elif nxt not in visited:
            visited.add(nxt);route.append(nxt);stack.append((nxt,iter(neighbours(nxt))))
    room_points=np.array([(x,y) for x in np.arange(.05,room[0],.10) for y in np.arange(.05,room[1],.10)])
    return {'points':points,'free_ids':free,'reachable_ids':np.array(sorted(visited)),
            'route_ids':np.array(route),'room_points':room_points,'room':room,
            'spacing_m':spacing,'body_clearance_m':body_clearance}


def survey_prefixes(episode,fractions=FRACTIONS,radius=.25):
    points=episode['points'];route=episode['route_ids'];walk=points[route]
    arc=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(walk,axis=0),axis=1))]
    reachable=points[episode['reachable_ids']];free=points[episode['free_ids']]
    room_points=episode['room_points']
    cover_r=np.zeros(len(reachable),bool);cover_f=np.zeros(len(free),bool);cover_room=np.zeros(len(room_points),bool)
    # Store prefix coverage once; revisiting a point adds length, not covered area.
    history=[]
    for i,p in enumerate(walk):
        cover_r|=np.sum((reachable-p)**2,axis=1)<=radius**2+1e-12
        cover_f|=np.sum((free-p)**2,axis=1)<=radius**2+1e-12
        cover_room|=np.sum((room_points-p)**2,axis=1)<=radius**2+1e-12
        history.append((float(cover_r.mean()),float(cover_f.mean()),float(cover_room.mean())))
    rows=[];arr=np.asarray(history)
    for fraction in fractions:
        reached=np.flatnonzero(arr[:,0]>=fraction-1e-12)
        index=int(reached[0]) if len(reached) else len(walk)-1
        rows.append({'target_reachable_fraction':fraction,'reached':bool(len(reached)),
                     'coverage_reachable':arr[index,0],'coverage_free':arr[index,1],
                     'coverage_room':arr[index,2],'covered_room_m2':arr[index,2]*float(np.prod(episode['room'])),
                     'walk_m':float(arc[index]),'walk_span_xy_m':np.ptp(walk[:index+1],axis=0).tolist(),
                     'path':np.unique(walk[:index+1],axis=0)})
    return rows


def infer_control(room,banks,path,events,control):
    objects=() if control=='A' else ('desk','cab') if control=='TA-current' else tuple(banks)
    selected={obj:bank[~ES._path_bad(bank,path,.08)] if obj in objects else bank for obj,bank in banks.items()}
    return ES.infer(room,selected,[],events,False,control!='T-walk-oracle',None,padding=.20)


def ambiguity_witness(result,tolerance=.5):
    """Two compatible full layouts imply a minimax centre error > tolerance.

    All boxes come from the same observation-filtered support banks. We add a
    hard no-overlap check, except the declared under-desk chair projection.
    This constructive sufficient witness is not an exhaustive impossibility test.
    """
    def compatible(layout):
        for i,(o,b) in enumerate(layout.items()):
            for p,c in list(layout.items())[i+1:]:
                if {o,p}=={'desk','chair'}:continue
                if ES._overlap(np.asarray(b),np.asarray(c))>1e-9:return False
        return True
    best=None
    for base in result.get('candidates',[]):
        if not compatible(base):continue
        for obj,row in result['objects'].items():
            bank=np.asarray(row.get('support_boxes',[]))
            if not len(bank):continue
            bc=(np.asarray(base[obj])[:2]+np.asarray(base[obj])[2:])/2
            distance=np.linalg.norm(ES.centres(bank)-bc,axis=1)
            for i in np.argsort(-distance):
                if distance[i]<=2*tolerance:break
                alternative=dict(base,**{obj:bank[i]})
                if compatible(alternative):
                    if best is None or distance[i]>best['separation_m']:
                        best={'certified_in_declared_geometric_model':True,'object':obj,
                              'separation_m':float(distance[i]),'minimax_error_lower_m':float(distance[i]/2),
                              'layouts':[{o:np.asarray(b).tolist() for o,b in layout.items()} for layout in [base,alternative]]}
                    break
        # One physically compatible base is sufficient; no claim of exhaustive search.
        break
    return best or {'certified_in_declared_geometric_model':False,
                    'interpretation':'No witness found by this bounded search; does not imply identifiable'}


def run(output,scene_limit=None):
    files=sorted(Path(paths.THOR).glob('FloorPlan*.json'))
    scenes=[s for f in files if (s:=SE.load_scene(str(f)))]
    if scene_limit:scenes=scenes[:scene_limit]
    rows=[];failures=[]
    for index,scene in enumerate(scenes):
        room=[scene['W'],scene['L']]
        dims={o:(b[2]-b[0],b[3]-b[1]) for o,b in scene['gt'].items()}
        banks=ES.make_bank(room,dims,spacing=.20)
        targets,_=contact_targets(scene,np.random.default_rng(19031+index))
        events=[{'object':o,'pos':p.tolist()} for o,p in targets.items() if p is not None]
        event_hash=hashlib.sha256(json.dumps(events,sort_keys=True).encode()).hexdigest()
        try:
            episode=coverage_route(scene);prefixes=survey_prefixes(episode)
        except ValueError as e:
            failures.append({'scene':scene['scene'],'reason':str(e)});prefixes=[]
        for fraction in FRACTIONS:
            prefix=next((p for p in prefixes if p['target_reachable_fraction']==fraction),None)
            for control in ['A','TA-current','TA-walk-oracle','T-walk-oracle']:
                if prefix is None:
                    rows.append({'scene':scene['scene'],'control':control,'fraction':fraction,'reached':False,
                                 'scores':{'full_point_hit':False,'same_candidate_hit':False,'all_support_hit':False}})
                    continue
                result=infer_control(room,banks,prefix['path'],events,control)
                row={k:v for k,v in prefix.items() if k!='path'}
                row.update(scene=scene['scene'],control=control,fraction=fraction,event_hash=event_hash,
                           event_counts={o:sum(e['object']==o for e in events) for o in banks},
                           status=result['status'],scores=ES.evaluate(result,scene['gt'],.5),
                           ambiguity=ambiguity_witness(result),
                           support_n={o:r['n'] for o,r in result['objects'].items()})
                rows.append(row)
        print(scene['scene'],'done',flush=True)
    summaries=[]
    for control in ['A','TA-current','TA-walk-oracle','T-walk-oracle']:
        for fraction in FRACTIONS:
            selected=[r for r in rows if r['control']==control and r['fraction']==fraction]
            observed=[r for r in selected if 'coverage_room' in r]
            summaries.append({'control':control,'fraction':fraction,'n_rooms':len(selected),
                'reached_rooms':sum(r['reached'] for r in selected),
                'median_room_coverage':float(np.median([r['coverage_room'] for r in observed])) if observed else None,
                'median_free_coverage':float(np.median([r['coverage_free'] for r in observed])) if observed else None,
                'median_walk_m':float(np.median([r['walk_m'] for r in observed])) if observed else None,
                'success_rate':sum(r['scores']['full_point_hit'] and r['reached'] for r in selected)/len(selected),
                'same_candidate_rate':sum(r['scores']['same_candidate_hit'] and r['reached'] for r in selected)/len(selected),
                'all_support_rate':sum(r['scores']['all_support_hit'] and r['reached'] for r in selected)/len(selected),
                'ambiguity_witness_rooms':sum(r.get('ambiguity',{}).get('certified_in_declared_geometric_model',False) and r['reached'] for r in selected),
                'per_object_hit':{o:sum(r['reached'] and r['scores'].get('center_error_m',{}).get(o) is not None and
                         r['scores']['center_error_m'][o]<=.5 for r in selected)/len(selected) for o in ['bed','desk','cab','chair']}})
    record={'scope':'Geometric development control, fixed pre-acquired contacts, later nested walk survey; no raw IMU',
        'protocol':{'fractions':FRACTIONS,'target':'Fraction of generator-reachable body-clear floor sampled within 0.25m',
           'body_clearance_m':.15,'grid_spacing_m':.20,'coverage_radius_m':.25,'success_center_tolerance_m':.5,
           'threshold_rate':.8,'following_points':2,'known_room_and_exact_target_sizes':True,
           'prior':'Uniform feasible bank, not known room family','decoder_grid_m':.20,
           'TA-current':'Only desk/cab exclude walk, production contact permissions retained',
           'TA-walk-oracle':'Perfect walk/contact separation excludes all objects only at walk samples; stronger assumption',
           'T-walk-oracle':'Same stronger walk assumption, no interaction coordinates',
           'statistical_unit':'Scene, not grid point or prefix; 14 development rooms',
           'contact_count_span':'Exactly fixed within scene, two or three available contacts; not an additional-visit experiment',
           'contact_availability':{row['scene']:row['event_counts'] for row in rows if row['control']=='A' and row['fraction']==0 and 'event_counts' in row},
           'decoder':'Finite candidate bank and beam, no proof of information impossibility'},
        'scene_count':len(scenes),'failures':failures,'summary':summaries,'rows':rows,
        'thresholds':{c:ES.stable_threshold([r for r in summaries if r['control']==c],x_key='fraction') for c in ['A','TA-current','TA-walk-oracle','T-walk-oracle']},
        'scene_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--scene-limit',type=int)
    a=p.parse_args();r=run(a.output,a.scene_limit)
    print(json.dumps({'rooms':r['scene_count'],'thresholds':r['thresholds']}))
