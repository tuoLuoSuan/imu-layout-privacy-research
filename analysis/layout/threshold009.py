"""Additional frozen budget cells, preserving every one of10000 room IDs.

The grid refines gaps around the prior80% positionF1 reference and probes
larger interaction budgets. It never assumes monotonicity or claims a
continuous/universal threshold. Only outline is rerun; core90-row comparisons
are kept separately frozen.
"""
import argparse,concurrent.futures,hashlib,json,time
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .exp_walk_range import coverage_route,survey_prefixes
from .selection_diagnostics import rerank_pools

CELLS=[(.90,11),(.92,11),(.94,11),(.95,9),(.95,10),(.96,9),(.98,6),(.98,7),(.98,8),(.98,9),(1.,6),(1.,7),(1.,21),(1.,28)]


def sources(repo,package):
    repo,package=map(Path,(repo,package));old=repo/'output/research-sync/2026-11-08-procthor-rescue-005/multi/native';prev=repo/'output/research-sync/2026-11-09-expansion-imu-008/new4000/native'
    return [(old if i<1000 else prev if i<5000 else package/'new5000/native')/f'multi-{i:05d}.json' for i in range(10000)]


def one(task):
    source,target=map(Path,task);rows=[];scene=M.load_native(source);ep=coverage_route(scene);ratio=len(ep['reachable_ids'])/len(ep['free_ids']);cs=sorted({c for c,n in CELLS});prefixes=dict(zip(cs,survey_prefixes(ep,[c/ratio for c in cs])));original=M._constraint_search
    for c in cs:
        pre=prefixes[c];path=pre['path'];cache={}
        for cov,n in CELLS:
            if cov!=c:continue
            events=M.event_sequence(scene,path,n,mode='dispersed')
            def select(inv,pools,targets,counts):return original(inv,rerank_pools(pools,[scene['W'],scene['L']],path,'outline'),targets,counts)
            M._constraint_search=select
            try:r=M.decode_instances([scene['W'],scene['L']],scene['inventory'],events,path,proposal_cache=cache)
            finally:M._constraint_search=original
            score=M.score_instances(r['boxes'],scene['gt']);execute=pre['reached'] and len(events)==n
            rows.append({'coverage':cov,'visits':n,'executable':bool(execute),'status':r['status'],'f1':score['f1'] if execute else 0.,'whole':bool(execute and score['all_instances_hit']),'unique_contacts':len({(e['object'],*e['pos']) for e in events}),'search_nodes':r.get('search_nodes')})
    record={'scene':scene['scene'],'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows};target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(record),encoding='utf-8');tmp.replace(target);return scene['scene']


def run(repo,package,workers=3,start_index=0,stop_index=10000):
    package=Path(package);out=package/'fine-grid';out.mkdir(exist_ok=True);files=sources(repo,package)[start_index:stop_index]
    protocol={'n_rooms':10000,'cells':CELLS,'method':'outline','tolerance_m':.5,'filter':'none','reference':'F1>=.8 and whole>=.8 separate, sampled Pareto only','ranking_source_sha256':hashlib.sha256(Path(__file__).with_name('selection_diagnostics.py').read_bytes()).hexdigest()}
    if not (out/'protocol.json').exists():(out/'protocol.json').write_text(json.dumps(protocol,indent=1),encoding='utf-8')
    expected={f.stem for f in files};done={f.stem for f in (out/'rooms').glob('*.json') if f.stem in expected};submitted=set(done);pending={};start=time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        while len(done)<len(files):
            for f in files:
                if len(pending)>=workers*3:break
                if f.stem in submitted or not f.exists():continue
                pending[pool.submit(one,(str(f),str(out/'rooms'/f.name)))]=f.stem;submitted.add(f.stem)
            for job in [j for j in pending if j.done()]:done.add(job.result());del pending[job]
            progress={'completed_local':len(done),'submitted_local':len(submitted),'total_local':len(files),'partition':[start_index,stop_index],'completed':len(list((out/'rooms').glob('*.json'))),'total':10000,'elapsed_s':round(time.time()-start,1)}
            (out/'progress.json').write_text(json.dumps(progress),encoding='utf-8')
            if len(done)<len(files):time.sleep(3)
    return progress


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',default='.');p.add_argument('--package',required=True);p.add_argument('--workers',type=int,default=3);p.add_argument('--start-index',type=int,default=0);p.add_argument('--stop-index',type=int,default=10000);a=p.parse_args();print(json.dumps(run(a.repo,a.package,a.workers,a.start_index,a.stop_index)))
