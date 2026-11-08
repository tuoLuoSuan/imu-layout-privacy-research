"""Select a layout from continuous supported regions, without a position lattice.

Bed/desk footprint overlap is excluded; storage/desk projection overlap is
allowed (the benchmark includes wall shelves above desks). Chair projection
overlap is not penalized. No truth or target placement is accepted.
"""
import numpy as np
from . import evidence_space as ES


def decode(room,regions,events,path,walk_clearance=.15,walk_tolerance=0.,
           contact_padding=.20,walk_excluded_objects=('bed','desk','cab','chair')):
    pools={}
    path=np.asarray(path,float).reshape(-1,2)
    for obj,region in regions.items():
        all_boxes=[]
        for mode in region['modes']:
            r=mode['q_regions'];size=np.asarray(mode['dimensions'])
            for x in [0.,.5,1.]:
                for y in [0.,.5,1.]:
                    q=r[:,:2]+(r[:,2:]-r[:,:2])*[x,y]
                    all_boxes.append(np.c_[q,q+size])
        if not all_boxes:return {'status':'no_supported_mode','boxes':{}}
        boxes=np.unique(np.round(np.vstack(all_boxes),11),axis=0)
        # Region boundaries are conservatively outward-rounded. Do not turn
        # sub-nanometre representation error into a missing supported layout.
        valid=~ES._path_bad(boxes,path,walk_tolerance-walk_clearance+1e-8) if obj in walk_excluded_objects else np.ones(len(boxes),bool)
        cost=np.zeros(len(boxes))
        mine=[e for e in events if e['object']==obj]
        for e in mine:
            keep,energy=ES._contact(boxes,e,contact_padding+1e-9,.60);valid&=keep
            cost+=np.minimum(energy,100)**2/max(1,len(mine))
        boxes=boxes[valid];cost=cost[valid]
        if not len(boxes):return {'status':'sampling_missed_feasible_set','boxes':{}}
        cc=ES.centres(boxes);point=region['point_m']
        cost+=.001*np.linalg.norm(cc-point,axis=1)
        pools[obj]=(boxes,cost)
    # The declared graph is a star: bed--desk and bed--storage. Solve that
    # discrete graph exactly rather than discard future-compatible beds in a beam.
    root_boxes,root_cost=pools['bed'];costs=root_cost.copy();choices={}
    for obj,(boxes,energy) in pools.items():
        if obj=='bed':continue
        best_id=np.full(len(root_boxes),-1,int);best_cost=np.full(len(root_boxes),np.inf)
        if obj not in ['desk','cab']:
            best_id[:]=int(energy.argmin());best_cost[:]=float(energy.min())
        else:
            allowed=.01 if obj=='cab' else 1e-9
            area=np.prod(boxes[:,2:]-boxes[:,:2],axis=1)
            for start in range(0,len(root_boxes),128):
                root=root_boxes[start:start+128]
                inter=np.maximum(0,np.minimum(root[:,None,2:],boxes[None,:,2:])-
                                   np.maximum(root[:,None,:2],boxes[None,:,:2]))
                denom=np.minimum(np.prod(root[:,2:]-root[:,:2],axis=1)[:,None],area[None,:])
                overlap=np.prod(inter,axis=2)/np.maximum(denom,1e-12)
                values=np.where(overlap<=allowed,energy[None,:],np.inf)
                ids=values.argmin(axis=1);v=values[np.arange(len(root)),ids]
                best_id[start:start+len(root)]=ids;best_cost[start:start+len(root)]=v
        costs+=best_cost;choices[obj]=best_id
    if not np.isfinite(costs).any():return {'status':'joint_search_conflict','boxes':{}}
    root_id=int(costs.argmin());layout={'bed':root_boxes[root_id]}
    for obj,ids in choices.items():layout[obj]=pools[obj][0][ids[root_id]]
    return {'status':'ok','boxes':layout,'candidates':[layout],
            'candidate_counts':{o:len(v[0]) for o,v in pools.items()},
            'scope':'Exact star-graph minimization over sampled continuous-region proposals; not an exhaustive continuous optimum'}
