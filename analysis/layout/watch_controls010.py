"""Matched controls on the frozen100 short raw joint-input episodes."""
import argparse,concurrent.futures,json
from pathlib import Path
import numpy as np
from . import action_model as AM,multi_instance as M
from .contact_contract import contacts_from_runs,decode
from .inertial_replay import rest_attitude,estimate
from .watch_cabinet import load,fuse
from .wrist_binary import predict
from .activity_audit import paired_binary


def one(task):
    source,native,model,old=map(Path,task);r=json.loads((source/'results.json').read_text());session=source/'input';priors=r['priors'];ch=AM.load_phone(session);t,A,_=ch['accelerometer'];tg,G,_=ch['gyroscope'];G=np.c_[*[np.interp(t,tg,G[:,j]) for j in range(3)]];R=rest_attitude(t,A,G);path,_=estimate(t,A,G,R)
    phone=next(a['prediction'] for a in r['rows'] if a['arm']=='phone_only');wt,wa=load(session,1700000000000000000);scene=M.load_native(native);truth={k.split('#')[0]:b for k,b in scene['gt'].items()};rows=[]
    for name,artifact,shift in [('same_learned_watch',model,0.),('old_real_only_watch',old,0.),('wrong_clock10s',model,10.),('watch_absent',None,0.)]:
        wrist={'runs':[]} if artifact is None else predict(wt+shift,wa,artifact,budget_s=t[-1]);runs=fuse({'runs':phone['runs']},wrist)['runs'];contacts=contacts_from_runs(t,path,R,runs);walk=np.zeros(len(t),bool)
        for label,a,b in runs:
            if label=='walk':walk|=(t>=a)&(t<=b)
        pred=decode(priors['room'],priors['start'],path,contacts,priors['sizes'],walk);score=M.score_instances(pred['boxes'],truth);rows.append({'arm':name,'score':score,'watch_runs':wrist['runs'],'cabinet_source':'watch_only','phone_cabinet_used':False})
    baseline=next(a['score'] for a in r['rows'] if a['arm']=='joint_learned_watch')
    return {'scene':source.name,'baseline_equal':rows[0]['score']==baseline,'rows':rows}


def run(source,native,model,old,out,workers=3):
    source,native,model,old,out=map(Path,(source,native,model,old,out));cases=sorted(p for p in source.glob('multi-*') if (p/'results.json').exists())
    if len(cases)!=100:raise ValueError('All100 cases required')
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:records=list(pool.map(one,[(str(p),str(native/(p.name+'.json')),str(model),str(old)) for p in cases]))
    arms=[a['arm'] for a in records[0]['rows']];flags={a:[next(r['score']['all_instances_hit'] for r in d['rows'] if r['arm']==a) for d in records] for a in arms}
    summary={a:{'whole':sum(flags[a]),'f1':float(np.mean([r['score']['f1'] for d in records for r in d['rows'] if r['arm']==a]))} for a in arms}
    result={'n':100,'baseline_differences':sum(not r['baseline_equal'] for r in records),'rows':summary,'paired_old_vs_new':paired_binary(flags['old_real_only_watch'],flags['same_learned_watch']),'scope':'Matched frozen short four-object controlled raw episodes; shared clock; not the10000-room geometric experiment','records':records};out.write_text(json.dumps(result,indent=1));print(json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--native',required=True);p.add_argument('--model',required=True);p.add_argument('--old',required=True);p.add_argument('--out',required=True);p.add_argument('--workers',type=int,default=3);a=p.parse_args();run(a.source,a.native,a.model,a.old,a.out,a.workers)
