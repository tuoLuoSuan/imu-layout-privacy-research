"""Evaluation-only full-information geometry check, never an attack input.

Bed: two opposite footprint contacts. Chair: centre plus footprint orientation.
Desk/storage: both operation-face endpoints, outward normal and known reach.
These extra observations are NOT supplied by the current five-class IMU model.
"""
import argparse,json
from pathlib import Path
import numpy as np
from . import sim_eval as SE,paths
from .continuous_regions import object_region


def face_box(endpoints,normal,dimensions,reach=.6):
    a,b=np.asarray(endpoints,float);n=np.asarray(normal,float)
    size=np.asarray(dimensions,float);length=float(np.linalg.norm(b-a))
    if not np.isclose(np.linalg.norm(n),1.) or not np.isclose((b-a)@n,0.,atol=1e-8):raise ValueError('Invalid face frame')
    match=np.isclose(size,length,atol=1e-7)
    if not match.any():raise ValueError('Endpoint span does not match declared object size')
    depth=float(size[1-int(np.flatnonzero(match)[0])])
    centre=(a+b)/2-(reach+depth/2)*n
    tangent=(b-a)/length
    corners=np.array([centre+x*tangent*length/2+y*n*depth/2 for x in [-1,1] for y in [-1,1]])
    return np.r_[corners.min(axis=0),corners.max(axis=0)]


def run(output):
    scenes=[s for f in sorted(Path(paths.THOR).glob('FloorPlan*.json')) if (s:=SE.load_scene(str(f)))]
    rows=[];invalid=[]
    for scene in scenes:
        if any(min(np.asarray(b[2:])-b[:2])<=0 for b in scene['gt'].values()):
            invalid.append({'scene':scene['scene'],'reason':'Zero-area footprint; not an eligible full-layout test'});continue
        prediction={};evidence={}
        for obj,target in scene['gt'].items():
            b=np.asarray(target,float);size=b[2:]-b[:2]
            if obj=='bed':
                events=[{'object':obj,'pos':p.tolist()} for p in [b[:2],b[2:]]]
                region=object_region([scene['W'],scene['L']],size,obj,events,[],padding=0.)
                centre=region['point_m'];prediction[obj]=np.r_[centre-size/2,centre+size/2]
                evidence[obj]={'opposite_contacts':[b[:2].tolist(),b[2:].tolist()]}
            elif obj=='chair':
                centre=(b[:2]+b[2:])/2;prediction[obj]=np.r_[centre-size/2,centre+size/2]
                evidence[obj]={'centre':centre.tolist(),'oriented_size':size.tolist()}
            else:
                # Visible +x operation face; supplied ONLY to this oracle check.
                n=np.array([1.,0.]);endpoints=np.array([[b[2]+.6,b[1]],[b[2]+.6,b[3]]])
                prediction[obj]=face_box(endpoints,n,size,.6)
                evidence[obj]={'face_endpoints':endpoints.tolist(),'outward_normal':n.tolist(),'reach_m':.6}
        errors={o:float(np.linalg.norm((p[:2]+p[2:]-np.asarray(scene['gt'][o][:2])-scene['gt'][o][2:])/2)) for o,p in prediction.items()}
        overlaps={o:SE.iou(p,scene['gt'][o]) for o,p in prediction.items()}
        rows.append({'scene':scene['scene'],'errors_m':errors,'iou':overlaps,
                     'all_exact':bool(max(errors.values())<1e-7 and min(overlaps.values())>1-1e-7),
                     'oracle_evidence':evidence})
    record={'scope':'Evaluation-only full-information geometry inversion, not IMU recovery or an activity threshold',
        'eligible_rooms':len(rows),'invalid_rooms':invalid,'exact_layouts':sum(r['all_exact'] for r in rows),
        'rate':sum(r['all_exact'] for r in rows)/len(rows),'rows':rows,
        'forbidden_interpretation':'Do not add these oracle observations to the attack arm or count them as measured IMU evidence'}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8');return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();r=run(a.output)
    print(json.dumps({'eligible':r['eligible_rooms'],'exact':r['exact_layouts'],'invalid':r['invalid_rooms']}))
