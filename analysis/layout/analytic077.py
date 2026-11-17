"""Additional analytic control: latent contact assignment for multiple beds.

The historical proposal generator required EVERY bed contact to lie on EACH
bed. That is only sound with one bed. Keep the archived decoder unchanged,
but add this corrected unrestricted analytic comparison for new experiments.
It has no learned parameters and does not receive event-instance identities.
"""
import itertools
import types
import numpy as np

from . import multi_instance as M
from .continuous_regions import intersect_regions,_event_options


def bed_proposals(room,entry,events,path,padding,walk_excluded=True,walk_clearance=.15,walk_tolerance=0.,region_prior=None):
    if entry['category']!='bed':
        return M._proposals(room,entry,events,path,padding,walk_excluded,walk_clearance,walk_tolerance,region_prior)
    # Derive free regions once. Per-instance support is a UNION over possible
    # subsets, then the unchanged global CSP covers all observed events.
    remaining=[e for e in events if e['object']!='bed']
    _,base=M._proposals(room,entry,remaining,path,padding,walk_excluded,walk_clearance,walk_tolerance,region_prior)
    mine=[e for e in events if e['object']=='bed'];subsets=[()]
    for n in range(1,min(3,len(mine))+1):subsets.extend(itertools.combinations(mine,n))
    if len(mine)>3:subsets.append(tuple(mine))
    boxes=[]
    for subset in subsets:
        for mode in base['modes']:
            regions=mode['q_regions'];size=np.asarray(mode['dimensions'])
            for event in subset:
                regions=intersect_regions(regions,_event_options('bed',event['pos'],size,padding,.6))
                if not len(regions):break
            if not len(regions):continue
            for x,y in itertools.product((0.,.5,1.),repeat=2):
                q=regions[:,:2]+(regions[:,2:]-regions[:,:2])*[x,y]
                boxes.append(np.c_[q,q+size])
    if not boxes:return np.empty((0,4)),base
    boxes=np.unique(np.round(np.vstack(boxes),10),axis=0)
    if walk_excluded:boxes=boxes[~M.ES._path_bad(boxes,path,walk_tolerance-walk_clearance+1e-8)]
    return boxes,base


def corrected_static(observation):
    inventory=[];counts={}
    for e in observation['inventory']:
        category=e['category'];i=counts.get(category,0);counts[category]=i+1
        inventory.append({'id':f'{category}#{i}',**e})
    # Isolated function globals, avoiding mutations of the frozen module or
    # a process-global monkey patch. All other CSP logic/limits are original.
    namespace=dict(M.decode_instances.__globals__);namespace['_proposals']=bed_proposals
    decoder=types.FunctionType(M.decode_instances.__code__,namespace,'decode_instances077',
                               M.decode_instances.__defaults__,M.decode_instances.__closure__)
    decoder.__kwdefaults__=M.decode_instances.__kwdefaults__
    result=decoder(observation['room'],inventory,
                   [{'object':e['object'],'pos':e['pos']} for e in observation['events']],
                   np.asarray(observation['walk'],float).reshape(-1,2),
                   known_desk_protocol=observation['desk_relation'],candidate_limit=128,
                   contact_padding=.20,walk_clearance=.15,walk_tolerance=0.)
    return {**result,'boxes':{k:np.asarray(v).tolist() for k,v in result.get('boxes',{}).items()},
            'repair':'bed contacts have latent instance ownership; union of 0..3-contact subsets plus all-contact subset',
            'scope':'additional unrestricted analytic baseline, finite candidate generation and original CSP'}
