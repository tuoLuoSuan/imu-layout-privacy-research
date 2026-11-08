"""A constructive identifiability witness and existing-record activity diagnostics."""
import json
from pathlib import Path
import numpy as np
from . import evidence_space as ES
from . import action_model,paths

def ambiguity_witness(clearance=.15):
    room=(4.,4.)
    common={"bed":(2.4,1.9,3.9,4.),"desk":(.05,3.30,1.1,3.95),"chair":(1.2,3.25,1.64,3.69)}
    first=dict(common,cab=(.05,.05,.65,1.10))
    second=dict(common,cab=(.05,1.45,.65,2.50))
    # A connected depth-first walk on floor free in BOTH worlds.
    spacing=.15;xs=np.arange(.10,room[0],spacing);ys=np.arange(.10,room[1],spacing)
    obstacles=list(common.values())+[first["cab"],second["cab"]]
    def free(y,x):
        p=(xs[x],ys[y])
        return not any(b[0]-clearance<p[0]<b[2]+clearance and b[1]-clearance<p[1]<b[3]+clearance for b in obstacles)
    start=(0,len(xs)-1);visited={start};walk=[start];stack=[(start,iter([(1,0),(-1,0),(0,1),(0,-1)]))]
    while stack:
        node,neighbors=stack[-1]
        try:
            dy,dx=next(neighbors);n=(node[0]+dy,node[1]+dx)
            if 0<=n[0]<len(ys) and 0<=n[1]<len(xs) and n not in visited and free(*n):
                visited.add(n);walk.append(n);stack.append((n,iter([(1,0),(-1,0),(0,1),(0,-1)])))
        except StopIteration:
            stack.pop()
            if stack:walk.append(stack[-1][0])
    points=np.array([[xs[x],ys[y]] for y,x in walk])
    ca=(np.array(first["cab"][:2])+first["cab"][2:])/2
    cb=(np.array(second["cab"][:2])+second["cab"][2:])/2
    separation=float(np.linalg.norm(ca-cb))
    return {"room":room,"first":first,"second":second,"walk":points,"body_clearance_m":clearance,
            "coverage":ES.spatial_coverage(points,room),
            "global_span_m":np.ptp(points,axis=0).tolist(),
            "cabinet_center_separation_m":separation,
            "worst_case_center_error_lower_bound_m":separation/2,
            "identical_observation_condition":"Same feasible body/device motion and no storage interaction in either fixed layout",
            "conclusion":"This coverage value is not sufficient to guarantee complete-layout recovery; this example does not exclude a larger threshold"}

def real_activity(session):
    session=Path(session);d=np.load(session/"ronin-xy.npy")
    t=d[:,0]-.5;p=d[:,1:3]
    pred=json.loads((session/"prediction.json").read_text(encoding="utf-8"))
    runs=json.loads((session/"actions.json").read_text(encoding="utf-8"))["runs"]
    labels=np.full(len(t),"unlabelled",dtype=object)
    for label,start,end in runs:labels[(t>=start)&(t<=end)]=label
    dt=np.diff(t);distance=np.linalg.norm(np.diff(p,axis=0),axis=1)
    parts={}
    for label in sorted(set(labels)):
        selected=(labels[:-1]==label)&(labels[1:]==label)
        duration=float(dt[selected].sum());length=float(distance[selected].sum())
        parts[label]={"supported_duration_s":duration,"model_path_m":length,
                      "mean_model_speed_m_s":length/duration if duration else None}
    angle=np.radians(pred["rot_deg"]);R=np.array([[np.cos(angle),np.sin(angle)],[-np.sin(angle),np.cos(angle)]])
    aligned=p@R;aligned-=aligned[0]-np.array(pred["start_anchored_at"])
    prefixes=[]
    for T in [8,12,16,20,25,30,35,40,45,50,56.5]:
        selected=t<=T
        prefixes.append({"budget_s":T,"estimated_path_coverage":ES.spatial_coverage(aligned[selected],pred["room"]),
                         "source":"Full-record estimated trajectory truncated for descriptive coverage; not independently tracked activity or causal re-fit",
                         "available_long_events":sum(end-start>=1 and end+1.5<=T for label,start,end in runs if label in ("seated","cabinet","lying"))})
    return {"session":session.name,"overall_duration_s":float(t[-1]-t[0]),"model_path_m":float(distance.sum()),
            "overall_model_speed_m_s":float(distance.sum()/np.diff(t).sum()),
            "by_predicted_action":parts,"prefixes":prefixes,
            "ground_truth_walk_speed_available":False,
            "speed_bias_identified":False,
            "scope":"Frozen-estimator activity accounting; all labels and positions are estimates, not video truth"}

def fit_distance_scale(estimated,reference,calibration_ids,evaluation_ids):
    """Explicit reference-assisted calibration; refuses to fit evaluation intervals."""
    if set(calibration_ids)&set(evaluation_ids):raise ValueError("Calibration/evaluation interval overlap")
    a=np.asarray(estimated,float);b=np.asarray(reference,float)
    if a.shape!=b.shape or not len(a) or np.any(a<=0) or np.any(b<=0):
        raise ValueError("Positive paired measured calibration distances required")
    return {"scale":float(np.dot(a,b)/np.dot(a,a)),
            "side_information":"Independent measured calibration distances",
            "applies_to":"Reference-assisted arm only; never an uncalibrated IMU-only claim"}

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("--session",default=paths.SESSION)
    parser.add_argument("--output",required=True);args=parser.parse_args()
    witness=ambiguity_witness();witness["walk"]=witness["walk"].tolist()
    record={"real":real_activity(args.session),"witness":witness}
    Path(args.output).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"real":record["real"]["by_predicted_action"],"witness_coverage":witness["coverage"],
                      "indistinguishable_center_gap_m":witness["cabinet_center_separation_m"]},ensure_ascii=False))
