"""Exploratory fixed router: actualK0 spatial CNN; actualK>0 frozen D.

No scores, target, family, coverage metadata or IDs are read by inference.
"""
from pathlib import Path
import numpy as np
import torch
from .recovery076_data import prepare,pack,read,sha
from .recovery083_fields import fields,scalar_features
from .recovery083_model import SpatialResidual083
from .recovery083_runtime import load_parent
from .recovery081_runtime import predict as predict081,refine_boxes
from .recovery077_runtime import decode_fast


def use_spatial_zero(observation):
    return len(observation['events'])==0


def residual_field(obs,batch,model):
    if batch['centres'].shape[0]!=1:raise ValueError('One observation at a time')
    field=torch.from_numpy(fields(obs))[None]
    with torch.inference_mode():
        z=model.trunk(field);z=torch.nn.functional.adaptive_avg_pool2d(z,(24,24));m=model.head(z).reshape(-1)
        add=torch.zeros_like(batch['walk_cost']);W,L=obs['room']
        for slot in range(add.shape[1]):
            if not batch['valid'][0,slot]:continue
            ids=torch.where(batch['candidate_valid'][0,slot])[0];c=batch['centres'][0,slot,ids];s=batch['sizes'][0,slot,ids]
            cat=int(batch['category'][0,slot]);cell=(c[:,1]/L*24).long().clamp(0,23)*24+(c[:,0]/W*24).long().clamp(0,23)
            scal=torch.from_numpy(np.stack([scalar_features(obs,cat,v.numpy()) for v in s]))
            add[0,slot,ids]=m[cat*576+cell]+model.scalar(scal).reshape(-1)
    return add


def load_models(root,lock_path):
    root=Path(root);lock=read(lock_path)
    if lock['rule']!='actual_events_zero_spatial_else_frozen_D':raise ValueError('Wrong routing rule')
    parents,refiners=load_parent(root)
    if parents['lock']['checkpoint_sha256']!=lock['D_checkpoint_sha256']:raise ValueError('Frozen D changed')
    for name,digest in lock['source_sha256'].items():
        if sha(Path(__file__).with_name(name))!=digest:raise ValueError('Frozen source changed: '+name)
    cp=root/'recovery083/seed8301/model-083.pt';cfg=root/'recovery083/seed8301/config.json'
    if sha(cp)!=lock['cnn_checkpoint_sha256'] or sha(cfg)!=lock['cnn_config_sha256']:raise ValueError('Spatial weights/config changed')
    config=read(cfg)
    if config['cells']!=24 or config['fields']!=6 or config['reach']!=.35 or config['sigma']!=.15:raise ValueError('Unexpected spatial field contract')
    if config['strength']!=parents['teacher_saved'].get('score_strength',1.):raise ValueError('077 strength differs from spatial training')
    model=SpatialResidual083(cells=24,width=tuple(config['width']));saved=torch.load(cp,map_location='cpu',weights_only=True)
    model.load_state_dict(saved['state_dict']);model.eval()
    return {'parents':parents,'refiners':refiners,'cnn':model,'lock':lock}


def predict(observation,models):
    sample=prepare(observation,24)
    if use_spatial_zero(observation):
        batch=pack([sample]);parent=models['parents'];strength=parent['teacher_saved'].get('score_strength',1.)
        with torch.inference_mode():
            o=parent['teacher'](batch,strength=strength);add=residual_field(observation,batch,models['cnn'])
            prob=(o['log_prob']+add).log_softmax(-1)
            boxes=decode_fast({**o,'log_prob':prob},batch,160,128)[0]
        # Matches the DS Spatial083 plus branch, including its K0 refiner.
        boxes,_=refine_boxes(observation,boxes,models['refiners'][6],'all');route='spatial_zero088'
    else:
        raw=predict081(observation,models['parents'],policy='none');K=len(observation['events'])
        boxes,_=refine_boxes(observation,raw['boxes'],models['refiners'][2] if K==2 else models['refiners'][6],'nonzero');route='frozen_D'
    return {'boxes':boxes,'route':route,'actual_contacts':len(observation['events']),
            'scope':'declared geometry and observed contact/walk; development-derived router, not independently confirmed or raw IMU'}
