"""Multiple-instance geometric reconstruction and category-wise matching.

Inventory categories/counts/dimensions are given side information. Observation
events contain only class and position; no true object identity is accepted.
Proposal sampling and beam search are bounded estimators, not identifiability
certificates or exhaustive continuous optimization.
"""
import itertools,json
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from . import evidence_space as ES,sim_eval as SE
from .continuous_regions import object_region,intersect_regions,_event_options


def category(name):return name.split('#')[0]


def diverse_beam(states,width):
    groups={}
    for state in sorted(states,key=lambda b:b[0]):groups.setdefault(state[1],[]).append(state)
    keys=sorted(groups,key=lambda m:-m.bit_count());out=[];i=0
    while len(out)<width:
        added=False
        for key in keys:
            if i<len(groups[key]):out.append(groups[key][i]);added=True
            if len(out)==width:break
        if not added:break
        i+=1
    return out


def score_instances(pred,truth,tolerance=.5):
    tp=0;matches=[];per={}
    for cls in sorted({category(k) for k in pred}|{category(k) for k in truth}):
        ps=[(k,np.asarray(v)) for k,v in pred.items() if category(k)==cls]
        ts=[(k,np.asarray(v)) for k,v in truth.items() if category(k)==cls];hit=0
        if ps and ts:
            pc=np.array([(b[:2]+b[2:])/2 for k,b in ps]);tc=np.array([(b[:2]+b[2:])/2 for k,b in ts])
            distance=np.linalg.norm(pc[:,None,:]-tc[None,:,:],axis=2);valid=distance<=tolerance
            cost=(~valid)*(min(len(ps),len(ts))+1)+np.minimum(distance,100)*1e-5
            a,b=linear_sum_assignment(cost)
            for i,j in zip(a,b):
                if valid[i,j]:hit+=1
                matches.append({'class':cls,'prediction':ps[i][0],'truth':ts[j][0],
                    'error_m':float(distance[i,j]),'hit':bool(valid[i,j]),'iou':SE.iou(ps[i][1],ts[j][1])})
        tp+=hit;per[cls]={'tp':hit,'fp':len(ps)-hit,'fn':len(ts)-hit,'n_truth':len(ts),'n_pred':len(ps)}
    fp=len(pred)-tp;fn=len(truth)-tp
    return {'tp':tp,'fp':fp,'fn':fn,'f1':2*tp/(len(pred)+len(truth)) if pred or truth else 0.,
        'all_instances_hit':bool(truth) and tp==len(pred)==len(truth),'per_class':per,'matches':matches}


def load_native(path):
    d=json.loads(Path(path).read_text(encoding='utf-8'));sel=d['selection']
    if d['stage']!='exported':raise ValueError('Native export failed')
    poly=np.asarray(sel['floor_polygon_xz']);lo=poly.min(axis=0);hi=poly.max(axis=0);gt={};inventory=[]
    by={o['id']:o for o in d['objects']}
    for name,oid in sel['selected_object_ids'].items():
        box=np.asarray(by[oid]['box_xz'])-np.r_[lo,lo];gt[name]=box
        inventory.append({'id':name,'category':category(name),'dimensions':box[2:]-box[:2]})
    p=np.array([[v['x'],v['z']] for v in d['reachable_positions']]);p=p[np.all((p>=lo)&(p<=hi),axis=1)]
    if not len(p):raise ValueError('No reachable start inside room')
    start=p[np.linalg.norm(p-(lo+hi)/2,axis=1).argmin()]-lo
    return {'scene':sel['house_id'],'W':float(hi[0]-lo[0]),'L':float(hi[1]-lo[1]),'S':start,
            'gt':gt,'inventory':inventory,'split':sel['source_split'],'counts':sel['counts']}


