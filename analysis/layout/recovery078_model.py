"""A permutation-invariant graph scorer over complete geometric layouts."""
import torch
from torch import nn
from torch.nn import functional as F

FIELDS={'nodes','edges','node_valid','hyp_valid','base_score','has_events'}


class LayoutRanker078(nn.Module):
    def __init__(self,width=96,rounds=2):
        super().__init__();self.width=width;self.rounds=rounds
        self.node=nn.Sequential(nn.Linear(41,width),nn.SiLU(),nn.Linear(width,width),nn.SiLU())
        self.edge=nn.Sequential(nn.Linear(2*width+8,width),nn.SiLU(),nn.Linear(width,width),nn.SiLU())
        self.update=nn.Sequential(nn.Linear(2*width,width),nn.SiLU(),nn.Linear(width,width))
        self.norm=nn.LayerNorm(width)
        self.head=nn.Sequential(nn.Linear(2*width,width),nn.SiLU(),nn.Linear(width,1))
        nn.init.zeros_(self.head[-1].weight);nn.init.zeros_(self.head[-1].bias)

    def forward(self,batch,strength=1.):
        if set(batch)!=FIELDS:raise ValueError('Unexpected graph inputs; labels must stay outside forward')
        x=self.node(batch['nodes']);valid=batch['node_valid']
        B,H,S,W=x.shape
        edge_valid=(valid[:,:,None]&valid[:,None,:])&~torch.eye(S,dtype=torch.bool,device=x.device)[None]
        for _ in range(self.rounds):
            pair=torch.cat([x[:,:,:,None].expand(-1,-1,-1,S,-1),
                            x[:,:,None].expand(-1,-1,S,-1,-1),batch['edges']],-1)
            message=self.edge(pair)*edge_valid[:,None,:,:,None]
            pooled=message.sum(3)/edge_valid.sum(2).clamp(min=1)[:,None,:,None]
            x=self.norm(x+self.update(torch.cat([x,pooled],-1)))
        mean=(x*valid[:,None,:,None]).sum(2)/valid.sum(1).clamp(min=1)[:,None,None]
        maximum=x.masked_fill(~valid[:,None,:,None],-1e4).amax(2)
        residual=self.head(torch.cat([mean,maximum],-1)).squeeze(-1)*batch['has_events'][:,None]
        scores=(batch['base_score']+float(strength)*residual).masked_fill(~batch['hyp_valid'],-1e4)
        return {'scores':scores,'residual':residual}


def ranking_loss(outputs,batch,labels):
    valid=batch['hyp_valid'];whole=(labels['whole']>.5)&valid
    footprint_cost=1-labels['mean_iou']
    cost=labels['dmax']/.5+.2*labels['mean_error']/.5+.2*footprint_cost
    fallback=(-cost/.2).masked_fill(~valid,-1e4)
    preferred=(-footprint_cost/.2).masked_fill(~whole,-1e4)
    target=torch.where(whole.any(1)[:,None],preferred,fallback).softmax(-1).detach()
    loss=-(target*outputs['scores'].log_softmax(-1)).sum(-1).mean()
    active=outputs['residual'][valid]
    return loss+.002*active.square().mean()


def pack_graph(entries):
    import numpy as np
    H=max(len(e['features']['base_score']) for e in entries);S=max(len(e['features']['node_valid']) for e in entries)
    result={};labels={}
    for key in FIELDS:
        values=[]
        for entry in entries:
            a=entry['features'][key]
            if key=='has_events':values.append(a);continue
            if key=='node_valid':pad=[(0,S-len(a))]
            elif key=='nodes':pad=[(0,H-a.shape[0]),(0,S-a.shape[1]),(0,0)]
            elif key=='edges':pad=[(0,H-a.shape[0]),(0,S-a.shape[1]),(0,S-a.shape[2]),(0,0)]
            else:pad=[(0,H-len(a))]
            values.append(np.pad(a,pad))
        result[key]=torch.from_numpy(np.stack(values))
        if key in ('nodes','edges','base_score'):result[key]=result[key].float()
    if all('labels' in e for e in entries):
        for key in entries[0]['labels']:
            labels[key]=torch.from_numpy(np.stack([np.pad(e['labels'][key],(0,H-len(e['labels'][key]))) for e in entries]))
    return result,labels
