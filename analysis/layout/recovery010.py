"""Truth-free wall priors before finite proposal retention.

The near-wall property is declared side information about the controlled
generator. Depth-normal support is a stronger, separately named assumption.
Strict filters never fall back to the unrestricted pool. Legacy defaults stay
unchanged; no target boxes are accepted by solve().
"""
import argparse,concurrent.futures,hashlib,json,time
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .desk_wall_audit import _filter_pool
from .selection_diagnostics import rerank_pools,minimum_cost_search
from .exp_walk_range import coverage_route,survey_prefixes
from .expansion_report import footprint_all

POLICIES=['post64_wall','post64_wall40k','pre64_wall','pre64_depth','pre64_depth_joint','region_wall','region_depth','depth_portfolio']


def wall_mask(boxes,room,tol=.15,depth_only=False):
    b=np.asarray(boxes,float).reshape(-1,4);r=np.asarray(room,float)
    if not len(b):return np.zeros(0,bool)
    gaps=np.minimum(b[:,:2],r-b[:,2:]);valid=np.all(b[:,:2]>=-1e-4,axis=1)&np.all(b[:,2:]<=r+1e-4,axis=1)
    gap=gaps[np.arange(len(b)),np.argmin(b[:,2:]-b[:,:2],axis=1)] if depth_only else gaps.min(axis=1)
    return valid&(gap<=tol+1e-8)&(gap>=-1e-4)


def wall_regions(size,room,tol=.15,depth_only=False):
    size=np.asarray(size,float);maximum=np.asarray(room,float)-size;regions=[]
    if np.any(maximum<0):return np.empty((0,4))
    for axis in [int(np.argmin(size))] if depth_only else [0,1]:
        a=np.r_[np.zeros(2),maximum];a[axis+2]=min(tol,maximum[axis]);regions.append(a)
        b=np.r_[np.zeros(2),maximum];b[axis]=max(0.,maximum[axis]-tol);regions.append(b)
    return np.array(regions)


def solve(room,inventory,events,path,policy='pre64_wall',tol=.15,cache=None,decoder_options=None):
    if policy not in POLICIES:raise ValueError('Unknown declared policy')
    options={} if decoder_options is None else dict(decoder_options)
    if set(options)-{'contact_padding','walk_clearance','walk_tolerance','walk_excluded_objects','candidate_limit','proposal_filter','event_support','known_desk_protocol','support_cost_weight'}:raise ValueError('Only declared observation bounds/candidate cap/evidence callbacks accepted')
    if policy=='depth_portfolio':
        first=solve(room,inventory,events,path,'pre64_depth_joint',tol,cache,options)
        attempts=[{'policy':'pre64_depth_joint','status':first['status'],'search_nodes':first.get('search_nodes',0)}]
        if first['status']=='ok':return {**first,'fallback_used':False,'attempts':attempts,'max_total_node_budget':40000}
        second=solve(room,inventory,events,path,'post64_wall',tol,cache,options)
        attempts.append({'policy':'post64_wall','status':second['status'],'search_nodes':second.get('search_nodes',0)})
        return {**second,'fallback_used':True,'attempts':attempts,'search_nodes':sum(r['search_nodes'] for r in attempts),'max_total_node_budget':40000}
    supplied_filter=options.pop('proposal_filter',None);original=M._constraint_search
    def select(inv,pools,targets,counts):
        ranked=rerank_pools(pools,room,path,'outline')
        if policy in ['post64_wall','post64_wall40k']:ranked=_filter_pool(ranked,room,tol)
        return minimum_cost_search(inv,ranked,targets,counts) if policy.endswith('_joint') else original(inv,ranked,targets,counts,node_limit=40000 if policy=='post64_wall40k' else 20000)
    def keep(entry,boxes,room):
        result=wall_mask(boxes,room,tol,'depth' in policy) if entry['category']=='desk' and policy not in ['post64_wall','post64_wall40k'] else np.ones(len(boxes),bool)
        return result if supplied_filter is None else result&supplied_filter(entry,boxes,room)
    def prior(entry,size,room):return wall_regions(size,room,tol,'depth' in policy) if entry['category']=='desk' else None
    M._constraint_search=select
    try:return M.decode_instances(room,inventory,events,path,proposal_cache=cache,
              proposal_filter=None if (policy in ['post64_wall','post64_wall40k'] or policy.startswith('region_')) and supplied_filter is None else keep,
              region_prior=prior if policy.startswith('region_') else None,**options)
    finally:M._constraint_search=original


