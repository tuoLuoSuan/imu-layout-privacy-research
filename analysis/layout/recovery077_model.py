"""Candidate-conditioned evidence scoring on top of the frozen physical field.

Candidate locations only enter through geometry relative to observed contacts,
walk exclusion and declared room walls. No anchor, ID, start or truth is read.
The residual is exactly zero without compatible contact support. The fixed
076 model remains a separately scoreable, identical-search ablation.
"""
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .recovery076_data import FIELDS,CATEGORIES
from .recovery076_model import EvidenceDecoder076

FEATURE_NAMES=(
    'bed','cab','desk','chair','log_short_size','log_long_size','log_contacts','log_same_class_slots',
    'residual_min','residual_mean','residual_max','residual_std','fraction_r01','fraction_r025','fraction_r05',
    'distance_min','distance_mean','distance_max','outside_min','outside_mean','outside_max',
    'contact_centroid_distance','mean_contact_spread','walk_cost',
    'wall_gap_1','wall_gap_2','wall_gap_3','wall_gap_4','fixed_energy',
    'contact_span_short','contact_span_long','desk_relation')


def candidate_features(batch):
    if set(batch)!=set(FIELDS):raise ValueError('Unexpected model input fields')
    c,size=batch['centres'],batch['sizes'];ev=batch['events'];cat=batch['category']
    B,S,L,_=c.shape;K=ev.shape[1]
    wanted=torch.tensor([1,2,0,0],device=c.device)[cat]
    compatible=(ev[:,:,2:5].argmax(-1)[:,None]==wanted[:,:,None])&batch['event_valid'][:,None]
    compatible=compatible&((cat!=2)[:,:,None]|batch['desk_relation'][:,None,None])&batch['valid'][:,:,None]
    support=compatible.any(-1)
    mask=compatible[:,:,None].expand(-1,-1,L,-1)
    n=mask.sum(-1).clamp(min=1)
    delta=ev[:,None,None,:,:2]-c[:,:,:,None]
    distance=delta.norm(dim=-1)
    outside=(delta.abs()-size[:,:,:,None]/2).clamp(min=0).norm(dim=-1)
    residual=torch.where(cat[:,:,None,None]==0,outside,
              torch.where(cat[:,:,None,None]==1,(outside-.60).abs(),
              torch.where(cat[:,:,None,None]==2,(outside-.40).abs(),distance)))
    def stats(x):
        mean=(x*mask).sum(-1)/n
        lo=x.masked_fill(~mask,1e4).amin(-1)
        hi=x.masked_fill(~mask,-1e4).amax(-1)
        std=(((x-mean[...,None]).square()*mask).sum(-1)/n+1e-8).sqrt()
        return [torch.where(support[:,:,None],v,torch.zeros_like(v)) for v in (lo,mean,hi,std)]
    r=stats(residual);d=stats(distance);o=stats(outside)
    fractions=[((residual<threshold)&mask).sum(-1)/n for threshold in (.10,.25,.5)]
    points=ev[:,None,:,:2].expand(-1,S,-1,-1)
    count=compatible.sum(-1).clamp(min=1)
    centroid=(points*compatible[...,None]).sum(-2)/count[...,None]
    span=points.masked_fill(~compatible[...,None],-1e4).amax(-2)-points.masked_fill(~compatible[...,None],1e4).amin(-2)
    span=torch.where(support[...,None],span,torch.zeros_like(span)).sort(-1).values
    centroid_distance=(c-centroid[:,:,None]).norm(dim=-1)*support[:,:,None]
    spread=(ev[:,None,:,8]*compatible).sum(-1)/count
    same=((cat[:,:,None]==cat[:,None,:])&batch['valid'][:,None]).sum(-1)
    # Recover only the declared boundary from the full candidate domain. The
    # operation also handles a jointly rotated coordinate system with x<0.
    cv=batch['candidate_valid']&batch['valid'][:,:,None]
    low=(c-size/2).masked_fill(~cv[...,None],1e4).amin((1,2))
    high=(c+size/2).masked_fill(~cv[...,None],-1e4).amax((1,2))
    walls=torch.cat([c-size/2-low[:,None,None],high[:,None,None]-c-size/2],-1).sort(-1).values
    typ=F.one_hot(cat,4).to(c.dtype)[:,:,None].expand(-1,-1,L,-1)
    dim=size.sort(-1).values.clamp(min=.1).log()
    scalar=lambda x:x[:,:,None].expand(-1,-1,L)
    fields=[typ,dim,
            torch.stack([scalar(compatible.sum(-1).float().log1p()),scalar(same.float().log1p())],-1),
            torch.stack(r+fractions+d[:3]+o[:3]+[centroid_distance,scalar(spread),batch['walk_cost']],-1),
            walls/3.,
            (-.5*(residual/.23)**2).masked_fill(~mask,-1e4).logsumexp(-1)[...,None].clamp(-30,0)/10.,
            span[:,:,None].expand(-1,-1,L,-1)/3.,
            batch['desk_relation'][:,None,None,None].expand(-1,S,L,1).to(c.dtype)]
    features=torch.cat(fields,-1)
    if features.shape[-1]!=len(FEATURE_NAMES):raise RuntimeError('Feature schema mismatch')
    return {'features':features.clamp(-10,10),'support':support}


