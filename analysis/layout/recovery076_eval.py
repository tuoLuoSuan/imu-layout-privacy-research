"""Same-observation baselines and geometry-surface scores; no cached old rates."""
from collections import defaultdict
import numpy as np
from scipy.optimize import linear_sum_assignment

from .recovery076_data import CATEGORIES


def static_decode(observation,unrestricted=False):
    from .recovery010 import solve
    from .multi_instance import decode_instances
    inventory=[];counts={}
    for e in observation['inventory']:
        c=e['category'];i=counts.get(c,0);counts[c]=i+1
        inventory.append({'id':f'{c}#{i}',**e})
    # Both arms receive exactly these positions; no heading is granted to 076
    # in this geometry benchmark. The original geometry solver is not changed.
    events=[{'object':e['object'],'pos':e['pos']} for e in observation['events']]
    options={'candidate_limit':128,'contact_padding':.20,'walk_clearance':.15,
             'walk_tolerance':0.,'known_desk_protocol':observation['desk_relation']}
    path=np.asarray(observation['walk'],float).reshape(-1,2)
    if unrestricted:
        result=decode_instances(observation['room'],inventory,events,path,**options)
    else:
        result=solve(observation['room'],inventory,events,path,'depth_portfolio',decoder_options=options)
    return {**result,'boxes':{k:np.asarray(v).tolist() for k,v in result.get('boxes',{}).items()}}


def score(boxes,truth):
    from .multi_instance import score_instances
    from .sim_eval import iou
    centre={str(t):score_instances(boxes,truth,t) for t in (.25,.5,1.)}
    hit=0
    for category in CATEGORIES:
        p=[b for k,b in boxes.items() if k.split('#')[0]==category]
        t=[b for k,b in truth.items() if k.split('#')[0]==category]
        if not p or not t:continue
        matrix=np.array([[iou(a,b) for b in t] for a in p]);valid=matrix>=.5
        a,b=linear_sum_assignment((~valid)*(min(len(p),len(t))+1)+(1-matrix)*1e-7)
        hit+=int(valid[a,b].sum())
    s=centre['0.5']
    return {'whole_room':int(s['all_instances_hit']),'whole_footprint':int(bool(truth) and hit==len(boxes)==len(truth)),
            'f1':s['f1'],'footprint_f1':2*hit/max(1,len(boxes)+len(truth)),
            'centre_tolerances':{t:int(v['all_instances_hit']) for t,v in centre.items()},
            'per_class':s['per_class'],'matches':s['matches']}


def failed_score():
    return {'whole_room':0,'whole_footprint':0,'f1':0.,'footprint_f1':0.,
            'centre_tolerances':{'0.25':0,'0.5':0,'1.0':0},'per_class':{},'matches':[]}


def aggregate(rows):
    if not rows:return {'n_requested':0}
    return {'n_requested':len(rows),'n_usable':sum(r['usable'] for r in rows),
            **{k:float(np.mean([r[k] for r in rows])) for k in ('whole_room','whole_footprint','f1','footprint_f1')},
            'whole_room_count':sum(r['whole_room'] for r in rows),
            'whole_footprint_count':sum(r['whole_footprint'] for r in rows)}


