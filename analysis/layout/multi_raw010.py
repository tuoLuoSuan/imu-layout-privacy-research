"""Raw phone+watch input into the SAME variable-inventory geometric solver.

Truth plans motion and evaluates outputs only. Inference reads sensor CSVs,
known room/start/inventory and fixed protocol/bounds. All repeated interactions
are retained with class/position only; no true instance identity is supplied.
"""
import argparse,concurrent.futures,hashlib,json,time
from pathlib import Path
import numpy as np
from . import multi_instance as M,action_model as AM,evidence_space as ES
from .exp_walk_range import coverage_route,survey_prefixes
from .sim_handset import generate,route
from .sim_watch import generate as generate_watch,write as write_watch
from .joint009 import mount
from .synthetic_bridge import write_input
from .inertial010 import replay
from .contact_contract import body_axis
from .watch_cabinet import load as load_watch,fuse
from .wrist_binary import predict
from .recovery010 import solve
from .selection_diagnostics import outline_cost
from .expansion_report import footprint_all
from .sim_motion import U_UP

OPTIONS={'contact_padding':.30,'walk_clearance':.15,'walk_tolerance':.20,'walk_excluded_objects':('desk','cab')}
CONTRACT={'anchor':'trajectory reference during the stable interaction; handset horizontal point in this generator','bed':'inside occupied footprint, no bed-foot equality','chair':'seat centre','cab':'0.60m from an operation face','walk':'desk/storage excluded; bed/chair contact allowed','frame':'known handset start, unknown yaw; fixed pose-to-body-axis protocol','inventory':'known counts/dimensions; no event-instance identity','observation_bounds':OPTIONS}


def compress(path):
    p=np.asarray(path,float)
    if len(p)<3:return p
    out=[p[0]]
    for i in range(1,len(p)-1):
        a=p[i]-out[-1];b=p[i+1]-p[i]
        if np.linalg.norm(a)<1e-10:continue
        if np.linalg.norm(b)<1e-10:continue
        if abs(a[0]*b[1]-a[1]*b[0])>1e-8 or np.dot(a,b)<=0:out.append(p[i])
    out.append(p[-1]);return np.asarray(out)


def plan(scene,coverage=1.,visits=14):
    ep=coverage_route(scene);ratio=len(ep['reachable_ids'])/len(ep['free_ids']);prefix=survey_prefixes(ep,[coverage/ratio])[0]
    if not prefix['reached']:raise ValueError('Frozen coverage target is not executable')
    ordered=ep['points'][ep['route_ids']];arc=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(ordered,axis=0),axis=1))];index=int(np.searchsorted(arc,prefix['walk_m']+1e-8,side='right')-1);survey=compress(ordered[:index+1]);events=M.event_sequence(scene,prefix['path'],visits)
    if len(events)!=visits:raise ValueError('Frozen interaction budget not executable')
    script=[];clock=0.;position=np.asarray(scene['S'],float);heading=np.array([0.,1.])
    def add(duration,label,target,u):
        nonlocal clock,position,heading
        script.append({'start':clock,'end':clock+duration,'label':label,'a':position.copy(),'b':np.asarray(target),'heading':np.asarray(u)})
        clock+=duration;position=np.asarray(target);heading=np.asarray(u)
    def walk(points):
        for target in points:
            d=np.asarray(target)-position;length=float(np.linalg.norm(d))
            if length<1e-6:continue
            u=d/length;add(2.,'other',position,u);add(max(2.,1.875*length/.65),'walk',target,u)
    add(5.,'other',position,heading);walk(route(position,survey[0],scene)[1:]);walk(survey[1:])
    for event in events:
        cls=event['object'];point=np.asarray(event['pos']);walk(route(position,point,scene)[1:])
        choices=[np.asarray(b) for name,b in scene['gt'].items() if M.category(name)==cls];b=min(choices,key=lambda b:np.linalg.norm((b[:2]+b[2:])/2-point));u=np.array([0.,1.])
        if cls=='cab':
            axis=int(np.argmax(np.maximum(b[:2]-point,point-b[2:])));u=np.eye(2)[axis]*np.sign((b[axis]+b[axis+2])/2-point[axis])
        elif cls=='chair':
            desks=[np.asarray(b) for name,b in scene['gt'].items() if M.category(name)=='desk'];d=min(desks,key=lambda b:np.linalg.norm((b[:2]+b[2:])/2-point));axis=int(np.argmin(d[2:]-d[:2]));u=np.eye(2)[axis]*np.sign((d[axis]+d[axis+2])/2-point[axis])
        elif cls=='bed':
            axis=int(np.argmax(b[2:]-b[:2]));u=np.eye(2)[axis]*(1 if scene[['W','L'][axis]]-b[axis+2]<b[axis] else -1)
        label={'bed':'lying','chair':'seated','cab':'cabinet'}[cls];add(2.,'other',position,u);add(9. if cls!='cab' else 10.,label,position,u);add(3.,'other',position,u)
    add(5.,'other',position,heading);return script,prefix


