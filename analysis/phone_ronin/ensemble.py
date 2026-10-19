"""Optional C4 input-frame averaging of the already licensed RoNIN network.

This is a finite rotation-consistency control, not EqNIO, a new training result,
an arbitrary-angle equivariance guarantee, or an accuracy improvement claim.
"""
import numpy as np

def rotate_features(windows,quarter_turns):
    x=np.asarray(windows)
    if x.ndim!=3 or x.shape[1:]!=(6,200) or not np.isfinite(x).all():raise ValueError('Finite native-model window shape required')
    r=x.copy()
    for _ in range(quarter_turns%4):
        for i in (0,3):
            old=r[:,i].copy();r[:,i]=-r[:,i+1];r[:,i+1]=old
    return r

def c4_predict(windows,predictor):
    outputs=[]
    for k in range(4):
        v=np.asarray(predictor(rotate_features(windows,k)),dtype=float).copy()
        if v.shape!=(len(windows),2) or not np.isfinite(v).all():raise ValueError('Finite XY velocities required')
        for _ in range(k):v=np.column_stack((v[:,1],-v[:,0]))
        outputs.append(v)
    return np.mean(outputs,axis=0)
