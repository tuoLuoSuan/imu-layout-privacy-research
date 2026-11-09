"""Reproduce the synthetic-domain scalar displacement training (no real data)."""
import argparse,concurrent.futures,hashlib,json
from pathlib import Path
import joblib,numpy as np
from sklearn.ensemble import ExtraTreesRegressor,HistGradientBoostingRegressor
from . import displacement011 as D,multi_instance as M,multi_raw010 as X


def extract(task):
    native,i=task;source=Path(native)/f'multi-{i:05d}.json';sc=M.load_native(source);s=json.loads(source.read_text())['agent_placement']['position'];sc['S']=np.array([s['x'],s['z']]);script,_=X.plan(sc);rows=[];targets=[]
    for speed in [.45,.65,.85]:
        phone=D.generate(sc,seed=1310000+i*10+round(speed*10),script_override=D.retime(script,speed));t,A,G=phone['t'],phone['acc'],phone['gyro'];path,R,info=D.base(t,A,G);Q=phone['truth']['R'][0]@R[0].T;truth=(phone['truth']['pos'][:,:2]-phone['truth']['pos'][0,:2])@Q[:2,:2]
        for a,b in D.segments(t,info):rows.append(D.segment_features(t,A,G,R,path,np.asarray(info['accelerometer_bias']),a,b));targets.append(float(np.linalg.norm(truth[b]-truth[a])))
    return rows,targets,hashlib.sha256(source.read_bytes()).hexdigest()


def train(native,out,workers=4):
    native,out=map(Path,(native,out));out.mkdir(parents=True,exist_ok=True)
    if any(out.glob('*.joblib')):raise FileExistsError('Frozen artifacts are immutable')
    freeze={'ids':list(range(20)),'speeds':[.45,.65,.85],'target':'Endpoint distance, simulation training labels only','inputs':'Raw phone six-axis features and estimated attitude/quiet segments, no scene/object/action/absolute-position inputs','seed':911,'scope':'Supervised same-generator-domain calibration; no natural-activity/zero-shot claim'};(out/'freeze.json').write_text(json.dumps(freeze,indent=1));rows=[];targets=[];sources={}
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for i,(r,y,sha) in enumerate(pool.map(extract,[(str(native),i) for i in range(20)])):rows+=r;targets+=y;sources[str(i)]=sha
    keys=sorted(rows[0]);features=np.array([[r[k] for k in keys] for r in rows]);np.savez_compressed(out/'matrix.npz',features=features,targets=targets,keys=keys)
    for name,model in [('trees-distance',ExtraTreesRegressor(n_estimators=300,min_samples_leaf=2,random_state=911,n_jobs=2)),('hgb-distance',HistGradientBoostingRegressor(max_iter=400,max_depth=6,l2_regularization=.1,early_stopping=False,random_state=911))]:
        model.fit(features,targets);f=out/(name+'.joblib');joblib.dump({'model':model,'keys':keys,'target':'distance','scope':'Controlled synthetic-domain supervision'},f,compress=3);(out/(name+'.json')).write_text(json.dumps({'model_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'n_training_segments':len(rows),'n_features':len(keys),'train_ids':list(range(20)),'sources':sources,'training':freeze},indent=1))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--workers',type=int,default=4);a=p.parse_args();train(a.native,a.out,a.workers)
