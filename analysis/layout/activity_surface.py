"""Factorial walk-coverage x independent-interaction benchmark.

Oracle geometric study, not raw IMU. Only already reachable operation locations
can supply cabinet events; bed/chair contacts can enter their own footprints.
Extra visits use an already explored approach and do not force new walk area.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from . import sim_eval as SE,evidence_space as ES,paths
from .continuous_regions import object_region,contains_box
from .continuous_decode import decode as joint_decode
from .exp_walk_range import coverage_route,survey_prefixes,FRACTIONS

VISITS=(0,1,2,3,6,9,12,18)
COVERAGES=(0.,.1,.25,.4,.55,.7,.85,.9,.95,.98,1.)
POLICIES=('repeat','dispersed')


def _distance(points,box):
    return np.linalg.norm(np.maximum(np.asarray(box[:2])-points,points-np.asarray(box[2:])).clip(min=0),axis=1)


def event_sequence(scene,path,count,policy):
    """A nested visit sequence at fixed walked area, no future-event access."""
    if policy not in POLICIES:raise ValueError('Unknown contact policy')
    path=np.asarray(path,float).reshape(-1,2);pool={}
    if not len(path):return []
    for obj in ['chair','cab','bed']:
        box=np.asarray(scene['gt'][obj]);size=box[2:]-box[:2];centre=(box[:2]+box[2:])/2
        if obj=='chair':
            if np.linalg.norm(path-centre,axis=1).min()<=np.linalg.norm(size/2)+.35:pool[obj]=[centre]
        elif obj=='bed':
            if _distance(path,box).min()<=.35:
                pool[obj]=[box[:2]+np.array(v)*size for v in [(.5,.5),(.05,.05),(.95,.95),(.05,.95),(.95,.05)]]
        else:
            faces=[]
            for side in range(4):
                normal=0 if side<2 else 1;tangent=1-normal
                values=[]
                for t in [.5,.05,.95,.25,.75]:
                    p=centre.copy();p[tangent]=box[tangent]+t*size[tangent]
                    p[normal]=box[normal]-.6 if side%2==0 else box[normal+2]+.6
                    if not np.all((p>=0)&(p<=np.array([scene['W'],scene['L']]))):continue
                    if np.linalg.norm(path-p,axis=1).min()<=.27:values.append(p)
                if values:faces.append(values)
            if faces:
                # One reachable operation face, not doors invented on all sides.
                pool[obj]=max(faces,key=len)
    available=[o for o in ['chair','cab','bed'] if o in pool]
    if not available:return []
    used={o:0 for o in available};out=[]
    for i in range(count):
        obj=available[i%len(available)]
        j=0 if policy=='repeat' else used[obj]%len(pool[obj]);used[obj]+=1
        out.append({'object':obj,'pos':pool[obj][j].tolist()})
    return out


def threshold_frontier(rate,xs,ns,target=.8,following=2):
    """Pareto-minimal grid points with confirmation in both activity axes."""
    rate=np.asarray(rate);passed=[]
    for j,n in enumerate(ns):
        for i,x in enumerate(xs):
            block=rate[j:j+following+1,i:i+following+1]
            if block.shape==(following+1,following+1) and np.isfinite(block).all() and np.all(block>=target):passed.append((i,j))
    return [{'coverage_target':float(xs[i]),'visits':int(ns[j])} for i,j in passed
            if not any(a<=i and b<=j and (a<i or b<j) for a,b in passed)]


def run(output,scene_limit=None):
    files=sorted(Path(paths.THOR).glob('FloorPlan*.json'))
    scenes=[s for f in files if (s:=SE.load_scene(str(f)))]
    if scene_limit:scenes=scenes[:scene_limit]
    rows=[];quality=[];checks=0
    for scene in scenes:
        dims={o:np.asarray(b[2:])-b[:2] for o,b in scene['gt'].items()}
        bad=[o for o,d in dims.items() if np.min(d)<=0]
        if bad:
            quality.append({'scene':scene['scene'],'invalid_objects':bad,'reason':'Non-positive footprint dimension; cannot count as complete-layout success'})
            for policy in POLICIES:
                for prefix in COVERAGES:
                    for count in VISITS:rows.append({'scene':scene['scene'],'policy':policy,'coverage_target':prefix,
                        'visits':count,'executable':False,'status':'invalid_geometry','objects':{},'scores':{str(t):{'layout_hit':False,'object_hits':0,'all_certified':False} for t in [.5,1.]}})
            continue
        room=[scene['W'],scene['L']];episode=coverage_route(scene)
        # Free-floor coverage, including unreachable components in the denominator.
        ratio=len(episode['reachable_ids'])/len(episode['free_ids'])
        prefixes=survey_prefixes(episode,[c/ratio for c in COVERAGES])
        for prefix,target in zip(prefixes,COVERAGES):prefix['target_reachable_fraction']=target
        banks=ES.make_bank(room,dims,spacing=.15)
        for prefix in prefixes:
            path=prefix['path'];cache={}
            selected={o:bank[~ES._path_bad(bank,path,-.15)] for o,bank in banks.items()}
            for policy in POLICIES:
                for count in VISITS:
                    events=event_sequence(scene,path,count,policy)
                    executable=len(events)==count and prefix['reached']
                    unique=sorted(set((e['object'],*e['pos']) for e in events))
                    key=tuple(unique)
                    if key not in cache:
                        compact=[{'object':o,'pos':[x,y]} for o,x,y in unique]
                        finite=ES.infer(room,selected,[],compact,False,True,None,padding=.20)
                        objects={};regions={}
                        for obj in scene['gt']:
                            region=object_region(room,dims[obj],obj,compact,path,path_margin=0.,walk_clearance_m=.15)
                            regions[obj]=region
                            covered=contains_box(region,scene['gt'][obj]);checks+=1
                            if not covered:raise AssertionError('Continuous support excluded compatible truth: '+scene['scene']+obj)
                            target=np.asarray(scene['gt'][obj]);tc=(target[:2]+target[2:])/2
                            point=None;radius=None
                            if obj in finite['boxes']:
                                b=finite['boxes'][obj];point=(b[:2]+b[2:])/2
                                lo=region['center_bounds_m'][:2];hi=region['center_bounds_m'][2:]
                                radius=float(np.linalg.norm(np.maximum(abs(lo-point),abs(hi-point))))
                            error=None if point is None else float(np.linalg.norm(point-tc))
                            if error is not None:assert error<=radius+1e-8
                            objects[obj]={'center_error_m':error,'radius_upper_m':radius,
                                'continuous_midpoint_error_m':float(np.linalg.norm(region['point_m']-tc)),
                                'continuous_midpoint_radius_m':region['radius_upper_m'],
                                'truth_in_continuous_set':covered,'region_count':region['region_count'],
                                'budget_relaxed':region['relaxed_by_budget']}
                        joint=joint_decode(room,regions,compact,path)
                        for obj,info in objects.items():
                            if obj not in joint['boxes']:
                                info['joint_error_m']=None;info['joint_radius_upper_m']=None
                            else:
                                b=joint['boxes'][obj];point=(b[:2]+b[2:])/2
                                target=np.asarray(scene['gt'][obj]);tc=(target[:2]+target[2:])/2
                                info['joint_error_m']=float(np.linalg.norm(point-tc))
                                lo=regions[obj]['center_bounds_m'][:2];hi=regions[obj]['center_bounds_m'][2:]
                                info['joint_radius_upper_m']=float(np.linalg.norm(np.maximum(abs(lo-point),abs(hi-point))))
                                assert info['joint_error_m']<=info['joint_radius_upper_m']+1e-8
                        cache[key]=(finite,objects)
                    finite,objects=cache[key]
                    scores={str(t):{'layout_hit':executable and all(o['center_error_m'] is not None and o['center_error_m']<=t for o in objects.values()),
                            'object_hits':sum(o['center_error_m'] is not None and o['center_error_m']<=t for o in objects.values()) if executable else 0,
                        'all_certified':executable and all(o['radius_upper_m'] is not None and o['radius_upper_m']<=t for o in objects.values()),
                        'continuous_layout_hit':executable and all(o['continuous_midpoint_error_m']<=t for o in objects.values()),
                        'continuous_object_hits':sum(o['continuous_midpoint_error_m']<=t for o in objects.values()) if executable else 0,
                        'continuous_all_certified':executable and all(o['continuous_midpoint_radius_m']<=t for o in objects.values())} for t in [.5,1.]}
                    rows.append({'scene':scene['scene'],'policy':policy,'coverage_target':prefix['target_reachable_fraction'],
                        'coverage_room':prefix['coverage_room'],'coverage_free':prefix['coverage_free'],'walk_m':prefix['walk_m'],
                        'visits':count,'executable':executable,'status':finite['status'],'n_unique_contacts':len(unique),
                        'contact_classes':sorted(set(e['object'] for e in events)),
                        'contact_span_xy':{o:np.ptp(np.array([e['pos'] for e in events if e['object']==o]),axis=0).tolist() if any(e['object']==o for e in events) else None for o in scene['gt']},
                        'objects':objects,'scores':scores,
                        'prediction':{o:np.asarray(b).tolist() for o,b in finite['boxes'].items()}})
        print(scene['scene'],'surface done',flush=True)
    summaries=[];surfaces={}
    for policy in POLICIES:
        for t in [.5,1.]:
            grids={m:np.zeros((len(VISITS),len(COVERAGES))) for m in ['layout_rate','object_rate','certified_rate','continuous_layout_rate','continuous_object_rate','continuous_certified_rate','executable_rate','room_coverage_median','joint_layout_rate','joint_layout_upper_rate','joint_object_rate']}
            for j,n in enumerate(VISITS):
                for i,c in enumerate(COVERAGES):
                    part=[r for r in rows if r['policy']==policy and r['visits']==n and r['coverage_target']==c and r['status']!='invalid_geometry']
                    stats={'policy':policy,'tolerance_m':t,'coverage_target':c,'visits':n,'n_rooms':len(part),
                        'layout_hits':sum(r['scores'][str(t)]['layout_hit'] for r in part),
                        'object_hits':sum(r['scores'][str(t)]['object_hits'] for r in part),
                        'all_certified_rooms':sum(r['scores'][str(t)]['all_certified'] for r in part),
                        'executable_rooms':sum(r['executable'] for r in part)}
                    grids['layout_rate'][j,i]=stats['layout_hits']/len(part)
                    grids['object_rate'][j,i]=stats['object_hits']/(4*len(part))
                    grids['certified_rate'][j,i]=stats['all_certified_rooms']/len(part)
                    grids['continuous_layout_rate'][j,i]=sum(r['scores'][str(t)].get('continuous_layout_hit',False) for r in part)/len(part)
                    grids['continuous_object_rate'][j,i]=sum(r['scores'][str(t)].get('continuous_object_hits',0) for r in part)/(4*len(part))
                    grids['continuous_certified_rate'][j,i]=sum(r['scores'][str(t)].get('continuous_all_certified',False) for r in part)/len(part)
                    joint_hits=sum(r['executable'] and all(o['joint_error_m'] is not None and o['joint_error_m']<=t for o in r['objects'].values()) for r in part)
                    grids['joint_layout_rate'][j,i]=joint_hits/len(part)
                    grids['joint_layout_upper_rate'][j,i]=(joint_hits+sum(not r['executable'] for r in part))/len(part)
                    grids['joint_object_rate'][j,i]=sum(r['executable'] and o['joint_error_m'] is not None and o['joint_error_m']<=t for r in part for o in r['objects'].values())/(4*len(part))
                    grids['executable_rate'][j,i]=stats['executable_rooms']/len(part)
                    grids['room_coverage_median'][j,i]=float(np.median([r['coverage_room'] for r in part if 'coverage_room' in r]))
                    summaries.append(stats)
            surfaces[policy+':'+str(t)]={**{k:v.tolist() for k,v in grids.items()},
                'layout_frontier':threshold_frontier(grids['layout_rate'],COVERAGES,VISITS),
                'joint_layout_frontier':threshold_frontier(grids['joint_layout_rate'],COVERAGES,VISITS),
                'continuous_layout_frontier':threshold_frontier(grids['continuous_layout_rate'],COVERAGES,VISITS),
                'certified_frontier':threshold_frontier(grids['certified_rate'],COVERAGES,VISITS)}
    record={'scope':'Controlled geometric development surface; not raw IMU, population validation, or universal leakage threshold',
        'protocol':{'coverage_targets':COVERAGES,'independent_visits':VISITS,'policies':POLICIES,
            'x':'Visited neighbourhood fraction of all body-clear floor, including unreachable components; radius0.25m; not full room area',
            'y':'Independent furniture visits; overlapping classifier windows are not visits',
            'z_primary':'Fraction of all selected rooms with all four predicted centres within0.5m',
            'z_secondary':'Mean fraction of four objects with centre error within tolerance',
            'known_information':'Room box, registered metric coordinates, four target classes and exact nominal sizes',
            'error_model':'Ideal walk coordinates, declared 0.15m L-infinity body clearance; contact bound0.20m; not a calibrated real-IMU bound',
            'frontier_rule':'Rate>=0.80 and next two coverage and next two count grades all pass; no monotonic smoothing',
            'missing_rule':'Zero-area object invalidates geometry input and is excluded before scoring; unreached coverage or unexecutable visits are censored, lower/upper response rates and availability reported',
            'joint_solver':'Continuous-region proposals; exact star constraints bed-desk non-overlap and bed-storage overlap<=1%; storage-desk and chair projections allowed to overlap; no target position read',
            'contact_protocol':'Cabinet events on one already reachable operation face; bed/seat contact can enter their footprint',
            'duplicate_rule':'Repeated exact same contact is redundant under deterministic geometry; counted as a visit but not independent information',
            'walk_evidence':'Only trusted walk samples exclude every object; stronger than the old desk/cab-only pipeline',
            'candidate_grid_m':.15,'statistical_unit':'Room; all rooms reused development data'},
        'scene_count':len(scenes),'eligible_scene_count':len(scenes)-len(quality),'quality_issues':quality,'evaluations':len(rows),'conditional_truth_checks':checks,
        'summary':summaries,'surfaces':surfaces,'rows':rows,
        'scene_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--scene-limit',type=int)
    a=p.parse_args();r=run(a.output,a.scene_limit);print(json.dumps({'evaluations':r['evaluations'],'quality':r['quality_issues']}))
