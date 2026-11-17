"""Complete-layout hypotheses and observation-only graph descriptors.

Labels are computed by a separate function AFTER generation. The first beam
entry is exactly the same-budget 077 answer. No target candidate is injected.
"""
import numpy as np
import torch
from scipy.spatial import cKDTree

from .recovery076_data import CATEGORIES
from .recovery076_eval import score
from .recovery077_model import candidate_features


def hypotheses(outputs,batch,candidates=80,beam=64):
    if batch['centres'].shape[0]!=1:raise ValueError('One room per candidate extraction')
    if min(candidates,beam)<1:raise ValueError('Positive search budgets required')
    p=outputs['log_prob'][0].detach().cpu().numpy();c=batch['centres'][0].numpy();s=batch['sizes'][0].numpy()
    valid=batch['valid'][0].numpy();cv=batch['candidate_valid'][0].numpy();cat=batch['category'][0].numpy()
    order=sorted(np.flatnonzero(valid),key=lambda j:-float(p[j].max()))
    costs=np.zeros(1);chosen=np.empty((1,0,4));indices=np.empty((1,0),np.int64);slots=[]
    for slot in order:
        pool=[];ids=[]
        for i in np.argsort(-p[slot],kind='stable'):
            if not cv[slot,i]:continue
            pos,size=c[slot,i],s[slot,i]
            if pool:
                a=np.asarray(pool);same=np.all(np.isclose(size,a[:,2:]-a[:,:2]),axis=-1)
                near=np.linalg.norm(pos-(a[:,:2]+a[:,2:])/2,axis=-1)<.18
                if np.any(same&near):continue
            pool.append(np.r_[pos-size/2,pos+size/2]);ids.append(i)
            if len(pool)>=candidates:break
        if not pool:raise ValueError('No candidates')
        boxes=np.asarray(pool);joint=costs[:,None]-p[slot,ids][None]
        if chosen.shape[1]:
            lo=np.maximum(chosen[:,:,None,:2],boxes[None,None,:,:2]);hi=np.minimum(chosen[:,:,None,2:],boxes[None,None,:,2:])
            inter=np.maximum(0,hi-lo).prod(-1);area=np.prod(chosen[:,:,2:]-chosen[:,:,:2],-1)[:,:,None]
            area2=np.prod(boxes[:,2:]-boxes[:,:2],-1)[None,None]
            joint=joint+20*(inter/np.maximum(1e-10,area+area2-inter)).sum(1)
        keep=np.argsort(joint.ravel(),kind='stable')[:beam];parent,proposal=np.unravel_index(keep,joint.shape)
        chosen=np.concatenate([chosen[parent],boxes[proposal,None]],1)
        indices=np.concatenate([indices[parent],np.asarray(ids)[proposal,None]],1)
        costs=joint[parent,proposal];slots.append(slot)
    permutation=np.argsort(slots);slots=np.asarray(slots)[permutation]
    boxes=chosen[:,permutation].astype(np.float32);indices=indices[:,permutation]
    return {'boxes':boxes,'indices':indices,'slots':slots,'category':cat[slots],
            'cost':costs.astype(np.float32),'unary_logp':p[slots[None],indices],
            'base_score':(-(costs-costs[0])/len(slots)).astype(np.float32)}


def as_boxes(hyp,index):
    out={};counts={}
    for cat,box in zip(hyp['category'],hyp['boxes'][index]):
        name=CATEGORIES[int(cat)];i=counts.get(name,0);counts[name]=i+1;out[f'{name}#{i}']=box.tolist()
    return out


