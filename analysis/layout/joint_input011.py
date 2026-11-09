"""Input-only CLI and separate synthetic evaluation for the011 joint chain.

infer_saved() accepts raw sensor directory, declared priors and frozen weights.
It never reads a native scene, evaluation-truth.npz or a cue/action script.
Those are used only by the separately named episode() evaluator.
"""
import argparse,concurrent.futures,hashlib,json
from pathlib import Path
import numpy as np
from . import multi_raw010 as X,multi_instance as M,displacement011 as D
from .oriented_raw011 import decode
from .contact_loops011 import refine
from .sim_watch import generate as watch_generate,write as watch_write
from .joint009 import mount
from .synthetic_bridge import write_input
from .expansion_report import footprint_all
from .pose_gauge011 import align


def infer_saved(session,priors,phone_motion_model,wrist_model,loops=False,watch_shift=0.,without_watch=False,trace=None,old_frontend=False):
    allowed={'room','start','inventory'}
    if set(priors)!=allowed:raise ValueError('Only declared room/start/inventory accepted')
    model=None if old_frontend else D.load(phone_motion_model);captured={}
    def front(t,A,G):
        p,R,info=X.replay(t,A,G) if old_frontend else D.replay(t,A,G,model,heading_regularization=True)
        captured.update(t=t,path=p.copy(),R=R);return p,R,info
    def refine_record(t,path,R,runs,prior):
        q,meta=refine(t,path,R,runs,prior);captured['path']=q.copy();return q,meta
    result=X.infer(session,priors,wrist_model,watch_shift=watch_shift,without_watch=without_watch,trajectory_frontend=front,candidate_limit=128,trajectory_refiner=refine_record if loops else None,layout_decoder=lambda *a:decode(*a,support_cost_weight=.3))
    result['input_contract']={'raw_phone_axes':6,'raw_watch_axes':3,'watch_gyro':False,'cabinet_source':'watch_only','reference_pose_read':False,'reference_scene_read':False,'cue_labels_read':False,'known_priors':sorted(allowed),'supervised_displacement_model':not old_frontend,'declared_heading_protocol':True,'storage_front_is_depth_normal':True,'contact_loop_refinement':loops}
    if trace is not None:np.savez_compressed(trace,**captured)
    return result


