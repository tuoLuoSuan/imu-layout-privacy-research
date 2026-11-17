"""Controlled080 fine-tuning: matched targets, finite padding, real minibatches.

Requires the COMPLETE frozen training export. Never imports/trains on test or
confirmation data. The existing080 model is the step-zero candidate.
"""
import argparse
from collections import defaultdict,Counter
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from analysis.layout.recovery076_data import read,sha,dump,validate_manifest
from analysis.layout.multi_instance import score_instances
from analysis.layout.recovery076_eval import score
from analysis.layout.recovery080_refine import Refine080,build_view


def load_k6_views(path,metas):
    extra={};seen=set();failures=[]
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        r=json.loads(line)
        if r['id'] in seen or r['id'] not in metas:raise ValueError('Duplicate/unknown K6 view ID')
        seen.add(r['id']);meta=metas[r['id']]
        if meta['contacts_requested']!=6 or r['split']!=meta['split'] or meta['split'] not in ('train','validation'):
            raise ValueError('K6 views must contain only explicit train/validation K6 IDs')
        if meta['status']!='ok':
            if r.get('boxes'):raise ValueError('Acquisition failure has nonempty K6 prediction')
            failures.append(r['id']);continue
        extra[r['id']]=r
    wanted={r['id'] for r in metas.values() if r['status']=='ok' and r['contacts_requested']==6 and r['split'] in ('train','validation')}
    if set(extra)!=wanted:raise ValueError('Incomplete K6 A/B views')
    return extra,failures


def match_targets(boxes,truth):
    for name,values in [('prediction',boxes),('truth',truth)]:
        for key,value in values.items():
            v=np.asarray(value,float)
            if v.shape!=(4,) or not np.isfinite(v).all() or np.any(v[2:]<=v[:2]):
                raise ValueError('Invalid actual '+name+' rectangle: '+key)
    matching=score_instances(boxes,truth,.5)['matches']
    if len(matching)!=len(boxes) or len(boxes)!=len(truth):raise ValueError('Incomplete category matching')
    mapping={m['prediction']:m['truth'] for m in matching};keys=sorted(boxes)
    return keys,np.asarray([truth[mapping[k]] for k in keys],np.float32)


def project(delta,boxes,room):
    size=boxes[...,2:]-boxes[...,:2];centre=(boxes[...,:2]+boxes[...,2:])/2+delta
    centre=torch.minimum(torch.maximum(centre,size/2),room-size/2)
    return torch.cat([centre-size/2,centre+size/2],-1)


def refinement_loss(delta,boxes,targets,valid,rooms):
    # Select valid objects BEFORE divisions/IoU. NaN*0 does not remove NaN.
    if not valid.any():raise ValueError('Empty training batch')
    b=boxes[valid];t=targets[valid];d=delta[valid]
    room=rooms[:,None,:].expand(-1,boxes.shape[1],-1)[valid]
    if not torch.isfinite(t).all() or ((t[:,2:]-t[:,:2])<=0).any():raise ValueError('Invalid real target')
    ref=project(d,b,room);pc=(ref[:,:2]+ref[:,2:])/2;tc=(t[:,:2]+t[:,2:])/2
    ctr=torch.nn.functional.smooth_l1_loss(pc/room*10,tc/room*10,reduction='none').mean(-1)
    lo=torch.maximum(ref[:,:2],t[:,:2]);hi=torch.minimum(ref[:,2:],t[:,2:])
    inter=(hi-lo).clamp(min=0).prod(-1)
    union=(ref[:,2:]-ref[:,:2]).prod(-1)+(t[:,2:]-t[:,:2]).prod(-1)-inter
    q=inter/union.clamp(min=1e-6)
    c0=(b[:,:2]+b[:,2:])/2;d0=(c0-tc).norm(dim=-1);d1=(pc-tc).norm(dim=-1)
    per=.5*ctr+.25*(1-q)+2*(.5-q).clamp(min=0)+.05*d.square().sum(-1)
    per=per+(d0<=.5)*(d1-.5).clamp(min=0)
    row=torch.where(valid)[0];total=per.new_zeros(len(rooms)).scatter_add(0,row,per)
    return (total/valid.sum(1).clamp(min=1)).mean()


def pack(entries):
    n=len(entries);s=max(len(e['boxes']) for e in entries);dim=entries[0]['x'].shape[-1]
    x=np.zeros((n,s,dim),np.float32);step=np.zeros((n,s,2),np.float32)
    boxes=np.zeros((n,s,4),np.float32);target=boxes.copy();valid=np.zeros((n,s),bool)
    for i,e in enumerate(entries):
        k=len(e['boxes']);x[i,:k]=e['x'];step[i,:k]=e['step'];boxes[i,:k]=e['boxes'];target[i,:k]=e['target'];valid[i,:k]=True
    return [torch.from_numpy(a) for a in (x,step,boxes,target,valid,np.asarray([e['room'] for e in entries],np.float32))]


