"""Small cabinet/non-cabinet wrist model on existing real development rounds.

Only this NEW wrist classifier is fitted; the phone RF and RoNIN stay frozen.
Training is r1/r2, wrist-only evaluation r3/r4. Cue/software-clock labels are
explicitly weak, and overlapping windows never constitute independent trials.
"""
import argparse,hashlib,json
from pathlib import Path
import joblib,numpy as np
from .action_features import event_features,temporal
from . import action_model as AM
from .watch_channel import read_watch,clock_interval,zero_wall_ms


def features(t,A,start):
    mask=(t>=start)&(t<start+3);r=event_features(t,A,start,start+3,normalize=True)
    r.update(temporal({'watch_acc':(t[mask]-start,A[mask])},'watch'));return r


def real_round(root,tag):
    p=Path(root)/('2026-11-06-round-'+tag);t,A,obs=read_watch(p/'watch.jsonl');lo,hi=clock_interval(obs)
    if hi<=lo:raise ValueError('No compatible software clock offset')
    time=(t+(lo+hi)/2000.-zero_wall_ms(str(p)))/1000;offset=json.loads((p/'cue-sync.json').read_text())['t0'];segments=AM.A_SEG if tag in ['r1','r2'] else AM.B_SEG
    rows=[]
    for begin,end,label in segments:
        for start in np.arange(offset+begin,offset+end-3+1e-8,.5):
            mask=(time>=start)&(time<start+3)
            if mask.sum()<20 or start+3-time[mask][-1]>.2 or time[mask][0]-start>.2:continue
            rows.append({'session':tag,'start_s':float(start),'label':int(label=='cabinet'),'features':features(time,A,start)})
    return rows,time,A,{'software_clock_width_ms':(hi-lo)/1000,'physical_clock_accepted':False,'watch_sha256':hashlib.sha256((p/'watch.jsonl').read_bytes()).hexdigest()}


def train(root,out):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import confusion_matrix,f1_score
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'model.joblib').exists():raise FileExistsError('Existing wrist model is immutable')
    data=[];provenance={};rest=[]
    for tag in ['r1','r2','r3','r4']:
        rows,t,A,meta=real_round(root,tag);data+=rows;provenance[tag]=meta
        if tag in ['r1','r2']:
            p=Path(root)/('2026-11-06-round-'+tag);off=json.loads((p/'cue-sync.json').read_text())['t0'];r=A[(t>=off+1)&(t<off+4)].mean(axis=0);rest.append(r/np.linalg.norm(r))
    keys=sorted(data[0]['features']);training=[r for r in data if r['session'] in ['r1','r2']];testing=[r for r in data if r['session'] in ['r3','r4']]
    clf=RandomForestClassifier(n_estimators=200,max_depth=5,min_samples_leaf=2,class_weight='balanced',random_state=909,n_jobs=1)
    clf.fit([[r['features'][k] for k in keys] for r in training],[r['label'] for r in training])
    model={'classifier':clf,'keys':keys};joblib.dump(model,out/'model.joblib',compress=3);scores={}
    for tag in ['r3','r4']:
        rows=[r for r in testing if r['session']==tag];truth=[r['label'] for r in rows];pred=clf.predict([[r['features'][k] for k in keys] for r in rows]);scores[tag]={'n_windows':len(rows),'confusion_matrix_tn_fp_fn_tp':confusion_matrix(truth,pred,labels=[0,1]).ravel().tolist(),'cabinet_f1':float(f1_score(truth,pred,zero_division=0))}
    up=np.mean(rest,axis=0);up/=np.linalg.norm(up)
    meta={'trained_sessions':['r1','r2'],'wrist_evaluation_sessions':['r3','r4'],'n_train_windows':len(training),'n_test_windows':len(testing),'provenance':provenance,'scores':scores,'neutral_up_from_development':up.tolist(),'model_sha256':hashlib.sha256((out/'model.joblib').read_bytes()).hexdigest(),'hyperparameters':'RF200,depth5,leaf2,balanced,seed909; one fixed fit, no parameter search','weak_labels':'cue script + software clock, no independently verified action labels','inference_features':'37 wrist acceleration features, no time/session/object/phone features','phone_and_ronin_unchanged':True}
    (out/'metadata.json').write_text(json.dumps(meta,indent=1),encoding='utf-8');print(json.dumps(meta),flush=True);return meta


def predict(t,A,model_dir,budget_s=None):
    model_dir=Path(model_dir);meta=json.loads((model_dir/'metadata.json').read_text());raw=model_dir/'model.joblib'
    if hashlib.sha256(raw.read_bytes()).hexdigest()!=meta['model_sha256']:raise ValueError('Wrist model hash mismatch')
    model=joblib.load(raw);t=np.asarray(t);A=np.asarray(A);budget=float(t[-1]) if budget_s is None else budget_s;matrix=[];windows=[]
    for end in np.arange(3.,budget+1e-9,.5):
        mask=(t>=end-3)&(t<end)
        if mask.sum()<15 or end-t[mask][-1]>.2 or t[mask][0]-(end-3)>.2:continue
        r=features(t,A,end-3);matrix.append([r[k] for k in model['keys']]);windows.append({'start_s':float(end-3),'end_s':float(end),'center_s':float(end-1.5),'available_s':float(end)})
    if matrix:
        labels=model['classifier'].predict(matrix);probs=model['classifier'].predict_proba(matrix)
        for w,label,pr in zip(windows,labels,probs):w.update(cabinet=bool(label),uncalibrated_probability=float(pr[1]))
    groups=[]
    for w in windows:
        if not w.get('cabinet'):continue
        if groups and w['center_s']-groups[-1][-1]['center_s']<=.51:groups[-1].append(w)
        else:groups.append([w])
    runs=[['cabinet',g[0]['start_s'],g[-1]['end_s']] for g in groups if len(g)>=2]
    return {'runs':runs,'windows':windows,'model_sha256':meta['model_sha256'],'scope':meta.get('scope','New wrist-only cabinet RF; learned on existing real r1/r2; no phone cabinet label')}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);a=p.parse_args();train(a.root,a.out)