def one(task):
    source,target,policies,cells=task;source,target=map(Path,(source,target))
    if target.exists():return json.loads(target.read_text())
    scene=M.load_native(source);room=[scene['W'],scene['L']];ep=coverage_route(scene);ratio=len(ep['reachable_ids'])/len(ep['free_ids']);coverages=sorted({c for c,n in cells});prefixes=dict(zip(coverages,survey_prefixes(ep,[c/ratio for c in coverages])));rows=[]
    for cov in coverages:
        prefix=prefixes[cov];path=prefix['path'];cache={}
        for c,n in cells:
            if c!=cov:continue
            events=M.event_sequence(scene,path,n);executable=bool(prefix['reached'] and len(events)==n)
            for policy in policies:
                start=time.time();result=solve(room,scene['inventory'],events,path,policy,cache=cache);score=M.score_instances(result['boxes'],scene['gt'])
                if not executable:score=M.score_instances({},scene['gt'])
                rows.append({'policy':policy,'coverage':c,'visits':n,'executable':executable,'coverage_actual':float(prefix['coverage_free']),'walk_m':float(prefix['walk_m']),'unique_contacts':len({(e['object'],*e['pos']) for e in events}),'events':events,'status':result['status'],'search_nodes':result.get('search_nodes',0),'fallback_used':result.get('fallback_used',False),'attempts':result.get('attempts',[]),'elapsed_s':time.time()-start,'score':score,'whole_iou0_5':bool(executable and footprint_all(result['boxes'],scene['gt'])),'boxes':{k:np.asarray(v).tolist() for k,v in result['boxes'].items()}})
    record={'scene':scene['scene'],'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'counts':scene['counts'],'rows':rows};target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(record),encoding='utf-8');tmp.replace(target);return record


def run(native,out,policies=POLICIES,cells=((1.,14),),limit=None,workers=6):
    files=sorted(Path(native).glob('*.json'));files=files if limit is None else files[:limit];out=Path(out);out.mkdir(parents=True,exist_ok=True)
    protocol={'n_rooms':len(files),'policies':policies,'cells':cells,'known_wall_tolerance_m':.15,'node_limit':20000,'candidate_limit':64,'fixed_denominator':True,'stage':'development' if len(policies)>1 else 'frozen confirmation','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};(out/'protocol.json').write_text(json.dumps(protocol,indent=1),encoding='utf-8');records=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for i,r in enumerate(pool.map(one,[(str(f),str(out/'rooms'/f.name),policies,cells) for f in files]),1):
            records.append(r)
            if i%25==0:print(json.dumps({'rooms':i,'total':len(files)}),flush=True)
    rows=[]
    for c,n in cells:
        for policy in policies:
            group=[r for q in records for r in q['rows'] if r['coverage']==c and r['visits']==n and r['policy']==policy];assert len(group)==len(files)
            rows.append({'policy':policy,'coverage':c,'visits':n,'n':len(files),'whole':sum(r['score']['all_instances_hit'] for r in group),'f1':float(np.mean([r['score']['f1'] for r in group])),'whole_iou0_5':sum(r['whole_iou0_5'] for r in group),'median_nodes':float(np.median([r['search_nodes'] for r in group])),'total_seconds':sum(r['elapsed_s'] for r in group)})
    summary={'protocol':protocol,'rows':rows};(out/'summary.json').write_text(json.dumps(summary,indent=1),encoding='utf-8');print(json.dumps(rows),flush=True);return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--policies',nargs='+',default=POLICIES);p.add_argument('--cells',nargs='+',default=['1:14']);p.add_argument('--limit',type=int);p.add_argument('--workers',type=int,default=6);a=p.parse_args();cells=[(float(c),int(n)) for c,n in (v.split(':') for v in a.cells)];run(a.native,a.out,a.policies,cells,limit=a.limit,workers=a.workers)
