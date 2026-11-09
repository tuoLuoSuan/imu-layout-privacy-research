"""Offline, stationary-updated inertial baseline for long controlled records.

Inputs are phone signals only. Stable raw-signal periods calibrate constant
gyro/accelerometer biases and correct tilt; no yaw, position, action or layout
truth is accepted. It requires actual zero velocity during those periods and
uses future stationary endpoints, so it is not a causal everyday PDR model.
"""
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from .inertial_replay import integrate_bracketed


def intervals(mask):
    mask=np.asarray(mask,bool)
    edges=np.r_[0,np.flatnonzero(mask[1:]!=mask[:-1])+1,len(mask)]
    return [(int(a),int(b)) for a,b in zip(edges,edges[1:]) if mask[a]]


def rest_mask(time,acceleration,gyro):
    t=np.asarray(time);A=np.asarray(acceleration);G=np.asarray(gyro)
    w=max(3,int(.4/np.median(np.diff(t))))
    mean=uniform_filter1d(A,w,axis=0,mode='nearest')
    var=np.maximum(uniform_filter1d(A*A,w,axis=0,mode='nearest')-mean*mean,0)
    gyr=np.sqrt(uniform_filter1d((G*G).sum(axis=1),w,mode='nearest'))
    stable=(np.sqrt(var.sum(axis=1))<.085)&(gyr<.009)&(abs(np.linalg.norm(mean,axis=1)-9.81)<.15)
    out=np.zeros(len(t),bool)
    # Require sustained stability, then erode the boundaries to avoid smooth
    # acceleration/transition shoulders being treated as exact zero velocity.
    for a,b in intervals(stable):
        if t[b-1]-t[a]>=.8:
            ids=np.arange(a,b);lo=t[a]+(.15 if a else 0.);hi=t[b-1]-(.15 if b<len(t) else 0.)
            out[ids[(t[ids]>=lo)&(t[ids]<=hi)]]=True
    return out


def align_up(v):
    v=np.asarray(v,float);v=v/np.linalg.norm(v);target=np.array([0.,0.,1.])
    cross=np.cross(v,target);s=np.linalg.norm(cross);c=np.dot(v,target)
    if s<1e-10:return np.eye(3) if c>0 else Rotation.from_rotvec([np.pi,0,0]).as_matrix()
    return Rotation.from_rotvec(cross/s*np.arctan2(s,c)).as_matrix()


def close_loop(time,path):
    """Only for an explicitly supplied physical return-to-start protocol."""
    t=np.asarray(time,float);q=np.asarray(path,float)
    return q-(t-t[0])[:,None]/(t[-1]-t[0])*(q[-1]-q[0])


def replay(time,acceleration,gyro):
    t=np.asarray(time,float);A=np.asarray(acceleration,float);G=np.asarray(gyro,float)
    stationary=rest_mask(t,A,G);blocks=intervals(stationary)
    if not blocks or blocks[0][0]>int(4/np.median(np.diff(t))):raise ValueError('Initial stable handset period required')
    bias=G[stationary].mean(axis=0)
    means=np.array([A[a:b].mean(axis=0) for a,b in blocks])
    accel_bias=np.zeros(3);calibrated=False
    # Multi-orientation gravity sphere calibration; reject ill-conditioned
    # data rather than inventing a bias from a single handset orientation.
    if len(means)>=6 and np.linalg.matrix_rank(means-means.mean(axis=0),tol=.02)==3:
        fit=least_squares(lambda x:np.linalg.norm(means-x,axis=1)-9.81,np.zeros(3),bounds=(-.3,.3),loss='soft_l1',f_scale=.02)
        if fit.success:accel_bias=fit.x;calibrated=True
    corrected=A-accel_bias
    R=np.empty((len(t),3,3));a,b=blocks[0];current=align_up(corrected[a:b].mean(axis=0));R[0]=current
    increments=Rotation.from_rotvec(((G[:-1]+G[1:])/2-bias)*np.diff(t)[:,None]).as_matrix()
    updates={int((a+b)//2):corrected[a:b].mean(axis=0) for a,b in blocks};previous_update=0
    for i,step in enumerate(increments,1):
        current=current@step
        R[i]=current
        if i in updates:
            correction=align_up(current@updates[i]);rv=Rotation.from_matrix(correction).as_rotvec()
            ids=np.arange(previous_update+1,i+1);fraction=(t[ids]-t[previous_update])/max(1e-9,t[i]-t[previous_update])
            # Offline endpoint tilt smoothing, with no absolute yaw reference.
            R[ids]=Rotation.from_rotvec(fraction[:,None]*rv).as_matrix()@R[ids]
            current=correction@current;previous_update=i
    world=np.einsum('nij,nj->ni',R,corrected)-[0,0,9.81]
    path=np.zeros((len(t),2));cursor=np.zeros(2);segments=[]
    for a,b in intervals(~stationary):
        if a==0 or b==len(t):
            path[a:b]=cursor;segments.append({'start_s':float(t[a]),'end_s':float(t[b-1]),'status':'unbracketed_not_integrated'})
        else:
            ids=np.arange(a-1,b+1);p=integrate_bracketed(t[ids],world[ids,:2]);path[a:b]=cursor+p[1:-1];cursor=cursor+p[-1]
            segments.append({'start_s':float(t[a-1]),'end_s':float(t[b]),'available_s':float(t[b]),'status':'endpoint_corrected','displacement_m':p[-1].tolist()})
        following=next((v for u,v in blocks if u==b),b);path[b:following]=cursor
    return path,R,{'stationary_mask':stationary,'stationary_fraction':float(stationary.mean()),'stationary_blocks':len(blocks),
      'gyro_bias':bias.tolist(),'accelerometer_bias':accel_bias.tolist(),'accelerometer_bias_calibrated':calibrated,
      'segments':segments,'causal':False,'known_distance_scale':False,'tilt_correction':'stationary gravity; yaw unobserved',
      'bias_calibration':'full-record reliable rest, no target distances'}
