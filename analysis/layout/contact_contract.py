"""Controlled handset-contact contract, separate from the legacy real solver.

The known carry protocol maps handset attitude to a relative body axis. It is
not a general six-axis body-heading estimator: independent wrist yaw breaks
this assumption. Absolute yaw remains unknown and is enumerated using the
known room/start. No target furniture coordinates are accepted by decoding.
"""
import numpy as np
from .sim_motion import U_UP,basis_from_up

CONTRACT={'version':'joint-contact-v2','anchor':'handset horizontal position, not pelvis position',
 'interaction_hands':'phone right hand held still; left wrist operates cabinet door',
 'lying_phone_from_foot_m':.65,'cabinet_phone_reach_m':.55,'chair_table_clearance_m':.165,
 'seated_phone_horizontal_offset_m':[0.,0.],
 'heading_assumption':'known rigid pose-to-body-axis protocol; no independent phone yaw',
 'prior':'Manhattan furniture, one of each class; seated facing associated desk; bed long axis points toward head',
 'absolute_yaw':'unknown; room/start geometry used for candidate selection',
 'scope':'Controlled bridge ablation, not the generic multi-instance10000-room decoder'}
POSE={'walk':'walk','other':'stand','seated':'sit','lying':'lie','cabinet':'reach'}


def validate_contact(event):
    if set(event)!={'xy','heading'}:raise ValueError('Only measured handset position and relative heading allowed')
    xy=np.asarray(event['xy'],float);u=np.asarray(event['heading'],float)
    if xy.shape!=(2,) or u.shape!=(2,) or not np.isfinite(np.r_[xy,u]).all() or np.linalg.norm(u)<1e-6:
        raise ValueError('Finite XY and nonzero horizontal heading required')
    return xy,u/np.linalg.norm(u)


def distance_scale(path,known_distance):
    path=np.asarray(path,float);length=float(np.linalg.norm(np.diff(path,axis=0),axis=1).sum())
    if known_distance<=0 or length<=1e-6 or not np.isfinite(path).all():raise ValueError('Positive independent calibration distance and predicted path required')
    return float(known_distance/length)


def register(path,degrees,start):
    angle=np.radians(degrees);R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    path=np.asarray(path,float)
    return (path-path[0])@R.T+np.asarray(start)


def body_axis(rotations,label):
    # The fixed protocol axis is defined in device coordinates. A free wrist
    # twist is not inferred or silently supplied from the simulated truth.
    local=basis_from_up(U_UP[POSE[label]]).T@np.array([0.,1.,0.])
    vec=np.einsum('nij,j->ni',np.asarray(rotations),local)[:,:2]
    return vec/np.maximum(np.linalg.norm(vec,axis=1,keepdims=True),1e-12)


def contacts_from_runs(time,xy,rotations,runs,minimum_s=2.):
    time=np.asarray(time);out={};durations={}
    for label,start,end in runs:
        if label not in ('seated','lying','cabinet') or end-start<minimum_s:continue
        mask=(time>=start+.5)&(time<=end)
        if mask.sum()<3:continue
        # Longest observed run per class; no ground-truth selection.
        if durations.get(label,-1)>=end-start:continue
        ids=np.flatnonzero(mask);ids=ids[-max(3,int(len(ids)*.25)):]
        heading=body_axis(np.asarray(rotations)[ids],label).mean(axis=0)
        out[label]={'xy':np.asarray(xy)[ids].mean(axis=0).tolist(),'heading':heading.tolist()};durations[label]=end-start
    return out


def oriented_box(centre,heading,depth,length):
    u=np.asarray(heading);axis=int(np.argmax(abs(u)))
    widths=np.array([length,depth]) if axis==1 else np.array([depth,length])
    centre=np.asarray(centre);return np.r_[centre-widths/2,centre+widths/2]


def boxes_from_contacts(contacts,sizes):
    parsed={k:validate_contact(v) for k,v in contacts.items()};boxes={}
    if 'seated' in parsed:
        p,u=parsed['seated'];cs=np.asarray(sizes['chair']);boxes['chair']=np.r_[p-cs/2,p+cs/2]
        depth,length=sorted(sizes['desk']);cd=float(cs[np.argmax(abs(u))])
        boxes['desk']=oriented_box(p+u*(depth/2+cd/2+CONTRACT['chair_table_clearance_m']),u,depth,length)
    if 'cabinet' in parsed:
        p,u=parsed['cabinet'];depth,length=sorted(sizes['cab'])
        boxes['cab']=oriented_box(p+u*(CONTRACT['cabinet_phone_reach_m']+depth/2),u,depth,length)
    if 'lying' in parsed:
        p,u=parsed['lying'];width,length=sorted(sizes['bed'])
        centre=p+(length/2-CONTRACT['lying_phone_from_foot_m'])*u
        boxes['bed']=oriented_box(centre,u,length,width)
    return boxes


def support_gap(box,heading,room):
    axis=int(np.argmax(abs(np.asarray(heading))))
    return float(room[axis]-box[axis+2] if heading[axis]>0 else box[axis])


def decode(room,start,path,contacts,sizes,walk=None,yaw_candidates=None):
    if not contacts:return {'status':'missing_action','boxes':{},'candidates':[],'contract':CONTRACT}
    parsed={k:validate_contact(v) for k,v in contacts.items()};path=np.asarray(path,float);origin=path[0]
    angles=sorted({round(float(np.degrees(a-np.arctan2(u[1],u[0]))%360),5) for _,u in parsed.values() for a in [0,np.pi/2,np.pi,3*np.pi/2]})
    if yaw_candidates is not None:
        angles=list(map(float,yaw_candidates))
        if not angles or not np.isfinite(angles).all():raise ValueError('Finite explicitly granted frame angles required')
    candidates=[];room=np.asarray(room,float)
    for angle in angles:
        a=np.radians(angle);R=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
        mapped={k:{'xy':((p-origin)@R.T+start).tolist(),'heading':(u@R.T).tolist()} for k,(p,u) in parsed.items()}
        boxes=boxes_from_contacts(mapped,sizes);q=register(path,angle,start)
        out=sum(np.maximum(-b[:2],b[2:]-room).clip(min=0).sum() for b in boxes.values())
        walk_out=float(np.maximum(-q,q-room).clip(min=0).mean())
        overlap=0.
        for i,(name,b) in enumerate(boxes.items()):
            for other,c in list(boxes.items())[i+1:]:
                if {name,other}=={'chair','desk'}:continue
                overlap+=float(np.maximum(np.minimum(b[2:],c[2:])-np.maximum(b[:2],c[:2]),0).prod())
        collision=0.
        if walk is not None and np.asarray(walk).any():
            for name in ['cab','desk']:
                if name in boxes:
                    b=boxes[name];collision+=float(np.mean(np.all((q>b[:2]+.05)&(q<b[2:]-.05),axis=1)&walk))
        observed={'bed':'lying','cab':'cabinet','desk':'seated'}
        gaps=[support_gap(b,mapped[observed[name]]['heading'],room) for name,b in boxes.items() if name!='chair']
        score=out*30+walk_out*10+overlap*10+collision*4+sum(abs(g-.10) for g in gaps)*.15
        candidates.append({'score':score,'yaw_deg':angle,'boxes':{k:b.tolist() for k,b in boxes.items()},'outside_m':float(out),'contact_inputs':mapped})
    candidates.sort(key=lambda c:c['score']);best=candidates[0]
    return {'status':'ok' if len(best['boxes'])==4 else 'partial','boxes':best['boxes'],'yaw_deg':best['yaw_deg'],'candidates':candidates,'contract':CONTRACT}
