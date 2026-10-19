"""Synthetic software exercise only. No research, hardware or layout validation."""
import argparse
from pathlib import Path
import numpy as np
from .attack import run_attack
from .evaluation import evaluate
from .output import write_json
from .activity import paired_activity_probabilities
from .inputs import fit_clock

def fixture():
    times=np.arange(1.5,7.51,.1);ends=times+.5;predictions=[];joint=[];phone=[]
    for t,end in zip(times,ends):
        # Deliberately add false movement outside the synthetic walk interval.
        walk=2.<=t<5.;predictions.append({'center_s':float(t),'target_end_s':float(end),
            'available_s':float(end+.01),'vx':1. if walk else .2,'vy':0.})
        joint.append({'window_end_s':float(end),'available_s':float(end+.01),'p_walk':.95 if walk else .05})
        phone.append({'window_end_s':float(end),'available_s':float(end+.01),'p_walk':.8 if walk else .3})
    clock={'phone_id':'synthetic-phone','watch_id':'synthetic-watch','paired_session_id':'synthetic-pair',
        'mode':'synthetic_fixture','anchors':[{'watch_epoch_ms':1_000_000.,'phone_s':0.,'uncertainty_s':.001},
            {'watch_epoch_ms':1_001_000.,'phone_s':1.,'uncertainty_s':.001}],
        'checks':[{'watch_epoch_ms':1_000_500.,'phone_s':.5,'uncertainty_s':.001}],
        'available_s':1.01,'valid_until_s':10.,'drift_bound_ppm':100.,'max_uncertainty_s':.1}
    # Known synthetic toy scores; explicitly no classifier learning or real data.
    phone_features=np.array([[r['p_walk']] for r in phone]);wrist_features=np.array([[r['p_walk']] for r in joint])
    shift=max(1,len(joint)//2)
    controls=paired_activity_probabilities(phone_features,wrist_features,lambda f:.2*f[:,0]+.8*f[:,1],shift_samples=shift,
        target_end_s=ends,availability_s=ends+.01,budget_s=8.1,clock_uncertainty_s=fit_clock(clock).uncertainty_s(8.1))
    shifted=[];phone_shifted=[]
    for i,r in enumerate(joint):
        r['p_walk']=float(controls['joint'][i]);shifted.append(dict(r,p_walk=float(controls['shifted_watch'][i])))
        phone_shifted.append(dict(r,p_walk=float(controls['shifted_phone'][i])))
    provenance={name:{'paired_session_id':'synthetic-pair','synthetic':True,'trained_model_id':None} for name in ('phone','joint','shifted_watch','shifted_phone')}
    provenance['shifted_watch'].update(shift_samples=shift,shift_scope='same_session_wrist_features_before_joint_inference',phone_features_unchanged=True,feature_stride_s=.1)
    provenance['shifted_phone'].update(shift_samples=shift,shift_scope='same_session_phone_features_before_joint_inference',watch_features_unchanged=True,feature_stride_s=.1)
    attack={'schema_version':2,'synthetic':True,'paired_session_id':'synthetic-pair','budget_s':8.1,'support_end_s':9.,
        'observation_start_s':0.,
        'phone_predictions':predictions,'probability_streams':{'phone':phone,'joint':joint,'shifted_watch':shifted,'shifted_phone':phone_shifted},
        'probability_provenance':provenance,'clock_contract':clock,'gate_policy':{'mode':'soft'},'seed':58}
    reference={'schema_version':1,'reference_source_id':'synthetic-independent-reference','time_resolution_s':.1,
        'reference_coverage_s':[0.,9.],'walk_intervals_s':[[2.,5.]],
        'region_events':[{'time_s':2.,'region':'R1'},{'time_s':4.,'region':'R2'}],
        'regions':{'R1':[-.2,-.5,1.5,.5],'R2':[2.,-.5,3.5,.5],'R3':[4.,-.5,5.,.5]},
        'alignment':{'rotation_rad':0.,'translation_xy_m':[0.,0.],
            'reference_source_id':'synthetic-coordinate-marker','fit_used_this_test_output':False}}
    return attack,reference

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    a,r=fixture();attack=run_attack(a);evaluation=evaluate(attack,r)
    for name,value in [('synthetic-attack-input.json',a),('synthetic-eval-reference.json',r),
            ('synthetic-attack-output.json',attack),('synthetic-eval-output.json',evaluation)]:
        write_json(args.output/name,value)
    print('Synthetic pipeline only: '+str(args.output))

if __name__=='__main__':main()
