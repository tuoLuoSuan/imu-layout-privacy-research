"""Read-only comparison after a fresh raw-IMU replay in an isolated directory.

The geometric multi-instance estimator is additionally tested as a diagnostic,
conditioned on registration from the production solver. A failed diagnostic
must not replace the working real-IMU entry or be hidden behind its result.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .selection_diagnostics import rerank_pools


def run(replay,baseline,out,bundle=None):
    replay,baseline,out=map(Path,(replay,baseline,out));p=json.loads((replay/'prediction.json').read_text(encoding='utf-8'));b=json.loads((baseline/'prediction.json').read_text(encoding='utf-8'))
    d=np.load(replay/'ronin-xy.npy');t=d[:,0]-.5;raw=d[:,1:3];angle=np.radians(p['rot_deg']);R=np.array([[np.cos(angle),np.sin(angle)],[-np.sin(angle),np.cos(angle)]])
    Q=raw@R;Q-=Q[0]-np.array(p['start_anchored_at']);walk=np.zeros(len(t),bool)
    for label,start,end in json.loads((replay/'actions.json').read_text(encoding='utf-8'))['runs']:
        if label=='walk':walk|=(t>=start)&(t<=end)
    mapping={'seated':'chair','cabinet':'cab','lying':'bed'};events=[{'object':mapping[k],'pos':v} for k,v in p['anchors'].items() if k in mapping]
    inventory=[{'id':'bed#0','category':'bed','dimensions':[1.525,2.085]},
        {'id':'desk#0','category':'desk','dimensions':[.6,1.2]},
        {'id':'cab#0','category':'cab','dimensions':[.6,.9]},
        {'id':'chair#0','category':'chair','dimensions':[.44,.44]}]
    truth={'bed#0':[1.17,1.96,2.695,4.045],'desk#0':[.05,1.05,.65,2.1],'cab#0':[.05,0,.65,1.05],'chair#0':[1.11,.92,1.55,1.36]}
    original=M._constraint_search;checks={};cache={}
    profiles={'ideal_hard_bounds':{},'contact_permissions':{'walk_excluded_objects':('desk','cab')},
        'noise_0_3m':{'walk_excluded_objects':('desk','cab'),'contact_padding':.3,'walk_tolerance':.3}}
    for label,options in profiles.items():
      for policy in ['legacy','outline']:
        def select(inventory,pools,targets,counts):return original(inventory,rerank_pools(pools,p['room'],Q[walk],policy),targets,counts)
        M._constraint_search=select
        try:r=M.decode_instances(p['room'],inventory,events,Q[walk],proposal_cache=cache,**options)
        finally:M._constraint_search=original
        checks[label+'|'+policy]={'status':r['status'],'bounds':options,'score':M.score_instances(r['boxes'],truth),'boxes':{k:np.asarray(v).tolist() for k,v in r['boxes'].items()}}
    prod=M.score_instances({k+'#0':v for k,v in p['boxes'].items()},truth)
    result={'production_status':p['status'],'production_score':prod,
        'previous_verified_rotation_deg':b['rot_deg'],'current_rotation_deg':p['rot_deg'],
        'max_coordinate_delta_m':{k:float(np.max(np.abs(np.asarray(v)-np.asarray(b['boxes'][k])))) for k,v in p['boxes'].items()},
        'geometric_estimator_diagnostic':checks,
        'diagnostic_scope':'Ideal-coordinate multi-instance solver, conditioned on production registration; not a new raw-IMU pipeline. Never substitutes its real-room diagnostic for production.',
        'raw_bundle_sha256':hashlib.sha256(Path(bundle).read_bytes()).hexdigest() if bundle else None}
    out.write_text(json.dumps(result,indent=1),encoding='utf-8');print(json.dumps(result,indent=1));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--replay',required=True);p.add_argument('--baseline',required=True);p.add_argument('--out',required=True);p.add_argument('--bundle');a=p.parse_args();run(a.replay,a.baseline,a.out,a.bundle)
