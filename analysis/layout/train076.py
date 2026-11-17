"""CPU training; explicit manifests; train/validation only; no old anchors."""
import argparse
import copy
import json
import time
from pathlib import Path

import numpy as np
import torch

from .recovery076_data import dump,load_rows,pack,read,sha
from .recovery076_model import EvidenceDecoder076,objective,decode
from .recovery076_eval import score,failed_score,aggregate


def validation(model,rows):
    model.eval();result=[]
    with torch.inference_mode():
        for row in rows:
            s=row['sample']
            if s is None:r=failed_score()
            else:
                batch=pack([s]);r=score(decode(model(batch),batch)[0],row['truth'])
            result.append({'id':row['row']['id'],'usable':s is not None,**r})
    return aggregate(result),result


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True)
    p.add_argument('--seed',type=int,default=7601);p.add_argument('--width',type=int,default=96)
    p.add_argument('--grid',type=int,default=24);p.add_argument('--epochs',type=int,default=40)
    p.add_argument('--batch-size',type=int,default=8);p.add_argument('--threads',type=int,default=4)
    p.add_argument('--validate-every',type=int,default=5);p.add_argument('--lr',type=float,default=.001)
    p.add_argument('--rotate',action='store_true',help='C4 coordinate augmentation, transformed jointly; not yaw inference')
    a=p.parse_args()
    if min(a.epochs,a.batch_size,a.threads,a.validate_every,a.width)<1 or a.lr<=0:p.error('Positive training settings required')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(a.threads);torch.manual_seed(a.seed);rng=np.random.default_rng(a.seed)
    rows=load_rows(a.manifest,{'train','validation'},a.grid)
    training=[r for r in rows if r['row']['split']=='train' and r['sample'] is not None]
    valid=[r for r in rows if r['row']['split']=='validation']
    if not training or not valid:raise ValueError('Nonempty explicit train/validation required; no fallback to test')
    protocol={'args':vars(a),'manifest_sha256':sha(a.manifest),
              'source_sha256':{f:sha(Path(__file__).with_name(f)) for f in ('train076.py','recovery076_model.py','recovery076_data.py','recovery076_eval.py','recovery076_augment.py')},
              'training_ids':[r['row']['id'] for r in training],'validation_ids':[r['row']['id'] for r in valid],
              'failed_training_ids':[r['row']['id'] for r in rows if r['sample'] is None and r['row']['split']=='train'],
              'selection':'validation whole-room centre, then footprint, then F1; equal scores retain earlier epoch',
              'test_opened':False,'observation_source':'manifest; inspect scope before making any IMU claim'}
    dump(out/'protocol.json',protocol)
    model=EvidenceDecoder076(a.width);optim=torch.optim.AdamW(model.parameters(),lr=a.lr,weight_decay=.001)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optim,a.epochs,eta_min=a.lr*.1)
    best=None;started=time.monotonic()
    dump(out/'architecture.json',{'name':'EvidenceDecoder076','parameters':sum(p.numel() for p in model.parameters()),
                                 'uses_anchor':False,'uses_absolute_position_in_kernel':False,'learns_furniture_sizes':False})
    with (out/'epochs.jsonl').open('w',encoding='utf-8') as log:
        for epoch in range(1,a.epochs+1):
            model.train();total=0.
            for begin in range(0,len(training),a.batch_size):
                if begin==0:order=rng.permutation(len(training))
                selected=[training[i] for i in order[begin:begin+a.batch_size]]
                batch=pack([r['sample'] for r in selected]);truths=[r['truth'] for r in selected]
                if a.rotate:
                    from .recovery076_augment import rotate_batch
                    batch,truths=rotate_batch(batch,truths,int(rng.integers(4)))
                optim.zero_grad(set_to_none=True);loss=objective(model(batch),batch,truths)
                if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss; no row discarded')
                loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),2.);optim.step()
                total+=float(loss.detach())*len(selected)
            scheduler.step()
            report={'epoch':epoch,'loss':total/len(training),'elapsed_seconds':time.monotonic()-started}
            if epoch==1 or epoch%a.validate_every==0 or epoch==a.epochs:
                stats,details=validation(model,valid);report['validation']=stats
                key=(stats['whole_room'],stats['whole_footprint'],stats['f1'])
                if best is None or key>best:
                    best=key
                    torch.save({'state_dict':model.state_dict(),'width':a.width,'grid':a.grid,'epoch':epoch,
                                'seed':a.seed,'manifest_sha256':sha(a.manifest),'architecture':'evidence076-v1',
                                'source_sha256':protocol['source_sha256'],
                                'seen_groups':sorted({r['row']['group'] for r in rows}),
                                'seen_fingerprints':sorted({r['row']['fingerprint'] for r in rows}),
                                'scope':read(a.manifest)['protocol']['scope']},out/'best.pt')
                    dump(out/'validation-best.json',{'epoch':epoch,'summary':stats,'rows':details})
            log.write(json.dumps(report)+'\n');log.flush();print(json.dumps(report),flush=True)
    dump(out/'complete.json',{'status':'training_completed','seconds':time.monotonic()-started,
                              'test_evaluated':False,'best_sha256':sha(out/'best.pt')})

if __name__=='__main__':main()
