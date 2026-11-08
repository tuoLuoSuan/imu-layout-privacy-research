"""Actual synthetic six-axis CSV -> frozen RoNIN -> frozen actions -> layout.

Generator truth is stored outside the input directory and only used after
inference. Physical consistency, learned-model compatibility and layout hits
are separate endpoints. This is a phone-only bridge ablation, not a claim of
validated joint phone/watch synthesis or5000 raw-IMU reconstruction trials.
"""
import argparse,csv,hashlib,json,math
from pathlib import Path
import numpy as np
from . import sim_motion as SM,action_model as AM,paths,multi_instance as M
from .simulation_validation import pose_derivatives,physical_report
from .exp_sim_check import rigid
from analysis.phone_ronin.adapter import prepare_features,make_windows,predict,integrate_centers

FIELDS=['sequence','sensor_timestamp_ns','received_elapsed_realtime_ns','writer_dequeued_elapsed_realtime_ns','x','y','z','accuracy']
PRESETS=[('original',7),('original',19),('original',31),('dwell_0.45',7),('dwell_0.45',19),('dwell_0.45',31),('dwell_0.75',7),('dwell_0.75',19),('dwell_0.75',31)]


def script_for(profile):
    if profile=='original':return SM.SCRIPT
    speed=float(profile.split('_')[1]);time=0.;script=[];point=SM.START.copy()
    def add(duration,label,target,pose):
        nonlocal time,point
        script.append((time,time+duration,label,np.asarray(target,float),'lie' if pose=='lie' else pose));time+=duration;point=np.asarray(target,float)
    def walk(target):add(max(2.5,float(np.linalg.norm(np.asarray(target)-point))/speed),'walk',target,'walk')
    add(5.,'other',point,'stand');walk((1.33,1.14));add(8.,'seated',point,'sit');add(2.,'other',point,'stand')
    walk((1.25,.54));add(8.,'cabinet',point,'reach');walk((1.95,1.7));walk((1.95,2.75))
    add(8.,'lying',point,'lie');add(2.,'other',point,'stand');walk(SM.START);add(5.,'other',point,'stand')
    return script


def generate(profile,seed,fs=120.):
    motion=SM.Motion(script_for(profile));duration=motion.t_end;t=np.arange(int(round(duration*fs)))/fs
    def pose_at(time):
        pos,R,_=SM.device_pose(time,motion.state(time))
        segment=motion._seg(time)
        if profile!='original' and segment[2]=='cabinet':
            u=(time-segment[0])/(segment[1]-segment[0]);gate=SM.smooth(u/.15)*SM.smooth((1-u)/.15)
            phase=2*math.pi*2*u
            pos=pos+gate*np.array([.035*math.sin(phase),.035*(1-math.cos(phase)),.02*math.sin(phase)])
            R=R@SM.rot(.10*gate*math.sin(phase),.10*gate*math.sin(phase+.4),.06*gate*math.sin(phase+.8))
        return pos,R
    acc=[];gyro=[];positions=[];rotations=[];labels=[];body=[]
    for time in t:
        pos,R=pose_at(float(time));_,a,w=pose_derivatives(pose_at,float(time),duration)
        acc.append(R.T@(a-np.array([0.,0.,-SM.G])));gyro.append(w);positions.append(pos);rotations.append(R);labels.append(motion._seg(float(time))[2]);body.append(motion.state(float(time))[0])
    clean_acc=np.array(acc);clean_gyro=np.array(gyro);rng=np.random.default_rng(seed)
    return {'t':t,'fs':fs,'ts_ns':1700000000000000000+np.rint(t*1e9).astype(np.int64),
        'acc':clean_acc+rng.normal(0,.055,clean_acc.shape)+[.04,-.03,.05],
        'gyro':clean_gyro+rng.normal(0,.008,clean_gyro.shape)+[.004,-.003,.002],
        'clean_acc':clean_acc,'clean_gyro':clean_gyro,'room_m':SM.ROOM,
        'truth':{'pos':np.array(positions),'R':np.array(rotations),'label':labels,'body':np.array(body),
                 'segments':[[s[0],s[1],s[2]] for s in motion.script]},
        'scope':'Analytic kinematic handset motion with one-room calibrated posture encoding; not validated human biomechanics or actual cabinet physics'}


def write_input(session,gen):
    phone=session/'phone';phone.mkdir(parents=True,exist_ok=True)
    for name,values in [('accelerometer',gen['acc']),('gyroscope',gen['gyro'])]:
        with (phone/(name+'.csv')).open('w',encoding='utf-8',newline='') as f:
            w=csv.writer(f);w.writerow(FIELDS)
            for i,(ts,value) in enumerate(zip(gen['ts_ns'],values),1):w.writerow([i,int(ts),int(ts)+5000000,int(ts)+9000000,*map(float,value),3])
    (session/'bundle-manifest.json').write_text(json.dumps({'native_sid':'synthetic-'+session.parent.name,'is_synthetic':True}),encoding='utf-8')