def entry(meta,obs,truth,boxes):
    keys,target=match_targets(boxes,truth);order,x,step=build_view(obs,boxes)
    if keys!=order or not np.isfinite(x).all() or not np.isfinite(step).all():raise ValueError('Bad features')
    return {'meta':meta,'obs':obs,'truth':truth,'keys':keys,'x':x,'step':step,
            'boxes':np.asarray([boxes[k] for k in keys],np.float32),'target':target,'room':obs['room']}


def evaluate(model,validation,requested):
    model.eval();whole=foot=0;f1=0.;by=defaultdict(lambda:[0,0,0.]);budgets=defaultdict(lambda:[0,0,0.,0])
    with torch.inference_mode():
        for start in range(0,len(validation),64):
            current=validation[start:start+64];x,step,b,t,valid,rooms=pack(current)
            d=model(x.reshape(-1,x.shape[-1]),step.reshape(-1,2)).reshape(*valid.shape,2)
            ref=project(d,b,rooms[:,None,:]).numpy()
            for i,e in enumerate(current):
                boxes={k:ref[i,j].tolist() for j,k in enumerate(e['keys'])} if e['obs']['events'] else dict(zip(e['keys'],e['boxes'].tolist()))
                value=score(boxes,e['truth']);whole+=value['whole_room'];foot+=value['whole_footprint'];f1+=value['f1']
                a=by[e['meta']['coverage_target']];a[0]+=value['whole_room'];a[1]+=value['whole_footprint'];a[2]+=value['f1']
                a=budgets[e['meta']['contacts_requested']];a[0]+=value['whole_room'];a[1]+=value['whole_footprint'];a[2]+=value['f1'];a[3]+=1
    return {'n_requested':requested,'n_usable':len(validation),'whole':whole,'footprint':foot,'f1':f1/requested,
            'by_coverage':{str(k):{'whole':v[0],'footprint':v[1],'f1_sum':v[2]} for k,v in by.items()},
            'by_budget':{str(k):{'whole':v[0],'footprint':v[1],'f1_sum':v[2],'n_usable':v[3]} for k,v in budgets.items()}}


