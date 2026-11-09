"""Separately declared long raw-input experiment with a physical closed loop.

The generator actually returns the handset to its starting point. That known
protocol is side information, never inferred from ground-truth furniture.
This does not alter the frozen open-ended16 or the100 short raw episodes.
"""
import argparse,concurrent.futures,hashlib,json
from pathlib import Path
import numpy as np
from . import multi_raw010 as X,multi_instance as M
from .sim_handset import generate,route
from .sim_watch import generate as watch_generate,write as watch_write
from .synthetic_bridge import write_input
from .joint009 import mount


def plan(scene):
    script,coverage=X.plan(scene);position=np.array(script[-1]['b']);clock=script[-1]['end'];u=script[-1]['heading']
    for target in route(position,scene['S'],scene)[1:]:
        target=np.asarray(target);d=target-position;length=float(np.linalg.norm(d))
        if length<1e-6:continue
        u=d/length
        script.append({'start':clock,'end':clock+2.,'label':'other','a':position.copy(),'b':position.copy(),'heading':u.copy()});clock+=2.
        duration=max(2.,1.875*length/.65);script.append({'start':clock,'end':clock+duration,'label':'walk','a':position.copy(),'b':target.copy(),'heading':u.copy()});clock+=duration;position=target
    script.append({'start':clock,'end':clock+5.,'label':'other','a':position.copy(),'b':position.copy(),'heading':u.copy()})
    return script,coverage


def one(task):
    source,out,model=map(Path,task);out.mkdir(parents=True,exist_ok=True);target=out/'results.json'
    if target.exists():return json.loads(target.read_text())
    scene=M.load_native(source);s=json.loads(source.read_text())['agent_placement']['position'];scene['S']=np.array([s['x'],s['z']]);script,prefix=plan(scene);seed=1210000+int(scene['scene'].split('-')[-1]);phone=generate(scene,seed,script_override=script);meta=json.loads((model/'metadata.json').read_text());watch=mount(watch_generate(phone,seed+300),meta['neutral_up_from_development']);session=out/'input';write_input(session,phone);watch_write(session,watch)
    priors={'room':[scene['W'],scene['L']],'start':scene['S'].tolist(),'inventory':[{**e,'dimensions':np.asarray(e['dimensions']).tolist()} for e in scene['inventory']],'end_returns_to_start':True};(session/'known-priors.json').write_text(json.dumps(priors));np.savez_compressed(out/'evaluation-truth.npz',t=phone['t'],position=phone['truth']['pos'],rotation=phone['truth']['R'],labels=phone['truth']['label'])
    rows=[]
    for arm,closed,method in [('finite_no_loop',False,'finite'),('finite_known_loop',True,'finite'),('continuous_known_loop',True,'continuous')]:
        r=X.infer(session,priors,model,closed_loop=closed,method=method);rows.append({'arm':arm,'prediction':r,'score':M.score_instances(r['boxes'],scene['gt'])})
    r={'scene':scene['scene'],'n_objects':len(scene['gt']),'duration_s':float(phone['t'][-1]),'truth_endpoint_gap_m':float(np.linalg.norm(phone['truth']['pos'][-1,:2]-phone['truth']['pos'][0,:2])),'protocol':'Actual return to known start, explicitly given to loop arms; .5m coordinate contact bound in continuous arm; not a natural unassisted recording','native_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows};target.write_text(json.dumps(r,indent=1));print(json.dumps({'scene':r['scene'],'scores':[(q['arm'],q['prediction']['status'],q['score']['tp']) for q in rows]}),flush=True);return r


def run(native,out,model,start=11000,count=8,workers=3):
    native,out,model=map(Path,(native,out,model));out.mkdir(parents=True,exist_ok=True);ids=list(range(start,start+count));(out/'freeze.json').write_text(json.dumps({'ids':ids,'prior':'Explicit return to known start','scope':'Controlled extra-side-information diagnostic; development first8 only, freeze any choice before new confirmation','input':'Actual raw phone6axis120Hz and watch3axis16.7Hz; cabinet watch only','code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=1))
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:records=list(pool.map(one,[(str(native/f'multi-{i:05d}.json'),str(out/f'multi-{i:05d}'),str(model)) for i in ids]))
    summary={a:{'whole':sum(q['score']['all_instances_hit'] for r in records for q in r['rows'] if q['arm']==a),'f1':float(np.mean([q['score']['f1'] for r in records for q in r['rows'] if q['arm']==a]))} for a in ['finite_no_loop','finite_known_loop','continuous_known_loop']};(out/'summary.json').write_text(json.dumps({'n':count,'rows':summary},indent=1));print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--model',required=True);p.add_argument('--start',type=int,default=11000);p.add_argument('--count',type=int,default=8);p.add_argument('--workers',type=int,default=3);a=p.parse_args();run(a.native,a.out,a.model,a.start,a.count,a.workers)
