"""Offline strapdown baseline with signal-detected stationary endpoints.

Requires actual zero velocity during stationary handset periods. Endpoint
correction uses the next stationary segment and is therefore not causal until
that endpoint is observed. It accepts signals and attitudes, never positions,
actions, scene truth or a target path scale.
"""
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.spatial.transform import Rotation


def rest_attitude(time,acceleration,gyro,rest_s=3.):
    t=np.asarray(time);A=np.asarray(acceleration);G=np.asarray(gyro);initial=t<t[0]+rest_s
    up=A[initial].mean(axis=0);up/=np.linalg.norm(up);x,y,z=up
    q=np.array([1+z,y,-x,0.]) if z>-.999999 else np.array([0.,1.,0.,0.]);q/=np.linalg.norm(q)
    rotation=Rotation.from_quat(np.r_[q[1:],q[0]]).as_matrix();bias=G[initial].mean(axis=0);out=np.empty((len(t),3,3));out[0]=rotation
    increments=Rotation.from_rotvec(((G[:-1]+G[1:])/2-bias)*np.diff(t)[:,None]).as_matrix()
    for i,step in enumerate(increments,1):rotation=rotation@step;out[i]=rotation
    return out


def integrate_bracketed(time,acceleration):
    time=np.asarray(time);a=np.asarray(acceleration);dt=np.diff(time)
    velocity=np.vstack([np.zeros(a.shape[1]),np.cumsum((a[:-1]+a[1:])*.5*dt[:,None],axis=0)])
    velocity-=(time-time[0])[:,None]/(time[-1]-time[0])*velocity[-1]
    return np.vstack([np.zeros(a.shape[1]),np.cumsum((velocity[:-1]+velocity[1:])*.5*dt[:,None],axis=0)])


def estimate(time,acceleration,gyro,attitude):
    t=np.asarray(time);A=np.asarray(acceleration);G=np.asarray(gyro);R=np.asarray(attitude);rate=1/np.median(np.diff(t));window=max(3,int(.40*rate))
    mean=uniform_filter1d(A,window,axis=0,mode='nearest');var=uniform_filter1d(A*A,window,axis=0,mode='nearest')-mean*mean
    variability=np.sqrt(np.maximum(var,0).sum(axis=1));gyro_rms=np.sqrt(uniform_filter1d((G*G).sum(axis=1),window,mode='nearest'))
    world=np.einsum('nij,nj->ni',R,A)-[0.,0.,9.81]
    # Low variance alone mistakes smooth deceleration for rest. Attitude is
    # obtained from the initial-rest gyro branch, not moving-accel tilt.
    stationary=(variability<.18)&(gyro_rms<.055)&(np.linalg.norm(uniform_filter1d(world,window,axis=0,mode='nearest'),axis=1)<.12)
    changes=np.r_[0,np.flatnonzero(stationary[1:]!=stationary[:-1])+1,len(t)]
    for a,b in zip(changes,changes[1:]):
        if stationary[a] and t[b-1]-t[a]<.30:stationary[a:b]=False
    moving=~stationary
    changes=np.r_[0,np.flatnonzero(moving[1:]!=moving[:-1])+1,len(t)];path=np.zeros((len(t),2));segments=[];cursor=np.zeros(2)
    for a,b in zip(changes,changes[1:]):
        if not moving[a]:path[a:b]=cursor;continue
        if a==0 or b==len(t):path[a:b]=cursor;segments.append({'start_s':float(t[a]),'end_s':float(t[b-1]),'status':'unbracketed_not_integrated'});continue
        ids=np.arange(a-1,b+1)
        p=integrate_bracketed(t[ids],world[ids,:2]);path[a:b]=cursor+p[1:-1];cursor=cursor+p[-1]
        segments.append({'start_s':float(t[a-1]),'end_s':float(t[b]),'available_s':float(t[b]),'status':'endpoint_corrected','displacement_m':p[-1].tolist()})
    return path,{'stationary_fraction':float(stationary.mean()),'segments':segments,'causal':False,'known_distance_scale':False}