def graph_features(observation,batch,hyp):
    if set(observation)!={'schema','frame','room','inventory','events','walk','desk_relation'}:
        raise ValueError('Unexpected observation fields')
    with torch.no_grad():all_features=candidate_features(batch)['features'][0].numpy()
    nodes=all_features[hyp['slots'][None],hyp['indices']].copy()
    # Current 077 unary score replaces the fixed-energy feature at position28.
    nodes[...,28]=np.clip(hyp['unary_logp']/10,-10,0)
    boxes=hyp['boxes'];centres=(boxes[...,:2]+boxes[...,2:])/2;size=boxes[...,2:]-boxes[...,:2]
    room=np.asarray(observation['room'],float);scale=float(np.linalg.norm(room))
    fractions=np.array([[.5,.5],[0,.5],[1,.5],[.5,0],[.5,1],[0,0],[0,1],[1,0],[1,1]])
    probes=boxes[...,:2][...,None,:]+size[...,None,:]*fractions
    walk=np.asarray(observation['walk'],float).reshape(-1,2)
    if len(walk):dist=cKDTree(np.unique(walk,axis=0)).query(probes.reshape(-1,2))[0].reshape(probes.shape[:-1])/scale
    else:dist=np.ones(probes.shape[:-1])
    # Rotating all geometry only permutes edge/corner probes; sorting preserves
    # that invariance. Far from a walk means unobserved, never 'occupied'.
    context=np.concatenate([dist[...,:1],np.sort(dist[...,1:5],-1),np.sort(dist[...,5:],-1)],-1).clip(0,1)
    nodes=np.concatenate([nodes,context],-1).astype(np.float32)
    d=np.abs(centres[:,:,None]-centres[:,None,:]);normal=d/scale
    lo=np.maximum(boxes[:,:,None,:2],boxes[:,None,:,:2]);hi=np.minimum(boxes[:,:,None,2:],boxes[:,None,:,2:])
    inter=np.maximum(0,hi-lo).prod(-1);area=size.prod(-1)
    iou=inter/np.maximum(1e-10,area[:,:,None]+area[:,None,:]-inter)
    gap=(d-(size[:,:,None]+size[:,None,:])/2)/scale
    ratio=np.log(np.maximum(area[:,:,None],1e-6)/np.maximum(area[:,None,:],1e-6))
    same=np.broadcast_to(hyp['category'][:,None]==hyp['category'][None,:],iou.shape)
    edges=np.concatenate([np.linalg.norm(normal,axis=-1)[...,None],np.sort(normal,-1),iou[...,None],
                          np.sort(gap,-1),ratio[...,None],same[...,None]],-1).astype(np.float32)
    return {'nodes':nodes,'edges':edges,'node_valid':np.ones(nodes.shape[1],bool),
            'hyp_valid':np.ones(len(nodes),bool),'base_score':hyp['base_score'],
            'has_events':np.asarray(bool(observation['events']),bool)}


def label_hypotheses(hyp,truth):
    """Training/evaluation labels only; never passed into graph_features/forward."""
    labels={k:[] for k in ('whole','footprint','f1','dmax','mean_error','mean_iou')}
    for i in range(len(hyp['boxes'])):
        result=score(as_boxes(hyp,i),truth);matches=result['matches']
        errors=[m['error_m'] for m in matches];ious=[m['iou'] for m in matches]
        labels['whole'].append(result['whole_room']);labels['footprint'].append(result['whole_footprint'])
        labels['f1'].append(result['f1']);labels['dmax'].append(max(errors,default=100.))
        labels['mean_error'].append(float(np.mean(errors)) if errors else 100.)
        labels['mean_iou'].append(float(np.mean(ious)) if ious else 0.)
    return {k:np.asarray(v,np.float32) for k,v in labels.items()}


def unique_hypotheses(hyp):
    """Remove pure same-class ID permutations using predictions only."""
    seen=set();keep=[]
    for i,boxes in enumerate(hyp['boxes']):
        key=tuple((int(c),*np.round(b,6)) for c,b in sorted(zip(hyp['category'],boxes),key=lambda z:(int(z[0]),*z[1])))
        if key in seen:continue
        seen.add(key);keep.append(i)
    result=dict(hyp)
    for key in ('boxes','indices','cost','unary_logp','base_score'):result[key]=hyp[key][keep]
    return result


