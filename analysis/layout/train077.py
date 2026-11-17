"""Train candidate-conditioned scoring on development rows only."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from .recovery076_data import read,dump,sha,pack
from .recovery076_eval import score,failed_score,aggregate
from .recovery077_model import CandidateScorer077,training_loss
from .recovery077_runtime import development_rows,decode_fast

SOURCE=('train077.py','recovery077_model.py','recovery077_runtime.py',
        'recovery076_model.py','recovery076_data.py','recovery076_eval.py')


def evaluate(model,entries,candidates=40,beam=32,strength=1.):
    rows=[];model.eval()
    with torch.inference_mode():
        for e in entries:
            s=e['sample'];boxes={}
            if s is None:result=failed_score();status='acquisition_failed'
            else:
                b=pack([s]);out=model(b,strength=strength);boxes=decode_fast(out,b,candidates,beam)[0]
                result=score(boxes,e['truth']);status='ok'
            rows.append({**{k:e['row'][k] for k in ('id','group','coverage_target','contacts_requested')},
                         'usable':s is not None,'status':status,'arm':'learned','boxes':boxes,**result})
    return aggregate(rows),rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--cache')
    p.add_argument('--out',required=True);p.add_argument('--epochs',type=int,default=12)
    p.add_argument('--width',type=int,default=64);p.add_argument('--grid',type=int,default=24)
    p.add_argument('--batch-size',type=int,default=8);p.add_argument('--threads',type=int,default=4)
    p.add_argument('--seed',type=int,default=7701);p.add_argument('--lr',type=float,default=.0005)
    p.add_argument('--validate-every',type=int,default=2);p.add_argument('--candidates',type=int,default=40)
    p.add_argument('--beam',type=int,default=32);a=p.parse_args()
    if min(a.epochs,a.width,a.batch_size,a.validate_every,a.threads)<1 or a.lr<=0:p.error('Positive parameters required')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(a.threads);torch.manual_seed(a.seed);rng=np.random.default_rng(a.seed)
    started=time.monotonic();rows=development_rows(a.manifest,a.grid,a.cache)
    training=[e for e in rows if e['row']['split']=='train' and e['sample'] is not None and len(e['sample']['events'])]
    validation=[e for e in rows if e['row']['split']=='validation']
    if not training or not validation:raise ValueError('Explicit nonempty development splits required')
    model=CandidateScorer077(a.width);optim=torch.optim.AdamW(model.scorer.parameters(),lr=a.lr,weight_decay=.001)
    protocol={'args':vars(a),'manifest_sha256':sha(a.manifest),'test_opened':False,
              'train_ids':[e['row']['id'] for e in training], 'validation_ids':[e['row']['id'] for e in validation],
              'source_sha256':{s:sha(Path(__file__).with_name(s)) for s in SOURCE},
              'parameters':sum(p.numel() for p in model.scorer.parameters()),
              'selection':'validation whole-room centre, then footprint, then mean F1; fixed epoch 0 eligible',
              'scope':read(a.manifest)['protocol']['scope']}
    dump(out/'protocol.json',protocol)
    best=None;history=[]
    for epoch in range(a.epochs+1):
        if epoch:
            model.train();total=0.;n=0;maxgrad=0.;supervised=0
            order=rng.permutation(len(training))
            for start in range(0,len(order),a.batch_size):
                entries=[training[i] for i in order[start:start+a.batch_size]]
                b=pack([e['sample'] for e in entries]);truth=[e['truth'] for e in entries]
                optim.zero_grad(set_to_none=True);loss,stats=training_loss(model(b),b,truth)
                if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss; no row dropped')
                loss.backward();grad=torch.nn.utils.clip_grad_norm_(model.scorer.parameters(),5.)
                if not torch.isfinite(grad):raise FloatingPointError('Nonfinite gradient')
                optim.step();total+=float(loss.detach())*len(entries);n+=len(entries)
                supervised+=stats['supervised_slots'];maxgrad=max(maxgrad,float(grad))
            report={'epoch':epoch,'loss':total/max(1,n),'max_gradient_norm':maxgrad,'supervised_slots':supervised,
                    'elapsed_seconds':time.monotonic()-started}
        else:report={'epoch':0,'elapsed_seconds':time.monotonic()-started}
        if epoch==0 or epoch%a.validate_every==0 or epoch==a.epochs:
            metrics,details=evaluate(model,validation,a.candidates,a.beam)
            report['validation']=metrics;key=(metrics['whole_room'],metrics['whole_footprint'],metrics['f1'])
            if best is None or key>best:
                best=key
                torch.save({'architecture':'candidate077-v1','state_dict':model.state_dict(),'width':a.width,
                            'grid':a.grid,'seed':a.seed,'epoch':epoch,'manifest_sha256':sha(a.manifest),
                            'source_sha256':protocol['source_sha256'],'scope':protocol['scope'],
                            'seen_groups':sorted({e['row']['group'] for e in rows}),
                            'seen_fingerprints':sorted({e['row']['fingerprint'] for e in rows})},out/'best.pt')
                dump(out/'validation-best.json',{'epoch':epoch,'summary':metrics,'rows':details})
            dump(out/f'validation-{epoch:03d}.json',{'epoch':epoch,'summary':metrics,'rows':details})
        history.append(report);dump(out/'epochs.json',history);print(json.dumps(report),flush=True)
    torch.save({'architecture':'candidate077-v1','state_dict':model.state_dict(),'width':a.width,
                'grid':a.grid,'epoch':a.epochs,'manifest_sha256':sha(a.manifest),
                'source_sha256':protocol['source_sha256'],'scope':protocol['scope']},out/'last.pt')
    dump(out/'complete.json',{'status':'completed','test_opened':False,'elapsed_seconds':time.monotonic()-started,
                              'best_sha256':sha(out/'best.pt')})

if __name__=='__main__':main()