def frozen_inference(session):
    channels=AM.load_phone(session);ta,A,aa=channels['accelerometer'];tg,G,ga=channels['gyroscope']
    times,features,info=prepare_features([(float(t),*map(float,x)) for t,x in zip(ta,A)],[(float(t),*map(float,x)) for t,x in zip(tg,G)])
    windows,wt=make_windows(times,features);velocity,_=predict(windows,paths.RONIN_ARCH,paths.RONIN_CKPT,hashlib.sha256(Path(paths.RONIN_CKPT).read_bytes()).hexdigest())
    xy=integrate_centers(wt[:,1],velocity);np.save(session/'ronin-xy.npy',np.c_[wt[:,1],xy,np.linalg.norm(velocity,axis=1)])
    actions=AM.predict_timeline(AM.load_model(),ta,A,tg,G,accel_arrivals=aa,gyro_arrivals=ga)
    (session/'actions.json').write_text(json.dumps(actions,ensure_ascii=False,indent=1),encoding='utf-8')
    from . import layout_solver as LS
    result=LS.solve(str(session));prediction=result[0] if isinstance(result,tuple) else result
    return wt[:,2],xy,actions,prediction,info


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    protocol={'presets':PRESETS,'models_frozen':True,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'model_sha256':{'ronin':hashlib.sha256(Path(paths.RONIN_CKPT).read_bytes()).hexdigest(),'actions':hashlib.sha256(AM.MODEL_PATH.read_bytes()).hexdigest()},
        'raw_inputs':'Only phone accelerometer/gyroscope CSV, common timestamps. Truth outside input directory.',
        'evaluation':'No scale fit; rigid trajectory alignment only diagnostic, never supplied to layout. Physical validity does not imply learned-model or layout validity.',
        'stop_rule':'Report all9 prespecified one-room/noise episodes; do not scale this bridge to5000 merely because one case works.'}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=1),encoding='utf-8');rows=[]
    for profile,seed in PRESETS:
        case=out/(profile+'-'+str(seed));case.mkdir(exist_ok=True);session=case/'input';gen=generate(profile,seed);write_input(session,gen)
        np.savez_compressed(case/'evaluation-truth.npz',time=gen['t'],position=gen['truth']['pos'],body=gen['truth']['body'],rotation=gen['truth']['R'],labels=np.asarray(gen['truth']['label']))
        row={'profile':profile,'seed':seed,'duration_s':float(gen['t'][-1]),'physics':physical_report(gen),
            'input_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (session/'phone').glob('*.csv')}}
        try:
            t,xy,actions,prediction,info=frozen_inference(session)
            truth_at=np.c_[np.interp(t,gen['t'],gen['truth']['body'][:,0]),np.interp(t,gen['t'],gen['truth']['body'][:,1])]
            align,R=rigid(xy,truth_at);aligned=align(xy);error=np.linalg.norm(aligned-truth_at,axis=1)
            truth_length=float(np.linalg.norm(np.diff(truth_at,axis=0),axis=1).sum());length=float(np.linalg.norm(np.diff(xy,axis=0),axis=1).sum())
            row['frontend']={'path_ratio':length/truth_length,'path_m':length,'truth_body_path_m':truth_length,'diagnostic_rigid_ADE_m':float(error.mean()),'diagnostic_rigid_p90_m':float(np.quantile(error,.9)),'no_scale_fit':True}
            per={};true=[];estimated=[]
            for w in actions['windows']:
                i=min(int(round(w['center_s']*gen['fs'])),len(gen['t'])-1);true.append(gen['truth']['label'][i]);estimated.append(w['label'])
            for label in ['walk','seated','lying','cabinet','other']:
                tp=sum(a==b==label for a,b in zip(true,estimated));n=sum(a==label for a in true);pred=sum(b==label for b in estimated)
                per[label]={'n_true':n,'n_pred':pred,'recall':tp/n if n else None,'f1':2*tp/(n+pred) if n+pred else None}
            row['actions']=per;row['predicted_runs']=actions['runs'];row['layout_status']=prediction['status']
            row['layout_score']=M.score_instances(prediction.get('boxes',{}),SM.FURN)
            np.savez_compressed(case/'trajectory-diagnostic.npz',time=t,predicted=xy,aligned_diagnostic=aligned,truth=truth_at)
        except Exception as exc:row.update(layout_status='pipeline_error',error=type(exc).__name__+': '+str(exc))
        (case/'result.json').write_text(json.dumps(row,ensure_ascii=False,indent=1),encoding='utf-8');rows.append(row)
        print(json.dumps({'profile':profile,'seed':seed,'physical_pass':row['physics']['passed'],'layout_status':row['layout_status'],'layout_all_hit':row.get('layout_score',{}).get('all_instances_hit',False),'path_ratio':row.get('frontend',{}).get('path_ratio')}),flush=True)
    result={'protocol':protocol,'n_cases':len(rows),'n_rooms':1,'rows':rows};(out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=1),encoding='utf-8');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();run(a.out)