def diverse_hypotheses(outputs,batch,candidates=80,beam=64,max_layouts=128):
    """Truth-free order portfolio; keep the exact077 answer as fallback.

    A single beam mostly varies the last objects. Changing expansion order
    lets early-pruned object configurations survive. All orders use exactly
    the same unary scores, candidate domain and pairwise overlap penalty.
    """
    base=hypotheses(outputs,batch,candidates,beam)
    p=outputs['log_prob'][0].detach().cpu().numpy()
    centres=batch['centres'][0].numpy();sizes=batch['sizes'][0].numpy()
    valid=batch['valid'][0].numpy();cv=batch['candidate_valid'][0].numpy()
    slots=np.flatnonzero(valid);pools={}
    for slot in slots:
        boxes=[];ids=[]
        for i in np.argsort(-p[slot],kind='stable'):
            if not cv[slot,i]:continue
            pos,size=centres[slot,i],sizes[slot,i]
            if boxes:
                a=np.asarray(boxes)
                same=np.all(np.isclose(size,a[:,2:]-a[:,:2]),axis=-1)
                near=np.linalg.norm(pos-(a[:,:2]+a[:,2:])/2,axis=-1)<.18
                if np.any(same&near):continue
            boxes.append(np.r_[pos-size/2,pos+size/2]);ids.append(i)
            if len(boxes)>=candidates:break
        pools[slot]=(np.asarray(boxes),np.asarray(ids))
    original=sorted(slots,key=lambda j:-float(p[j].max()))
    area={j:float(np.prod(sizes[j,0])) for j in slots}
    orders=[original[::-1],sorted(slots,key=lambda j:-area[j]),
            sorted(slots,key=lambda j:area[j]),original[len(original)//2:]+original[:len(original)//2]]
    portfolios=[base];seen_orders={tuple(original)}
    for order in orders:
        if tuple(order) in seen_orders:continue
        seen_orders.add(tuple(order))
        costs=np.zeros(1);chosen=np.empty((1,0,4));indices=np.empty((1,0),np.int64)
        for slot in order:
            boxes,ids=pools[slot];joint=costs[:,None]-p[slot,ids][None]
            if chosen.shape[1]:
                lo=np.maximum(chosen[:,:,None,:2],boxes[None,None,:,:2]);hi=np.minimum(chosen[:,:,None,2:],boxes[None,None,:,2:])
                inter=np.maximum(0,hi-lo).prod(-1);a=np.prod(chosen[:,:,2:]-chosen[:,:,:2],-1)[:,:,None]
                a2=np.prod(boxes[:,2:]-boxes[:,:2],-1)[None,None]
                joint+=20*(inter/np.maximum(1e-10,a+a2-inter)).sum(1)
            keep=np.argsort(joint.ravel(),kind='stable')[:beam]
            parent,proposal=np.unravel_index(keep,joint.shape)
            chosen=np.concatenate([chosen[parent],boxes[proposal,None]],1)
            indices=np.concatenate([indices[parent],ids[proposal,None]],1);costs=joint[parent,proposal]
        permutation=np.argsort(order);index=indices[:,permutation]
        portfolios.append({'boxes':chosen[:,permutation].astype(np.float32),'indices':index,
            'cost':costs.astype(np.float32),'unary_logp':p[slots[None],index]})
    # Round-robin, rather than truncating to one order's nearly identical tail.
    rows=[(j,i) for i in range(beam) for j,h in enumerate(portfolios) if i<len(h['boxes'])]
    merged={k:np.stack([portfolios[j][k][i] for j,i in rows]) for k in ('boxes','indices','cost','unary_logp')}
    merged.update(slots=base['slots'],category=base['category'])
    # Nonpositive reference penalties guarantee that a zero-strength ranker
    # and a zero-contact input reproduce077. Real unary values remain in nodes.
    merged['base_score']=-np.maximum(0,merged['cost']-base['cost'][0])/len(slots)
    merged['base_score'][1:]-=1e-6
    merged=unique_hypotheses(merged)
    for k in ('boxes','indices','cost','unary_logp','base_score'):merged[k]=merged[k][:max_layouts]
    return merged


def sampled_hypotheses(outputs,batch,candidates=80,beam=64,max_layouts=128,draws=8):
    """Deterministic perturb-and-search from the WHOLE declared grid.

    Perturbation is for proposal diversity only. Final costs/features use the
    original unary field. Randomness has a fixed local seed, never a room ID,
    layout family or target. No-event inference keeps the unchanged baseline.
    """
    base=unique_hypotheses(hypotheses(outputs,batch,candidates,beam))
    if not bool(batch['event_valid'].any()):return base
    p=outputs['log_prob'][0].detach().cpu().numpy()
    c=batch['centres'][0].numpy();s=batch['sizes'][0].numpy()
    cv=batch['candidate_valid'][0].numpy();slots=base['slots']
    support=outputs['has_contact_support'][0].detach().cpu().numpy()
    rng=np.random.default_rng(7801);portfolios=[base]
    for draw in range(draws):
        temp=np.where(support,.35,1.25)*(1. if draw%2==0 else 2.)
        noisy=p+rng.gumbel(size=p.shape)*temp[:,None]
        order=rng.permutation(slots)
        costs=np.zeros(1);chosen=np.empty((1,0,4));indices=np.empty((1,0),np.int64)
        for slot in order:
            boxes=[];ids=[]
            for i in np.argsort(-noisy[slot],kind='stable'):
                if not cv[slot,i]:continue
                pos,size=c[slot,i],s[slot,i]
                if boxes:
                    a=np.asarray(boxes);same=np.all(np.isclose(size,a[:,2:]-a[:,:2]),axis=-1)
                    near=np.linalg.norm(pos-(a[:,:2]+a[:,2:])/2,axis=-1)<.18
                    if np.any(same&near):continue
                boxes.append(np.r_[pos-size/2,pos+size/2]);ids.append(i)
                if len(boxes)>=candidates:break
            boxes=np.asarray(boxes);ids=np.asarray(ids);joint=costs[:,None]-noisy[slot,ids][None]
            if chosen.shape[1]:
                lo=np.maximum(chosen[:,:,None,:2],boxes[None,None,:,:2]);hi=np.minimum(chosen[:,:,None,2:],boxes[None,None,:,2:])
                inter=np.maximum(0,hi-lo).prod(-1);a=np.prod(chosen[:,:,2:]-chosen[:,:,:2],-1)[:,:,None]
                a2=np.prod(boxes[:,2:]-boxes[:,:2],-1)[None,None]
                joint+=20*(inter/np.maximum(1e-10,a+a2-inter)).sum(1)
            keep=np.argsort(joint.ravel(),kind='stable')[:min(16,beam)]
            parent,proposal=np.unravel_index(keep,joint.shape)
            chosen=np.concatenate([chosen[parent],boxes[proposal,None]],1)
            indices=np.concatenate([indices[parent],ids[proposal,None]],1);costs=joint[parent,proposal]
        permutation=np.argsort(order);boxes=chosen[:,permutation].astype(np.float32);index=indices[:,permutation]
        unary=p[slots[None],index]
        lo=np.maximum(boxes[:,:,None,:2],boxes[:,None,:,:2]);hi=np.minimum(boxes[:,:,None,2:],boxes[:,None,:,2:])
        inter=np.maximum(0,hi-lo).prod(-1);area=np.prod(boxes[...,2:]-boxes[...,:2],-1)
        iou=inter/np.maximum(1e-10,area[:,:,None]+area[:,None,:]-inter)
        true_cost=-unary.sum(-1)+20*np.triu(iou,k=1).sum((1,2))
        portfolios.append({'boxes':boxes,'indices':index,'unary_logp':unary,'cost':true_cost})
    rows=[(j,i) for i in range(max(len(h['boxes']) for h in portfolios))
          for j,h in enumerate(portfolios) if i<len(h['boxes'])]
    merged={k:np.stack([portfolios[j][k][i] for j,i in rows]) for k in ('boxes','indices','cost','unary_logp')}
    merged.update(slots=slots,category=base['category'])
    merged['base_score']=-np.maximum(0,merged['cost']-base['cost'][0])/len(slots)
    merged['base_score'][1:]-=1e-6;merged=unique_hypotheses(merged)
    for k in ('boxes','indices','cost','unary_logp','base_score'):merged[k]=merged[k][:max_layouts]
    return merged


def with_analytic_proposals(hyp,batch,outputs,analytic_boxes,max_layouts=128):
    """Project a complete observation-only analytic answer to the SAME grid.

    Keep both complete answers and crossovers, without target matching. Sizes
    and prediction-to-prediction distances resolve same-category slot order.
    """
    from scipy.optimize import linear_sum_assignment
    slots=hyp['slots'];category=hyp['category']
    if len(analytic_boxes)!=len(slots):raise ValueError('A complete analytic prediction is required')
    p=outputs['log_prob'][0].detach().cpu().numpy()
    c=batch['centres'][0].numpy();s=batch['sizes'][0].numpy();cv=batch['candidate_valid'][0].numpy()
    assigned=np.empty(len(slots),np.int64)
    for cat in np.unique(category):
        which=np.flatnonzero(category==cat)
        boxes=np.asarray([b for name,b in analytic_boxes.items() if name.split('#')[0]==CATEGORIES[int(cat)]],float)
        if boxes.shape!=(len(which),4) or not np.isfinite(boxes).all():raise ValueError('A complete finite category set is required')
        target_c=(boxes[:,:2]+boxes[:,2:])/2;target_s=boxes[:,2:]-boxes[:,:2]
        if np.any(target_s<=0):raise ValueError('Invalid analytic rectangle')
        declared=np.sort(s[slots[which],0],axis=-1)
        size_cost=((declared[:,None]-np.sort(target_s,axis=-1)[None])**2).sum(-1)
        base_centres=(hyp['boxes'][0,which,:2]+hyp['boxes'][0,which,2:])/2
        tie=((base_centres[:,None]-target_c[None])**2).sum(-1)
        a,b=linear_sum_assignment(1000*size_cost+tie)
        for x,y in zip(a,b):
            j=slots[which[x]]
            distance=((c[j]-target_c[y])**2).sum(-1)+100*((s[j]-target_s[y])**2).sum(-1)
            distance=np.where(cv[j],distance,np.inf);assigned[which[x]]=int(distance.argmin())
    # Complete analytic answer, all one-object repairs in both directions.
    original=hyp['indices'][0];new=[assigned]
    for i in range(len(slots)):
        row=original.copy();row[i]=assigned[i];new.append(row)
        row=assigned.copy();row[i]=original[i];new.append(row)
    index=np.asarray(new,np.int64);centre=c[slots[None],index];size=s[slots[None],index]
    boxes=np.concatenate([centre-size/2,centre+size/2],-1).astype(np.float32)
    unary=p[slots[None],index]
    lo=np.maximum(boxes[:,:,None,:2],boxes[:,None,:,:2]);hi=np.minimum(boxes[:,:,None,2:],boxes[:,None,:,2:])
    inter=np.maximum(0,hi-lo).prod(-1);area=size.prod(-1)
    overlap=inter/np.maximum(1e-10,area[:,:,None]+area[:,None,:]-inter)
    cost=-unary.sum(-1)+20*np.triu(overlap,k=1).sum((1,2))
    extra={'boxes':boxes,'indices':index,'unary_logp':unary,'cost':cost}
    # Put the exact077 fallback first, then analytic/crossover predictions,
    # then the remaining077 search alternatives. No truth-dependent pruning.
    merged={k:np.concatenate([hyp[k][:1],extra[k],hyp[k][1:]],0) for k in extra}
    merged.update(slots=slots,category=category)
    merged['base_score']=-np.maximum(0,merged['cost']-hyp['cost'][0])/len(slots)
    merged['base_score'][1:]-=1e-6;merged=unique_hypotheses(merged)
    for k in ('boxes','indices','cost','unary_logp','base_score'):merged[k]=merged[k][:max_layouts]
    return merged