def event_sequence(scene,path,count,mode='dispersed'):
    """Simulation generator may read truth. It never emits instance labels."""
    if mode not in ['dispersed','repeat']:raise ValueError('Unknown interaction location protocol')
    path=np.asarray(path,float).reshape(-1,2);pools={}
    if not len(path):return []
    for name,box in scene['gt'].items():
        cls=category(name);box=np.asarray(box);size=box[2:]-box[:2];centre=(box[:2]+box[2:])/2
        if cls=='chair' and np.linalg.norm(path-centre,axis=1).min()<=np.linalg.norm(size/2)+.35:pools[name]=[centre]
        elif cls=='bed':
            distance=np.linalg.norm(np.maximum(box[:2]-path,path-box[2:]).clip(min=0),axis=1)
            if distance.min()<=.35:pools[name]=[box[:2]+np.array(v)*size for v in [(.5,.5),(.05,.05),(.95,.95),(.05,.95),(.95,.05)]]
        elif cls=='cab':
            faces=[]
            for side in range(4):
                normal=0 if side<2 else 1;tangent=1-normal;points=[]
                for t in [.5,.05,.95,.25,.75]:
                    p=centre.copy();p[tangent]=box[tangent]+t*size[tangent];p[normal]=box[normal]-.6 if side%2==0 else box[normal+2]+.6
                    if np.all((p>=0)&(p<=np.array([scene['W'],scene['L']]))) and np.linalg.norm(path-p,axis=1).min()<=.27:points.append(p)
                if points:faces.append(points)
            if faces:pools[name]=max(faces,key=len)
    if mode=='repeat':pools={k:v[:1] for k,v in pools.items()}
    classes=[c for c in ['chair','cab','bed'] if any(category(k)==c for k in pools)]
    used={k:0 for k in pools};class_visits={c:0 for c in classes};out=[]
    if not classes:return out
    for i in range(count):
        c=classes[i%len(classes)];instances=sorted(k for k in pools if category(k)==c)
        key=instances[class_visits[c]%len(instances)];class_visits[c]+=1
        point=pools[key][used[key]%len(pools[key])];used[key]+=1
        out.append({'object':c,'pos':point.tolist()})
    return out


def _proposals(room,entry,events,path,padding,walk_excluded=True,walk_clearance=.15,walk_tolerance=0.):
    cls=entry['category'];mine=[e for e in events if e['object']==cls]
    hard=mine if cls=='bed' else []
    base=object_region(room,entry['dimensions'],cls,hard,path,path_margin=walk_tolerance,
        walk_clearance_m=walk_clearance,use_path=walk_excluded)
    boxes=[];points=[]
    combinations=[()]
    if cls in ['cab','chair']:
        combinations+=list(itertools.combinations(mine,1))
        if cls=='cab':combinations+=list(itertools.combinations(mine,2))
    for subset in combinations:
        for mode in base['modes']:
            regions=mode['q_regions'];size=np.asarray(mode['dimensions'])
            for e in subset:regions=intersect_regions(regions,_event_options(cls,e['pos'],size,padding,.6))
            if not len(regions):continue
            for x in [0.,.5,1.]:
                for y in [0.,.5,1.]:
                    q=regions[:,:2]+(regions[:,2:]-regions[:,:2])*[x,y];boxes.append(np.c_[q,q+size])
    if not boxes:return np.empty((0,4)),base
    boxes=np.unique(np.round(np.vstack(boxes),10),axis=0)
    if walk_excluded:boxes=boxes[~ES._path_bad(boxes,path,walk_tolerance-walk_clearance+1e-8)]
    return boxes,base


def decode_instances(room,inventory,events,path,known_desk_protocol=False,beam_width=48,candidate_limit=64,proposal_cache=None,
                     contact_padding=.20,walk_clearance=.15,walk_tolerance=0.,
                     walk_excluded_objects=('bed','desk','cab','chair')):
    if contact_padding<0 or walk_clearance<0 or walk_tolerance<0:raise ValueError('Nonnegative observation bounds required')
    for e in events:
        if set(e)!={'object','pos'} or e['object'] not in ['bed','chair','cab']:raise ValueError('Only class/position observations allowed; no instance identity')
    unique=sorted(set((e['object'],*e['pos']) for e in events));events=[{'object':c,'pos':[x,y]} for c,x,y in unique]
    targets=list(events)
    if known_desk_protocol:targets+= [{'object':'desk_relation','pos':e['pos']} for e in events if e['object']=='chair']
    if len(targets)>60:raise ValueError('Diagnostic event budget exceeded')
    full=(1<<len(targets))-1;pools={};counts={}
    for entry in inventory:
        cls=entry['category']
        excluded=cls in walk_excluded_objects
        if proposal_cache is None:boxes,base=_proposals(room,entry,events,path,contact_padding,excluded,walk_clearance,walk_tolerance)
        else:
            key=(entry['id'],tuple(entry['dimensions']),tuple((e['object'],*e['pos']) for e in events),np.asarray(path,float).tobytes(),contact_padding,excluded,walk_clearance,walk_tolerance)
            if key not in proposal_cache:proposal_cache[key]=_proposals(room,entry,events,path,contact_padding,excluded,walk_clearance,walk_tolerance)
            boxes,base=proposal_cache[key]
        if not len(boxes):return {'status':'no_proposals','boxes':{},'candidate_counts':counts}
        masks=np.zeros(len(boxes),dtype=np.uint64);energy=np.zeros(len(boxes))
        for j,e in enumerate(targets):
            if e['object']==cls:
                keep,residual=ES._contact(boxes,e,contact_padding+1e-8,.6);masks|=keep.astype(np.uint64)*np.uint64(1<<j)
            elif cls=='desk' and e['object']=='desk_relation':
                point=np.asarray(e['pos']);outside=np.maximum(boxes[:,:2]-point,point-boxes[:,2:]).clip(min=0)
                keep=np.linalg.norm(outside,axis=1)<=.90+1e-8;masks|=keep.astype(np.uint64)*np.uint64(1<<j)
        centre=ES.centres(boxes);energy=.001*np.linalg.norm(centre-base['point_m'],axis=1)
        bits=np.array([int(v).bit_count() for v in masks]);order=np.lexsort((energy,-bits));half=candidate_limit//2
        groups={}
        for j in order:groups.setdefault(int(masks[j]),[]).append(j)
        selected=[];keys=sorted(groups,key=lambda m:-m.bit_count())
        for round_index in range(candidate_limit):
            for mask in keys:
                group=groups[mask]
                index=round_index if round_index<4 else int((round_index-3)*(len(group)-1)/max(1,candidate_limit-4))
                if index<len(group):selected.append(group[index])
                if len(set(selected))>=candidate_limit:break
            if len(set(selected))>=candidate_limit:break
        ids=np.array(sorted(set(selected)));pools[entry['id']]=(boxes[ids],masks[ids],energy[ids]);counts[entry['id']]=len(boxes)
    return _constraint_search(inventory,pools,targets,counts)


