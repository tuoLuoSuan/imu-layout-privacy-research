"""Supervised segment displacement on raw synthetic development signals.

Inference consumes phone signals and its saved model only. Geometry, scripts,
ground-truth poses and object identities are not accepted by replay(). The
model is a controlled synthetic-domain inertial regressor, not RoNIN repair.
"""
import argparse,hashlib,json
from pathlib import Path
import joblib
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.ndimage import uniform_filter1d
from sklearn.ensemble import HistGradientBoostingRegressor,ExtraTreesRegressor
from sklearn.multioutput import MultiOutputRegressor
from . import inertial010 as F,multi_instance as M,multi_raw010 as X
from .contact_contract import body_axis
from .sim_handset import generate


def cores(time,mask):
    t=np.asarray(time);out=np.zeros(len(t),bool)
    for a,b in F.intervals(mask):
        ids=np.arange(a,b);mid=(t[a]+t[b-1])/2;half=min(.15,(t[b-1]-t[a])*.2)
        out[ids[abs(t[ids]-mid)<=half]]=True
    return out


def base(t,A,G):return F.replay(t,A,G,stationary_override=cores(t,F.rest_mask(t,A,G)))


def basis(R,a,b):
    lo=a+(b-a)//4;hi=a+3*(b-a)//4;u=body_axis(R[lo:max(lo+1,hi)],'walk').mean(axis=0);u/=max(1e-9,np.linalg.norm(u))
    return np.array([[u[0],-u[1]],[u[1],u[0]]])


