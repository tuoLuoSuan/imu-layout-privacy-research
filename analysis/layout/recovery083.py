"""Observation-only counterfactual one-object repair scoring.

The model scores a candidate conditional on the frozen parent layout, contacts,
declared room/inventory and unordered walk points. Labels are exact changes in
maximum same-class matching cardinality, computed outside forward. No true
instance correspondence or target coordinates are model inputs.
"""
import math
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree
import torch
from torch import nn

CATEGORIES=('bed','cab','desk','chair')
FIELDS={'query','objects','events','room','pair','allow','valid_query'}


def _match_count(valid):
    if not valid.size:return 0
    i,j=linear_sum_assignment((~valid).astype(float))
    return int(valid[i,j].sum())


def _iou_matrix(a,b):
    inter=np.maximum(0,np.minimum(a[:,None,2:],b[None,:,2:])-np.maximum(a[:,None,:2],b[None,:,:2])).prod(-1)
    union=(a[:,2:]-a[:,:2]).prod(-1)[:,None]+(b[:,2:]-b[:,:2]).prod(-1)[None]-inter
    return inter/np.maximum(union,1e-12)


def gain_labels(parent,categories,candidates,truth):
    """Exact +/-1 matching-count changes, all candidate positions at once."""
    p=np.asarray(parent,float);cand=np.asarray(candidates,float);cats=np.asarray(categories)
    if not np.isfinite(p).all() or not np.isfinite(cand).all() or (p[:,2:]<=p[:,:2]).any() or (cand[...,2:]<=cand[...,:2]).any():
        raise ValueError('Invalid actual rectangle')
    result=np.zeros(cand.shape[:2]+(2,),np.int8);base=np.zeros(2,np.int64)
    for cat in np.unique(cats):
        ids=np.flatnonzero(cats==cat)
        t=np.asarray([b for k,b in truth.items() if k.split('#')[0]==CATEGORIES[int(cat)]],float)
        if len(t)!=len(ids) or not np.isfinite(t).all() or (t[:,2:]<=t[:,:2]).any():raise ValueError('Category/target mismatch')
        pc=(p[ids,:2]+p[ids,2:])/2;tc=(t[:,:2]+t[:,2:])/2
        matrices=[np.linalg.norm(pc[:,None]-tc[None],axis=-1)<=.5,_iou_matrix(p[ids],t)>=.5]
        class_base=[_match_count(v) for v in matrices];base+=class_base
        for local,slot in enumerate(ids):
            cc=(cand[slot,:,:2]+cand[slot,:,2:])/2
            edge=[np.linalg.norm(cc[:,None]-tc[None],axis=-1)<=.5,_iou_matrix(cand[slot],t)>=.5]
            for metric,v in enumerate(matrices):
                other=np.delete(v,local,axis=0);without=_match_count(other)
                remaining=np.asarray([_match_count(np.delete(other,j,axis=1)) for j in range(len(t))])
                new=np.maximum(without,(remaining[None]+edge[metric]).max(-1))
                result[slot,:,metric]=new-class_base[metric]
    if (np.abs(result)>1).any():raise AssertionError('One row cannot change matching by more than one')
    return result,base


def refiner_features_many(obs,category,boxes):
    """Vectorized080 observation features, with no targets or per-room IDs."""
    b=np.asarray(boxes,float);room=np.asarray(obs['room'],float);scale=min(room)
    centre=(b[:,:2]+b[:,2:])/2;size=b[:,2:]-b[:,:2];far=room-b[:,2:]
    x=np.c_[centre/room,size/room,np.minimum(b[:,:2],far)/room,np.minimum(b[:,0],1),
            np.minimum(far[:,0],1),np.minimum(b[:,1],1),np.minimum(far[:,1],1),
            np.broadcast_to(np.eye(4)[category],(len(b),4))]
    contacts=np.asarray([e['pos'] for e in obs['events'] if e['object']==CATEGORIES[category]],float).reshape(-1,2)
    if len(contacts):
        delta=centre[:,None]-contacts[None];distance=np.linalg.norm(delta,axis=-1);idx=distance.argmin(1)
        local=np.c_[delta[np.arange(len(b)),idx]/scale,distance[np.arange(len(b)),idx]/scale]
    else:local=np.tile([0,0,1.],(len(b),1))
    walk=np.asarray(obs['walk'],float).reshape(-1,2)
    if len(walk):
        distance,idx=cKDTree(walk).query(centre);local_walk=np.c_[(walk[idx]-centre)/scale,distance/scale]
    else:local_walk=np.tile([0,0,1.],(len(b),1))
    return np.c_[x,local,local_walk,np.full(len(b),len(contacts)/3),np.full(len(b),len(obs['inventory'])/8)].astype(np.float32)


