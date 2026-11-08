"""Label why each development room was or was not recovered.

Per object, three flags that are allowed to overlap: the truth itself violates
the constraints the decoder declared, the declared support never comes within
tolerance of the truth, and a point estimate was selected but missed. A
certified ambiguity witness is reported beside them. The decoder never sees
truth; every truth read here is evaluator side.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from . import evidence_space as ES, sim_eval as SE, paths
from .activity_experiment import contact_targets
from .exp_walk_range import survey_prefixes, infer_control, ambiguity_witness, FRACTIONS

CONTROLS=('A','TA-current','TA-walk-oracle','T-walk-oracle')
OBJECTS=('bed','desk','cab','chair')
PADDING=.20
REACH=.60
MARGIN=.08
TOL=.5


def _grid(scene,spacing,body_clearance):
    room=np.array([scene['W'],scene['L']])
    xs=np.linspace(body_clearance,room[0]-body_clearance,max(2,int(np.ceil(room[0]/spacing))))
    ys=np.linspace(body_clearance,room[1]-body_clearance,max(2,int(np.ceil(room[1]/spacing))))
    xx,yy=np.meshgrid(xs,ys)
    points=np.c_[xx.ravel(),yy.ravel()]
    blocked=np.zeros(len(points),bool)
    boxes=list(scene['gt'].values())
    for box in boxes:
        b=np.asarray(box)
        blocked|=np.all((points>b[:2]-body_clearance)&(points<b[2:]+body_clearance),axis=1)
    return points,blocked,boxes,len(xs),len(ys),room


def _neighbours(i,points,blocked,boxes,nx,ny,body_clearance):
    y,x=divmod(i,nx)
    for dy,dx in ((0,1),(1,0),(0,-1),(-1,0)):
        cy,cx=y+dy,x+dx
        if not (0<=cy<ny and 0<=cx<nx):continue
        j=cy*nx+cx
        if blocked[j]:continue
        a=points[i];b=points[j];valid=True
        for box in boxes:
            lo=np.asarray(box[:2])-body_clearance;hi=np.asarray(box[2:])+body_clearance
            axis=0 if dy==0 else 1;other=1-axis
            if lo[other]<a[other]<hi[other] and min(max(a[axis],b[axis]),hi[axis])>max(min(a[axis],b[axis]),lo[axis]):
                valid=False;break
        if valid:yield j


def sweep_route(scene,spacing=.20,body_clearance=.15):
    """Same passable grid as the depth-first survey, swept row by row.

    A second nested ordering only: identical grid, identical clearance and the
    same coverage definition, so the two orders are comparable.
    """
    points,blocked,boxes,nx,ny,room=_grid(scene,spacing,body_clearance)
    free=np.flatnonzero(~blocked)
    if not len(free):raise ValueError('No body-clear floor centre in rectangle approximation')
    start=int(free[np.linalg.norm(points[free]-scene['S'],axis=1).argmin()])
    reachable={start};stack=[start]
    while stack:
        i=stack.pop()
        for j in _neighbours(i,points,blocked,boxes,nx,ny,body_clearance):
            if j not in reachable:reachable.add(j);stack.append(j)
    order=[]
    for y in range(ny):
        columns=range(nx) if y%2==0 else range(nx-1,-1,-1)
        order.extend([y*nx+x for x in columns if y*nx+x in reachable])
    def path_between(source,target):
        if source==target:return [source]
        parent={source:None};queue=[source]
        while queue:
            nxt=[]
            for i in queue:
                for j in _neighbours(i,points,blocked,boxes,nx,ny,body_clearance):
                    if j in parent:continue
                    parent[j]=i
                    if j==target:
                        chain=[j]
                        while parent[chain[-1]] is not None:chain.append(parent[chain[-1]])
                        return chain[::-1]
                    nxt.append(j)
            queue=nxt
        return None
    route=[start];current=start
    for node in order:
        if node==current:continue
        step=path_between(current,node)
        if not step:continue
        route.extend(step[1:]);current=node
    room_points=np.array([(x,y) for x in np.arange(.05,room[0],.10) for y in np.arange(.05,room[1],.10)])
    return {'points':points,'free_ids':free,'reachable_ids':np.array(sorted(reachable)),
            'route_ids':np.array(route),'room_points':room_points,'room':room,
            'spacing_m':spacing,'body_clearance_m':body_clearance}


def truth_checks(scene,events,path,control):
    """Evaluator side: is the true layout itself admissible in the declared model?"""
    excluded=() if control=='A' else ('desk','cab') if control=='TA-current' else OBJECTS
    checks={}
    for obj,box in scene['gt'].items():
        box=np.asarray(box,float)
        events_ok=True
        for event in events:
            if event['object']!=obj:continue
            keep,_=ES._contact(box[None,:],event,PADDING,REACH)
            if not bool(keep[0]):events_ok=False;break
        path_ok=True
        if obj in excluded and len(path):
            path_ok=not bool(ES._path_bad(box[None,:],np.asarray(path,float),MARGIN)[0])
        checks[obj]={'events_compatible':events_ok,'path_compatible':path_ok,
                     'admissible_in_declared_model':bool(events_ok and path_ok)}
    return checks


def label(check,box_count,nearest,error):
    if not check['admissible_in_declared_model']:return 'model_excludes_truth'
    if not box_count:return 'support_empty'
    if nearest is None or nearest>TOL:return 'support_misses_truth'
    if error is None or error>TOL:return 'selected_but_wrong'
    return 'recovered'


def diagnose(scene,events,prefix,control,result,scores,witness):
    checks=truth_checks(scene,events,prefix['path'],control)
    rows=[]
    for obj in OBJECTS:
        if obj not in scene['gt']:continue
        row=result['objects'].get(obj,{})
        boxes=np.asarray(row.get('support_boxes',[]))
        target=np.asarray(scene['gt'][obj],float)
        centre=(target[:2]+target[2:])/2
        nearest=None
        if len(boxes):
            nearest=float(np.linalg.norm(ES.centres(boxes)-centre,axis=1).min())
        error=scores['center_error_m'].get(obj)
        check=checks[obj]
        rows.append({'object':obj,**check,'support_n':int(row.get('n',0) or 0),
                     'nearest_support_centre_m':nearest,'point_error_m':error,
                     'truth_centre_in_envelope':scores['truth_center_in_envelope'].get(obj),
                     'witness_for_object':bool(witness.get('certified_in_declared_geometric_model') and witness.get('object')==obj),
                     'witness_separation_m':witness.get('separation_m') if witness.get('object')==obj else None,
                     'label':label(check,len(boxes),nearest,error)})
    return rows,witness


def run(output,scene_limit=None,fractions=FRACTIONS,orders=('depth_first','row_sweep'),full=None):
    files=sorted(Path(paths.THOR).glob('FloorPlan*.json'))
    scenes=[s for f in files if (s:=SE.load_scene(str(f)))]
    if scene_limit:scenes=scenes[:scene_limit]
    rows=[];failures=[]
    for order in orders:
        for index,scene in enumerate(scenes):
            room=[scene['W'],scene['L']]
            dims={o:(b[2]-b[0],b[3]-b[1]) for o,b in scene['gt'].items()}
            banks=ES.make_bank(room,dims,spacing=.20)
            targets,_=contact_targets(scene,np.random.default_rng(19031+index))
            events=[{'object':o,'pos':p.tolist()} for o,p in targets.items() if p is not None]
            try:
                episode=sweep_route(scene) if order=='row_sweep' else None
                if episode is None:
                    from .exp_walk_range import coverage_route
                    episode=coverage_route(scene)
                prefixes=survey_prefixes(episode)
            except ValueError as e:
                failures.append({'scene':scene['scene'],'order':order,'reason':str(e)});continue
            for fraction in fractions:
                prefix=next((p for p in prefixes if p['target_reachable_fraction']==fraction),None)
                if prefix is None:continue
                for control in CONTROLS:
                    result=infer_control(room,banks,prefix['path'],events,control)
                    scores=ES.evaluate(result,scene['gt'],TOL)
                    witness=ambiguity_witness(result,TOL)
                    objects,witness=diagnose(scene,events,prefix,control,result,scores,witness)
                    rows.append({'scene':scene['scene'],'order':order,'control':control,'fraction':fraction,
                                 'coverage_room':prefix['coverage_room'],'walk_m':prefix['walk_m'],
                                 'status':result['status'],
                                 'witness':{'certified':bool(witness.get('certified_in_declared_geometric_model')),
                                            'object':witness.get('object'),
                                            'separation_m':witness.get('separation_m')},
                                 'objects':objects})
            print(order,scene['scene'],'done',flush=True)
    summary=[]
    for order in orders:
        for fraction in fractions:
            for control in CONTROLS:
                selected=[r for r in rows if r['order']==order and r['control']==control and r['fraction']==fraction]
                for obj in OBJECTS:
                    picked=[o for r in selected for o in r['objects'] if o['object']==obj]
                    if not picked:continue
                    counts={}
                    for item in picked:counts[item['label']]=counts.get(item['label'],0)+1
                    missed=[i for i in picked if i['label']!='recovered']
                    summary.append({'order':order,'control':control,'fraction':fraction,'object':obj,
                                    'n':len(picked),'labels':counts,
                                    'admissible_rate':sum(i['admissible_in_declared_model'] for i in picked)/len(picked),
                                    'witness_rate':sum(i['witness_for_object'] for i in picked)/len(picked),
                                    'missed':len(missed),
                                    'missed_with_witness':sum(1 for i in missed if i['witness_for_object']),
                                    'witness_minimax_floor_m':float(np.median([i['witness_separation_m'] for i in missed if i['witness_for_object']]))/2 if any(i['witness_for_object'] for i in missed) else None,
                                    'median_point_error_m':float(np.median([i['point_error_m'] for i in picked if i['point_error_m'] is not None])) if any(i['point_error_m'] is not None for i in picked) else None})
                rooms=selected
                summary.append({'order':order,'control':control,'fraction':fraction,'object':'layout','n':len(rooms),
                                'layouts_with_witness':sum(1 for r in rooms if r['witness']['certified']),
                                'layouts_one_object_model_excluded':sum(1 for r in rooms if any(o['label']=='model_excludes_truth' for o in r['objects'])),
                                'layouts_support_empty_any':sum(1 for r in rooms if any(o['label']=='support_empty' for o in r['objects'])),
                                'layouts_fully_recovered':sum(1 for r in rooms if all(o['label']=='recovered' for o in r['objects'])),
                                'layouts_miss_without_witness':sum(1 for r in rooms if any(o['label'] not in ('recovered','model_excludes_truth','support_empty') and not o['witness_for_object'] for o in r['objects'])),
                                'median_room_coverage':float(np.median([r['coverage_room'] for r in rooms])) if rooms else None,
                                'median_walk_m':float(np.median([r['walk_m'] for r in rooms])) if rooms else None})
    def compact(value,digits=3):
        if isinstance(value,float):return round(value,digits)
        if isinstance(value,dict):return {k:compact(v,digits) for k,v in value.items()}
        if isinstance(value,list):return [compact(v,digits) for v in value]
        return value

    record={'scope':'Evaluator-side diagnosis of the geometric development control; no raw IMU',
            'protocol':{'orders':list(orders),'fractions':list(fractions),'controls':list(CONTROLS),
                        'padding_m':PADDING,'reach_m':REACH,'path_margin_m':MARGIN,'tolerance_m':TOL,
                        'labels':'model_excludes_truth | support_empty | support_misses_truth | selected_but_wrong | recovered',
                        'labels_overlap':'flags per object are recorded beside the primary label',
                        'second_order':'row_sweep uses the same grid, clearance and coverage definition as the depth-first survey'},
            'failures':failures,'summary':compact(summary),
            'rows_scope':'per-row detail kept for the final fraction only; every fraction is aggregated in summary',
            'rows':compact([r for r in rows if r['fraction']==max(fractions)])}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8')
    if full:
        Path(full).write_text(json.dumps({'rows':compact(rows)},ensure_ascii=False,indent=1),encoding='utf-8')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--scene-limit',type=int)
    p.add_argument('--full',help='optional path for the complete per-fraction rows')
    a=p.parse_args();r=run(a.output,a.scene_limit,full=a.full)
    print(json.dumps({'rows':len(r['rows']),'failures':r['failures']}))