def _constraint_search(inventory,pools,targets,counts,node_limit=20000):
    """Forward checking keeps future furniture from being greedily squeezed out.

    Domains are the same bounded, truth-free proposals. Event-to-instance
    assignment is existential. A resource limit is an unresolved search result,
    never an information-theoretic impossibility certificate.
    """
    names=[e['id'] for e in inventory];compat={};covers={};nodes=0;limit_hit=False
    for name,(boxes,masks,energy) in pools.items():
        covers[name]=[sum(1<<j for j,m in enumerate(masks) if int(m)&(1<<t)) for t in range(len(targets))]
    for a,b in itertools.combinations(names,2):
        if {category(a),category(b)}=={'desk','chair'}:continue
        aa=pools[a][0];bb=pools[b][0]
        inter=np.maximum(0,np.minimum(aa[:,None,2:],bb[None,:,2:])-np.maximum(aa[:,None,:2],bb[None,:,:2]))
        area=np.minimum(np.prod(aa[:,2:]-aa[:,:2],axis=1)[:,None],np.prod(bb[:,2:]-bb[:,:2],axis=1)[None,:])
        valid=np.prod(inter,axis=2)<=1e-8*np.maximum(area,1e-12)
        compat[a,b]=[sum(1<<int(j) for j in np.flatnonzero(row)) for row in valid]
        compat[b,a]=[sum(1<<int(j) for j in np.flatnonzero(row)) for row in valid.T]
    def indices(mask):
        while mask:
            bit=mask&-mask;yield bit.bit_length()-1;mask^=bit
    full=(1<<len(targets))-1
    def search(domains,placed,covered):
        nonlocal nodes,limit_hit
        nodes+=1
        if nodes>node_limit:limit_hit=True;return None
        domains=dict(domains);changed=True
        while changed:
            changed=False
            for t in indices(full&~covered):
                providers=[n for n,d in domains.items() if d&covers[n][t]]
                if not providers:return None
                if len(providers)==1:
                    name=providers[0];new=domains[name]&covers[name][t]
                    if new!=domains[name]:domains[name]=new;changed=True
        for a,b in itertools.combinations(domains,2):
            if (a,b) not in compat:continue
            if not any(compat[a,b][i]&domains[b] for i in indices(domains[a])):return None
        if not domains:return placed if covered==full else None
        name=min(domains,key=lambda n:domains[n].bit_count());boxes,masks,cost=pools[name]
        order=sorted(indices(domains[name]),key=lambda i:(-(int(masks[i])&~covered).bit_count(),float(cost[i])))
        for i in order:
            remaining={};valid=True
            for other,d in domains.items():
                if other==name:continue
                d=d&compat[name,other][i] if (name,other) in compat else d
                if not d:valid=False;break
                remaining[other]=d
            if valid:
                result=search(remaining,{**placed,name:i},covered|int(masks[i]))
                if result is not None:return result
                if limit_hit:return None
        return None
    solution=search({n:(1<<len(pools[n][0]))-1 for n in names},{},0)
    if solution is None:return {'status':'search_budget_exhausted' if limit_hit else 'proposal_conflict','boxes':{},'candidate_counts':counts,'search_nodes':nodes}
    return {'status':'ok','boxes':{n:pools[n][0][i] for n,i in solution.items()},'candidate_counts':counts,'search_nodes':nodes,
        'scope':'Bounded candidate CSP with latent event assignment and forward physical checks; not a continuous optimum or certificate'}