def main():
    p=argparse.ArgumentParser();p.add_argument('--coarse',default='output/layout-recon/recovery080/train-coarse.jsonl')
    p.add_argument('--manifest',default='output/layout-recon/recovery076/main400/manifest.json')
    p.add_argument('--base-rows',default='output/layout-recon/recovery078/main400-k2all-7801-eval-160b/rows.jsonl')
    p.add_argument('--init',default='output/layout-recon/recovery080/refine/refine080.pt')
    p.add_argument('--k6-views',help='Optional frozen A/B k6 reproduction export: add training B views and validate the actual-count K6 route')
    p.add_argument('--mode',choices=('k6','balanced'),required=True);p.add_argument('--out',required=True)
    p.add_argument('--steps',type=int,default=2000);p.add_argument('--batch-size',type=int,default=32)
    p.add_argument('--eval-every',type=int,default=200);p.add_argument('--lr',type=float,default=1e-4)
    p.add_argument('--seed',type=int,default=8101);p.add_argument('--threads',type=int,default=4);a=p.parse_args()
    if min(a.steps,a.batch_size,a.eval_every)<1:p.error('Positive update budgets required')
    torch.set_num_threads(a.threads);torch.manual_seed(a.seed);rng=np.random.default_rng(a.seed)
    mp=Path(a.manifest);root=mp.parent;manifest=validate_manifest(read(mp));metas={r['id']:r for r in manifest['rows']}
    raw=Path(a.coarse).read_bytes()
    if not raw.endswith(b'\n'):raise ValueError('Training export incomplete: last line not sealed')
    coarse=[json.loads(s) for s in raw.splitlines() if s.strip()];ids=[r['id'] for r in coarse]
    expected={r['id'] for r in manifest['rows'] if r['split']=='train' and r['status']=='ok'}
    if len(ids)!=len(set(ids)) or set(ids)!=expected:raise ValueError(f'Training export incomplete/mixed: {len(ids)} vs {len(expected)} expected IDs')
    import hashlib
    data_sha=hashlib.sha256(raw).hexdigest()
    extra={};extra_failures=[]
    if a.k6_views:
        extra,extra_failures=load_k6_views(a.k6_views,metas)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False);train=[];validation=[];excluded=[]
    def load(meta,boxes):
        if sha(root/meta['input'])!=meta['input_sha256'] or sha(root/meta['target'])!=meta['target_sha256']:raise ValueError('Frozen input mismatch')
        return entry(meta,read(root/meta['input']),read(root/meta['target'])['boxes'],boxes)
    for r in coarse:
        meta=metas[r['id']]
        if r.get('split')!='train':raise ValueError('Nontraining record in export')
        if not r.get('boxes'):excluded.append(r['id']);continue
        if meta['contacts_requested']==0 or (a.mode=='k6' and meta['contacts_requested']!=6):continue
        train.append(load(meta,r['boxes']))
        if r['id'] in extra:
            # Training views contain only training labels, never validation IDs.
            train.append(load(meta,extra[r['id']]['boxes']))
    base=[json.loads(s) for s in Path(a.base_rows).read_text(encoding='utf-8').splitlines() if json.loads(s)['arm']=='learned']
    wanted={r['id'] for r in manifest['rows'] if r['split']=='validation'}
    if len(base)!=len(wanted) or {r['id'] for r in base}!=wanted:raise ValueError('Incomplete validation')
    for r in base:
        meta=metas[r['id']]
        if meta['status']=='ok' and r['boxes']:
            e=load(meta,r['boxes'])
            if len(e['obs']['events'])==6 and extra:
                e=entry(meta,e['obs'],e['truth'],extra[r['id']]['boxes'])
            validation.append(e)
    state=torch.load(a.init,map_location='cpu',weights_only=True);model=Refine080(state['width'],state['dim']);model.load_state_dict(state['state_dict'])
    optim=torch.optim.AdamW(model.parameters(),lr=a.lr,weight_decay=1e-3)
    buckets=defaultdict(lambda:defaultdict(list))
    for i,e in enumerate(train):buckets[(e['meta']['contacts_requested'],e['meta']['coverage_target'])][e['meta']['group']].append(i)
    strata=sorted(buckets);group_keys={k:sorted(v) for k,v in buckets.items()}
    if not train or not strata:raise ValueError('No training data')
    protocol={'args':vars(a),'manifest_sha256':sha(mp),'coarse_sha256':data_sha,'initial_sha256':sha(a.init),
          'base_rows_sha256':sha(a.base_rows),'trainer_sha256':sha(__file__),
          'k6_views_sha256':sha(a.k6_views) if a.k6_views else None,
          'k6_acquisition_failure_ids_not_used_for_training':extra_failures,
          'feature_source_sha256':sha(ROOT/'analysis/layout/recovery080_refine.py'),
          'train_ids':[e['meta']['id'] for e in train],'validation_ids':sorted(wanted),'excluded_training_prediction_failures':excluded,
          'strata':{str(k):sum(map(len,v.values())) for k,v in buckets.items()},
          'labels':'same-category one-to-one coarse matching; IDs are not correspondences',
          'loss':'room-normalized080v2, centre protection, valid-object selection before arithmetic',
          'selection':'development whole, then footprint, then F1; all no lower than step-zero; centre counts in each coverage stratum and K2 footprint count must also not regress',
          'inference_gate':'actual event count zero bypasses refiner','test_opened':False}
    protocol['validation_coarse_policy']='K2 original078, actual K6 epoch6/0.25, others077' if extra else 'original K2-only078 routing'
    dump(out/'protocol.json',protocol);initial=evaluate(model,validation,len(wanted));best=(initial['whole'],initial['footprint'],initial['f1']);history=[]
    def save(path,step):
        torch.save({'architecture':'refine081-v1','state_dict':model.state_dict(),'dim':state['dim'],'width':state['width'],'step':step,'protocol':protocol},path)
    save(out/'best.pt',0);started=time.monotonic()
    for update in range(a.steps+1):
        if update:
            chosen=[]
            for _ in range(a.batch_size):
                k=strata[int(rng.integers(len(strata)))];g=group_keys[k][int(rng.integers(len(group_keys[k])))];c=buckets[k][g]
                chosen.append(train[c[int(rng.integers(len(c)))]])
            model.train();x,step,b,t,valid,rooms=pack(chosen);optim.zero_grad(set_to_none=True)
            d=model(x.reshape(-1,x.shape[-1]),step.reshape(-1,2)).reshape(*valid.shape,2)
            loss=refinement_loss(d,b,t,valid,rooms)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss; no step skipped')
            loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.)
            if not torch.isfinite(norm):raise FloatingPointError('Nonfinite gradient')
            optim.step()
        if update%a.eval_every==0 or update==a.steps:
            value=evaluate(model,validation,len(wanted));eligible=value['whole']>=initial['whole'] and value['footprint']>=initial['footprint'] and value['f1']>=initial['f1']-1e-9
            eligible=eligible and all(value['by_coverage'][k]['whole']>=v['whole'] for k,v in initial['by_coverage'].items())
            eligible=eligible and value['by_budget']['2']['footprint']>=initial['by_budget']['2']['footprint']
            key=(value['whole'],value['footprint'],value['f1'])
            if eligible and key>best:best=key;save(out/'best.pt',update)
            log={'step':update,'validation':value,'eligible':eligible,'seconds':time.monotonic()-started}
            if update:log['training_loss']=float(loss.detach())
            history.append(log);dump(out/'history.json',history);print(json.dumps(log),flush=True)
    save(out/'last.pt',a.steps);dump(out/'complete.json',{'steps':a.steps,'initial':initial,'best_key':best,'test_opened':False,'best_sha256':sha(out/'best.pt')})


if __name__=='__main__':main()
