"""Measured-route prefixes, fixed furniture and truth-free reconstruction arms.

This is a geometric oracle study. It does not synthesize raw IMU observations.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from . import evidence_space as ES
from . import sim_eval as SE
from . import paths

BUDGETS=(0.,2.,4.,8.,12.,20.,32.,48.,64.,96.)
ARMS={"P-U":(False,False,False),"P-K":(False,False,True),"T-U":(True,False,False),
      "A-U":(False,True,False),"TA-U":(True,True,False),"TA-K":(True,True,True),
      "P-prototype":(False,False,True)}
TOLERANCES=(.25,.5,1.)


def prefix_episode(episode,budget):
    """A common budget contract for path and available spatialised events."""
    return (episode['points'][episode['arc']<=budget],
            [dict(e) for e in episode['events'] if e['available_distance_m']<=budget])

def contact_targets(scene,rng):
    boxes=scene["gt"]
    chair=(np.asarray(boxes["chair"][:2])+boxes["chair"][2:])/2
    b=np.asarray(boxes["bed"]);bed=b[:2]+rng.uniform(.10,.90,2)*(b[2:]-b[:2])
    c=np.asarray(boxes["cab"]);mid=(c[:2]+c[2:])/2
    choices=[(np.array([c[0]-.6,mid[1]]),1),(np.array([c[2]+.6,mid[1]]),1),
             (np.array([mid[0],c[1]-.6]),0),(np.array([mid[0],c[3]+.6]),0)]
    possible=[]
    for p,axis in choices:
        if not (0<=p[0]<=scene["W"] and 0<=p[1]<=scene["L"]):continue
        if any(boxes[o][0]<p[0]<boxes[o][2] and boxes[o][1]<p[1]<boxes[o][3] for o in ["desk","cab"]):continue
        possible.append((p,axis))
    if not possible:
        return {"chair":chair,"bed":bed,"cab":None},None
    p,axis=min(possible,key=lambda v:np.linalg.norm(v[0]-scene["S"]))
    return {"chair":chair,"bed":bed,"cab":p},axis

def free_targets(scene,count=8):
    xs=np.arange(.12,scene["W"],.30);ys=np.arange(.12,scene["L"],.30)
    points=np.array([(x,y) for x in xs for y in ys if not any(
        scene["gt"][o][0]<x<scene["gt"][o][2] and scene["gt"][o][1]<y<scene["gt"][o][3] for o in ["desk","cab"])])
    chosen=[np.asarray(scene["S"])]
    out=[]
    for _ in range(count):
        d=np.min(np.sum((points[:,None,:]-np.asarray(chosen)[None,:,:])**2,axis=2),axis=1)
        p=points[int(d.argmax())];out.append(p);chosen.append(p)
    return out

def route_episode(scene,policy,seed):
    rng=np.random.default_rng(seed)
    base,axis=contact_targets(scene,rng)
    floor=free_targets(scene)
    points=[np.asarray(scene["S"],float)];events=[];length=0.
    current=points[0]
    for visit in range(12):
        obj=("chair","cab","bed")[visit%3]
        if base[obj] is None:
            continue
        target=base[obj].copy()
        if policy=="dispersed":
            if obj=="bed":
                b=np.asarray(scene["gt"]["bed"])
                target=b[:2]+rng.uniform(.1,.9,2)*(b[2:]-b[:2])
            if obj=="cab":
                b=scene["gt"]["cab"]
                target[axis]=rng.uniform(b[axis]+.10*(b[axis+2]-b[axis]),b[axis+2]-.10*(b[axis+2]-b[axis]))
        destinations=([floor[visit%len(floor)]] if policy=="dispersed" else [])+[target]
        for destination in destinations:
            # Reuse the existing collision-checked planner, take the outward leg.
            local=dict(scene,S=current)
            all_points,walk=SE.traj_of(local,{"seated":destination})
            end=int(np.argmin(np.linalg.norm(all_points-np.asarray(destination),axis=1)))
            leg=all_points[:end+1]
            # Interaction approaches are snapped to free floor. Only walk samples enter exclusion evidence.
            leg=leg[walk[:end+1]]
            for point in leg:
                length+=float(np.linalg.norm(point-current))
                points.append(np.asarray(point));current=np.asarray(point)
        events.append({"object":obj,"pos":target.tolist(),"available_distance_m":length})
    points=np.asarray(points);arc=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
    return {"points":points,"arc":arc,"events":events,"walk_length_m":float(arc[-1])}

def known_prior(target,scenes):
    rows={}
    for obj in target["gt"]:
        values=[]
        for scene in scenes:
            if scene["scene"]==target["scene"]:continue
            b=scene["gt"][obj]
            values.append(((np.asarray(b[:2])+b[2:])/2/np.array([scene["W"],scene["L"]])).tolist())
        rows[obj]=values
    return rows

def prototype_prediction(target,scenes,banks):
    training=[s for s in scenes if s['scene']!=target['scene']]
    names=sorted(banks)
    if not training:
        return ES.infer((target['W'],target['L']),banks,[],[],False,False)
    vectors=np.array([np.concatenate([((np.asarray(s['gt'][o][:2])+s['gt'][o][2:])/2)/
                                      np.array([s['W'],s['L']]) for o in names]) for s in training])
    distances=np.linalg.norm(vectors[:,None,:]-vectors[None,:,:],axis=2)
    reference=vectors[int(distances.sum(axis=1).argmin())]
    boxes={}
    for j,o in enumerate(names):
        point=reference[2*j:2*j+2]*[target['W'],target['L']]
        boxes[o]=banks[o][np.linalg.norm(ES.centres(banks[o])-point,axis=1).argmin()]
    return {'status':'ok','boxes':boxes,'candidates':[boxes],
            'objects':{o:{'support_boxes':bank,'center_diameter_m':float(np.linalg.norm(np.ptp(ES.centres(bank),axis=0)))} for o,bank in banks.items()}}

def _summary(rows):
    summaries=[]
    for policy in ["local_repeat","dispersed"]:
        for arm in ARMS:
            for budget in BUDGETS:
                r=[r for r in rows if r["policy"]==policy and r["arm"]==arm and r["budget_m"]==budget]
                if not r:continue
                summaries.append({"policy":policy,"arm":arm,"budget_m":budget,"n_rooms":len(r),
                                  "median_coverage":float(np.median([v["coverage"] for v in r])),
                                  "median_events":float(np.median([v["n_events"] for v in r])),
                                  "success_rate":float(np.mean([v["scores"]["0.5"]["full_point_hit"] for v in r])),
                                  "same_candidate_rate":float(np.mean([v["scores"]["0.5"]["same_candidate_hit"] for v in r])),
                                  "all_support_rate":float(np.mean([v["scores"]["0.5"]["all_support_hit"] for v in r])),
                                  "per_object_success":{o:float(np.mean([v['scores']['0.5']['center_error_m'][o] is not None and
                                      v['scores']['0.5']['center_error_m'][o]<=.5 for v in r])) for o in ['bed','desk','cab','chair']}})
    return summaries

def run(out,seed=17031,noise_bound=0.,scene_limit=None,fast=False):
    files=sorted(Path(paths.THOR).glob("FloorPlan*.json"))
    scenes=[s for f in files if (s:=SE.load_scene(str(f)))]
    if scene_limit is not None:scenes=scenes[:scene_limit]
    rows=[];failures=[]
    for index,scene in enumerate(scenes):
        room=(scene["W"],scene["L"])
        dimensions={obj:(b[2]-b[0],b[3]-b[1]) for obj,b in scene["gt"].items()}
        banks=ES.make_bank(room,dimensions,spacing=.20)
        prior=known_prior(scene,scenes)
        prototype=prototype_prediction(scene,scenes,banks)
        cache={}
        for policy in ["local_repeat","dispersed"]:
            try:episode=route_episode(scene,policy,seed+index)
            except ValueError as e:
                failures.append({"scene":scene["scene"],"policy":policy,"reason":str(e)});continue
            # Independent stream: do not couple offset noise to sampled bed contacts.
            rng=np.random.default_rng(np.random.SeedSequence([seed,index,907]))
            common=rng.uniform(-noise_bound,noise_bound,2)
            # All arms see the same fixed latent room, route and available events.
            for budget in BUDGETS:
                visible,truth_events=prefix_episode(episode,budget)
                observations=[dict(e,pos=(np.asarray(e["pos"])+common).tolist()) for e in truth_events]
                observed_path=visible+common
                coverage=ES.spatial_coverage(visible,room)
                for arm,(use_path,use_actions,use_prior) in ARMS.items():
                    key=(arm,hashlib.sha256(observed_path.tobytes()).hexdigest() if use_path else None,
                         tuple((e['object'],*e['pos']) for e in observations) if use_actions else None)
                    if key not in cache:
                        cache[key]=prototype if arm=='P-prototype' else ES.infer(room,banks,observed_path,observations,use_path,use_actions,
                                    prior if use_prior else None,padding=.20+noise_bound,
                                    path_margin=.08+noise_bound,candidate_limit=32 if fast else 48,beam_width=24 if fast else 48)
                    result=cache[key]
                    scores={str(tol):ES.evaluate(result,scene["gt"],tol) for tol in TOLERANCES}
                    rows.append({"scene":scene["scene"],"policy":policy,"arm":arm,"budget_m":budget,
                                 "actual_route_m":min(budget,episode["walk_length_m"]),"coverage":coverage,
                                 "n_events":len(truth_events),"event_counts":{o:sum(e["object"]==o for e in truth_events) for o in scene["gt"]},
                                 "event_span_per_axis_m":{o:np.ptp(np.array([e['pos'] for e in truth_events if e['object']==o]),axis=0).tolist()
                                     if any(e['object']==o for e in truth_events) else None for o in scene['gt']},
                                 "status":result["status"],"scores":scores})
        print(scene["scene"],"completed",flush=True)
    summaries=_summary(rows)
    thresholds={}
    per_object_thresholds={}
    for policy in ["local_repeat","dispersed"]:
        for arm in ["TA-U","TA-K"]:
            selected=[r for r in summaries if r["policy"]==policy and r["arm"]==arm]
            thresholds[policy+":"+arm]=ES.stable_threshold(selected,x_key="budget_m")
            for obj in ['bed','desk','cab','chair']:
                projected=[dict(r,success_rate=r['per_object_success'][obj]) for r in selected]
                per_object_thresholds[policy+':'+arm+':'+obj]=ES.stable_threshold(projected,x_key='budget_m')
    record={"scope":"Geometric oracle development benchmark; not raw IMU or independent room confirmation",
            "candidate_model":"Known room and target sizes; fixed world; phone-in-bed, seated centre, unknown storage face; no hard wall template",
            "prior_K":"Leave-target-room-out class-position density, not an unknown-room-type classifier",
            "noise_model":"Common bounded 2D offset shared by path and all contacts","noise_bound_m":noise_bound,
            "seed":seed,"scene_count":len(scenes),"rows":rows,"summary":summaries,"thresholds":thresholds,
            "per_object_protocol_thresholds":per_object_thresholds,"failures":failures,
            "scene_sha256":{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
            "protocol":{"coverage_radius_m":.25,"budget_unit":"walking metres, separate from interaction count",
                        "success_center_tolerances_m":list(TOLERANCES),"primary_tolerance_m":.5,
                        "threshold_rate":.8,"subsequent_confirmation_points":2,
                        "fixed_furniture":True,"new_independent_rooms":False,"beam_is_approximate":True}}
    Path(out).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding="utf-8")
    return record

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--seed",type=int,default=17031)
    parser.add_argument("--noise-bound",type=float,default=0.)
    parser.add_argument("--scene-limit",type=int)
    parser.add_argument("--fast",action="store_true")
    args=parser.parse_args()
    result=run(args.output,args.seed,args.noise_bound,args.scene_limit,args.fast)
    print(json.dumps({"scenes":result["scene_count"],"rows":len(result["rows"]),"thresholds":result["thresholds"],"failures":result["failures"]},ensure_ascii=False))
