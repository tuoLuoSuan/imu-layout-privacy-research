"""Anchor-free learned contact likelihoods over a whole-room candidate field.

The MLP sees only category, declared size, activity type and measured spread.
It learns local contact offsets and uncertainty, never an absolute room location.
No per-room latent, start, anchor, room ID, raster or quality gate exists.
"""
import numpy as np
import torch
from scipy.optimize import linear_sum_assignment
from torch import nn
from torch.nn import functional as F

from .recovery076_data import FIELDS, CATEGORIES


class EvidenceDecoder076(nn.Module):
    def __init__(self,width=96):
        super().__init__(); self.width=width
        self.kernel=nn.Sequential(nn.Linear(10,width),nn.SiLU(),nn.Linear(width,width),
                                  nn.SiLU(),nn.Linear(width,4))
        nn.init.zeros_(self.kernel[-1].weight);nn.init.zeros_(self.kernel[-1].bias)

    def forward(self,batch):
        if set(batch)!=set(FIELDS):raise ValueError('Unexpected model input fields')
        c,size=batch['centres'],batch['sizes']
        ev=batch['events']; category=batch['category']; valid=batch['valid']
        B,S,L,_=c.shape;K=ev.shape[1]
        # Size is deliberately local. The network never sees room dimensions.
        typ=F.one_hot(category,4).to(c.dtype)[:,:,None].expand(-1,-1,K,-1)
        cls=ev[:,None,:,2:5].expand(-1,S,-1,-1)
        dim=size[:,:,0,None].expand(-1,-1,K,-1)
        spread=ev[:,None,:,8:9].expand(-1,S,-1,-1)
        params=self.kernel(torch.cat([typ,cls,dim,spread],-1))
        offset=.75*torch.tanh(params[...,:2])
        heading=ev[:,:,5:7]; has=ev[:,:,7:8]
        default=torch.zeros_like(heading);default[...,0]=1.
        axis=heading*has+default*(1-has);side=torch.stack([-axis[...,1],axis[...,0]],-1)
        shift=offset[...,:1]*axis[:,None]+offset[...,1:]*side[:,None]
        point=ev[:,None,:,0:2]+shift
        delta=point[:,:,None]-c[:,:,:,None]
        absdelta=delta.abs();half=size[:,:,:,None]/2
        outside=(absdelta-half).clamp(min=0).norm(dim=-1)
        # Bed: phone can be anywhere on its footprint. Chair: seat centre.
        # Cabinet: an operating face about 0.6 m away. Desk relation is optional.
        residual=torch.where(category[:,:,None,None]==0,outside,
                   torch.where(category[:,:,None,None]==1,(outside-.60).abs(),
                   torch.where(category[:,:,None,None]==2,(outside-.40).abs(),delta.norm(dim=-1))))
        sigma=.06+.34*torch.sigmoid(params[...,2])+ev[:,None,:,8].clamp(max=.5)
        score=-.5*(residual/sigma[:,:,None])**2
        # A measured heading may favour a forward cabinet/desk; no heading is
        # invented for the geometric benchmark or for missing device attitude.
        forward=-(delta*axis[:,None,None]).sum(-1)
        directional=((category==1)|(category==2))[:,:,None,None]*has[:,None,:,0][:,:,None]
        score=score-directional*F.relu(-forward)/.20
        score=score+params[...,3].clamp(-3,3)[:,:,None]
        wanted=torch.tensor([1,2,0,0],device=c.device)[category]
        compatible=(ev[:,:,2:5].argmax(-1)[:,None]==wanted[:,:,None])&batch['event_valid'][:,None]
        compatible=compatible&((category!=2)[:,:,None]|batch['desk_relation'][:,None,None])
        compatible=compatible&valid[:,:,None]
        has_support=compatible.any(-1)
        masked=score.masked_fill(~compatible[:,:,None],-1e4)
        energy=torch.logsumexp(masked,-1)-compatible.sum(-1).clamp(min=1).log()[:,:,None]
        energy=torch.where(has_support[:,:,None],energy,torch.zeros_like(energy))
        energy=energy-6.*batch['walk_cost']
        energy=energy.masked_fill(~batch['candidate_valid']&valid[:,:,None],-1e4)
        return {'log_prob':energy.log_softmax(-1),'energy':energy,
                'has_contact_support':has_support}


