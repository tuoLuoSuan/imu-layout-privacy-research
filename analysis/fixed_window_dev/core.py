"""Development-only fixed-window baseline. Never a formal calibration model."""
import math
import numpy as np
from analysis.session_readiness.quality import assess,checked

TRAIN_FIELDS={'id','source_sha256','block','features','label'}
PREDICT_FIELDS=TRAIN_FIELDS-{'label'}


def fixed_window(series,bounds,start=20.,end=55.):
    a=checked(series)
    if type(start) not in (int,float) or type(end) not in (int,float) or not math.isfinite(start+end) or not 0<=start<end:
        raise ValueError('Finite ordered recording-relative window required')
    q=assess(a,bounds)
    if q['hard_failure'] or bounds[1]-bounds[0]<end-1e-9:
        raise ValueError('Whole recording lacks validated window support')
    relative=a[:,0]-bounds[0]
    b=np.array(a[(relative>=start-1e-9)&(relative<end-1e-9)],copy=True)
    checked(b)
    if b[0,0]-bounds[0]-start>.25+1e-9 or end-(b[-1,0]-bounds[0])>.25+1e-9:
        raise ValueError('Window edge lacks support')
    return b


def _features(row,n=None):
    x=np.asarray(row['features'],dtype=float)
    if x.ndim!=1 or not len(x) or not np.isfinite(x).all() or (n is not None and len(x)!=n):
        raise ValueError('Finite matching feature vector required')
    for k in ('id','block'):
        if not isinstance(row[k],str) or not row[k]:raise ValueError('Opaque session and block identity required')
    s=row['source_sha256']
    if not isinstance(s,str) or len(s)!=64 or any(c not in '0123456789abcdef' for c in s):raise ValueError('Source SHA required')
    return x


def fit_development(rows):
    if len(rows)!=2 or any(set(r)!=TRAIN_FIELDS for r in rows):raise ValueError('This development fit uses exactly two training sessions')
    if any(type(r['label']) is not int for r in rows) or {r['label'] for r in rows}!={0,1}:
        raise ValueError('Balanced binary development pair required')
    if len({r['id'] for r in rows})!=2 or len({r['source_sha256'] for r in rows})!=2 or len({r['block'] for r in rows})!=1:
        raise ValueError('One distinct, balanced source pair from one training block required')
    n=len(_features(rows[0]));x=np.array([_features(r,n) for r in rows]);ys=np.array([r['label'] for r in rows])
    mu=x.mean(0);scale=x.std(0);scale=np.where(scale<1e-8,1.,scale)
    x=np.c_[(x-mu)/scale,np.ones(2)];beta=np.zeros(x.shape[1]);penalty=np.r_[np.ones(x.shape[1]-1),0.]
    for _ in range(100):
        prob=1/(1+np.exp(-np.clip(x@beta,-40,40)))
        gradient=x.T@(prob-ys)/2+penalty*beta
        hessian=(x.T*(prob*(1-prob)))@x/2+np.diag(penalty)+np.eye(len(beta))*1e-8
        step=np.linalg.solve(hessian,gradient);beta-=step
        if np.max(np.abs(step))<1e-8:break
    return {'schema':'fixed-window-two-row-development-v3','training_rows':2,'formal_calibration_model':False,
        'training_ids':[r['id'] for r in rows],'training_sha256':[r['source_sha256'] for r in rows],
        'training_blocks':[rows[0]['block']],'mean':mu.tolist(),'scale':scale.tolist(),'beta':beta.tolist(),
        'lambda_l2':1.,'formal_score':None,'physical_clock_accepted':False}


def predict_development(model,rows):
    if model.get('schema')!='fixed-window-two-row-development-v3' or model.get('formal_calibration_model') is not False:
        raise ValueError('Explicit development model required')
    if not rows or any(set(r)!=PREDICT_FIELDS for r in rows):raise ValueError('Prediction inputs cannot contain label/reference')
    if len({r['id'] for r in rows})!=len(rows) or len({r['source_sha256'] for r in rows})!=len(rows):raise ValueError('Duplicate prediction identity')
    out=[];n=len(model['mean'])
    for r in rows:
        x=_features(r,n)
        if r['id'] in model['training_ids'] or r['source_sha256'] in model['training_sha256'] or r['block'] in model['training_blocks']:
            raise ValueError('Prediction block/source overlaps training')
        z=float(np.r_[(x-np.asarray(model['mean']))/model['scale'],1.]@model['beta'])
        p=float(np.clip(1/(1+math.exp(-max(-40,min(40,z)))),1e-6,1-1e-6))
        out.append({'id':r['id'],'probability':p})
    return out


def score(predictions,labels):
    if not predictions or any(set(p)!={'id','probability'} for p in predictions) or len({p['id'] for p in predictions})!=len(predictions):
        raise ValueError('Unique prediction rows required')
    if {p['id'] for p in predictions}!=set(labels) or any(type(y) is not int or y not in (0,1) for y in labels.values()):
        raise ValueError('Exact binary label/prediction identity required')
    if any(type(p['probability']) not in (int,float) or not math.isfinite(p['probability']) or not 0<=p['probability']<=1 for p in predictions):
        raise ValueError('Finite probability required')
    rows=[{'id':p['id'],'y':labels[p['id']],'p_R':p['probability'],
        'loss':(p['probability']-labels[p['id']])**2} for p in predictions]
    return {'brier':float(np.mean([r['loss'] for r in rows])),'rows':rows,'sessions':len(rows),'formal_score':None}


def uniform_multiclass_brier(k):
    if type(k) is not int or k<2:raise ValueError('At least two classes required')
    return 1-1/k