def refine_candidates(obs,category,boxes,model):
    b=np.asarray(boxes,float);room=np.asarray(obs['room'],float);size=b[:,2:]-b[:,:2]
    step=((room-size)/(2*23.)).astype(np.float32)
    with torch.inference_mode():d=model(torch.from_numpy(refiner_features_many(obs,category,b)),torch.from_numpy(step)).numpy()
    centre=(b[:,:2]+b[:,2:])/2+d
    centre=np.minimum(np.maximum(centre,size/2),room-size/2)
    return np.c_[centre-size/2,centre+size/2]


def _geometry(boxes,room):
    b=np.asarray(boxes,float);centre=(b[:,:2]+b[:,2:])/2;size=b[:,2:]-b[:,:2]
    wall=np.c_[b[:,:2],room-b[:,2:]]/np.tile(room,2)
    return centre,size,wall


def query_features(obs,parent,categories,boxes,slots):
    """One-object alternatives; every feature is computed from observations."""
    parent=np.asarray(parent,float);boxes=np.asarray(boxes,float);cats=np.asarray(categories);slots=np.asarray(slots)
    room=np.asarray(obs['room'],float);diag=np.linalg.norm(room);smin=min(room)
    pc,ps,pw=_geometry(parent,room);qc,qs,qw=_geometry(boxes,room);qcat=cats[slots]
    events=obs['events'];ec=np.asarray([CATEGORIES.index(e['object']) for e in events],int)
    ep=np.asarray([e['pos'] for e in events],float).reshape(-1,2);K=len(ep);S=len(parent);Q=len(boxes)
    support=np.asarray([sum(ec==c)+(sum(ec==3) if c==2 and obs['desk_relation'] else 0) for c in cats])
    obj=np.c_[np.eye(4)[cats],pc/room,ps/room,np.log(ps),pw,np.log1p(support)]
    fractions=np.asarray([[.5,.5],[0,.5],[1,.5],[.5,0],[.5,1],[0,0],[0,1],[1,0],[1,1]])
    probes=boxes[:,None,:2]+qs[:,None]*fractions[None]
    walk=np.asarray(obs['walk'],float).reshape(-1,2)
    distances=cKDTree(walk).query(probes.reshape(-1,2))[0].reshape(Q,9)/diag if len(walk) else np.ones((Q,9))
    displacement=qc-pc[slots]
    query=np.c_[np.eye(4)[qcat],qc/room,qs/room,np.log(qs),qw,distances,
                displacement/room,np.linalg.norm(displacement,axis=-1)/diag,np.log1p(support[slots])]
    evone=np.asarray([[int(c==v) for v in (0,1,3)] for c in ec],float).reshape(K,3)
    event_features=np.c_[evone,ep/room,np.asarray([e.get('spread',0.) for e in events])]
    delta=pc[None]-qc[:,None];gap=np.abs(delta)-(qs[:,None]+ps[None])/2
    inter=np.maximum(0,np.minimum(boxes[:,None,2:],parent[None,:,2:])-np.maximum(boxes[:,None,:2],parent[None,:,:2])).prod(-1)
    union=qs.prod(-1)[:,None]+ps.prod(-1)[None]-inter
    self_edge=slots[:,None]==np.arange(S)[None]
    relation=((qcat[:,None]==2)&(cats[None]==3))|((qcat[:,None]==3)&(cats[None]==2))
    po=np.concatenate([delta/room,gap/room,(inter/np.maximum(union,1e-9))[...,None],
                       (qcat[:,None]==cats[None])[...,None],self_edge[...,None],
                       (relation&obs['desk_relation'])[...,None]],-1)
    allow_obj=~self_edge
    if K:
        de=ep[None]-qc[:,None];outside=np.maximum(0,np.abs(de)-qs[:,None]/2)
        distance=np.linalg.norm(de,axis=-1);outer=np.linalg.norm(outside,axis=-1)
        residual=np.where(qcat[:,None]==0,outer,np.where(qcat[:,None]==1,np.abs(outer-.60),np.where(qcat[:,None]==2,np.abs(outer-.40),distance)))
        same=qcat[:,None]==ec[None];desk=(qcat[:,None]==2)&(ec[None]==3)&obs['desk_relation']
        pe=np.concatenate([de/room,outside/room,np.minimum(residual/.5,10)[...,None],same[...,None],
                           (outer<1e-8)[...,None],desk[...,None]],-1)
        allow_event=same|desk
    else:pe=np.empty((Q,0,8));allow_event=np.empty((Q,0),bool)
    pair=np.concatenate([po,pe,np.zeros((Q,1,8))],1)
    allow=np.c_[allow_obj,allow_event,np.ones(Q,bool)]
    features={'query':query,'objects':obj,'events':event_features,
        'room':np.r_[np.log(room),S/8,K/14,float(obs['desk_relation']),len(walk)/256],
        'pair':pair,'allow':allow,'valid_query':np.ones(Q,bool)}
    for k,v in features.items():
        features[k]=v.astype(bool if k in ('allow','valid_query') else np.float32)
        if not np.isfinite(features[k]).all():raise ValueError('Nonfinite observation features')
    if query.shape[-1]!=27 or obj.shape[-1]!=15 or pair.shape[-1]!=8:raise AssertionError('Feature schema')
    return features


