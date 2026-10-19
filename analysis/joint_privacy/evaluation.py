"""Evaluation-only references, region metrics and oracle mechanism diagnosis.

This entry may read independent geometry/labels. Attack code never imports it.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from .attack import apply_policy
from analysis.phone_ronin.adapter import integrate_centers

def _overlap(start,end,intervals):
    return sum(max(0.,min(end,b)-max(start,a)) for a,b in intervals)

def _validate_reference(reference):
    required={'schema_version','reference_source_id','time_resolution_s','reference_coverage_s',
        'walk_intervals_s','region_events','regions','alignment'}
    if set(reference)!=required or reference['schema_version']!=1 or not reference['reference_source_id']:
        raise ValueError('Independent reference contract required')
    if not math.isfinite(reference['time_resolution_s']) or reference['time_resolution_s']<=0:raise ValueError('Reference temporal resolution required')
    intervals=reference['walk_intervals_s'];previous=-math.inf
    for a,b in intervals:
        if not (math.isfinite(a) and math.isfinite(b) and previous<=a<b):raise ValueError('Ordered nonoverlapping walk intervals required')
        previous=b
    lo,hi=reference['reference_coverage_s']
    if not math.isfinite(lo) or not math.isfinite(hi) or lo>=hi:raise ValueError('Reference time coverage required')

def oracle_diagnostic(attack,reference):
    """Use future/manual labels only inside this explicitly privileged diagnosis."""
    _validate_reference(reference)
    if not attack.get('variants'):return {'status':'attack_not_ready','gate_policy':attack['gate_policy']}
    t=np.asarray(attack['center_times_s']);ends=np.asarray(attack['target_ends_s']);v=np.asarray(attack['phone_velocities'])
    lo,hi=reference['reference_coverage_s']
    if lo>min(ends-1) or hi<max(ends):return {'status':'reference_support_incomplete','gate_policy':attack['gate_policy']}
    probabilities=[_overlap(e-1,e,reference['walk_intervals_s']) for e in ends]
    gate=apply_policy(probabilities,attack['gate_policy']);velocity=v*gate[:,None]
    p=integrate_centers(t,velocity)
    return {'status':'oracle_diagnostic_only','gate_policy':attack['gate_policy'],
        'probability_definition':'fraction walking in the same 1-second model target interval',
        'positions':p.tolist(),'velocities':velocity.tolist(),'gate_values':gate.tolist(),
        'modeled_path_m':float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum()),
        'reference_time_resolution_s':reference['time_resolution_s'],
        'deployment_input':False}

def _temporal_metrics(times,positions,intervals):
    walk=nonwalk=0.
    for a,b,x,y in zip(times,times[1:],positions,positions[1:]):
        fraction=_overlap(a,b,intervals)/(b-a);distance=float(np.linalg.norm(np.asarray(y)-x))
        walk+=distance*fraction;nonwalk+=distance*(1-fraction)
    return {'modeled_distance_during_reference_walk_m':walk,
        'modeled_distance_during_reference_nonwalk_m':nonwalk,
        'metric_is_not_position_error':True}

def _region_scores(points,regions,actual):
    predicted=set()
    for name,box in regions.items():
        if len(box)!=4 or not all(math.isfinite(v) for v in box) or not(box[0]<box[2] and box[1]<box[3]):raise ValueError('Finite measured region rectangles required')
        if any(box[0]<=x<=box[2] and box[1]<=y<=box[3] for x,y in points):predicted.add(name)
    tp=len(predicted&actual);precision=tp/len(predicted) if predicted else None;recall=tp/len(actual) if actual else None
    f1=2*tp/(len(predicted)+len(actual)) if predicted or actual else None
    return {'predicted':sorted(predicted),'reference':sorted(actual),'precision':precision,'recall':recall,
        'f1':f1,'false_regions':sorted(predicted-actual),'missed_regions':sorted(actual-predicted),
        'sampling':'model-center points only; no interpolated human ground-truth trajectory'}

def evaluate(attack,reference):
    _validate_reference(reference)
    report={'status':'evaluation_only','synthetic':attack['synthetic'],'research_validated':False,
        'spatial_status':'attack_not_ready','spatial_metrics':None,'wall_error_m':None,
        'reference_source_id':reference['reference_source_id'],'time_resolution_s':reference['time_resolution_s']}
    if not attack.get('variants'):return report
    times=attack['center_times_s'];lo,hi=reference['reference_coverage_s']
    if lo>times[0] or hi<times[-1]:return dict(report,spatial_status='reference_support_incomplete')
    report.update(evaluation_end_s=times[-1],observation_budget_s=attack['budget_s'],
        model_unscored_tail_s=attack['budget_s']-times[-1])
    variants=dict(attack['variants']);oracle=oracle_diagnostic(attack,reference)
    if oracle['status']=='oracle_diagnostic_only':variants['oracle_diagnostic']=oracle
    report['temporal_metrics']={name:_temporal_metrics(times,v['positions'],reference['walk_intervals_s']) for name,v in variants.items()}
    walk_weight=np.asarray([_overlap(e-1,e,reference['walk_intervals_s']) for e in attack['target_ends_s']])
    for name,v in variants.items():
        gate=np.asarray(v['gate_values']);walk_sum=walk_weight.sum();nonwalk_sum=(1-walk_weight).sum()
        retained=float(gate@walk_weight/walk_sum) if walk_sum>0 else None
        report['temporal_metrics'][name].update(walk_gate_mean=retained,
            walk_gate_suppression_fraction=1-retained if retained is not None else None,
            nonwalk_gate_mean=float(gate@(1-walk_weight)/nonwalk_sum) if nonwalk_sum>0 else None,
            gate_metric='reference target-window-weighted scale retention; not discrete classification accuracy')
    baseline=report['temporal_metrics']['phone']['modeled_distance_during_reference_walk_m']
    for v in report['temporal_metrics'].values():
        v['walk_model_distance_retained_fraction']=v['modeled_distance_during_reference_walk_m']/baseline if baseline>0 else None
    alignment=reference['alignment']
    if alignment is None:return dict(report,spatial_status='unknown_coordinate_alignment')
    if set(alignment)!={'rotation_rad','translation_xy_m','reference_source_id','fit_used_this_test_output'} or alignment['fit_used_this_test_output'] is not False or not alignment['reference_source_id']:
        raise ValueError('Independent coordinate alignment required; no fitting to test errors')
    angle=alignment['rotation_rad'];translation=np.asarray(alignment['translation_xy_m'],dtype=float)
    if not math.isfinite(angle) or translation.shape!=(2,) or not np.isfinite(translation).all():raise ValueError('Finite 2D alignment required')
    rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
    # Region events in the prefix only; the layout lives solely on this side.
    actual={r['region'] for r in reference['region_events'] if attack['observation_start_s']<=r['time_s']<=times[-1]}
    if not actual.issubset(reference['regions']):raise ValueError('Unknown reference region')
    report['spatial_metrics']={name:_region_scores(np.asarray(v['positions'])@rotation.T+translation,
        reference['regions'],actual) for name,v in variants.items()}
    report.update(spatial_status='region_evidence_only',oracle_status=oracle['status'],
        evaluation_end_s=times[-1],observation_budget_s=attack['budget_s'],
        model_unscored_tail_s=attack['budget_s']-times[-1],
        limits='Region access is visited-space evidence, not inferred walls, doors or full room area')
    return report

def main():
    from .output import write_json
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('attack',type=Path);p.add_argument('reference',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=evaluate(json.loads(args.attack.read_text(encoding='utf-8')),json.loads(args.reference.read_text(encoding='utf-8')))
    write_json(args.output,result);print(json.dumps({'output':str(args.output),'status':result['spatial_status']}))

if __name__=='__main__':main()
