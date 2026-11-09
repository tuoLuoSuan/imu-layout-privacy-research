"""Experimental offline recurrent-posture bias calibration, input signals only."""
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import lsmr
from sklearn.cluster import AgglomerativeClustering
from .inertial010 import intervals


def calibrate(time,acceleration,gyro):
    t=np.asarray(time,float)
    if len(t)<3 or np.any(np.diff(t)<=0):raise ValueError('Strictly increasing clock required')
    A,G=np.asarray(acceleration,float),np.asarray(gyro,float)
    if A.shape!=G.shape or A.shape!=(len(t),3):raise ValueError('Phone6 axes must share a clock')
    w=max(3,int(round(.4/np.median(np.diff(t)))))
    ma,mg=[uniform_filter1d(v,w,axis=0,mode='nearest') for v in [A,G]]
    va=np.maximum(uniform_filter1d(A*A,w,axis=0,mode='nearest')-ma*ma,0)
    vg=np.maximum(uniform_filter1d(G*G,w,axis=0,mode='nearest')-mg*mg,0)
    # Variability detects a stable hold even with a nonzero angular-rate bias.
    # A truly constant yaw turn is not identifiable from bias by this gate;
    # the controlled protocol must provide genuinely stationary holds.
    stable=(np.sqrt(va.sum(axis=1))<.085)&(np.sqrt(vg.sum(axis=1))<.009)&(abs(np.linalg.norm(ma,axis=1)-9.81)<.25)
    bins=[];rest=np.zeros(len(t),bool)
    for a,b in intervals(stable):
        if t[b-1]-t[a]<.8:continue
        ids=np.arange(a,b);ids=ids[(t[ids]>=t[a]+(.15 if a else 0.))&(t[ids]<=t[b-1]-(.15 if b<len(t) else 0.))]
        rest[ids]=True
        for part in np.array_split(ids,max(1,int(np.ceil((t[ids[-1]]-t[ids[0]])/2)))):
            if len(part)>=8:bins.append(part)
    if not bins or t[bins[0][0]]-t[0]>4.:raise ValueError('Initial stable handset period required')
    centre=np.array([np.mean(t[i]) for i in bins])
    am=np.array([np.mean(A[i],axis=0) for i in bins]);gm=np.array([np.mean(G[i],axis=0) for i in bins])
    up=am/np.linalg.norm(am,axis=1)[:,None]
    labels=AgglomerativeClustering(n_clusters=None,distance_threshold=.10,linkage='complete').fit_predict(up) if len(up)>1 else np.zeros(1,int)
    n=len(centre);k=int(labels.max())+1;rr=[];cc=[];vv=[];targets=[]
    def equation(terms,target,scale):
        row=len(targets)
        for j,v in terms.items():rr.append(row);cc.append(j);vv.append(v/scale)
        targets.append(np.asarray(target)/scale)
    for i in range(n):equation({i:1.,n+int(labels[i]):1.},am[i],.004)
    for i in range(1,n):equation({i:1.,i-1:-1.},np.zeros(3),.003*np.sqrt(max(.1,centre[i]-centre[i-1])))
    equation({0:1.},np.zeros(3),1e-5)
    mat=coo_matrix((vv,(rr,cc)),shape=(len(targets),n+k)).tocsr();y=np.asarray(targets)
    solution=np.c_[*[lsmr(mat,y[:,a],atol=1e-11,btol=1e-11,maxiter=4000)[0] for a in range(3)]]
    ab=solution[:n];ab-=ab[0]
    acurve=np.c_[*[np.interp(t,centre,ab[:,a]) for a in range(3)]]
    gcurve=np.c_[*[np.interp(t,centre,gm[:,a]) for a in range(3)]]
    info={'rest_samples':int(rest.sum()),'stable_bins':n,'latent_gravity_clusters':k,
          'max_acc_drift_correction_m_s2':float(np.linalg.norm(acurve,axis=1).max()),
          'max_gyro_bias_correction_rad_s':float(np.linalg.norm(gcurve,axis=1).max()),
          'assumptions':'Offline recurrent stable phone orientations, actual zero angular rate in accepted holds; no script/class/pose/scene truth',
          'scope':'Relative accelerometer drift only. Absolute accelerometer bias/scale not identified by one repeated pose.'}
    return A-acurve,G-gcurve,info


def replay(time,acceleration,gyro,model):
    from .displacement011 import replay as original
    A,G,meta=calibrate(time,acceleration,gyro)
    p,R,info=original(time,A,G,model,heading_regularization=True)
    info['bias_tracker014']=meta
    return p,R,info
