"""Gated zero-rate iteration. Experimental alternative;014a is preserved."""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import lsmr
from sklearn.cluster import AgglomerativeClustering
from .inertial010 import rest_mask, intervals


def _bins(t,mask,A,G):
    bins=[]
    for a,b in intervals(mask):
        for group in np.array_split(np.arange(a,b),max(1,int(np.ceil((t[b-1]-t[a])/2.)))):
            mid=(t[group[0]]+t[group[-1]])/2
            ids=group[abs(t[group]-mid)<=.15]
            if len(ids)>=8:bins.append(ids)
    if not bins:raise ValueError('No reliable zero-rate holds')
    return np.array([t[i].mean() for i in bins]),np.array([A[i].mean(axis=0) for i in bins]),np.array([G[i].mean(axis=0) for i in bins])


def _fit(centre,values,labels,observation_sigma,drift_sigma,relative):
    n=len(centre);k=int(labels.max())+1 if relative else 0;rr=[];cc=[];vv=[];ys=[]
    def eq(terms,target,scale):
        row=len(ys)
        for j,v in terms.items():rr.append(row);cc.append(j);vv.append(v/scale)
        ys.append(np.asarray(target)/scale)
    for i in range(n):eq({i:1.,n+int(labels[i]):1.} if relative else {i:1.},values[i],observation_sigma)
    for i in range(1,n):eq({i:1.,i-1:-1.},np.zeros(3),drift_sigma*np.sqrt(max(.1,centre[i]-centre[i-1])))
    if relative:eq({0:1.},np.zeros(3),1e-5)
    mat=coo_matrix((vv,(rr,cc)),shape=(len(ys),n+k)).tocsr();target=np.array(ys)
    result=np.c_[*[lsmr(mat,target[:,a],atol=1e-11,btol=1e-11,maxiter=4000)[0][:n] for a in range(3)]]
    return result-result[0] if relative else result


def calibrate(time,acceleration,gyro):
    t=np.asarray(time,float);A=np.asarray(acceleration,float);G=np.asarray(gyro,float)
    if len(t)<3 or np.any(np.diff(t)<=0):raise ValueError('Strictly increasing clock required')
    if A.shape!=G.shape or A.shape!=(len(t),3):raise ValueError('Phone6 axes must share a clock')
    # The existing capture protocol already requires an initial stationary hold.
    # Anchor rate bias there. Subsequent holds must pass the original absolute
    # gyro gate after current bias correction, not just have small rate variance.
    initial=(t-t[0])<=2.;seed=np.mean(G[initial],axis=0);curve=np.tile(seed,(len(t),1))
    for _ in range(3):
        mask=rest_mask(t,A,G-curve)
        if not np.any(mask) or t[np.flatnonzero(mask)[0]]-t[0]>4.:raise ValueError('Initial stable handset period required')
        centre,am,gm=_bins(t,mask,A,G)
        gb=_fit(centre,gm,np.zeros(len(centre),int),.0005,.0002,False)
        curve=np.c_[*[np.interp(t,centre,gb[:,a]) for a in range(3)]]
    up=am/np.linalg.norm(am,axis=1)[:,None]
    labels=AgglomerativeClustering(n_clusters=None,distance_threshold=.10,linkage='complete').fit_predict(up) if len(up)>1 else np.zeros(1,int)
    ab=_fit(centre,am,labels,.006,.003,True)
    acurve=np.c_[*[np.interp(t,centre,ab[:,a]) for a in range(3)]]
    adjacent=mask[1:]&mask[:-1]
    diff=np.diff(G,axis=0)[adjacent]
    noise=np.median(abs(diff-np.median(diff,axis=0)),axis=0)/(.67448975*np.sqrt(2)) if len(diff) else np.ones(3)*.003
    mean_se=float(np.linalg.norm(noise)/np.sqrt(max(8,round(.3/np.median(np.diff(t))))))
    drift_rms=float(np.sqrt(np.mean(np.sum((curve-curve.mean(axis=0))**2,axis=1))))
    info={'rest_samples':int(mask.sum()),'stable_bins':len(centre),'latent_gravity_clusters':int(labels.max()+1),
          'max_acc_drift_correction_m_s2':float(np.linalg.norm(acurve,axis=1).max()),
          'max_gyro_bias_correction_rad_s':float(np.linalg.norm(curve,axis=1).max()),
          'initial_hold_s':2.,'zero_rate_iterations':3,
          'gyro_drift_rms_rad_s':drift_rms,'gyro_mean_se_rad_s':mean_se,'initial_gyro_bias_norm_rad_s':float(np.linalg.norm(seed)),
          'assumptions':'Offline; initial2s stationary as already required by capture; recurring stable handset postures; no truth/action scripts',
          'scope':'Tracks relative acc drift and gyro zero rate; absolute acc scale/bias and arbitrary changing carry unobserved.'}
    return A-acurve,G-curve,info


def gated_gyro(time,acceleration,gyro):
    _,corrected,info=calibrate(time,acceleration,gyro)
    use=info['gyro_drift_rms_rad_s']>1.5*info['gyro_mean_se_rad_s']+1e-8 or info['initial_gyro_bias_norm_rad_s']>.006
    info.update(gyro_correction_applied=bool(use),acceleration_correction_applied=False,
                gate_scope='1.5 estimated mean standard errors or initial bias>.006rad/s; chosen on development8, not calibrated test')
    return np.asarray(acceleration),corrected if use else np.asarray(gyro),info


def replay(time,acceleration,gyro,model):
    from .displacement011 import replay as original
    A,G,meta=calibrate(time,acceleration,gyro)
    p,R,info=original(time,A,G,model,heading_regularization=True);info['bias_tracker014b']=meta
    return p,R,info
