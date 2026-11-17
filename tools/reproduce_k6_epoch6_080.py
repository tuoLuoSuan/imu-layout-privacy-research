"""Reproduce a recorded development Pareto point; never overwrite/deploy it."""
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from analysis.layout.recovery076_data import read,dump,sha,CATEGORIES
from analysis.layout.recovery078_model import LayoutRanker078,pack_graph
from analysis.layout.train078 import load_graph_cache,ranking_loss_f1,evaluate


def main():
    original=ROOT/'output/layout-recon/recovery079/k6-7901'
    protocol=read(original/'protocol.json');args=protocol['args']
    for name,digest in protocol['source_sha256'].items():
        if sha(ROOT/'analysis/layout'/name)!=digest:raise ValueError('Original training source changed: '+name)
    graphs=ROOT/args['graphs']
    if sha(graphs)!=protocol['graphs_sha256']:raise ValueError('Original graph cache changed')
    if args['fallback_objective']!='f1' or args['seed']!=7901 or args['width']!=48:
        raise ValueError('Unexpected original protocol')
    out=ROOT/'output/layout-recon/recovery080/k6-epoch6-reproduction'
    out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(args['threads']);torch.manual_seed(args['seed']);rng=np.random.default_rng(args['seed'])
    saved=load_graph_cache(graphs);entries=saved['entries']
    train=[e for e in entries if e['meta']['split']=='train' and e['features'] is not None and bool(e['features']['has_events'])]
    validation=[e for e in entries if e['meta']['split']=='validation']
    model=LayoutRanker078(args['width']);optim=torch.optim.AdamW(model.parameters(),lr=args['lr'],weight_decay=.001)
    started=time.monotonic();history=[]
    for epoch in range(1,7):
        model.train();total=0.;order=rng.permutation(len(train))
        for start in range(0,len(order),args['batch_size']):
            current=[train[i] for i in order[start:start+args['batch_size']]]
            batch,labels=pack_graph(current);optim.zero_grad(set_to_none=True)
            loss=ranking_loss_f1(model(batch),batch,labels)
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
            loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.)
            if not torch.isfinite(norm):raise FloatingPointError('Nonfinite gradient')
            optim.step();total+=float(loss.detach())*len(current)
        row={'epoch':epoch,'loss':total/len(train),'seconds':time.monotonic()-started}
        if epoch%args['validate_every']==0:
            metrics,_=evaluate(model,validation);row['strength_025']=metrics[.25]
        history.append(row);print(json.dumps(row),flush=True)
    value=history[-1]['strength_025']
    expected={'whole_count':108,'footprint_count':44,'f1':.6270290554600692}
    if value['whole_count']!=108 or value['footprint_count']!=44 or abs(value['f1']-expected['f1'])>1e-6:
        dump(out/'mismatch.json',{'actual':value,'expected':expected,'history':history})
        raise ValueError('Recorded point did not reproduce; no accepted snapshot written')
    state={'architecture':'layout078-v1','state_dict':model.state_dict(),'width':48,'rounds':2,
           'seed':7901,'epoch':6,'strength':.25,'protocol':protocol,
           'reproduction':{'source_sha256':sha(__file__),'original_protocol_sha256':sha(original/'protocol.json'),
             'scope':'post-hoc development Pareto candidate; failed original footprint guard; not selected/deployed',
             'joint_guard_passed':False}}
    torch.save(state,out/'epoch6-pareto.pt')
    # All selections below use the same fixed .25 strength, not target labels.
    _,indices=evaluate(model,entries)
    with (out/'coarse-predictions.jsonl').open('w',encoding='utf-8') as file:
        for entry,index in zip(entries,indices[.25]):
            meta=entry['meta'];boxes={};base={}
            if index>=0:
                counts={}
                for slot,cat in enumerate(entry['hypotheses']['category']):
                    name=CATEGORIES[int(cat)];count=counts.get(name,0);counts[name]=count+1;key=f'{name}#{count}'
                    boxes[key]=entry['hypotheses']['boxes'][index,slot].tolist()
                    base[key]=entry['hypotheses']['boxes'][0,slot].tolist()
            file.write(json.dumps({'id':meta['id'],'split':meta['split'],'group':meta['group'],
                 'coverage_target':meta['coverage_target'],'index':index,'boxes':boxes,'baseline_boxes':base})+'\n')
    result={'scope':state['reproduction']['scope'],'validation':value,'train_usable':len(train),
            'history':history,'elapsed_seconds':time.monotonic()-started,
            'snapshot_sha256':sha(out/'epoch6-pareto.pt'),'predictions_sha256':sha(out/'coarse-predictions.jsonl')}
    dump(out/'reproduction.json',result);print(json.dumps({'status':'reproduced','validation':value,'out':str(out)}),flush=True)


if __name__=='__main__':main()
