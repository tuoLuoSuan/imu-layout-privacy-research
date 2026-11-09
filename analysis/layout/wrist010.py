"""One wrist classifier trained on existing real development and simulation.

The phone model remains frozen. Real r3/r4 and new synthetic confirmation
rooms are never fitted. Domain/class weights prevent many synthetic windows
from overwhelming the few real cabinet examples. This is supervised domain
augmentation, not a repaired zero-shot transfer claim.
"""
import argparse,hashlib,json
from pathlib import Path
import joblib,numpy as np
from scipy.spatial.transform import Rotation
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix,f1_score
from . import multi_instance as M
from .wrist_binary import features,real_round,predict
from .sim_handset import generate
from .sim_watch import generate as generate_watch,write as write_watch
from .joint009 import mount
from .synthetic_bridge import write_input


class DomainEnsemble:
    """Union of learned wrist experts; returned scores are uncalibrated.

No source-domain flag is accepted at prediction time. The maximum preserves
an event supported by either training domain, at a potential false-positive
cost that must be evaluated separately.
    """
    classes_=np.array([0,1])
    def __init__(self,real,synthetic):self.real=real;self.synthetic=synthetic
    def predict_proba(self,X):
        p=np.maximum(self.real.predict_proba(X)[:,1],self.synthetic.predict_proba(X)[:,1])
        return np.c_[1-p,p]
    def predict(self,X):return (self.predict_proba(X)[:,1]>.5).astype(int)


def balanced_weights(domains,labels):
    domains=np.asarray(domains);labels=np.asarray(labels);w=np.zeros(len(labels),float);names=sorted(set(domains))
    if domains.shape!=labels.shape or not len(names):raise ValueError('Matched training domains/labels required')
    for name in names:
        for label in [0,1]:
            ids=(domains==name)&(labels==label)
            if not ids.any():raise ValueError('Every training domain needs both classes')
            w[ids]=1/(len(names)*2*ids.sum())
    return w


def window_label(time,labels,start,end):
    time=np.asarray(time);labels=np.asarray(labels);mask=(time>=start)&(time<end)
    if mask.sum()<10:return None
    fraction=float(np.mean(labels[mask]=='cabinet'))
    return 1 if fraction>=.75 else 0 if fraction==0 else None


