"""Matched wrist timing/absence controls without rerunning phone models.

Cached phone predictions are immutable outputs of the actual raw-signal model.
Positions and attitude are recomputed from raw phone signals, never from truth.
"""
import argparse,concurrent.futures,json
from pathlib import Path
import numpy as np
from . import action_model as AM,multi_instance as M
from .contact_contract import contacts_from_runs,decode
from .inertial_replay import rest_attitude,estimate
from .watch_cabinet import load,detect,fuse
from .activity_audit import paired_binary


def one(task):
    source,native=map(Path,task);r=json.loads((source/'results.json').read_text());session=source/'input';priors=r['priors'];ch=AM.load_phone(session);t,A,_=ch['accelerometer'];tg,G,_=ch['gyroscope'];G=np.c_[*[np.interp(t,tg,G[:,j]) for j in range(3)]];R=rest_attitude(t,A,G);path,_=estimate(t,A,G,R)
    phone=next(a['prediction'] for a in r['rows'] if a['arm']=='phone_only');wt,wa=load(session,1700000000000000000);scene=M.load_native(native);truth={k.split('#')[0]:b for k,b in scene['gt'].items()};rows=[]
    for name,shift in [('correct_watch',0.),('clock_shift_10s',10.),('watch_absent',None)]:
        wrist={'runs':[]} if shift is None else detect(wt+shift,wa,budget_s=t[-1],phone=(t,A,G));runs=fuse({'runs':phone['runs']},wrist)['runs'];contacts=contacts_from_runs(t,path,R,runs);walk=np.zeros(len(t),bool)
        for label,a,b in runs:
            if label=='walk':walk|=(t>=a)&(t<=b)
        pred=decode(priors['room'],priors['start'],path,contacts,priors['sizes'],walk);score=M.score_instances(pred['boxes'],truth);rows.append({'arm':name,'score':score,'watch_runs':wrist['runs']})
    original=next(a['score'] for a in r['rows'] if a['arm']=='joint_rule_watch')
    return {'scene':source.name,'baseline_replay_equal':rows[0]['score']==original,'rows':rows}


def run(source,native,out,workers=3):
    source,native,out=map(Path,(source,native,out));cases=sorted(p for p in source.glob('multi-*') if (p/'results.json').exists());records=[]
    if len(cases)!=100:raise ValueError('All100 fixed cases required')
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:records=list(pool.map(one,[(str(p),str(native/(p.name+'.json'))) for p in cases]))
    summary={arm:{'whole_hits':sum(a['score']['all_instances_hit'] for r in records for a in r['rows'] if a['arm']==arm),'f1':float(np.mean([a['score']['f1'] for r in records for a in r['rows'] if a['arm']==arm]))} for arm in ['correct_watch','clock_shift_10s','watch_absent']}
    flags={arm:[next(a['score']['all_instances_hit'] for a in r['rows'] if a['arm']==arm) for r in records] for arm in summary}
    result={'n_rooms':100,'scope':'Exploratory matched controls for synthetic-domain wrist-rule branch, not the failed real-trained RF transfer arm','baseline_replay_differences':sum(not r['baseline_replay_equal'] for r in records),'summary':summary,'paired_clock':paired_binary(flags['clock_shift_10s'],flags['correct_watch']),'rows':records};out.write_text(json.dumps(result,indent=1),encoding='utf-8');print(json.dumps(summary));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--workers',type=int,default=3);a=p.parse_args();run(a.source,a.native,a.out,a.workers)
