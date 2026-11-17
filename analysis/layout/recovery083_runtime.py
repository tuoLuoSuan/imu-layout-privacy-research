"""One-step observation-only repair; the exact frozen parent is the default."""
from pathlib import Path
import numpy as np
import torch
from .recovery076_data import prepare,sha
from .recovery083 import Repair083,CATEGORIES,query_features,pack_features,refine_candidates
from .recovery081_runtime import load_models,predict as predict081,refine_boxes
from .recovery080_refine import Refine080


def action_field(obs,parent,refiner):
    sample=prepare(obs,24);cats=sample['category'];counts={};keys=[]
    for c in cats:
        name=CATEGORIES[int(c)];j=counts.get(name,0);counts[name]=j+1;keys.append(f'{name}#{j}')
    if set(keys)!=set(parent):raise ValueError('Parent inventory mismatch')
    p=np.asarray([parent[k] for k in keys],float);S,L=sample['candidate_valid'].shape
    if not np.allclose(np.sort(p[:,2:]-p[:,:2],-1),np.sort(sample['sizes'][:,0],-1),atol=1e-5):raise ValueError('Parent size correspondence')
    boxes=np.repeat(p[:,None],L+1,axis=1);valid=np.c_[np.ones(S,bool),sample['candidate_valid']]
    for slot,cat in enumerate(cats):
        c=sample['centres'][slot];s=sample['sizes'][slot];b=np.c_[c-s/2,c+s/2].astype(float);ok=sample['candidate_valid'][slot]
        boxes[slot,1:][ok]=refine_candidates(obs,int(cat),b[ok],refiner)
    return keys,p,cats,boxes,valid


def predict_utilities(model,obs,parent,categories,actions,chunk=2048):
    S,L=actions.shape[:2];boxes=actions.reshape(-1,4);slots=np.repeat(np.arange(S),L);result=[]
    model.eval()
    with torch.inference_mode():
        for start in range(0,len(boxes),chunk):
            f=query_features(obs,parent,categories,boxes[start:start+chunk],slots[start:start+chunk])
            probability=model(pack_features([f]))[0].softmax(-1).numpy()
            result.append(probability[...,2]-probability[...,0])
    return np.concatenate(result).reshape(S,L,2)


def choose_action(utilities,actions,parent,valid,room,policy):
    if policy.get('identity',False):return None
    u=utilities[...,0]+float(policy['foot_weight'])*utilities[...,1]
    centres=(actions[...,:2]+actions[...,2:])/2;pc=(parent[:,:2]+parent[:,2:])/2
    distance=np.linalg.norm(centres-pc[:,None],axis=-1)/np.linalg.norm(room)
    u=u-.002*distance;u=np.where(valid,u,-1e4);u[:,0]=0.
    slot,index=np.unravel_index(int(u.argmax()),u.shape)
    if index==0 or u[slot,index]<=float(policy['threshold']):return None
    return int(slot),int(index)


def load_repair(checkpoint):
    saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if saved['architecture']!='repair083-v1':raise ValueError('Wrong repair architecture')
    for name,digest in saved['protocol']['runtime_source_sha256'].items():
        if sha(Path(__file__).with_name(name))!=digest:raise ValueError('Repair runtime source changed: '+name)
    model=Repair083(saved['width']);model.load_state_dict(saved['state_dict']);model.eval()
    return model,saved


def load_parent(root):
    root=Path(root)
    models=load_models(root/'recovery078/main400-k2all-7801/best.pt',root/'recovery077/main400-calibration/calibrated.pt',
                       root/'recovery081/train-k6-8101/best.pt',root/'recovery080/k6-epoch6-reproduction/epoch6-pareto.pt')
    path=root/'recovery082/refine-k2/refine-k2.pt'
    if sha(path)!='a3330fe464dea376f19f3da5149f28f1312ae7cbd00d33cd416d22db061e4a68':raise ValueError('Frozen D K2 refiner changed')
    s=torch.load(path,map_location='cpu',weights_only=True);r=Refine080(s['width'],s['dim']);r.load_state_dict(s['state_dict']);r.eval()
    models['lock']['checkpoint_sha256']['refiner_k2']=sha(path)
    return models,{2:r,6:models['refiner']}


def predict(obs,model,saved,parent_models,refiners):
    if parent_models['lock']['checkpoint_sha256']!=saved['protocol']['parent_checkpoint_sha256']:
        raise ValueError('Frozen parent differs from the repair training protocol')
    raw=predict081(obs,parent_models,policy='none');K=len(obs['events'])
    refiner=refiners[2] if K==2 else refiners[6]
    parent,_=refine_boxes(obs,raw['boxes'],refiner,'nonzero')
    result={'boxes':parent,'parent_boxes':parent,'repair_applied':False,'policy':saved['policy'],
            'scope':'conditional geometric observations, not raw IMU; new model unconfirmed'}
    if K not in (2,6) or saved['policy'].get('identity',False):return result
    keys,p,cats,actions,valid=action_field(obs,parent,refiner)
    u=predict_utilities(model,obs,p,cats,actions);chosen=choose_action(u,actions,p,valid,obs['room'],saved['policy'])
    if chosen is not None:
        slot,index=chosen;boxes=dict(parent);boxes[keys[slot]]=actions[slot,index].tolist()
        result.update(boxes=boxes,repair_applied=True,slot=slot,candidate=index)
    return result