def train(native,real_root,out,old_metadata):
    native,real_root,out,old_metadata=map(Path,(native,real_root,out,old_metadata));out.mkdir(parents=True,exist_ok=True)
    if (out/'model.joblib').exists():raise FileExistsError('Training artifact is immutable')
    old=json.loads(old_metadata.read_text());ids=[8*i for i in range(20)];data=[];sources={};excluded=0
    freeze={'real_fit':['r1','r2'],'wrist_eval_only':['r3','r4'],'synthetic_fit_ids':ids,'domain_balance':'Equal real/sim mass, equal positive/negative mass within each domain','hyperparameters':'RF200,depth5,leaf2,seed909; no search','features':'Same37 wrist-only acceleration features as009; no time, source-domain, phone state, object ID or true pose feature','augmentation':'One fixed-seed whole-record mounting rotation up to15deg plus0.02m/s2 noise on synthetic training only'}
    (out/'training-freeze.json').write_text(json.dumps(freeze,indent=1),encoding='utf-8')
    for tag in ['r1','r2']:
        rows,_,_,meta=real_round(real_root,tag);sources[tag]=meta
        data += [{'domain':'real','label':r['label'],'features':r['features'],'session':tag} for r in rows]
    for index in ids:
        source=native/f'multi-{index:05d}.json';sc=M.load_native(source);d=json.loads(source.read_text());s=d['agent_placement']['position'];sc['S']=np.array([s['x'],s['z']]);seed=1010000+index
        phone=generate(sc,seed);watch=mount(generate_watch(phone,seed+300),old['neutral_up_from_development']);rng=np.random.default_rng(seed+400);Q=Rotation.from_rotvec(rng.uniform(-.15,.15,3)).as_matrix();watch['acc']=watch['acc']@Q.T+rng.normal(0,.02,watch['acc'].shape)
        folder=out/'training-inputs'/sc['scene'];folder.mkdir(parents=True,exist_ok=True);write_input(folder,phone);write_watch(folder,watch);sources[sc['scene']]={'native_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'seed':seed}
        labels=np.asarray(phone['truth']['label'])[np.minimum(np.rint(watch['t']*phone['fs']).astype(int),len(phone['t'])-1)]
        for end in np.arange(3.,watch['t'][-1]+1e-8,.5):
            label=window_label(watch['t'],labels,end-3,end)
            if label is None:excluded+=1;continue
            data.append({'domain':'sim','label':label,'features':features(watch['t'],watch['acc'],end-3),'session':sc['scene']})
    keys=sorted(data[0]['features']);X=np.array([[r['features'][k] for k in keys] for r in data]);y=np.array([r['label'] for r in data]);domains=np.array([r['domain'] for r in data]);weights=balanced_weights(domains,y)
    if not np.isfinite(X).all():raise ValueError('No silent dropping of nonfinite training windows')
    classifier=RandomForestClassifier(n_estimators=200,max_depth=5,min_samples_leaf=2,random_state=909,n_jobs=1);classifier.fit(X,y,sample_weight=weights)
    joblib.dump({'classifier':classifier,'keys':keys},out/'model.joblib',compress=3)
    metadata={**freeze,'scope':'Mixed-domain wrist RF trained on real r1/r2 and20 synthetic development rooms; no zero-shot transfer claim','neutral_up_from_development':old['neutral_up_from_development'],'model_sha256':hashlib.sha256((out/'model.joblib').read_bytes()).hexdigest(),'n_training_windows':len(data),'domain_windows':{name:int(np.sum(domains==name)) for name in ['real','sim']},'excluded_ambiguous_synthetic_windows':excluded,'sources':sources,'class_domain_total_mass':{name:{str(label):float(weights[(domains==name)&(y==label)].sum()) for label in [0,1]} for name in ['real','sim']}}
    # Freeze the fitted bytes before accessing either wrist evaluation session.
    (out/'metadata.json').write_text(json.dumps(metadata,indent=1),encoding='utf-8')
    scores={}
    for tag in ['r3','r4']:
        rows,_,_,meta=real_round(real_root,tag);truth=[r['label'] for r in rows];pred=classifier.predict([[r['features'][k] for k in keys] for r in rows]);scores[tag]={'n_windows':len(rows),'cabinet_f1':float(f1_score(truth,pred,zero_division=0)),'confusion_tn_fp_fn_tp':confusion_matrix(truth,pred,labels=[0,1]).ravel().tolist(),'weak_labels_and_software_clock':True}
    (out/'wrist-evaluation.json').write_text(json.dumps(scores,indent=1),encoding='utf-8');print(json.dumps({'training_windows':len(data),'model_sha256':metadata['model_sha256'],'wrist_eval':scores}),flush=True);return metadata


def train_ensemble(native,real_root,source_training,real_model,out):
    from .watch_cabinet import load
    native,real_root,source_training,real_model,out=map(Path,(native,real_root,source_training,real_model,out));out.mkdir(parents=True,exist_ok=True)
    if (out/'model.joblib').exists():raise FileExistsError('Immutable ensemble')
    old=json.loads((real_model/'metadata.json').read_text());assert old['trained_sessions']==['r1','r2']
    if hashlib.sha256((real_model/'model.joblib').read_bytes()).hexdigest()!=old['model_sha256']:raise ValueError('Real expert identity mismatch')
    real=joblib.load(real_model/'model.joblib');keys=real['keys'];data=[]
    freeze={'architecture':'Two learned wrist RF experts; maximum positive score, fixed0.5 decision; no domain input flag','real_training':['r1','r2'],'synthetic_training_ids':[8*i for i in range(20)],'synthetic_hyperparameters':'RF200,depth5,leaf2,balanced,seed909','real_expert_sha256':old['model_sha256'],'weak_real_labels':True,'scope':'Supervised two-domain coverage, not zero-shot transfer or calibrated probabilities'}
    (out/'training-freeze.json').write_text(json.dumps(freeze,indent=1),encoding='utf-8')
    for index in freeze['synthetic_training_ids']:
        name=f'multi-{index:05d}';source=native/(name+'.json');sc=M.load_native(source);d=json.loads(source.read_text());s=d['agent_placement']['position'];sc['S']=np.array([s['x'],s['z']]);phone=generate(sc,1010000+index);t,A=load(source_training/'training-inputs'/name,1700000000000000000)
        labels=np.asarray(phone['truth']['label'])[np.minimum(np.rint(t*phone['fs']).astype(int),len(phone['t'])-1)]
        for end in np.arange(3.,t[-1]+1e-8,.5):
            label=window_label(t,labels,end-3,end)
            if label is not None:data.append((label,features(t,A,end-3)))
    synthetic=RandomForestClassifier(n_estimators=200,max_depth=5,min_samples_leaf=2,class_weight='balanced',random_state=909,n_jobs=1)
    synthetic.fit([[f[k] for k in keys] for y,f in data],[y for y,f in data])
    # A model created with `python -m` must not pickle its class as __main__.
    from importlib import import_module
    model=import_module('analysis.layout.wrist010').DomainEnsemble(real['classifier'],synthetic)
    joblib.dump({'classifier':model,'keys':keys},out/'model.joblib',compress=3)
    metadata={**freeze,'neutral_up_from_development':old['neutral_up_from_development'],'model_sha256':hashlib.sha256((out/'model.joblib').read_bytes()).hexdigest(),'n_synthetic_windows':len(data),'features':'Same37 acceleration-only features; no timestamps or object/source IDs'}
    (out/'metadata.json').write_text(json.dumps(metadata,indent=1),encoding='utf-8');scores={}
    for tag in ['r3','r4']:
        rows,_,_,_=real_round(real_root,tag);truth=[r['label'] for r in rows];pred=model.predict([[r['features'][k] for k in keys] for r in rows]);scores[tag]={'n_windows':len(rows),'cabinet_f1':float(f1_score(truth,pred,zero_division=0)),'confusion_tn_fp_fn_tp':confusion_matrix(truth,pred,labels=[0,1]).ravel().tolist(),'weak_labels_and_software_clock':True}
    (out/'wrist-evaluation.json').write_text(json.dumps(scores,indent=1),encoding='utf-8');print(json.dumps({'ensemble':metadata['model_sha256'],'wrist_eval':scores}),flush=True);return metadata


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--real-root',required=True);p.add_argument('--out',required=True);p.add_argument('--old-metadata');p.add_argument('--source-training');p.add_argument('--real-model');a=p.parse_args()
    if a.source_training:train_ensemble(a.native,a.real_root,a.source_training,a.real_model,a.out)
    else:train(a.native,a.real_root,a.out,a.old_metadata)
