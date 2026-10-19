"""Attack-only entry: phone model velocities + predicted activity probabilities.

No room dimensions, reference paths, region labels or radar inputs are accepted.
The output is visited-path evidence, with walls explicitly unknown.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from analysis.phone_ronin.adapter import integrate_centers
from .inputs import fit_clock
from .activity import minimum_shift_samples

KEYS={'schema_version','synthetic','paired_session_id','budget_s','support_end_s',
    'phone_predictions','probability_streams','probability_provenance','clock_contract','gate_policy','seed','observation_start_s'}

def apply_policy(probabilities,policy):
    p=np.asarray(probabilities,dtype=float)
    if not np.isfinite(p).all() or np.any((p<0)|(p>1)):raise ValueError('Finite probabilities in [0,1] required')
    if policy=={'mode':'soft'}:return p.copy()
    if set(policy)!={'mode','on','off'} or policy['mode']!='hysteresis' or not 0<=policy['off']<policy['on']<=1:
        raise ValueError('One explicit gate policy required for all learned/oracle gates')
    state=False;out=[]
    for value in p:
        if value>=policy['on']:state=True
        elif value<=policy['off']:state=False
        out.append(float(state))
    return np.asarray(out)

def _probabilities(stream,targets,budget,max_age_s=1.5,*,availability_mode='prefix_retrospective'):
    if availability_mode not in ('prefix_retrospective','target_time'):raise ValueError('Explicit probability timing mode required')
    eligible=[];previous=None
    for r in stream:
        if r.get('window_end_s',math.inf)>budget or r.get('available_s',math.inf)>budget:continue
        if set(r)!={'window_end_s','available_s','p_walk'} or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in r.values()):raise ValueError('Invalid activity probability row')
        if not 0<=r['p_walk']<=1 or r['available_s']<r['window_end_s']:raise ValueError('Invalid probability/availability')
        if previous is not None and r['window_end_s']<=previous:raise ValueError('Ordered probability rows required')
        previous=r['window_end_s'];eligible.append(r)
    values=[]
    for target in targets:
        candidates=[r for r in eligible if r['window_end_s']<=target and target-r['window_end_s']<=max_age_s
            and (availability_mode=='prefix_retrospective' or r['available_s']<=target)]
        if not candidates:return None
        values.append(candidates[-1]['p_walk'])
    return np.asarray(values)

def run_attack(document):
    if not isinstance(document,dict) or not KEYS.issubset(document) or set(document)-KEYS-{'probability_time_mode'} or document['schema_version']!=2:raise ValueError('Attack schema v2 rejects unknown inputs')
    mode=document.get('probability_time_mode','prefix_retrospective')
    if mode not in ('prefix_retrospective','target_time'):raise ValueError('Explicit probability timing mode required')
    budget=document['budget_s'];support=document['support_end_s']
    if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>0 for x in (budget,support)):raise ValueError('Positive finite budget/support required')
    start=document['observation_start_s']
    if not isinstance(start,(int,float)) or isinstance(start,bool) or not math.isfinite(start) or not 0<=start<budget:
        raise ValueError('Explicit finite task/observation origin required')
    result={'schema_version':2,'status':'not_ready','budget_s':float(budget),'probability_time_mode':mode,
        'paired_session_id':document['paired_session_id'],'synthetic':document['synthetic'],
        'observation_start_s':start,'task_exposure_s':budget-start,
        'research_validated':False,'walls':None,'variants':{},'gate_policy':document['gate_policy']}
    if budget>support:return dict(result,status='outside_recorded_session')
    rows=[]
    for r in document['phone_predictions']:
        if r.get('target_end_s',math.inf)>budget or r.get('available_s',math.inf)>budget:continue
        if r.get('target_end_s',-math.inf)-1<start:continue
        if set(r)!={'center_s','target_end_s','available_s','vx','vy'} or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in r.values()):raise ValueError('Invalid phone predictions')
        if not r['center_s']<r['target_end_s']<=r['available_s']:raise ValueError('Prediction availability precedes input support')
        rows.append(r)
    if len(rows)<2:return dict(result,status='insufficient_phone_context')
    t=np.asarray([r['center_s'] for r in rows]);ends=np.asarray([r['target_end_s'] for r in rows]);v=np.asarray([[r['vx'],r['vy']] for r in rows])
    if np.any(np.diff(t)<=0) or np.any(np.diff(ends)<=0):raise ValueError('Ordered unique predictions required')
    if np.max(np.diff(t))>.25:return dict(result,status='phone_prediction_gap')
    result.update(center_times_s=t.tolist(),target_ends_s=ends.tolist(),phone_velocities=v.tolist(),
        integration='trapezoid between model centers; not position at observation cutoff')
    # A missing wrist model/clock must not block the phone-only + oracle
    # mechanism check. It must also never fabricate a joint result.
    base=integrate_centers(t,v)
    result['variants']['phone']={'velocities':v.tolist(),'positions':base.tolist(),'gate_values':np.ones(len(t)).tolist(),
        'modeled_path_m':float(np.linalg.norm(np.diff(base,axis=0),axis=1).sum())}
    try:
        clock=fit_clock(document['clock_contract']);clock.require_budget(budget)
    except (ValueError,TypeError):return dict(result,status='unverified_clock_pairing')
    if document['clock_contract']['paired_session_id']!=document['paired_session_id']:
        return dict(result,status='unverified_clock_pairing')
    provenance=document['probability_provenance']
    names={'phone','joint','shifted_watch','shifted_phone'}
    if not isinstance(document['synthetic'],bool) or set(provenance)!=names:raise ValueError('Explicit probability provenance required')
    for name in names:
        p=provenance[name]
        if set(p)-{'paired_session_id','synthetic','trained_model_id','held_out_split_id','training_data_id','model_sha256',
            'shift_samples','shift_scope','phone_features_unchanged','watch_features_unchanged','feature_stride_s'}:
            raise ValueError('Unknown activity provenance fields')
        if p.get('paired_session_id')!=document['paired_session_id'] or p.get('synthetic')!=document['synthetic']:
            return dict(result,status='unverified_probability_provenance')
        if not document['synthetic'] and (not p.get('trained_model_id') or not p.get('held_out_split_id') or not p.get('training_data_id') or len(p.get('model_sha256',''))!=64):
            return dict(result,status='unverified_probability_provenance')
        if not document['synthetic'] and any(c not in '0123456789abcdef' for c in p['model_sha256']):raise ValueError('Lowercase model SHA256 required')
    if not document['synthetic'] and any(provenance['phone'].get(k)!=provenance['joint'].get(k) for k in ('held_out_split_id','training_data_id')):
        return dict(result,status='unmatched_activity_training_or_split')
    streams=document['probability_streams']
    if set(streams)!=names:raise ValueError('Matched phone/joint and both feature-mismatch streams required')
    admitted=[r['window_end_s'] for r in streams['joint'] if r.get('window_end_s',math.inf)<=budget and r.get('available_s',math.inf)<=budget]
    if len(admitted)<2:return dict(result,status='incomplete_probability_coverage')
    for name,scope,unchanged in [('shifted_watch','wrist','phone'),('shifted_phone','phone','watch')]:
        mismatch=provenance[name];shift=mismatch.get('shift_samples');stride=mismatch.get('feature_stride_s')
        if mismatch.get('shift_scope')!='same_session_'+scope+'_features_before_joint_inference' or mismatch.get(unchanged+'_features_unchanged') is not True or not isinstance(shift,int) or isinstance(shift,bool) or shift<=0:
            return dict(result,status='missing_feature_mismatch_control')
        if not document['synthetic'] and any(mismatch.get(k)!=provenance['joint'].get(k) for k in ('model_sha256','trained_model_id','held_out_split_id','training_data_id')):
            return dict(result,status='unmatched_mismatch_control_model')
        if not isinstance(stride,(int,float)) or not math.isfinite(stride) or stride<=0 or len(admitted)<2:
            return dict(result,status='unknown_mismatch_time_separation')
        if stride>min(np.diff(admitted))+1e-9:return dict(result,status='invalid_mismatch_feature_stride')
        required=minimum_shift_samples(clock.uncertainty_s(budget),stride)
        if min(shift,len(admitted)-shift)<required:return dict(result,status='mismatch_below_clock_uncertainty')
    selected={name:_probabilities(streams[name],ends,budget,availability_mode=mode) for name in streams}
    if any(p is None for p in selected.values()):return dict(result,status='incomplete_probability_coverage')
    gates={name:apply_policy(p,document['gate_policy']) for name,p in selected.items()}
    joint=gates['joint'];seed=document['seed']
    if not isinstance(seed,int) or isinstance(seed,bool) or seed<0:raise ValueError('Fixed nonnegative seed required')
    rng=np.random.default_rng(seed)
    shift=max(1,len(joint)//2)
    controls={'phone':np.ones(len(t)),'phone_gated':gates['phone'],'joint_gated':joint,
        'constant':np.full(len(t),joint.mean()),'shuffled':rng.permutation(joint),
        'circular_shift':np.roll(joint,shift),'watch_misaligned':gates['shifted_watch'],'phone_misaligned':gates['shifted_phone']}
    for name,gate in controls.items():
        velocity=v*gate[:,None];positions=integrate_centers(t,velocity)
        result['variants'][name]={'velocities':velocity.tolist(),'positions':positions.tolist(),'gate_values':gate.tolist(),
            'modeled_path_m':float(np.linalg.norm(np.diff(positions,axis=0),axis=1).sum())}
    result.update(status='synthetic_pipeline_only' if document['synthetic'] else 'joint_candidate_unvalidated',
        gate_diagnostics={'joint_mean':float(joint.mean()),'constant_mean':float(controls['constant'].mean()),
            'joint_values':joint.tolist(),'shuffled_values':controls['shuffled'].tolist(),
            'circular_shift_values':controls['circular_shift'].tolist(),'circular_shift_samples':shift,
            'primary_mismatch':'same-session wrist features shifted before the same joint classifier; phone fixed',
            'secondary_score_mismatch':'circular_shift of final gate is an additional diagnostic, not wrist-feature mismatch',
            'negative_controls':'offline within this prefix; not causal per-window deployments',
            'path_reduction_is_not_evidence_of_benefit':True},
        clock_uncertainty_at_budget_s=clock.uncertainty_s(budget))
    return result

def main():
    from .output import write_json
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--probability-time-mode',choices=('prefix_retrospective','target_time'))
    args=p.parse_args();document=json.loads(args.input.read_text(encoding='utf-8'))
    if args.probability_time_mode:document['probability_time_mode']=args.probability_time_mode
    value=run_attack(document)
    write_json(args.output,value);print(json.dumps({'output':str(args.output),'status':value['status']}))

if __name__=='__main__':main()
