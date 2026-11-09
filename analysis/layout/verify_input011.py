"""Fresh-process input isolation and default-behaviour regression checks."""
import argparse, hashlib, json, os, shutil, subprocess, sys, types
from pathlib import Path
import numpy as np
from . import action_model as AM, inertial010 as F, multi_instance as M


def baseline(name):
    text=subprocess.check_output(['git','show','0c71b94:analysis/layout/'+name+'.py']).decode('utf-8-sig')
    module=types.ModuleType('analysis.layout._baseline_'+name);module.__package__='analysis.layout'
    exec(compile(text,'0c71b94/'+name+'.py','exec'),module.__dict__);return module


def verify(root,native,model,wrist):
    root,native,model,wrist=map(Path,(root,native,model,wrist));out=root/'input-firewall';out.mkdir(parents=True,exist_ok=True)
    source=root/'confirm32/multi-11119';isolated=out/'input'
    for name in ['phone/accelerometer.csv','phone/gyroscope.csv','watch/accelerometer.csv','known-priors.json']:
        dst=isolated/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/'input'/name,dst)
    # Deliberately unusable canaries: inference must neither load nor parse them.
    for name in ['evaluation-truth.npz','native-scene.json','cue-script.json']:(isolated/name).write_text('FORBIDDEN_EVALUATION_CANARY')
    argv=['analysis.layout.joint_input011','infer','--session',str(isolated),'--priors',str(isolated/'known-priors.json'),'--model',str(model),'--wrist',str(wrist),'--out',str(out/'prediction.json'),'--loops']
    script="""import sys,os,runpy,json
forbidden=('evaluation-truth','native-scene','cue-script','raw-native800','multi/native')
def guard(event,args):
    if event=='open':
        p=str(args[0]).replace(chr(92),'/')
        if any(v in p for v in forbidden):raise RuntimeError('Forbidden reference access: '+p)
sys.addaudithook(guard)
sys.argv=json.loads(sys.argv[1])
runpy.run_module(sys.argv[0],run_name='__main__')
"""
    subprocess.run([sys.executable,'-X','utf8','-c',script,json.dumps(argv)],check=True,env={**os.environ,'OMP_NUM_THREADS':'1'})
    actual=json.loads((out/'prediction.json').read_text());reference=next(r['prediction'] for r in json.loads((source/'results.json').read_text())['rows'] if r['arm']=='new_raw')
    numeric_deltas=[]
    def equivalent(a,b):
        if isinstance(a,dict):return a.keys()==b.keys() and all(equivalent(a[k],b[k]) for k in a)
        if isinstance(a,list):return len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
        if isinstance(a,(float,int)) and not isinstance(a,bool):numeric_deltas.append(abs(a-b));return abs(a-b)<=1e-9
        return a==b
    same=equivalent(actual,reference);boxes_exact=actual['boxes']==reference['boxes']
    if not (same and boxes_exact):raise AssertionError('Isolated public CLI differs from frozen primary beyond numerical rounding')
    from .joint_input011 import infer_saved
    priors=json.loads((isolated/'known-priors.json').read_text());rejected=False
    try:infer_saved(isolated,{**priors,'gt':{}},model,wrist,True)
    except ValueError:rejected=True
    assert rejected
    # The old replay source is executed directly from the committed revision.
    channels=AM.load_phone(isolated);t,A,_=channels['accelerometer'];tg,G,_=channels['gyroscope'];G=np.c_[*[np.interp(t,tg,G[:,i]) for i in range(3)]]
    old=baseline('inertial010');p0,R0,i0=old.replay(t,A,G);p1,R1,i1=F.replay(t,A,G)
    assert np.array_equal(p0,p1) and np.array_equal(R0,R1)
    assert np.array_equal(i0.pop('stationary_mask'),i1.pop('stationary_mask')) and i0==i1
    oldM=baseline('multi_instance');oldS=baseline('recovery010');oldS.M=oldM;checks=[]
    from .exp_walk_range import coverage_route
    from .recovery010 import solve
    for ident in [0,1,2]:
        sc=M.load_native(native/f'multi-{ident:05d}.json');ep=coverage_route(sc);path=ep['points'][ep['route_ids']];events=M.event_sequence(sc,path,14)
        # Identical finite inputs; no new callbacks or options selected.
        a=oldM.decode_instances([sc['W'],sc['L']],sc['inventory'],events,path)
        b=M.decode_instances([sc['W'],sc['L']],sc['inventory'],events,path)
        for key in ['boxes','status','search_nodes']:
            if key in a:
                if key=='boxes':
                    assert a[key].keys()==b[key].keys()
                    for k in a[key]:np.testing.assert_array_equal(a[key][k],b[key][k])
                else:assert a[key]==b[key]
        aa=oldS.solve([sc['W'],sc['L']],sc['inventory'],events,path,'depth_portfolio');bb=solve([sc['W'],sc['L']],sc['inventory'],events,path,'depth_portfolio')
        assert aa['status']==bb['status'] and aa['boxes'].keys()==bb['boxes'].keys()
        for k in aa['boxes']:np.testing.assert_array_equal(aa['boxes'][k],bb['boxes'][k])
        checks.append({'scene':sc['scene'],'events':len(events),'identical':True,'status':b['status'],'portfolio_identical':True,'portfolio_status':bb['status']})
    result={'public_cli_boxes_exactly_equal':boxes_exact,'public_cli_all_fields_equal_abs1e_9':same,'all_fields_max_numeric_delta':max(numeric_deltas),'reference_read_blocked_by_python_audit_hook':True,'canaries_not_read':True,'extra_truth_prior_rejected':rejected,'inertial_default_vs_0c71b94_exact':True,'default_decoder_checks':checks,'isolated_files':[str(f.relative_to(isolated)) for f in isolated.rglob('*') if f.is_file()],'phone_input_sha256':hashlib.sha256((isolated/'phone/accelerometer.csv').read_bytes()).hexdigest(),'scope':'One representative seven-object recording. Blocks known evaluation paths, not a formal proof of arbitrary code noninterference.'}
    (out/'verification.json').write_text(json.dumps(result,indent=1));print(json.dumps(result,indent=1));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--native',required=True);p.add_argument('--model',required=True);p.add_argument('--wrist',required=True);a=p.parse_args();verify(a.root,a.native,a.model,a.wrist)
