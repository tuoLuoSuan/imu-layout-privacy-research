"""Measured handset orientation channels under the fixed carry/interaction protocol.

No true wall/object orientation or event-instance association is supplied.
Absolute yaw is unknown. The four frame hypotheses use stable wrist-detected
cabinet visits and known pose-to-body axes, never room reference furniture.
"""
import numpy as np
from . import evidence_space as ES
from .contact_contract import body_axis
from .multi_raw010 import interaction_events,OPTIONS
from .recovery010 import solve
from .selection_diagnostics import outline_cost


def bed_orientation_mask(boxes,heading):
    boxes=np.asarray(boxes);axis=int(np.argmax(abs(np.asarray(heading))))
    return np.argmax(boxes[:,2:]-boxes[:,:2],axis=1)==axis


def directed_contact(category,boxes,point,heading,padding=.3):
    boxes=np.asarray(boxes);p=np.asarray(point);axis=int(np.argmax(abs(np.asarray(heading))));other=1-axis;sign=1 if heading[axis]>=0 else -1
    face=boxes[:,axis] if sign>0 else boxes[:,axis+2];distance=(face-p[axis])*sign
    along=(p[other]>=boxes[:,other]-padding)&(p[other]<=boxes[:,other+2]+padding)
    if category=='cab':keep=along&(abs(distance-.6)<=padding+1e-8)&(np.argmin(boxes[:,2:]-boxes[:,:2],axis=1)==axis);res=abs(distance-.6)
    elif category=='desk_relation':
        keep=along&(distance>=-padding)&(distance<=.9)&(np.argmin(boxes[:,2:]-boxes[:,:2],axis=1)==axis);res=np.zeros(len(boxes))
    else:return ES._contact(boxes,{'object':category,'pos':point},padding,.6)
    return keep,res/max(padding,1e-9)


def decode(priors,t,path,R,runs,walk,candidate_limit=128,support_cost_weight=0.):
    t=np.asarray(t);path=np.asarray(path);R=np.asarray(R);events=interaction_events(t,path,runs);directions=[]
    for label,a,b in runs:
        if label not in ['seated','lying','cabinet'] or b-a<2.:continue
        ids=np.flatnonzero((t>=a+.25*(b-a))&(t<=a+.75*(b-a)))
        if len(ids)<3:continue
        h=body_axis(R[ids],label).mean(axis=0);h/=max(1e-9,np.linalg.norm(h));directions.append(h)
    if len(directions)!=len(events):raise AssertionError('Every contact must keep its own measured heading')
    cab=[h for e,h in zip(events,directions) if e['object']=='cab'];axis_source=cab or [h for e,h in zip(events,directions) if e['object']=='bed'] or directions
    offset=np.degrees(np.arctan2(axis_source[0][1],axis_source[0][0])) if axis_source else 0.;angles=[a-offset for a in [0,90,180,270]];candidates=[]
    for degrees in angles:
        a=np.radians(degrees);Q=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]]);q=(path-path[0])@Q.T+priors['start'];ev=[{'object':e['object'],'pos':((np.asarray(e['pos'])-path[0])@Q.T+priors['start']).tolist()} for e in events];heads=[h@Q.T for h in directions];lookup={(e['object'],*e['pos']):h for e,h in zip(ev,heads)};lying=[h for e,h in zip(ev,heads) if e['object']=='bed']
        def filtering(entry,boxes,room):return bed_orientation_mask(boxes,np.mean(lying,axis=0)) if entry['category']=='bed' and lying else np.ones(len(boxes),bool)
        def support(entry,boxes,e):
            c='chair' if e['object']=='desk_relation' else e['object'];h=lookup[c,*e['pos']]
            return directed_contact(e['object'],boxes,e['pos'],h,.3) if e['object'] in ['cab','desk_relation'] else ES._contact(boxes,e,.3,.6)
        obs=np.unique(np.round(q[np.asarray(walk,bool)][::12]/.1)*.1,axis=0) if np.any(walk) else np.empty((0,2));opts={**OPTIONS,'candidate_limit':candidate_limit,'proposal_filter':filtering,'event_support':support,'known_desk_protocol':True,'support_cost_weight':support_cost_weight};result=solve(priors['room'],priors['inventory'],ev,obs,'depth_portfolio',decoder_options=opts);outside=np.maximum(-q,q-np.array(priors['room'])).clip(min=0);cost=100*float(outside.mean())+10*float(outside.max());cost+=1000 if result['status']!='ok' else float(np.mean(outline_cost(np.array(list(result['boxes'].values())),priors['room'],obs)));candidates.append({**result,'yaw_deg':float(degrees),'registration_cost':cost,'events':ev,'measured_heading':np.asarray(heads).tolist(),'n_walk_points':len(obs)})
    best=min(candidates,key=lambda r:r['registration_cost']);return {**best,'boxes':{k:np.asarray(v).tolist() for k,v in best['boxes'].items()},'orientation_source':'Signal-estimated phone attitude under fixed pose-to-body protocol; absolute yaw unknown','table_relation':'A seated person faces some table within0.9m, unknown partner and along-edge offset','frame_hypotheses':[{k:r[k] for k in ['yaw_deg','registration_cost','status']} for r in candidates]}