class CandidateScorer077(nn.Module):
    def __init__(self,width=64):
        super().__init__();self.width=width
        self.fixed=EvidenceDecoder076()
        for p in self.fixed.parameters():p.requires_grad_(False)
        self.scorer=nn.Sequential(nn.Linear(len(FEATURE_NAMES),width),nn.SiLU(),
                                  nn.Linear(width,width),nn.SiLU(),nn.Linear(width,1))
        nn.init.zeros_(self.scorer[-1].weight);nn.init.zeros_(self.scorer[-1].bias)

    def forward(self,batch,strength=1.):
        if set(batch)!=set(FIELDS):raise ValueError('Unexpected model input fields')
        with torch.no_grad():
            base=self.fixed(batch);features=candidate_features(batch)
        correction=self.scorer(features['features']).squeeze(-1)
        correction=correction*features['support'][:,:,None]
        # No sigmoid-limited uncertainty or learned coordinate offset. Bound
        # only by a small training regularizer; alpha is chosen on validation.
        energy=base['energy']+float(strength)*correction
        energy=energy.masked_fill(~batch['candidate_valid']&batch['valid'][:,:,None],-1e4)
        return {'energy':energy,'log_prob':energy.log_softmax(-1),
                'has_contact_support':features['support'],'correction':correction,
                'fixed_energy':base['energy']}


def training_loss(outputs,batch,truths,target_sigma=.18):
    """Set-valued candidate supervision, conditional on actually present evidence.

    Same-class targets form a union of centres, weighted by declared-size
    compatibility. Identical slots need not be assigned arbitrary truth IDs.
    Joint instance exclusion is performed by the common candidate decoder.
    """
    losses=[];supervised=0
    for b,truth in enumerate(truths):
        for slot in torch.where(batch['valid'][b]&outputs['has_contact_support'][b])[0]:
            cat=int(batch['category'][b,slot]);target=[v for k,v in truth.items() if k.split('#')[0]==CATEGORIES[cat]]
            if not target:raise ValueError('Declared category has no training target')
            boxes=torch.as_tensor(np.asarray(target),dtype=batch['centres'].dtype,device=batch['centres'].device)
            centre=(boxes[:,:2]+boxes[:,2:])/2;extent=boxes[:,2:]-boxes[:,:2]
            distance=(batch['centres'][b,slot,:,None]-centre[None]).square().sum(-1)
            size_error=(batch['sizes'][b,slot,:,None]-extent[None]).square().sum(-1)
            logits=(-distance/(2*target_sigma**2)-size_error/(2*.15**2)).logsumexp(-1)
            logits=logits.masked_fill(~batch['candidate_valid'][b,slot],-1e4)
            target_prob=logits.softmax(-1).detach()
            losses.append(-(target_prob*outputs['log_prob'][b,slot]).sum());supervised+=1
    if losses:
        data_loss=torch.stack(losses).mean()
        active=batch['valid']&outputs['has_contact_support']
        reg=outputs['correction'][active].square().mean()
        value=data_loss+.002*reg
    else:value=outputs['correction'].sum()*0.;data_loss=value
    return value,{'supervised_slots':supervised,'data_loss':float(data_loss.detach())}
