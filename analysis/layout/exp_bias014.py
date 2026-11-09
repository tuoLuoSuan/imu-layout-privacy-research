"""Controlled raw-input bias experiment; old013 data/curves stay frozen.

Both arms use contact loops THEN optional cabinet-wall correction. The only
intervention is signal-only bias tracking before the frozen displacement model.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import numpy as np
from . import multi_raw010 as X, multi_instance as M
from .displacement011 import generate, retime, load, replay as old_replay
from .bias_tracker014 import replay as new_replay
from .bias_tracker014b import replay as gated_replay
from .sensor013 import degrade, report
from .sim_watch import generate as generate_watch, write as write_watch
from .joint009 import mount
from .synthetic_bridge import write_input
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .oriented_raw011 import decode
from .expansion_report import footprint_all
from .pose_gauge011 import align

OLD=Path('output/research-sync/2026-11-09-joint-input-and-recovery-010')
MODEL=Path('output/research-sync/2026-11-09-raw-input-repair-011/spectral-training/trees-distance.joblib')
WRIST=OLD/'wrist-ensemble-final'


def infer_saved(session,priors,correct_bias=True,trace=None,tracker='b'):
    if set(priors)!={'room','start','inventory'}:raise ValueError('Only room/start/inventory accepted')
    model=load(MODEL)
    def front(t,A,G):
        if correct_bias and tracker in ['g','gg']:
            from .bias_tracker014b import calibrate,gated_gyro
            _,Gc,meta=(gated_gyro if tracker=='gg' else calibrate)(t,A,G);p,R,info=old_replay(t,A,Gc,model,heading_regularization=True)
            meta['acceleration_correction_applied']=False;info['gyro_tracker014']=meta
            return p,R,info
        return (gated_replay if tracker=='b' else new_replay)(t,A,G,model) if correct_bias else old_replay(t,A,G,model,heading_regularization=True)
    def refine(t,p,R,runs,known):
        p,a=loops(t,p,R,runs,known);p,b=wall(t,p,R,runs,known)
        if trace is not None:trace.update(time=t,path=p.copy(),rotation=R.copy())
        return p,{'point_plane_loops':a,'cabinet_wall':b}
    result=X.infer(session,priors,WRIST,trajectory_frontend=front,candidate_limit=128,trajectory_refiner=refine,
                    layout_decoder=lambda *a:decode(*a,support_cost_weight=.3))
    result['input_contract']={'phone_axes':6,'watch_axes':3,'cabinet_source':'watch_only','truth_read':False,
                              'bias_tracking':correct_bias,'offline':True,'fixed_recurrent_handset_postures':True,
                              'same_displacement_weights':True,'same_contact_loops_and_wall_prior':True}
    return result


def worker(task):
    i,s,root,tracker=task;root=Path(root);key=f'multi-{i:05d}-s{s:g}';target=root/(key+'.json')
    if target.exists():return json.loads(target.read_text())
    folder=root/'records'/key;session=folder/'input'
    native=OLD/'raw-native800/native'/f'multi-{i:05d}.json'
    scene=M.load_native(native);raw=json.loads(native.read_text());sp=raw['agent_placement']['position'];scene['S']=np.array([sp['x'],sp['z']])
    script,_=X.plan(scene);speed=.65 if i%3==0 else .55 if i%3==1 else .75
    clean=generate(scene,seed=1770000+i,script_override=retime(script,speed));phone=degrade(clean,s,seed=314000+i)
    write_input(session,phone);meta=json.loads((WRIST/'metadata.json').read_text());write_watch(session,mount(generate_watch(clean,1770300+i),meta['neutral_up_from_development']))
    priors={'room':[scene['W'],scene['L']],'start':scene['S'].tolist(),
            'inventory':[{**e,'dimensions':np.asarray(e['dimensions']).tolist()} for e in scene['inventory']]}
    (session/'known-priors.json').write_text(json.dumps(priors))
    np.savez_compressed(folder/'evaluation-truth.npz',time=clean['t'],position=clean['truth']['pos'],rotation=clean['truth']['R'],label=clean['truth']['label'])
    records=[]
    for name,correct in [('reference',False),('bias014',True)]:
        trace={};error=None
        try:pred=infer_saved(session,priors,correct,trace,tracker)
        except ValueError as e:pred={'status':'frontend_error','boxes':{}};error=str(e)
        row={'arm':name,'prediction':pred,'error':error,'score':M.score_instances(pred['boxes'],scene['gt']),
             'whole_iou0_5':footprint_all(pred['boxes'],scene['gt'])}
        if trace:
            np.savez_compressed(folder/(name+'-estimated.npz'),**trace)
            gt,_=align(trace['path'],trace['rotation'],clean['truth']['pos'][:,:2],clean['truth']['R'])
            row['relative_ade_m']=float(np.linalg.norm(trace['path']-gt,axis=1).mean())
        records.append(row)
    result={'scene':scene['scene'],'severity':s,'n_objects':len(scene['gt']),'speed_m_s':speed,'duration_s':float(clean['t'][-1]),
            'sensor_error':report(clean,phone),'native_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),
            'rows':records,'input_sha256':{f.relative_to(session).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in session.rglob('*') if f.is_file()}}
    target.write_text(json.dumps(result,indent=1));print(json.dumps({'scene':i,'severity':s,'scores':[(r['arm'],r['prediction']['status'],r['score']['tp']) for r in records]}),flush=True)
    return result


def run(out,start,count,severities,workers=3,tracker='b'):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);ids=list(range(start,start+count))
    protocol={'ids':ids,'severities':severities,'tracker':tracker,'source_sha256':{n:hashlib.sha256(Path(__file__).with_name(n+'.py').read_bytes()).hexdigest() for n in ['bias_tracker014','bias_tracker014b','exp_bias014','sensor013','wall_refine012','contact_loops011','oriented_raw011']},
              'model_sha256':hashlib.sha256(MODEL.read_bytes()).hexdigest(),'seeds':{'phone':1770000,'watch':1770300,'sensor':314000},
              'intervention':'Raw-signal recurrent-posture acc drift + zero-rate gyro bias tracking before the SAME frozen displacement model; phone HAR still raw; watch unchanged.',
              'both_arms':'point/plane contact loops then cabinet-wall correction, oriented decoder cap128, contact.3, walk.2',
              'limits':'Same-domain supervised model, controlled fixed recurrent phone postures, relative synthetic sensor sweep, not a calibrated physical-device tolerance.',
              'role':'development' if start==11000 else 'new signal confirmation; no selection on these outputs'}
    f=out/'protocol.json'
    if f.exists() and json.loads(f.read_text())!=protocol:raise ValueError('Frozen protocol changed')
    f.write_text(json.dumps(protocol,indent=1))
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:records=list(pool.map(worker,[(i,s,str(out),tracker) for i in ids for s in severities]))
    summary={}
    for s in severities:
        summary[str(s)]={}
        for arm in ['reference','bias014']:
            rr=[q for r in records if r['severity']==s for q in r['rows'] if q['arm']==arm]
            summary[str(s)][arm]={'n':len(rr),'whole':sum(r['score']['all_instances_hit'] for r in rr),'f1':float(np.mean([r['score']['f1'] for r in rr])),
                                  'ok':sum(r['prediction']['status']=='ok' for r in rr),'iou':sum(r['whole_iou0_5'] for r in rr),
                                  'median_ade_m':float(np.median([r['relative_ade_m'] for r in rr if 'relative_ade_m' in r])) if any('relative_ade_m' in r for r in rr) else None}
    (out/'summary.json').write_text(json.dumps(summary,indent=1));print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--start',type=int,default=11000);p.add_argument('--count',type=int,default=8)
    p.add_argument('--severities',default='0,0.5,1');p.add_argument('--workers',type=int,default=3);p.add_argument('--infer-session');p.add_argument('--priors');p.add_argument('--prediction')
    p.add_argument('--tracker',choices=['a','b','g','gg'],default='gg')
    a=p.parse_args()
    if a.infer_session:
        Path(a.prediction).write_text(json.dumps(infer_saved(a.infer_session,json.loads(Path(a.priors).read_text()),tracker=a.tracker),indent=1))
    else:run(a.out,a.start,a.count,[float(s) for s in a.severities.split(',')],a.workers,a.tracker)
