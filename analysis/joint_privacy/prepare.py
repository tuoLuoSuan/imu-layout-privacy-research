"""Inspect existing paired originals and emit features; never invent a classifier.

Without a checked clock file this remains a two-loader smoke check, not pairing.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from analysis.phone_ronin.prefix import load_arrival_session,prefix_inputs
from .inputs import load_watch,fit_clock,watch_features
from .output import write_json

def prepare(phone,watch,budget_s,clock_contract=None,*,watch_max_gap_s=.25):
    if watch_max_gap_s not in (.25,.5):raise ValueError('Disclosed watch feature-gap policy must be .25 or .5 seconds')
    a,g,aa,ga,source=load_arrival_session(phone);w=load_watch(watch)
    report={'status':'unverified_clock_pairing','research_validated':False,'joint_result':False,
        'phone_source':source,'watch_source':w['source'],'budget_s':budget_s,
        'phone_features':[],'watch_features':[],'walk_probabilities':None,
        'watch_feature_policy':{'window_s':1.,'stride_s':.25,'max_gap_s':watch_max_gap_s},
        'missing':['checked clock pairing','matched held-out activity models','independent spatial reference']}
    if not clock_contract:return report
    phone_sha=source['carrier_sha256'];watch_sha=w['source']['sha256']
    if clock_contract['phone_id']!=phone_sha or clock_contract['watch_id']!=watch_sha:
        raise ValueError('Clock contract must bind the exact original SHA256 identities')
    clock=fit_clock(clock_contract);clock.require_budget(budget_s)
    support=source['recorded_stop_s']
    if support is None:return dict(report,status='unknown_support')
    if budget_s>support:return dict(report,status='outside_recorded_session')
    ap,gp,diagnostic=prefix_inputs(a,g,aa,ga,budget_s)
    if min(len(ap),len(gp))<2:return dict(report,status='insufficient_sensor_context')
    watch_stop=w['source']['recorded_stop_epoch_ms']
    if watch_stop is None:return dict(report,status='watch_unsealed')
    if budget_s>clock.map_ms(watch_stop)-clock.uncertainty_s(clock.map_ms(watch_stop)):
        return dict(report,status='outside_watch_support')
    wf=watch_features(w['rows'],budget_s,clock=clock,max_gap_s=watch_max_gap_s)
    if not wf:return dict(report,status='insufficient_watch_feature_context')
    # Same trailing amplitude features for the phone-only comparator. Gyro RMS
    # is in measured rad/s; wrist gyro channels are deliberately absent.
    rows=[[i,r[0]*1000,*r[1:],'visible'] for i,r in enumerate(ap)]
    pf=watch_features(rows,budget_s,max_gap_s=.1)
    if not pf:return dict(report,status='insufficient_phone_feature_context')
    for f in pf:
        selected=[r for r in gp if f['window_start_s']<=r[0]<=f['window_end_s']]
        f['gyro_rms_rad_s']=float(np.sqrt(np.mean(np.square(np.asarray([r[1:] for r in selected]))))) if selected else None
        used=[receipt for r,receipt in zip(a,aa) if f['window_start_s']<=r[0]<=f['window_end_s'] and receipt<=budget_s]
        used+= [receipt for r,receipt in zip(g,ga) if f['window_start_s']<=r[0]<=f['window_end_s'] and receipt<=budget_s]
        f['available_s']=max(used) if used else None
    report.update(status='paired_features_only_no_classifier',phone_features=pf,watch_features=wf,
        clock_pairing=clock_contract,native_prefix_diagnostics=diagnostic,
        missing=['matched held-out activity models','independent spatial reference'],
        limits=['Motion features are not walk probabilities. No XGBoost model is trained.',
            'Clock uncertainty is propagated and checked; the supplied anchors remain an external measurement.',
            'Phone and wrist native rates stay separate; no invented six-axis wrist stream.'])
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phone',type=Path,required=True);p.add_argument('--watch',type=Path,required=True)
    p.add_argument('--clock',type=Path);p.add_argument('--budget',type=float,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--watch-max-gap',type=float,choices=(.25,.5),default=.25);args=p.parse_args()
    clock=json.loads(args.clock.read_text(encoding='utf-8')) if args.clock else None
    result=prepare(args.phone,args.watch,args.budget,clock,watch_max_gap_s=args.watch_max_gap);write_json(args.output,result)
    print(json.dumps({'status':result['status'],'output':str(args.output)},ensure_ascii=False))

if __name__=='__main__':main()