def segment_features(t,A,G,R,path,bias,a,b):
    ids=np.arange(a,b+1);T=t[ids]-t[a];H=basis(R,a,b);d=(path[b]-path[a])@H;world=np.einsum('nij,nj->ni',R[ids],A[ids]-bias)-[0,0,9.81];local=np.c_[world[:,:2]@H,world[:,2]];xyz=path[ids]@H;angle=Rotation.from_matrix(R[a].T@R[b]).as_rotvec()
    out={'duration':float(T[-1]),'d_forward':float(d[0]),'d_side':float(d[1]),'path_length':float(np.linalg.norm(np.diff(xyz,axis=0),axis=1).sum())}
    for name,data in [('raw_acc',A[ids]),('gyro',G[ids]),('linear',local)]:
        for label,vec in [('mean',data.mean(axis=0)),('std',data.std(axis=0)),('q10',np.quantile(data,.1,axis=0)),('q90',np.quantile(data,.9,axis=0))]:
            out.update({name+'_'+label+str(j):float(v) for j,v in enumerate(vec)})
    for label,vec in [('start_up',np.median(A[max(0,a-12):a+13],axis=0)),('end_up',np.median(A[max(0,b-12):min(len(t),b+13)],axis=0)),('rotation',angle),('first_linear',local[:max(1,len(ids)//3)].mean(axis=0)),('last_linear',local[-max(1,len(ids)//3):].mean(axis=0))]:out.update({label+str(j):float(v) for j,v in enumerate(vec)})
    for j in range(3):
        out['acc_integral'+str(j)]=float(np.trapezoid(local[:,j],T));out['acc_first_moment'+str(j)]=float(np.trapezoid((T[-1]-T)*local[:,j],T));out['gyro_integral'+str(j)]=float(np.trapezoid(G[ids,j],T))
    smooth=uniform_filter1d(local,max(1,int(.08/np.median(np.diff(t)))),axis=0,mode='nearest')
    for j in range(3):
        for k,value in enumerate(np.interp(np.linspace(0,T[-1],20),T,smooth[:,j])):out['linear_phase'+str(j)+'_'+str(k)]=float(value)
    for name,data in [('vertical',local[:,2]),('horizontal',np.linalg.norm(local[:,:2],axis=1)),('angular',np.linalg.norm(G[ids],axis=1))]:
        spectrum=abs(np.fft.rfft((data-data.mean())*np.hanning(len(data))))**2/max(1,len(data))**2;freq=np.fft.rfftfreq(len(data),np.median(np.diff(t)))
        for k,(lo,hi) in enumerate([(0,.5),(.5,1),(1,1.5),(1.5,2),(2,3),(3,6),(6,12)]):out[name+'_power'+str(k)]=float(spectrum[(freq>=lo)&(freq<hi)].sum())
        out[name+'_spectral_mean']=float((spectrum*freq).sum()/max(1e-12,spectrum.sum()))
    return out


def segments(t,info):
    for s in info['segments']:
        if s['status']!='endpoint_corrected':continue
        a=int(np.searchsorted(t,s['start_s']));b=int(np.searchsorted(t,s['end_s']))
        if b-a>=4:yield a,b


def retime(script,speed):
    out=[];clock=0.
    for s in script:
        duration=s['end']-s['start']
        if s['label']=='walk':duration=max(2.,1.875*np.linalg.norm(np.asarray(s['b'])-s['a'])/speed)
        out.append({**s,'start':clock,'end':clock+duration});clock+=duration
    return out


def train(native,out,rooms=20):
    native,out=map(Path,(native,out));out.mkdir(parents=True,exist_ok=True)
    if (out/'model.joblib').exists():raise FileExistsError('Frozen model must not be overwritten')
    freeze={'room_ids':list(range(rooms)),'speeds':[.45,.65,.85],'labels':'Endpoint displacement in signal-estimated local handset heading frame, simulation truth for training only','inputs':'Raw accelerometer/gyro, signal-derived attitude/stationary segments; no scene/object/action labels or absolute positions','hyperparameters':'HGB400/depth6/l2.1 and ExtraTrees300/leaf2, seed911; compare only on old8 development recordings','scope':'Supervised same-generator-domain inertial regression, not zero-shot transfer'};(out/'training-freeze.json').write_text(json.dumps(freeze,indent=1))
    rows=[];targets=[];groups=[];sources={}
    for i in freeze['room_ids']:
        source=native/f'multi-{i:05d}.json';sc=M.load_native(source);s=json.loads(source.read_text())['agent_placement']['position'];sc['S']=np.array([s['x'],s['z']]);script,_=X.plan(sc);sources[sc['scene']]=hashlib.sha256(source.read_bytes()).hexdigest()
        for speed in freeze['speeds']:
            phone=generate(sc,seed=1310000+i*10+round(speed*10),script_override=retime(script,speed));t,A,G=phone['t'],phone['acc'],phone['gyro'];path,R,info=base(t,A,G);Q=phone['truth']['R'][0]@R[0].T;truth_local=(phone['truth']['pos'][:,:2]-phone['truth']['pos'][0,:2])@Q[:2,:2]
            for a,b in segments(t,info):
                rows.append(segment_features(t,A,G,R,path,np.asarray(info['accelerometer_bias']),a,b));targets.append((truth_local[b]-truth_local[a])@basis(R,a,b));groups.append(i)
        print(json.dumps({'training_room':i,'segments':len(rows)}),flush=True)
    keys=sorted(rows[0]);features=np.array([[r[k] for k in keys] for r in rows]);y=np.array(targets);np.savez_compressed(out/'training-matrix.npz',features=features,targets=y,groups=groups,keys=keys)
    for name,model in [('hgb',MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=400,max_depth=6,l2_regularization=.1,early_stopping=False,random_state=911))),('trees',ExtraTreesRegressor(n_estimators=300,min_samples_leaf=2,random_state=911,n_jobs=1))]:
        model.fit(features,y);artifact={'model':model,'keys':keys,'scope':freeze['scope']};file=out/(name+'.joblib');joblib.dump(artifact,file,compress=3);(out/(name+'.json')).write_text(json.dumps({'model_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'n_training_segments':len(rows),'n_features':len(keys),'sources':sources,'training':freeze},indent=1));print(json.dumps({'trained':name,'segments':len(rows),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}),flush=True)


def load(model):
    model=Path(model);meta=json.loads(model.with_suffix('.json').read_text())
    if hashlib.sha256(model.read_bytes()).hexdigest()!=meta['model_sha256']:raise ValueError('Displacement model identity mismatch')
    return joblib.load(model)


def dominant_headings(displacements):
    d=np.asarray(displacements,float);out=d.copy();length=np.linalg.norm(d,axis=1);ids=np.flatnonzero(length>.12)
    if len(ids)<4:return out
    angle=np.arctan2(d[ids,1],d[ids,0]);weight=np.minimum(length[ids],1.)
    distance=abs(np.angle(np.exp(4j*(angle[:,None]-angle[None,:]))))/4
    neighbourhood=distance<np.radians(5.);winner=int(np.argmax(neighbourhood@weight));members=neighbourhood[winner]
    if weight[members].sum()<.45*weight.sum():return out
    mode=np.angle(np.sum(weight[members]*np.exp(4j*angle[members])))/4
    for i in ids:
        a=np.arctan2(d[i,1],d[i,0]);target=mode+np.round((a-mode)/(np.pi/2))*(np.pi/2)
        if abs(np.angle(np.exp(1j*(a-target))))<=np.radians(3.):out[i]=length[i]*np.array([np.cos(target),np.sin(target)])
    return out


def replay(t,A,G,model,straight=False,heading_regularization=False):
    model=load(model) if isinstance(model,(str,Path)) else model;path,R,info=base(t,A,G);pairs=list(segments(t,info));rows=[segment_features(t,A,G,R,path,np.asarray(info['accelerometer_bias']),a,b) for a,b in pairs]
    predicted=model['model'].predict([[r[k] for k in model['keys']] for r in rows]) if rows else np.empty((0,2))
    if model.get('target')=='distance':predicted=np.c_[np.maximum(np.asarray(predicted).reshape(-1),0.),np.zeros(len(predicted))]
    endpoints=np.array([d@basis(R,a,b).T for (a,b),d in zip(pairs,predicted)])
    if heading_regularization:endpoints=dominant_headings(endpoints)
    out=np.zeros_like(path);cursor=np.zeros(2);last=0
    for (a,b),endpoint in zip(pairs,endpoints):
        out[last:a+1]=cursor;fraction=(t[a:b+1]-t[a])/(t[b]-t[a]);local=path[a:b+1]-path[a];corrected=local+fraction[:,None]*(endpoint-local[-1])
        if straight and np.linalg.norm(endpoint)>1e-6:
            progress=np.maximum.accumulate(np.clip(corrected@endpoint/(endpoint@endpoint),0.,1.));corrected=progress[:,None]*endpoint
        out[a:b+1]=cursor+corrected;cursor=cursor+endpoint;last=b+1
    out[last:]=cursor;info['trajectory_model']='Supervised synthetic-domain stationary-bracket displacement011';info['model_inputs']='phone6axis only; watch remains cabinet source downstream';info['straight_between_stops']=straight;info['controlled_dominant_heading_regularization']=heading_regularization;return out,R,info


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--rooms',type=int,default=20);a=p.parse_args();train(a.native,a.out,a.rooms)