def interaction_events(t,path,runs):
    t=np.asarray(t);path=np.asarray(path);events=[]
    for label,a,b in runs:
        if label not in ['seated','lying','cabinet'] or b-a<2.:continue
        ids=np.flatnonzero((t>=a+.25*(b-a))&(t<=a+.75*(b-a)))
        if len(ids)<3:continue
        ids=ids[-max(3,len(ids)//4):];p=np.median(path[ids],axis=0)
        events.append({'object':{'seated':'chair','lying':'bed','cabinet':'cab'}[label],'pos':p.tolist()})
    return events


def qualified_runs(t,acceleration,runs):
    # Declared pose encoding: thigh-vertical for seated, flat for lying.
    # Require a sustained event and check its stable tail's gravity direction.
    # This rejects standing/turning phone RF artifacts without changing weights.
    t=np.asarray(t);A=np.asarray(acceleration);out=[]
    for label,a,b in runs:
        if label not in ['seated','lying']:out.append([label,a,b]);continue
        if b-a<4.:continue
        ids=np.flatnonzero((t>=a+.5)&(t<=b))
        if not len(ids):continue
        v=np.median(A[ids],axis=0);v/=max(1e-9,np.linalg.norm(v));z=v[2]
        seat=np.asarray(U_UP['sit']);seat=seat/np.linalg.norm(seat);stand=np.asarray(U_UP['stand']);stand=stand/np.linalg.norm(stand)
        if label=='seated' and np.dot(v,seat)<=np.dot(v,stand)+.015:continue
        if label=='lying' and not z<-.75:continue
        out.append([label,a,b])
    return out


def decode_observations(priors,path,events,walk,yaw_angles,method='finite',candidate_limit=64):
    path=np.asarray(path);origin=path[0];candidates=[]
    for degrees in yaw_angles:
        a=np.radians(degrees);R=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]]);q=(path-origin)@R.T+priors['start'];ev=[{'object':e['object'],'pos':((np.asarray(e['pos'])-origin)@R.T+priors['start']).tolist()} for e in events]
        #120Hz handset stream:0.1s sampling, then0.10m spatial raster.
        # All resulting cells are retained;0.20m walk uncertainty is explicit.
        observed=np.unique(np.round(q[np.asarray(walk,bool)][::12]/.10)*.10,axis=0) if np.any(walk) else np.empty((0,2))
        if method=='continuous':
            from .continuous_solver010 import solve as continuous
            result=continuous(priors['room'],priors['inventory'],ev,observed,padding=.5,seconds=15.)
        elif method=='finite':result=solve(priors['room'],priors['inventory'],ev,observed,'depth_portfolio',decoder_options={**OPTIONS,'candidate_limit':candidate_limit})
        else:raise ValueError('Unknown separately declared raw decoder')
        outside=np.maximum(-q,q-np.array(priors['room'])).clip(min=0);cost=100*float(outside.mean())+10*float(outside.max())
        cost+=1000 if result['status']!='ok' else float(np.mean(outline_cost(np.array(list(result['boxes'].values())),priors['room'],observed)))
        candidates.append({**result,'yaw_deg':float(degrees),'registration_cost':cost,'events':ev,'n_walk_points':len(observed)})
    best=min(candidates,key=lambda r:r['registration_cost']);return {**best,'boxes':{k:np.asarray(b).tolist() for k,b in best['boxes'].items()},'frame_hypotheses':[{k:r[k] for k in ['yaw_deg','registration_cost','status']} for r in candidates],'contract':CONTRACT}


def infer(session,priors,wrist_model,watch_shift=0.,without_watch=False,closed_loop=False,method='finite',trajectory_frontend=None,candidate_limit=64,trajectory_refiner=None,layout_decoder=None):
    ch=AM.load_phone(session);t,A,_=ch['accelerometer'];tg,G,_=ch['gyroscope'];G=np.c_[*[np.interp(t,tg,G[:,i]) for i in range(3)]];path,R,info=(replay if trajectory_frontend is None else trajectory_frontend)(t,A,G);info.pop('stationary_mask');phone=AM.predict_timeline(AM.load_model(),t,A,t,G)
    if closed_loop:
        if not priors.get('end_returns_to_start'):raise ValueError('Loop closure requires explicit return-to-start protocol')
        from .inertial010 import close_loop
        info['declared_loop_endpoint_correction_m']=float(np.linalg.norm(path[-1]-path[0]));path=close_loop(t,path);info['known_return_to_start']=True
    wt,wa=load_watch(session,int(1700000000000000000));watch={'runs':[]} if without_watch else predict(wt+watch_shift,wa,wrist_model);runs=qualified_runs(t,A,fuse(phone,watch)['runs'])
    if trajectory_refiner is not None:path,info['contact_refinement']=trajectory_refiner(t,path,R,runs,priors)
    events=interaction_events(t,path,runs);mask=np.zeros(len(t),bool)
    for label,a,b in runs:
        if label=='walk':mask|=(t>=a)&(t<=b)
    cabinet=next((r for r in runs if r[0]=='cabinet' and r[2]-r[1]>=2.),None)
    if cabinet is not None:
        ids=(t>=cabinet[1]+.5)&(t<=cabinet[2]);h=body_axis(R[ids],'cabinet').mean(axis=0);offset=np.degrees(np.arctan2(h[1],h[0]));angles=[a-offset for a in [0,90,180,270]]
    else:angles=[0.,90.,180.,270.]
    result=decode_observations(priors,path,events,mask,angles,method,candidate_limit) if layout_decoder is None else layout_decoder(priors,t,path,R,runs,mask,candidate_limit)
    return {**result,'runs':runs,'cabinet_source':'watch_only','phone_cabinet_used':False,'watch_runs':watch['runs'],'trajectory':'full-record signal-rest bias calibration + stationary tilt updates + endpoint ZUPT','zero_velocity':info}