def episode(task):
    source,out,motion,wrist,loops,speed=task;source,out,motion,wrist=map(Path,(source,out,motion,wrist));out.mkdir(parents=True,exist_ok=True);target=out/'results.json'
    if target.exists():return json.loads(target.read_text())
    sc=M.load_native(source);native=json.loads(source.read_text());agent=native['agent_placement']['position'];sc['S']=np.array([agent['x'],agent['z']]);script,_=X.plan(sc);script=D.retime(script,speed);i=int(sc['scene'].split('-')[-1]);phone=D.generate(sc,seed=1410000+i,script_override=script);meta=json.loads((wrist/'metadata.json').read_text());watch=mount(watch_generate(phone,1410300+i),meta['neutral_up_from_development']);session=out/'input';write_input(session,phone);watch_write(session,watch)
    priors={'room':[sc['W'],sc['L']],'start':sc['S'].tolist(),'inventory':[{**e,'dimensions':np.asarray(e['dimensions']).tolist()} for e in sc['inventory']]};(session/'known-priors.json').write_text(json.dumps(priors));np.savez_compressed(out/'evaluation-truth.npz',time=phone['t'],position=phone['truth']['pos'],rotation=phone['truth']['R'],label=phone['truth']['label']);rows=[]
    for arm,old,absent,shift in [('new_raw',False,False,0.),('old_raw_matched',True,False,0.),('watch_absent',False,True,0.),('watch_clock10s',False,False,10.)]:
        trace=out/(arm+'-estimated.npz');pred=infer_saved(session,priors,motion,wrist,loops,shift,absent,trace,old);score=M.score_instances(pred['boxes'],sc['gt']);est=np.load(trace);q,_=align(est['path'],est['R'],phone['truth']['pos'][:,:2],phone['truth']['R']);err=np.linalg.norm(est['path']-q,axis=1);rows.append({'arm':arm,'oracle_assisted':False,'prediction':pred,'score':score,'whole_iou0_5':footprint_all(pred['boxes'],sc['gt']),'relative_frame_ade_m':float(err.mean()),'relative_frame_p90_m':float(np.quantile(err,.9))})
    # Explicit evaluation-only oracle. No such option exists in infer_saved CLI.
    def oracle(t,A,G):return phone['truth']['pos'][:,:2],phone['truth']['R'],{'stationary_mask':np.zeros(len(t),bool),'causal':False,'oracle_assisted':True}
    pred=X.infer(session,priors,wrist,trajectory_frontend=oracle,candidate_limit=128,trajectory_refiner=refine if loops else None,layout_decoder=lambda *a:decode(*a,support_cost_weight=.3));rows.append({'arm':'truth_pose_same_predicted_actions','oracle_assisted':True,'prediction':pred,'score':M.score_instances(pred['boxes'],sc['gt']),'whole_iou0_5':footprint_all(pred['boxes'],sc['gt'])})
    hashes={str(f.relative_to(session)):hashlib.sha256(f.read_bytes()).hexdigest() for f in session.rglob('*') if f.is_file()};r={'scene':sc['scene'],'n_objects':len(sc['gt']),'speed_m_s':speed,'duration_s':float(phone['t'][-1]),'input_sha256':hashes,'native_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows};target.write_text(json.dumps(r,indent=1));print(json.dumps({'scene':r['scene'],'n':r['n_objects'],'speed':speed,'scores':[(q['arm'],q['prediction']['status'],q['score']['tp']) for q in rows]}),flush=True);return r


def evaluate(native,out,motion,wrist,loops=False,start=11100,count=32,workers=4):
    native,out,motion,wrist=map(Path,(native,out,motion,wrist));out.mkdir(parents=True,exist_ok=True);ids=list(range(start,start+count));speeds=[.65 if k<16 else .55 if k<24 else .75 for k in range(count)]
    freeze={'ids':ids,'speeds':speeds,'loops':loops,'candidate_limit':128,'contact_padding_m':.3,'walk_tolerance_m':.2,'primary':'All4..7 centres<=0.5m, no extras/misses','motion_model_sha256':hashlib.sha256(motion.read_bytes()).hexdigest(),'watch_model_sha256':json.loads((wrist/'metadata.json').read_text())['model_sha256'],'role':'New long recordings held out from011 selection; some layouts had earlier short/geometry uses; not unseen natural rooms','code_sha256':{name:hashlib.sha256(Path(__file__).with_name(name+'.py').read_bytes()).hexdigest() for name in ['joint_input011','displacement011','contact_loops011','oriented_raw011','multi_instance','multi_raw010','recovery010','inertial010']}}
    existing=out/'freeze.json'
    if existing.exists() and json.loads(existing.read_text())!=freeze:raise ValueError('Frozen evaluation protocol changed')
    existing.write_text(json.dumps(freeze,indent=1));records=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(episode,[(str(native/f'multi-{i:05d}.json'),str(out/f'multi-{i:05d}'),str(motion),str(wrist),loops,s) for i,s in zip(ids,speeds)]):records.append(r)
    names=[r['arm'] for r in records[0]['rows']];summary={a:{'whole':sum(q['score']['all_instances_hit'] for r in records for q in r['rows'] if q['arm']==a),'ok':sum(q['prediction']['status']=='ok' for r in records for q in r['rows'] if q['arm']==a),'f1':float(np.mean([q['score']['f1'] for r in records for q in r['rows'] if q['arm']==a]))} for a in names};(out/'summary.json').write_text(json.dumps({'n':count,'rows':summary},indent=1));print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True);i=sub.add_parser('infer');i.add_argument('--session',required=True);i.add_argument('--priors',required=True);i.add_argument('--model',required=True);i.add_argument('--wrist',required=True);i.add_argument('--out',required=True);i.add_argument('--loops',action='store_true');i.add_argument('--trace');e=sub.add_parser('evaluate');e.add_argument('--native',required=True);e.add_argument('--out',required=True);e.add_argument('--model',required=True);e.add_argument('--wrist',required=True);e.add_argument('--loops',action='store_true');e.add_argument('--start',type=int,default=11100);e.add_argument('--count',type=int,default=32);e.add_argument('--workers',type=int,default=4);a=p.parse_args()
    if a.command=='infer':Path(a.out).write_text(json.dumps(infer_saved(a.session,json.loads(Path(a.priors).read_text()),a.model,a.wrist,a.loops,trace=a.trace),indent=1))
    else:evaluate(a.native,a.out,a.model,a.wrist,a.loops,a.start,a.count,a.workers)
