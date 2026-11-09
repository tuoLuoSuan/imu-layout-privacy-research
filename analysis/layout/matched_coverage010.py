"""Separate extra walk evidence from coverage-dependent contact generation."""
import argparse,concurrent.futures,json
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .recovery010 import solve
from .exp_walk_range import coverage_route,survey_prefixes
from .activity_audit import paired_binary,bootstrap_means


def one(task):
    source,baseline,out=map(Path,task);target=out/source.name
    if target.exists():return json.loads(target.read_text())
    scene=M.load_native(source);ep=coverage_route(scene);ratio=len(ep['reachable_ids'])/len(ep['free_ids']);low,high=survey_prefixes(ep,[.95/ratio,1./ratio]);events=M.event_sequence(scene,low['path'],14);r=solve([scene['W'],scene['L']],scene['inventory'],events,high['path'],'depth_portfolio');score=M.score_instances(r['boxes'],scene['gt']);old=json.loads(baseline.read_text());lookup={(x['policy'],x['coverage'],x['visits']):x for x in old['rows']};a=lookup['depth_portfolio',.95,14];c=lookup['depth_portfolio',1.,14]
    if a['events']!=events:raise AssertionError('Frozen contact generation drift')
    d={'scene':scene['scene'],'a_95walk_95contacts':a['score'],'b_100walk_95contacts':score,'c_100walk_100contacts':c['score'],'contacts_exactly_equal_ac':a['events']==c['events'],'status_b':r['status'],'executable':bool(high['reached'] and low['reached'] and len(events)==14),'events':events};target.write_text(json.dumps(d));return d


def run(native,baseline,out,workers=4):
    native,baseline,out=map(Path,(native,baseline,out));out.mkdir(parents=True,exist_ok=True);rooms=out/'rooms';rooms.mkdir(exist_ok=True);files=sorted(native.glob('*.json'))
    if len(files)!=1000:raise ValueError('Frozen new1000 required')
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:records=list(pool.map(one,[(str(f),str(baseline/'rooms'/f.name),str(rooms)) for f in files]))
    keys=['a_95walk_95contacts','b_100walk_95contacts','c_100walk_100contacts'];flags={k:np.array([r['executable'] and r[k]['all_instances_hit'] for r in records]) for k in keys};f1={k:np.array([r[k]['f1'] if r['executable'] else 0. for r in records]) for k in keys};pairs=[]
    for a,b in zip(keys,keys[1:]):
        diff=np.c_[flags[b].astype(float)-flags[a],f1[b]-f1[a]];ci=np.quantile(bootstrap_means(diff,draws=5000),[.025,.975],axis=0);pairs.append({'a':a,'b':b,**paired_binary(flags[a],flags[b]),'whole_difference_bootstrap95':ci[:,0].tolist(),'f1_difference':float(diff[:,1].mean()),'f1_difference_bootstrap95':ci[:,1].tolist()})
    result={'n':1000,'role':'Exploratory fixed-contact counterfactual on frozen confirmation rooms, estimator unchanged','arms':{k:{'whole':int(flags[k].sum()),'mean_f1':float(f1[k].mean())} for k in keys},'contacts_exactly_equal_ac':sum(r['contacts_exactly_equal_ac'] for r in records),'paired':pairs};(out/'summary.json').write_text(json.dumps(result,indent=1));print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--baseline',required=True);p.add_argument('--out',required=True);p.add_argument('--workers',type=int,default=4);a=p.parse_args();run(a.native,a.baseline,a.out,a.workers)