def pack_features(entries):
    B=len(entries);Q=max(len(e['query']) for e in entries);S=max(len(e['objects']) for e in entries);K=max(len(e['events']) for e in entries)
    out={'query':np.zeros((B,Q,27),np.float32),'objects':np.zeros((B,S,15),np.float32),
         'events':np.zeros((B,K,6),np.float32),'room':np.zeros((B,6),np.float32),
         'pair':np.zeros((B,Q,S+K+1,8),np.float32),'allow':np.zeros((B,Q,S+K+1),bool),
         'valid_query':np.zeros((B,Q),bool)}
    out['allow'][:,:,-1]=True
    for i,e in enumerate(entries):
        q=len(e['query']);s=len(e['objects']);k=len(e['events'])
        for name,length in [('query',q),('objects',s),('events',k),('valid_query',q)]:out[name][i,:length]=e[name]
        out['room'][i]=e['room']
        out['pair'][i,:q,:s]=e['pair'][:,:s];out['pair'][i,:q,S:S+k]=e['pair'][:,s:s+k]
        out['pair'][i,:q,-1]=e['pair'][:,-1]
        out['allow'][i,:q,:s]=e['allow'][:,:s];out['allow'][i,:q,S:S+k]=e['allow'][:,s:s+k]
    return {k:torch.from_numpy(v) for k,v in out.items()}


class RepairAttention(nn.Module):
    def __init__(self,width,heads=4):
        super().__init__();self.heads=heads;self.width=width
        self.norm=nn.LayerNorm(width);self.q=nn.Linear(width,width);self.k=nn.Linear(width,width);self.v=nn.Linear(width,width)
        self.bias=nn.Sequential(nn.Linear(8,32),nn.SiLU(),nn.Linear(32,heads));self.out=nn.Linear(width,width)
        self.ff=nn.Sequential(nn.LayerNorm(width),nn.Linear(width,2*width),nn.SiLU(),nn.Linear(2*width,width))

    def forward(self,x,context,pair,allow):
        B,Q,W=x.shape;C=context.shape[1];H=self.heads;D=W//H
        q=self.q(self.norm(x)).reshape(B,Q,H,D).transpose(1,2)
        k=self.k(context).reshape(B,C,H,D).transpose(1,2);v=self.v(context).reshape(B,C,H,D).transpose(1,2)
        logits=(q@k.transpose(-1,-2))/math.sqrt(D)+self.bias(pair).permute(0,3,1,2)
        weight=logits.masked_fill(~allow[:,None],-1e4).softmax(-1)
        read=(weight@v).transpose(1,2).reshape(B,Q,W)
        x=x+self.out(read);return x+self.ff(x)


class Repair083(nn.Module):
    def __init__(self,width=128):
        super().__init__();self.width=width
        enc=lambda n:nn.Sequential(nn.Linear(n,width),nn.SiLU(),nn.Linear(width,width))
        self.query=enc(27);self.objects=enc(15);self.events=enc(6);self.room=enc(6)
        self.types=nn.Parameter(torch.zeros(3,width));self.layers=nn.ModuleList([RepairAttention(width) for _ in range(2)])
        self.head=nn.Linear(width,6);nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)

    def forward(self,batch):
        if set(batch)!=FIELDS:raise ValueError('Only observation tensors accepted')
        x=self.query(batch['query'])
        context=torch.cat([self.objects(batch['objects'])+self.types[0],self.events(batch['events'])+self.types[1],
                           self.room(batch['room'])[:,None]+self.types[2]],1)
        for layer in self.layers:x=layer(x,context,batch['pair'],batch['allow'])
        return self.head(x).reshape(x.shape[0],x.shape[1],2,3)