def surfaces(rows,draws=2000):
    cells=defaultdict(list)
    for row in rows:cells[(row['arm'],row['coverage_target'],row['contacts_requested'])].append(row)
    table=[]
    for (arm,c,k),values in sorted(cells.items()):
        table.append({'arm':arm,'coverage_target':c,'contacts_requested':k,**aggregate(values)})
    comparisons=[];rng=np.random.default_rng(760)
    lookup={(r['id'],r['arm']):r for r in rows}
    for (arm,c,k),values in sorted(cells.items()):
        if arm=='learned':continue
        by_group=defaultdict(list)
        for r in values:
            learned=lookup.get((r['id'],'learned'))
            if learned is None:continue
            by_group[r['group']].append([learned['whole_room']-r['whole_room'],
                                         learned['whole_footprint']-r['whole_footprint']])
        if not by_group:continue
        d=np.array([np.mean(v,axis=0) for _,v in sorted(by_group.items())])
        boot=d[rng.integers(len(d),size=(draws,len(d)))].mean(1)
        comparisons.append({'baseline':arm,'coverage_target':c,'contacts_requested':k,
                            'independent_condition_groups':len(d),'paired_rows':sum(map(len,by_group.values())),
                            'centre_delta':float(d[:,0].mean()),'centre_ci95':np.quantile(boot[:,0],[.025,.975]).tolist(),
                            'footprint_delta':float(d[:,1].mean()),'footprint_ci95':np.quantile(boot[:,1],[.025,.975]).tolist()})
    overall=[]
    for arm in sorted({r['arm'] for r in rows}-{'learned'}):
        for scope in ('nonzero_contact_grid','low_coverage_nonzero'):
            grouped=defaultdict(list)
            for r in rows:
                if r['arm']!=arm or r['contacts_requested']<2:continue
                if scope=='low_coverage_nonzero' and r['coverage_target']>.5:continue
                learned=lookup.get((r['id'],'learned'))
                if learned is None:continue
                grouped[r['group']].append([learned['whole_room']-r['whole_room'],
                                             learned['whole_footprint']-r['whole_footprint']])
            if not grouped:continue
            d=np.array([np.mean(v,axis=0) for _,v in sorted(grouped.items())])
            boot=d[rng.integers(len(d),size=(draws,len(d)))].mean(1)
            overall.append({'baseline':arm,'scope':scope,'condition_groups':len(d),
                            'centre_delta':float(d[:,0].mean()),'centre_ci95':np.quantile(boot[:,0],[.025,.975]).tolist(),
                            'footprint_delta':float(d[:,1].mean()),'footprint_ci95':np.quantile(boot[:,1],[.025,.975]).tolist()})
    return {'cells':table,'paired':comparisons,'overall_paired':overall,
            'uncertainty':'paired bootstrap by condition group; all counterfactual copies and budget cells clustered'}


def contact_swap_diagnostic(model,entries,original_rows):
    """Within-condition contact intervention; failed/missing donors are disclosed.

    Keeps recipient walk and all declared side information. This is a deliberate
    inconsistent-evidence diagnostic, never a new acquisition success rate.
    """
    import torch
    from .recovery076_data import pack
    from .recovery076_model import decode
    candidates=defaultdict(list);rows=[];unavailable=[]
    originals={r['id']:r for r in original_rows if r['arm']=='learned'}
    for entry in entries:
        r=entry['row'];candidates[(r['group'],r['coverage_target'],r['contacts_requested'])].append(entry)
    with torch.inference_mode():
        for entry in entries:
            r=entry['row'];sample=entry['sample'];key=(r['group'],r['coverage_target'],r['contacts_requested'])
            donors=[d for d in candidates[key] if d['sample'] is not None and d['row']['fingerprint']!=r['fingerprint']]
            if sample is None or not donors:unavailable.append(r['id']);continue
            donor=sorted(donors,key=lambda d:d['row']['id'])[0];a,b=sample['observation'],donor['sample']['observation']
            if any(a[k]!=b[k] for k in ('room','inventory','frame','desk_relation')):
                raise ValueError('Counterfactual donors do not share declared conditions')
            changed=dict(sample,events=donor['sample']['events'],event_valid=donor['sample']['event_valid'])
            batch=pack([changed]);changed_boxes=decode(model(batch),batch)[0]
            outcome=score(changed_boxes,entry['truth'])
            rows.extend([originals[r['id']],{**originals[r['id']],**outcome,'arm':'paired_contact_swap',
                                            'boxes':changed_boxes,'donor_id':donor['row']['id']}])
    return {'scope':'same-condition different-layout contact swap; recipient walk retained',
            'requested_rows':len(entries),'paired_recipients':len(rows)//2,'unavailable_ids':unavailable,
            'rows':rows,'summary':surfaces(rows) if rows else None}
