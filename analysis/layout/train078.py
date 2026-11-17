"""Train a whole-layout graph scorer on a frozen, development-only cache."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import torch

from .recovery076_data import dump,sha
from .recovery078_model import LayoutRanker078,pack_graph,ranking_loss

STRENGTHS=(0.,.25,.5,.75,1.)


def ranking_loss_f1(outputs,batch,labels):
    """Whole-correct first; when none exist, preserve attainable partial hits."""
    valid=batch['hyp_valid'];whole=(labels['whole']>.5)&valid
    footprint_cost=1-labels['mean_iou']
    cost=labels['dmax']/.5+.2*labels['mean_error']/.5+.2*footprint_cost
    best_f1=labels['f1'].masked_fill(~valid,-1).amax(1,keepdim=True)
    best_partial=valid&(labels['f1']>=best_f1-1e-6)
    fallback=(-cost/.2).masked_fill(~best_partial,-1e4)
    preferred=(-footprint_cost/.2).masked_fill(~whole,-1e4)
    target=torch.where(whole.any(1)[:,None],preferred,fallback).softmax(-1).detach()
    loss=-(target*outputs['scores'].log_softmax(-1)).sum(-1).mean()
    return loss+.002*outputs['residual'][valid].square().mean()


def choose_strength(metrics,max_f1_drop=None,max_footprint_drop=None):
    base=metrics[0.];eligible=[]
    for strength in STRENGTHS:
        value=metrics[strength]
        if max_f1_drop is not None and value['f1']<base['f1']-max_f1_drop-1e-9:continue
        if max_footprint_drop is not None and value['footprint_rate']<base['footprint_rate']-max_footprint_drop-1e-9:continue
        eligible.append(strength)
    return max(eligible,key=lambda x:(metrics[x]['whole_count'],metrics[x]['footprint_count'],metrics[x]['f1'],-x))


def summarize(entries,indices):
    n=len(entries);metrics={k:0. for k in ('whole','footprint','f1')}
    for entry,index in zip(entries,indices):
        if entry['features'] is None:continue
        for key in metrics:metrics[key]+=float(entry['labels'][key][index])
    return {'n_requested':n,'n_usable':sum(e['features'] is not None for e in entries),
            'whole_count':int(metrics['whole']),'whole_rate':metrics['whole']/max(1,n),
            'footprint_count':int(metrics['footprint']),'footprint_rate':metrics['footprint']/max(1,n),
            'f1':metrics['f1']/max(1,n)}


def evaluate(model,entries,batch_size=8):
    model.eval();selected={strength:[] for strength in STRENGTHS}
    with torch.inference_mode():
        for start in range(0,len(entries),batch_size):
            current=entries[start:start+batch_size];usable=[(i,e) for i,e in enumerate(current) if e['features'] is not None]
            choices={strength:[-1]*len(current) for strength in STRENGTHS}
            if usable:
                batch,_=pack_graph([e for _,e in usable]);out=model(batch)
                for strength in STRENGTHS:
                    scores=(batch['base_score']+strength*out['residual']).masked_fill(~batch['hyp_valid'],-1e4)
                    index=scores.argmax(-1).tolist()
                    for (i,_),j in zip(usable,index):choices[strength][i]=j
            for strength in STRENGTHS:selected[strength].extend(choices[strength])
    return {strength:summarize(entries,choices) for strength,choices in selected.items()},selected


def load_graph_cache(path):
    saved=torch.load(path,map_location='cpu',weights_only=False)
    if saved['protocol']['schema']!='graphs078-v1':raise ValueError('Unknown graph cache')
    for name in ('recovery078_candidates.py','recovery078_model.py'):
        if sha(Path(__file__).with_name(name))!=saved['protocol']['source_sha256'][name]:
            raise ValueError('Graph feature/model source changed; rebuild the cache')
    if any(e['meta']['split'] not in ('train','validation') for e in saved['entries']):raise ValueError('Test/confirmation in development cache')
    ids=[e['meta']['id'] for e in saved['entries']]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate graph ID')
    return saved


def main():
    p=argparse.ArgumentParser();p.add_argument('--graphs',required=True);p.add_argument('--out',required=True)
    p.add_argument('--epochs',type=int,default=20);p.add_argument('--validate-every',type=int,default=2)
    p.add_argument('--width',type=int,default=96);p.add_argument('--seed',type=int,default=7801)
    p.add_argument('--batch-size',type=int,default=4);p.add_argument('--threads',type=int,default=4)
    p.add_argument('--lr',type=float,default=.001);p.add_argument('--patience-checks',type=int,default=6)
    p.add_argument('--fallback-objective',choices=('dmax','f1'),default='dmax')
    p.add_argument('--max-f1-drop',type=float,help='Optional validation guard; 0 means no mean instance-F1 regression')
    p.add_argument('--max-footprint-drop',type=float,help='Optional validation guard on whole-footprint rate')
    p.add_argument('--min-oracle-gain',type=float,default=.05,
                   help='Stop before training if validation candidate oracle has insufficient headroom')
    a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(a.threads);torch.manual_seed(a.seed);rng=np.random.default_rng(a.seed)
    saved=load_graph_cache(a.graphs);entries=saved['entries']
    train=[e for e in entries if e['meta']['split']=='train' and e['features'] is not None and bool(e['features']['has_events'])]
    validation=[e for e in entries if e['meta']['split']=='validation']
    if not train or not validation:raise ValueError('Nonempty explicit train and validation required')
    base=sum(int(e['labels']['whole'][0]) for e in validation if e['features'] is not None)
    oracle=sum(int(e['labels']['whole'].max()) if bool(e['features']['has_events']) else int(e['labels']['whole'][0])
               for e in validation if e['features'] is not None)
    headroom=(oracle-base)/len(validation)
    model=LayoutRanker078(a.width)
    protocol={'args':vars(a),'graphs_sha256':sha(a.graphs),'candidate_protocol':saved['protocol'],
              'train_ids':[e['meta']['id'] for e in train],'validation_ids':[e['meta']['id'] for e in validation],
              'source_sha256':{name:sha(Path(__file__).with_name(name)) for name in
                               ('train078.py','recovery078_model.py','recovery078_candidates.py')},
              'parameters':sum(p.numel() for p in model.parameters()),'test_opened':False,
              'selection':'validation whole-room, then footprint, then F1, then smaller residual strength and earlier epoch',
              'candidate_oracle':{'base':base,'oracle':oracle,'n':len(validation),'gain':headroom}}
    dump(out/'protocol.json',protocol)
    if headroom<a.min_oracle_gain:
        dump(out/'complete.json',{'status':'stopped_candidate_headroom_insufficient','candidate_oracle':protocol['candidate_oracle']})
        print(json.dumps({'status':'stopped_candidate_headroom_insufficient','headroom':headroom}),flush=True);return
    optim=torch.optim.AdamW(model.parameters(),lr=a.lr,weight_decay=.001)
    best=None;history=[];stale=0;started=time.monotonic()
    for epoch in range(a.epochs+1):
        report={'epoch':epoch}
        if epoch:
            model.train();total=0.;gradient=0.;order=rng.permutation(len(train))
            for start in range(0,len(order),a.batch_size):
                batch_entries=[train[i] for i in order[start:start+a.batch_size]]
                batch,labels=pack_graph(batch_entries);optim.zero_grad(set_to_none=True)
                output=model(batch);loss=(ranking_loss_f1(output,batch,labels) if a.fallback_objective=='f1' else ranking_loss(output,batch,labels))
                if not torch.isfinite(loss):raise FloatingPointError('Nonfinite listwise loss; no batch omitted')
                loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.)
                if not torch.isfinite(norm):raise FloatingPointError('Nonfinite graph gradient')
                optim.step();total+=float(loss.detach())*len(batch_entries);gradient=max(gradient,float(norm))
            report.update(loss=total/len(train),max_gradient=gradient)
        if epoch==0 or epoch%a.validate_every==0 or epoch==a.epochs:
            metrics,indices=evaluate(model,validation)
            strength=choose_strength(metrics,a.max_f1_drop,a.max_footprint_drop)
            value=metrics[strength];key=(value['whole_count'],value['footprint_count'],value['f1'])
            report.update(strength=strength,validation=value,all_strengths=metrics)
            if best is None or key>best:
                best=key;stale=0
                torch.save({'architecture':'layout078-v1','state_dict':model.state_dict(),'width':a.width,'rounds':2,
                            'seed':a.seed,'epoch':epoch,'strength':strength,'protocol':protocol},out/'best.pt')
                dump(out/'validation-best.json',{'epoch':epoch,'strength':strength,'summary':value,'all_strengths':metrics,
                     'selected':[{'id':e['meta']['id'],'group':e['meta']['group'],'index':i,
                                  'whole':int(e['labels']['whole'][i]) if i>=0 else 0,
                                  'footprint':int(e['labels']['footprint'][i]) if i>=0 else 0}
                                 for e,i in zip(validation,indices[strength])]})
            else:stale+=1
        report['elapsed_seconds']=time.monotonic()-started;history.append(report);dump(out/'epochs.json',history)
        print(json.dumps(report),flush=True)
        if epoch and stale>=a.patience_checks:break
    dump(out/'complete.json',{'status':'completed','elapsed_seconds':time.monotonic()-started,'epochs':epoch,
                             'test_opened':False,'best_sha256':sha(out/'best.pt')})

if __name__=='__main__':main()
