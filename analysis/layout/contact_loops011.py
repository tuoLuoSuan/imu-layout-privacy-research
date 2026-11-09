"""Contact-aided trajectory smoothing with unknown landmark positions.

Only predicted seat/cabinet visits, estimated handset pose and declared counts
enter. Seats give latent point loops; cabinet faces give latent normal-plane
loops, allowing different tangential reach locations. This is an offline
regularizer with conditional associations, not a calibrated posterior.
"""
import numpy as np
from sklearn.cluster import KMeans
from .contact_contract import body_axis


def optimize(time,path,observations,counts,cabinet=True):
    t=np.asarray(time,float);q=np.asarray(path,float);obs=sorted([dict(e) for e in observations if e['class']=='chair' or cabinet and e['class']=='cab'],key=lambda e:e['time']);groups={}
    for cls in ['chair','cab']:
        ids=[i for i,e in enumerate(obs) if e['class']==cls];k=min(int(counts.get(cls,0)),len(ids))
        if not k:continue
        x=np.array([obs[i]['point'] for i in ids]);labels=np.zeros(len(ids),int) if k==1 else KMeans(n_clusters=k,n_init=10,random_state=911).fit_predict(x)
        for i,j in zip(ids,labels):groups.setdefault((cls,int(j)),[]).append(i)
    groups={g:ids for g,ids in groups.items() if len(ids)>=2}
    if not groups:return q.copy(),{'used_loops':0,'given_furniture_position':False}
    knots=np.unique(np.r_[t[0],[e['time'] for e in obs],t[-1]]);index={float(a):i for i,a in enumerate(knots)};n=2*len(knots);landmarks={}
    for group in groups:landmarks[group]=n;n+=2 if group[0]=='chair' else 1
    rows=[];targets=[]
    def add(terms,target,weight):
        row=np.zeros(n)
        for k,v in terms.items():row[k]=v*weight
        rows.append(row);targets.append(target*weight)
    for axis in [0,1]:add({axis:1.},0.,1e5)
    for i in range(1,len(knots)):
        # Correlated segment drift need not grow as independent sqrt(time)
        # noise. This is a declared regularization scale, not a covariance fit.
        sigma=.02+.005*max(.1,knots[i]-knots[i-1])
        for axis in [0,1]:add({2*i+axis:1.,2*(i-1)+axis:-1.},0.,1/sigma)
    for group,ids in groups.items():
        start=landmarks[group]
        if group[0]=='cab':
            normal=np.mean([obs[i]['normal'] for i in ids],axis=0);normal/=max(1e-9,np.linalg.norm(normal))
        for i in ids:
            e=obs[i];j=index[float(e['time'])];point=np.asarray(e['point'])
            if group[0]=='chair':
                for axis in [0,1]:add({2*j+axis:1.,start+axis:1.},point[axis],1/.04)
            else:add({2*j:normal[0],2*j+1:normal[1],start:1.},float(normal@point),1/.08)
    solution=np.linalg.lstsq(np.asarray(rows),targets,rcond=None)[0];delta=solution[:2*len(knots)].reshape(-1,2);delta=delta-delta[0];correction=np.c_[*[np.interp(t,knots,delta[:,a]) for a in [0,1]]]
    return q-correction,{'used_loops':sum(len(ids)-1 for ids in groups.values()),'given_furniture_position':False,'cabinet_plane_loops':cabinet,'max_correction_m':float(np.linalg.norm(correction,axis=1).max()),'knots_s':knots.tolist(),'corrections_m':delta.tolist(),'associations':[{'category':g[0],'latent_cluster':g[1],'event_indices':ids} for g,ids in groups.items()],'scope':'Unknown point/plane landmarks with regularized time-varying drift; class/association/posture assumptions conditional'}


def refine(t,path,R,runs,priors,cabinet=True):
    t=np.asarray(t);obs=[]
    for label,a,b in runs:
        if label not in ['seated','cabinet']:continue
        if b-a<(4. if label=='seated' else 2.):continue
        ids=np.flatnonzero((t>=a+.25*(b-a))&(t<=a+.75*(b-a)))
        if len(ids)<3:continue
        event={'class':'chair' if label=='seated' else 'cab','time':float(np.median(t[ids])),'point':np.median(path[ids],axis=0).tolist()}
        if label=='cabinet':event['normal']=body_axis(R[ids],'cabinet').mean(axis=0).tolist()
        obs.append(event)
    counts={c:sum(e['category']==c for e in priors['inventory']) for c in ['chair','cab']}
    return optimize(t,path,obs,counts,cabinet)
