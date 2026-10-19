"""Matched activity-model interface, with wrist-feature mismatch before inference.

The caller supplies a separately trained predictor; this module never trains or
creates real walk probabilities. Wrist-shift fixes phone; phone-shift fixes wrist.
"""
import math
import numpy as np

def minimum_shift_samples(clock_uncertainty_s,stride_s):
    if not math.isfinite(clock_uncertainty_s) or clock_uncertainty_s<0 or not math.isfinite(stride_s) or stride_s<=0:
        raise ValueError('Finite clock uncertainty and positive feature spacing required')
    return math.ceil(clock_uncertainty_s/stride_s)+1

def paired_activity_probabilities(phone_features,watch_features,predict_joint,*,shift_samples,
        target_end_s,availability_s,budget_s,clock_uncertainty_s):
    p=np.asarray(phone_features,dtype=float);w=np.asarray(watch_features,dtype=float)
    t=np.asarray(target_end_s,dtype=float);a=np.asarray(availability_s,dtype=float)
    if p.ndim!=2 or w.ndim!=2 or len(p)!=len(w) or t.shape!=(len(p),) or a.shape!=t.shape or not np.isfinite(t).all() or not np.isfinite(a).all() or not np.isfinite(budget_s):raise ValueError('Aligned feature timing required')
    if np.any(np.diff(t)<=0) or np.any(a<t):raise ValueError('Ordered causal feature support required')
    mask=(t<=budget_s)&(a<=budget_s);p=p[mask];w=w[mask];t=t[mask]
    if len(p)<2 or not np.isfinite(p).all() or not np.isfinite(w).all():raise ValueError('Aligned finite current-prefix feature rows required')
    if not isinstance(shift_samples,int) or isinstance(shift_samples,bool) or not 0<shift_samples<len(w):raise ValueError('Nonzero within-prefix circular shift required')
    required=minimum_shift_samples(clock_uncertainty_s,float(np.min(np.diff(t))))
    if min(shift_samples,len(w)-shift_samples)<required:
        raise ValueError('Circular mismatch separation must exceed clock uncertainty in both directions')
    values=[]
    for phone,wrist in ((p,w),(p,np.roll(w,shift_samples,axis=0)),(np.roll(p,shift_samples,axis=0),w)):
        probability=np.asarray(predict_joint(np.concatenate((phone,wrist),axis=1)),dtype=float)
        if probability.shape!=(len(p),) or not np.isfinite(probability).all() or np.any((probability<0)|(probability>1)):raise ValueError('Predictor must return finite walk probabilities')
        values.append(probability.copy())
    return {'joint':values[0],'shifted_watch':values[1],'shifted_phone':values[2]}