def episode(task):
    source,out,wrist_model=map(Path,task);out.mkdir(parents=True,exist_ok=True);target=out/'results.json'
    if target.exists():return json.loads(target.read_text())
    scene=M.load_native(source);native=json.loads(source.read_text());start=native['agent_placement']['position'];scene['S']=np.array([start['x'],start['z']]);script,prefix=plan(scene);seed=1110000+int(scene['scene'].split('-')[-1]);phone=generate(scene,seed,script_override=script);phone['contract']=CONTRACT;meta=json.loads((wrist_model/'metadata.json').read_text());watch=mount(generate_watch(phone,seed+300),meta['neutral_up_from_development']);session=out/'input';write_input(session,phone);write_watch(session,watch)
    priors={'room':[scene['W'],scene['L']],'start':scene['S'].tolist(),'inventory':[{**e,'dimensions':np.asarray(e['dimensions']).tolist()} for e in scene['inventory']]};(session/'known-priors.json').write_text(json.dumps(priors));np.savez_compressed(out/'evaluation-truth.npz',t=phone['t'],position=phone['truth']['pos'],rotation=phone['truth']['R'],labels=phone['truth']['label'])
    prediction=infer(session,priors,wrist_model);rows=[{'arm':'raw_joint','prediction':prediction,'score':M.score_instances(prediction['boxes'],scene['gt']),'whole_iou0_5':footprint_all(prediction['boxes'],scene['gt'])}]
    truth_runs=[[s['label'],s['start'],s['end']] for s in script];ev=interaction_events(phone['t'],phone['truth']['pos'][:,:2],truth_runs);mask=np.array(phone['truth']['label'])=='walk';oracle=decode_observations(priors,phone['truth']['pos'][:,:2],ev,mask,[0.]);rows.append({'arm':'truth_pose_truth_actions','oracle_assisted':True,'prediction':oracle,'score':M.score_instances(oracle['boxes'],scene['gt']),'whole_iou0_5':footprint_all(oracle['boxes'],scene['gt'])})
    valid=[]
    for event in ev:
        boxes=np.array([b for name,b in scene['gt'].items() if M.category(name)==event['object']]);valid.append(bool(ES._contact(boxes,event,.20,.60)[0].any()))
    record={'scene':scene['scene'],'n_objects':sum(scene['counts'].values()),'counts':scene['counts'],'duration_s':float(phone['t'][-1]),'contract_contacts_valid':sum(valid),'contract_contacts_total':len(valid),'planned_coverage':float(prefix['coverage_free']),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'wrist_model_sha256':meta['model_sha256'],'rows':rows};target.write_text(json.dumps(record,indent=1),encoding='utf-8');print(json.dumps({'scene':scene['scene'],'n_objects':record['n_objects'],'seconds':record['duration_s'],'contract':all(valid),'tp':{r['arm']:r['score']['tp'] for r in rows}}),flush=True);return record


def run(native,out,wrist_model,start=11000,count=8,workers=1):
    native,out,wrist_model=map(Path,(native,out,wrist_model));out.mkdir(exist_ok=True);ids=range(start,start+count);(out/'freeze.json').write_text(json.dumps({'ids':list(ids),'contract':CONTRACT,'model_sha256':json.loads((wrist_model/'metadata.json').read_text())['model_sha256'],'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'input':'Raw phone6axis120Hz + watch3axis16.7Hz; no truth in inference','role':'Development8 followed by separately frozen new16 confirmation'},indent=1));records=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(episode,[(str(native/f'multi-{i:05d}.json'),str(out/f'multi-{i:05d}'),str(wrist_model)) for i in ids]):records.append(r)
    summary={'n':len(records),'rows':{arm:{'whole':sum(r['score']['all_instances_hit'] for d in records for r in d['rows'] if r['arm']==arm),'f1':float(np.mean([r['score']['f1'] for d in records for r in d['rows'] if r['arm']==arm]))} for arm in ['raw_joint','truth_pose_truth_actions']}};(out/'summary.json').write_text(json.dumps(summary,indent=1));print(json.dumps(summary),flush=True);return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--wrist-model',required=True);p.add_argument('--start',type=int,default=11000);p.add_argument('--count',type=int,default=8);p.add_argument('--workers',type=int,default=1);a=p.parse_args();run(a.native,a.out,a.wrist_model,a.start,a.count,a.workers)
