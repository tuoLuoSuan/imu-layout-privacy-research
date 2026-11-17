"""Observation-only078 inference; frozen077 proposals plus graph ranking."""
from pathlib import Path
import numpy as np
import torch

from .recovery076_data import sha,prepare,pack
from .eval077 import load_checkpoint as load077
from .recovery078_candidates import hypotheses,unique_hypotheses,diverse_hypotheses,sampled_hypotheses,with_analytic_proposals,graph_features,as_boxes
from .recovery078_model import LayoutRanker078,pack_graph


def load_checkpoint(path,teacher_path):
    saved=torch.load(path,map_location='cpu',weights_only=True)
    if saved.get('architecture')!='layout078-v1':raise ValueError('078 checkpoint required')
    for name in ('recovery078_candidates.py','recovery078_model.py'):
        if sha(Path(__file__).with_name(name))!=saved['protocol']['source_sha256'][name]:
            raise ValueError('Frozen078 inference source differs: '+name)
    candidate=saved['protocol']['candidate_protocol']
    if candidate['args'].get('analytic',False):
        for name in ('analytic077.py','multi_instance.py','continuous_regions.py'):
            if sha(Path(__file__).with_name(name))!=candidate['source_sha256'][name]:raise ValueError('Frozen analytic source differs: '+name)
    if sha(teacher_path)!=candidate['teacher_checkpoint_sha256']:raise ValueError('Wrong frozen077 proposal model')
    teacher,teacher_saved=load077(teacher_path)
    model=LayoutRanker078(saved['width'],saved['rounds'])
    model.load_state_dict(saved['state_dict']);model.eval()
    return model,saved,teacher,teacher_saved


def _domain_rules(observation,batch,rules):
    """Optional real-data rules: sparseness-weighted walk barrier and chair-contact trust."""
    import numpy as np
    walk=np.asarray(observation['walk'],float);room=np.asarray(observation['room'],float)
    length=float(np.linalg.norm(np.diff(walk,axis=0),axis=1).sum()) if len(walk)>1 else 0.0
    density=length/max(float(room[0]*room[1]),1e-6)
    threshold=rules.get('walk_density_threshold')
    if threshold is not None and density<threshold:
        cat=batch['category'][0].cpu().numpy()
        valid=batch['valid'][0].cpu().numpy()
        solid=((cat==0)|(cat==1)|(cat==2))&valid
        scale=np.ones(batch['walk_cost'].shape[-2],dtype=np.float32)
        scale[solid]=float(rules.get('solid_walk_scale',4.0))
        batch['walk_cost']=batch['walk_cost']*scale[None,:,None]
    return density


def _chair_energy(observation,sample,energy,tol):
    import numpy as np, torch
    points=[event['pos'] for event in observation['events'] if event['object']=='chair']
    if not points:return energy
    cat=torch.as_tensor(sample['category']);slots=torch.where(cat==3)[0]
    if not len(slots):return energy
    centres=torch.as_tensor(sample['centres'])[slots]
    distance=torch.stack([torch.linalg.norm(centres-torch.tensor(point,dtype=torch.float32),dim=-1)
                          for point in points]).amin(0)
    mask=torch.zeros_like(energy,dtype=torch.bool)
    mask[0,slots,:]=distance>tol
    return energy.masked_fill(mask,-1e4)


def predict(observation,model,saved,teacher,teacher_saved,rules=None,search=None):
    sample=prepare(observation,teacher_saved['grid']);batch=pack([sample])
    density=_domain_rules(observation,batch,rules or {})
    config=dict(saved['protocol']['candidate_protocol']['args'])
    if search:
        if search.get('candidates') is not None:config['candidates']=int(search['candidates'])
        if search.get('beam') is not None:config['beam']=int(search['beam'])
    with torch.inference_mode():
        output=teacher(batch,strength=teacher_saved.get('score_strength',1.))
        specialization=config.get('only_cell')
        contact_count=(int(float(specialization.split(',')[1])) if specialization else config.get('only_contacts'))
        # A specialist is routed using ACTUAL supplied contact count only.
        # Coverage/family metadata and targets never enter this decision.
        if contact_count is not None and len(observation['events'])!=contact_count:
            from .recovery077_runtime import decode_fast
            energy=output['energy']
            tol=(rules or {}).get('chair_contact_tol')
            if tol is not None:energy=_chair_energy(observation,sample,energy.clone(),tol)
            output={'log_prob':energy.log_softmax(-1),'energy':energy,
                    'has_contact_support':output['has_contact_support']}
            return {'boxes':decode_fast(output,batch,config['candidates'],config['beam'])[0],'walk_density':density,
                    'route':'frozen077_other_contact_count','development_specialization':specialization,
                    'contact_specialization':contact_count,
                    'diagnostics':sample['diagnostics'],'scope':'synthetic geometric observations; frozen077 fallback'}
        if config.get('sampled',False):
            h=sampled_hypotheses(output,batch,config['candidates'],config['beam'],config['max_layouts'],config['draws'])
        elif config.get('diverse',False):
            h=diverse_hypotheses(output,batch,config['candidates'],config['beam'],config['max_layouts'])
        else:h=unique_hypotheses(hypotheses(output,batch,config['candidates'],config['beam']))
        if config.get('analytic',False) and observation['events']:
            from .analytic077 import corrected_static
            raw=corrected_static(observation)
            if raw['status']=='ok':h=with_analytic_proposals(h,batch,output,raw['boxes'],config['max_layouts'])
        features=graph_features(observation,batch,h)
        # Identical numeric contract to the small on-disk graph cache.
        features['nodes']=features['nodes'].astype(np.float16)
        features['edges']=features['edges'].astype(np.float16)
        graph,_=pack_graph([{'features':features}]);out=model(graph,strength=saved['strength'])
        index=int(out['scores'][0].argmax())
    return {'boxes':as_boxes(h,index),'selected_index':index,'hypotheses':len(h['boxes']),
            'route':'078_graph','routing_uses_coverage_or_family':False,
            'residual_strength':saved['strength'],'diagnostics':sample['diagnostics'],
            'development_specialization':config.get('only_cell'),
            'contact_specialization':contact_count,
            'scope':'synthetic geometric decoder; declared room/inventory and observed contact/walk positions; not raw IMU',
            'score_is_calibrated_probability':False}