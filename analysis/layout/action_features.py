"""Public, unchanged feature formulas used by the five-class handheld model.

Extracted from action_recognition.pipeline and the existing dataset_ext temporal
features so inference does not depend on private output-directory code.
"""
import math
import numpy as np

def event_features(times,xyz,start_s,end_s,*,normalize=True):
    t=np.asarray(times,float);x=np.asarray(xyz,float)
    if t.ndim!=1 or x.shape!=(len(t),3) or not math.isfinite(start_s) or not math.isfinite(end_s) or end_s<=start_s:
        raise ValueError('Finite ordered time interval and XYZ stream required')
    if not np.isfinite(t).all() or np.any(np.diff(t)<=0):raise ValueError('Ordered original timestamps required')
    selected=(t>=start_s)&(t<end_s);t=t[selected];x=x[selected]
    if len(t)<4:raise ValueError('Insufficient event samples')
    if not np.isfinite(x).all():raise ValueError('Nonfinite selected samples')
    norm=np.linalg.norm(x,axis=1);scale=float(np.median(norm)) if normalize else 1.
    if scale<=1e-8:raise ValueError('Invalid acceleration normalization')
    x=x/scale;norm=norm/scale
    result={f'norm_{k}':float(v) for k,v in {
        'mean':norm.mean(),'std':norm.std(),'q10':np.quantile(norm,.1),
        'q50':np.median(norm),'q90':np.quantile(norm,.9),'range':np.ptp(norm),
        'rms':np.sqrt(np.mean(norm**2))}.items()}
    edge=max(1,len(x)//5);first=x[:edge].mean(axis=0);last=x[-edge:].mean(axis=0)
    for i,axis in enumerate('xyz'):
        result[axis+'_mean']=float(x[:,i].mean());result[axis+'_std']=float(x[:,i].std())
        result[axis+'_range']=float(np.ptp(x[:,i]));result[axis+'_end_minus_start']=float(last[i]-first[i])
    den=np.linalg.norm(first)*np.linalg.norm(last)
    result['end_start_direction_angle_rad']=float(np.arccos(np.clip(np.dot(first,last)/den,-1,1))) if den>1e-12 else 0.
    jerk=np.diff(x,axis=0)/np.diff(t)[:,None]
    result['normalized_jerk_rms']=float(np.sqrt(np.mean(np.sum(jerk**2,axis=1))))
    for a,b in [(0,1),(0,2),(1,2)]:
        result[f'corr_{a}{b}']=float(np.corrcoef(x[:,a],x[:,b])[0,1]) if min(x[:,a].std(),x[:,b].std())>1e-10 else 0.
    if not all(math.isfinite(v) for v in result.values()):raise ValueError('Invalid event features')
    return result

def assess(times, lo, hi):
    t = np.asarray(times, float); picked = t[(t >= lo) & (t < hi)]
    if not len(picked): return dict(samples=0, valid=False, gap=None)
    gap = float(max(picked[0]-lo, hi-picked[-1], np.diff(picked).max() if len(picked) > 1 else 0.0))
    return dict(samples=int(len(picked)), gap=gap, valid=bool(len(picked) >= 4 and gap <= 0.5+1e-9))

def select(t, x, lo, hi):
    picked = (t >= lo) & (t < hi)
    return (t[picked]-lo, x[picked])

def temporal(segments, device):
    t, x = segments[device+'_acc']; norm = np.linalg.norm(x, axis=1)
    if not len(t): return {}
    scale = float(np.median(norm)) or 1.0
    normalized = x/scale; mag = norm/scale; out = {}
    for i in range(3):
        a = mag[(t >= i) & (t < i+1)]
        out[f'temporal_acc_mean_{i}'] = float(a.mean()) if len(a) else 0.0
        out[f'temporal_acc_std_{i}'] = float(a.std()) if len(a) else 0.0
    for name, picked in [('first', t < .5), ('last', t >= 2.5)]:
        a = normalized[picked].mean(axis=0) if picked.any() else np.zeros(3)
        for j in range(3): out[f'temporal_direction_{name}_{j}'] = float(a[j])
    out['temporal_acc_norm_integral'] = float(np.trapezoid(mag, t))
    if device == 'phone' and 'phone_gyro' in segments:
        tg, g = segments['phone_gyro']
        if len(tg):
            for j in range(3):
                out[f'temporal_gyro_integral_{j}'] = float(np.trapezoid(g[:, j], tg))
                out[f'temporal_gyro_abs_integral_{j}'] = float(np.trapezoid(abs(g[:, j]), tg))
            for i in range(3):
                sel = (tg >= i) & (tg < i+1)
                out[f'temporal_gyro_energy_{i}'] = float(np.mean(np.sum(g[sel]**2, axis=1))) if sel.any() else 0.0
    return out

def features_at(ta, A, tg, G, s0):
    f, sgs = {}, {}
    for nm, (t, x), pre, norm in (('acc', (ta, A), 'acc', True), ('gyro', (tg, G), 'gyro', False)):
        if not assess(t, s0, s0+3)['valid']: return None
        f.update({pre+'_'+k: v for k, v in event_features(t, x, s0, s0+3, normalize=norm).items()})
        sgs['phone_'+pre] = select(t, x, s0, s0+3)
    f.update(temporal(sgs, 'phone'))
    return f
