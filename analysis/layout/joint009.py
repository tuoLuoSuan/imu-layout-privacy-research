"""Raw phone+watch confirmation with explicit known near-wall handset start.

The earlier centre-start16-room result is retained. Here100 NEW room seeds
use their predeclared engine agent/start location, which is supplied as a prior
and removes many180-degree frame ambiguities. Only four-object rooms are in
this bridge subcohort; the10000-room multi-instance geometry set is unchanged.
"""
import argparse,concurrent.futures,hashlib,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from . import multi_instance as M,action_model as AM
from .contact_contract import CONTRACT,contacts_from_runs,decode
from .sim_handset import generate,s5
from .sim_watch import generate as generate_watch,write as write_watch
from .synthetic_bridge import write_input
from .inertial_replay import rest_attitude,estimate
from .watch_cabinet import load as load_watch,detect as rule_watch,fuse
from .wrist_binary import predict as learned_watch
from .simulation_validation import physical_report
from .sim_motion import U_UP


def mount(wrist,neutral_up,phone=None,calibration=None):
    # One fixed mounting transform, calibrated from r1/r2 standing gravity.
    # It is applied to ALL actions. Gravity does not determine twist about
    # vertical; the shortest-arc/no-extra-twist convention is an assumption.
    source=np.asarray(U_UP['stand']);source/=np.linalg.norm(source);target=np.asarray(neutral_up)
    Q=Rotation.align_vectors(np.array([target]),np.array([source]))[0].as_matrix()
    matrices=np.tile(Q,(len(wrist['t']),1,1))
    if calibration is not None:
        target0=np.asarray(calibration['vectors']['other']);target1=np.asarray(calibration['vectors']['cabinet'])
        up1=np.asarray(U_UP['reach']);up1/=np.linalg.norm(up1)
        Q0=Rotation.align_vectors([target0],[source])[0].as_matrix();Q1=Rotation.align_vectors([target1],[up1])[0].as_matrix();previous=Q0
        for segment in phone['script']:
            mask=(wrist['t']>=segment['start'])&(wrist['t']<segment['end']);current=Q1 if segment['label']=='cabinet' else Q0;rv=Rotation.from_matrix(previous.T@current).as_rotvec()
            matrices[mask]=previous@Rotation.from_rotvec(s5((wrist['t'][mask]-segment['start'])/.8)[:,None]*rv).as_matrix();previous=current
    wrist['acc']=np.einsum('nij,nj->ni',matrices,wrist['acc']);wrist['clean_acc']=np.einsum('nij,nj->ni',matrices,wrist['clean_acc']);wrist['truth']['R']=wrist['truth']['R']@np.swapaxes(matrices,1,2)
    return wrist


def infer(session,priors,wrist_model,budget_s=None,watch_shift=0.,watch_mode='learned'):
    ch=AM.load_phone(session);t,A,_=ch['accelerometer'];tg,G,_=ch['gyroscope'];G=np.c_[*[np.interp(t,tg,G[:,j]) for j in range(3)]]
    budget=float(min(t[-1],tg[-1])) if budget_s is None else float(budget_s);keep=t<=budget;t=t[keep];A=A[keep];G=G[keep]
    if len(t)<400:return {'status':'insufficient','boxes':{},'runs':[]}
    R=rest_attitude(t,A,G);path,info=estimate(t,A,G,R);phone=AM.predict_timeline(AM.load_model(),t,A,t,G,budget_s=budget)
    wrist=load_watch(session,1700000000000000000)
    if watch_mode=='phone':runs=phone['runs'];watch={'runs':[]}
    else:
        if wrist is None:watch={'runs':[],'status':'missing'}
        else:
            wt,wa=wrist;wt=wt+watch_shift
            watch=learned_watch(wt,wa,wrist_model,budget_s=budget) if watch_mode=='learned' else rule_watch(wt,wa,budget_s=budget,phone=(t,A,G))
        runs=fuse(phone,watch)['runs']
    contacts=contacts_from_runs(t,path,R,runs);walk=np.zeros(len(t),bool)
    for label,a,b in runs:
        if label=='walk':walk|=(t>=a)&(t<=b)
    prediction=decode(priors['room'],priors['start'],path,contacts,priors['sizes'],walk)
    return {**prediction,'runs':runs,'watch_runs':watch['runs'],'cabinet_source':'phone' if watch_mode=='phone' else 'watch_accelerometer',
       'phone_cabinet_used':watch_mode=='phone','trajectory_frontend':'initial-rest calibrated gyro + offline bracketed ZUPT','budget_s':budget,'zero_velocity':info}


