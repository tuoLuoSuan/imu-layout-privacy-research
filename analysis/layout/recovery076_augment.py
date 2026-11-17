"""Coordinate transformations, never independent rotations of targets/inputs."""
import copy
import numpy as np
import torch


def rotate_batch(batch,truths,k):
    result={key:value.clone() for key,value in batch.items()};targets=copy.deepcopy(truths)
    # A coordinate rotation about the origin needs no true room pose. Negative
    # coordinates are fine here: candidates/clearance were transformed together.
    q=torch.tensor([[[1.,0.],[0.,1.]],[[0.,-1.],[1.,0.]],
                    [[-1.,0.],[0.,-1.]],[[0.,1.],[-1.,0.]]],device=batch['centres'].device)[k%4]
    result['centres']=result['centres']@q.T
    result['events'][...,:2]=result['events'][...,:2]@q.T
    result['events'][...,5:7]=result['events'][...,5:7]@q.T
    if k%2:result['sizes']=result['sizes'].flip(-1)
    for boxes in targets:
        for name,box in boxes.items():
            a=np.asarray(box);centre=(a[:2]+a[2:])/2@q.cpu().numpy().T;size=a[2:]-a[:2]
            if k%2:size=size[::-1]
            boxes[name]=np.r_[centre-size/2,centre+size/2].tolist()
    return result,targets
