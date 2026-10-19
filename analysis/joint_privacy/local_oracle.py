"""Evaluation-only, separate local oracle fragments with explicit unknowns.

Phone-only baseline, soft gates and complete 1s targets only. This does not
authenticate the caller's timing/labels or stitch paths across excluded gaps.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from analysis.phone_ronin.adapter import integrate_centers
from .evaluation import evaluate
from .output import write_json


def _keys(value,keys):
    if not isinstance(value,dict) or set(value)!=set(keys):raise ValueError('Exact local reference schema required')


def _number(value,positive=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Finite numeric local times required')
    if positive and value<=0:raise ValueError('Positive local timing required')
    return float(value)


def evaluate_local_segments(attack,reference):
    """Score declared common interiors separately; unobserved is never still."""
    _keys(reference,{'schema_version','reference_source_id','time_resolution_s','timing_support_accepted',
        'interval_basis','maximum_center_gap_s','intervals','excluded_intervals_s'})
    if type(reference['schema_version']) is not int or reference['schema_version']!=1:raise ValueError('Local reference version 1 required')
    if not isinstance(reference['reference_source_id'],str) or not reference['reference_source_id'].strip():
        raise ValueError('Independent reference source identity required')
    if type(reference['timing_support_accepted']) is not bool:raise ValueError('Explicit timing acceptance declaration required')
    if reference['interval_basis']!='declared_common_interiors':raise ValueError('Use already propagated common interiors')
    resolution=_number(reference['time_resolution_s'],True);gap=_number(reference['maximum_center_gap_s'],True)
    intervals=reference['intervals'];excluded=reference['excluded_intervals_s']
    if not isinstance(intervals,list) or not isinstance(excluded,list):raise ValueError('Explicit interval lists required')
    previous=-math.inf;ids=set()
    for r in intervals:
        _keys(r,{'id','start_s','end_s','activity'})
        if not isinstance(r['id'],str) or not r['id'].strip() or r['id'] in ids:raise ValueError('Unique reference interval identity required')
        ids.add(r['id']);a=_number(r['start_s']);b=_number(r['end_s'])
        if not previous<=a<b:raise ValueError('Ordered nonoverlapping reference intervals required')
        if r['activity'] not in ('walk','nonwalk','unknown'):raise ValueError('Explicit local activity required')
        previous=b
    previous=-math.inf
    for r in excluded:
        if not isinstance(r,list) or len(r)!=2:raise ValueError('Explicit excluded interval required')
        a,b=map(_number,r)
        if not previous<=a<b:raise ValueError('Ordered nonoverlapping excluded intervals required')
        previous=b
    if attack.get('gate_policy')!={'mode':'soft'}:raise ValueError('Local fragments support soft policy only; no stateful resets')
    if type(attack.get('synthetic')) is not bool:raise ValueError('Explicit synthetic flag required')
    budget=_number(attack['budget_s'],True);origin=_number(attack['observation_start_s'])
    if origin>=budget:raise ValueError('Ordered observation interval required')
    t=np.asarray(attack['center_times_s'],dtype=float);ends=np.asarray(attack['target_ends_s'],dtype=float)
    v=np.asarray(attack['phone_velocities'],dtype=float)
    if t.ndim!=1 or not len(t) or ends.shape!=t.shape or v.shape!=(len(t),2) or not all(np.isfinite(x).all() for x in (t,ends,v)):
        raise ValueError('Finite matching model targets and velocities required')
    if np.any(np.diff(t)<=0) or np.any(ends>budget) or np.any(ends-1<origin) or not np.allclose(t,ends-.5,rtol=0,atol=1e-9):
        raise ValueError('Complete ordered one-second targets inside original budget required')
    if set(attack['variants'])!={'phone'}:raise ValueError('Phone-only baseline input required before learned joint evaluation')
    phone=attack['variants']['phone']
    if not np.array_equal(np.asarray(phone['velocities'],dtype=float),v) or phone['gate_values']!=[1.]*len(t):
        raise ValueError('Consistent ungated phone baseline required')
    result={'status':'unverified_reference_timing','synthetic':attack['synthetic'],'reference_source_id':reference['reference_source_id'],
        'research_validated':False,'clock_verified':False,'caller_declarations_authenticated':False,
        'observation_start_s':origin,'observation_budget_s':budget,'eligible_target_indices':[],
        'excluded_indices':{'marker_overlap':[],'unknown_or_uncovered':[],'singleton':[]},
        'segments':[],'global_trajectory':None,'aggregate_path_m':None,'wall_error_m':None,'joint_result':False,
        'scoring_exclusion_reduces_observation_budget':False,
        'limits':'Only local modeled motion, not position error or wrist benefit; timing and action declarations require external evidence.'}
    if not reference['timing_support_accepted']:return result
    admitted=[]
    for i,e in enumerate(ends):
        a=e-1
        if any(a<b and x<e for x,b in excluded):result['excluded_indices']['marker_overlap'].append(i);continue
        r=next((r for r in intervals if r['start_s']<=a and e<=r['end_s']),None)
        if r is None or r['activity']=='unknown':result['excluded_indices']['unknown_or_uncovered'].append(i);continue
        admitted.append((i,r))
    result['eligible_target_indices']=[i for i,r in admitted]
    groups=[]
    for i,r in admitted:
        if not groups or i!=groups[-1][-1][0]+1 or r['id']!=groups[-1][-1][1]['id'] or t[i]-t[groups[-1][-1][0]]>gap:
            groups.append([])
        groups[-1].append((i,r))
    for group in groups:
        ix=[i for i,r in group];r=group[0][1]
        if len(ix)<2:result['excluded_indices']['singleton'].extend(ix);continue
        tt=t[ix];vv=v[ix];ee=ends[ix];pp=integrate_centers(tt,vv)
        path=float(np.linalg.norm(np.diff(pp,axis=0),axis=1).sum())
        local={'synthetic':attack['synthetic'],'budget_s':budget,'observation_start_s':float(ee[0]-1),
            'center_times_s':tt.tolist(),'target_ends_s':ee.tolist(),'phone_velocities':vv.tolist(),
            'gate_policy':{'mode':'soft'},'variants':{'phone':{'positions':pp.tolist(),'velocities':vv.tolist(),
                'gate_values':[1.]*len(ix),'modeled_path_m':path}}}
        ref={'schema_version':1,'reference_source_id':reference['reference_source_id'],'time_resolution_s':resolution,
            'reference_coverage_s':[float(ee[0]-1),float(ee[-1])],
            'walk_intervals_s':[[float(ee[0]-1),float(ee[-1])]] if r['activity']=='walk' else [],
            'region_events':[],'regions':{},'alignment':None}
        metrics=evaluate(local,ref)['temporal_metrics'];oracle=metrics['oracle_diagnostic']
        result['segments'].append({'reference_interval_id':r['id'],'activity':r['activity'],'source_indices':ix,
            'target_support_s':ref['reference_coverage_s'],'center_support_s':[float(tt[0]),float(tt[-1])],
            'local_phone_positions':pp.tolist(),'phone_model_path_m':path,
            'oracle_model_path_m':oracle['modeled_distance_during_reference_walk_m']+oracle['modeled_distance_during_reference_nonwalk_m'],
            'temporal_metrics':metrics})
    result['status']='local_oracle_diagnostic_only' if result['segments'] else 'no_supported_local_segments'
    return result


def _pairs(pairs):
    value={}
    for k,v in pairs:
        if k in value:raise ValueError('Duplicate JSON key: '+k)
        value[k]=v
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('attack',type=Path);p.add_argument('reference',type=Path)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    def read(path):return json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=_pairs)
    result=evaluate_local_segments(read(args.attack),read(args.reference));write_json(args.output,result)
    print(json.dumps({'status':result['status'],'segments':len(result['segments']),'output':str(args.output)}))


if __name__=='__main__':main()