def episode(task):
    source,target,wrist_model=map(Path,task[:3]);calibration=json.loads(Path(task[3]).read_text()) if len(task)>3 and task[3] else None;target.mkdir(parents=True,exist_ok=True);f=target/'results.json'
    if f.exists():return json.loads(f.read_text(encoding='utf-8'))
    scene=M.load_native(source);native=json.loads(source.read_text(encoding='utf-8'));start=native['agent_placement']['position'];scene['S']=np.array([start['x'],start['z']])
    if sum(scene['counts'].values())!=4:raise ValueError('Bridge supports exactly one object per class')
    modelmeta=json.loads((wrist_model/'metadata.json').read_text());seed=990000+int(scene['scene'].split('-')[-1]);gen=generate(scene,seed)
    wrist=mount(generate_watch(gen,seed+300),modelmeta['neutral_up_from_development'],gen,calibration);session=target/'input';write_input(session,gen);write_watch(session,wrist)
    truth={k.split('#')[0]:b for k,b in scene['gt'].items()};priors={'room':[scene['W'],scene['L']],'start':scene['S'].tolist(),'sizes':{k:sorted(b[2:]-b[:2]) for k,b in truth.items()},'start_source':'native planned agent position, provided as known near-wall prior; not centre inferred from furniture'}
    (session/'known-priors.json').write_text(json.dumps(priors),encoding='utf-8')
    np.savez_compressed(target/'evaluation-truth.npz',time=gen['t'],position=gen['truth']['pos'],rotation=gen['truth']['R'],labels=gen['truth']['label'],watch_time=wrist['t'],watch_position=wrist['truth']['pos'],watch_rotation=wrist['truth']['R'])
    rows=[]
    for name,mode,shift in [('phone_only','phone',0.),('joint_rule_watch','rule',0.),('joint_learned_watch','learned',0.),('wrong_watch_clock_10s','learned',10.)]:
        pred=infer(session,priors,wrist_model,watch_mode=mode,watch_shift=shift);rows.append({'arm':name,'prediction':pred,'score':M.score_instances(pred['boxes'],truth)})
    runs=[[label,a,b] for a,b,label in gen['truth']['segments']];contacts=contacts_from_runs(gen['t'],gen['truth']['pos'][:,:2],gen['truth']['R'],runs)
    oracle=decode(priors['room'],priors['start'],gen['truth']['pos'][:,:2],contacts,priors['sizes'],np.array(gen['truth']['label'])=='walk');rows.append({'arm':'truth_pose_truth_actions','oracle_assisted':True,'prediction':oracle,'score':M.score_instances(oracle['boxes'],truth)})
    result={'scene':scene['scene'],'seed':seed,'native_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'phone_physics':physical_report(gen),'watch_sample_rate_hz':wrist['fs'],'watch_axes':3,'watch_gyro_used':False,'watch_shared_clock':'ideal simulation clock','priors':priors,'duration_s':float(gen['t'][-1]),'rows':rows}
    f.write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8');return result


def run(native,out,wrist_model,workers=3,start_index=5000,calibration=None):
    native,out,wrist_model=map(Path,(native,out,wrist_model));out.mkdir(parents=True,exist_ok=True);ids=[f'multi-{i:05d}' for i in range(start_index,start_index+800,8)]
    freeze={'ids':ids,'n_rooms':100,'selection':'Fixed first100 four-object rooms in new5000 seeds, no outcome exclusions','contract':CONTRACT,'start_prior':'Known planned near-wall device start; generic10000 benchmark still uses centre-nearest start','source_sha256':{name:hashlib.sha256(Path(__file__).with_name(name+'.py').read_bytes()).hexdigest() for name in ['joint009','contact_contract','sim_handset','sim_watch','watch_cabinet','inertial_replay','wrist_binary']},'wrist_model_sha256':json.loads((wrist_model/'metadata.json').read_text())['model_sha256'],'phone_and_ronin_weights_unchanged':True,'calibration':'same-episode initial3s rest; no distance fit for primary ZUPT arm','primary_arm':'joint_learned_watch','raw_input':'phone6axis120Hz, watch3axis16.7Hz; ideal clock','scope':'100 controlled same-family room episodes, not10000 end-to-end trials or real-world validation'}
    freeze['wrist_pose_calibration_sha256']=hashlib.sha256(Path(calibration).read_bytes()).hexdigest() if calibration else None
    freeze['pose_protocol']='Standing and raised/reaching wrist orientation means from r1/r2; same classifier, no holdout fitting' if calibration else 'Fixed neutral mounting only'
    (out/'freeze.json').write_text(json.dumps(freeze,indent=1),encoding='utf-8');rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(episode,[(str(native/(name+'.json')),str(out/name),str(wrist_model),str(calibration) if calibration else None) for name in ids]):
            rows.append(r);print(json.dumps({'scene':r['scene'],'done':len(rows),'total':100,'hits':{a['arm']:a['score']['tp'] for a in r['rows']}}),flush=True)
    result={'n_rooms':len(rows),'summary':{arm:{'all_hit':sum(a['score']['all_instances_hit'] for r in rows for a in r['rows'] if a['arm']==arm),'f1':float(np.mean([a['score']['f1'] for r in rows for a in r['rows'] if a['arm']==arm]))} for arm in [a['arm'] for a in rows[0]['rows']]},'rows':rows}
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8');print(json.dumps(result['summary']),flush=True);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--wrist-model',required=True);p.add_argument('--workers',type=int,default=3);p.add_argument('--start-index',type=int,default=5000);p.add_argument('--calibration');a=p.parse_args();run(a.native,a.out,a.wrist_model,a.workers,a.start_index,a.calibration)