def _iou(a,b):
    intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    return intersection/max(1e-10,np.prod(a[2:]-a[:2])+np.prod(b[2:]-b[:2])-intersection)


def decode(outputs,batch,candidates=18,beam=24):
    """Joint, bounded search. Returns a point estimate even if ambiguous.

    The posterior field is not calibrated confidence. Identical type/size slots
    are resolved jointly with overlap penalties, not by averaging their modes.
    """
    logp=outputs['log_prob'].detach().cpu().numpy()
    centres=batch['centres'].cpu().numpy();sizes=batch['sizes'].cpu().numpy()
    valid=batch['valid'].cpu().numpy();cats=batch['category'].cpu().numpy()
    eligible=batch['candidate_valid'].cpu().numpy();results=[]
    for b in range(len(logp)):
        states=[(0.,[])];slots=np.flatnonzero(valid[b])
        # Commit strongest local evidence first; identical scores are deterministic.
        slots=sorted(slots,key=lambda j:-float(logp[b,j].max()))
        for slot in slots:
            proposals=[]
            for i in np.argsort(-logp[b,slot],kind='stable'):
                if not eligible[b,slot,i]:continue
                pos=centres[b,slot,i];size=sizes[b,slot,i]
                box=np.r_[pos-size/2,pos+size/2]
                if any(np.linalg.norm(pos-(q[1][:2]+q[1][2:])/2)<.18 and
                       np.allclose(size,q[1][2:]-q[1][:2]) for q in proposals):continue
                proposals.append((int(i),box))
                if len(proposals)>=candidates:break
            expanded=[]
            for cost,chosen in states:
                for i,box in proposals:
                    overlap=sum(_iou(box,other)*20 for _,other,_ in chosen)
                    expanded.append((cost-float(logp[b,slot,i])+overlap,chosen+[(slot,box,i)]))
            states=sorted(expanded,key=lambda row:row[0])[:beam]
        if not states:raise ValueError('No feasible candidate; no sample silently omitted')
        counts={};boxes={}
        for slot,box,_ in sorted(states[0][1]):
            category=CATEGORIES[cats[b,slot]];number=counts.get(category,0);counts[category]=number+1
            boxes[f'{category}#{number}']=box.tolist()
        results.append(boxes)
    return results


def objective(outputs,batch,truths):
    """Category-wise one-to-one supervised NLL; truth enters here, never forward."""
    costs=[]
    for b,truth in enumerate(truths):
        for category in range(4):
            slots=torch.where(batch['valid'][b]&(batch['category'][b]==category))[0]
            target=[box for name,box in truth.items() if name.split('#')[0]==CATEGORIES[category]]
            if len(target)!=len(slots):raise ValueError('Inventory and training truth counts disagree')
            if not len(target):continue
            boxes=torch.as_tensor(np.asarray(target),dtype=batch['centres'].dtype,device=batch['centres'].device)
            centre=(boxes[:,:2]+boxes[:,2:])/2;extent=boxes[:,2:]-boxes[:,:2]
            xyz=batch['centres'][b,slots];size=batch['sizes'][b,slots]
            distance=(xyz[:,:,None]-centre[None,None]).square().sum(-1)
            distance=distance+.25*(size[:,:,None]-extent[None,None]).square().sum(-1)
            distance=distance.masked_fill(~batch['candidate_valid'][b,slots,:,None],1e6)
            index=distance.argmin(1)
            loss=-outputs['log_prob'][b,slots].gather(1,index)
            row,col=linear_sum_assignment(loss.detach().cpu().numpy())
            costs.append(loss[row,col].mean())
    if not costs:raise ValueError('Empty target set')
    return torch.stack(costs).mean()
