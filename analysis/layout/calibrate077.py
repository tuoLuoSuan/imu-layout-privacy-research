"""Freeze a residual-score strength using validation only, never the old test.

This is model selection, not an independent efficacy experiment. Alpha=0 is
eligible so the package cannot disguise a selected fixed model as learned.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import torch

from .recovery076_data import dump,read,sha,pack,load_rows
from .recovery076_eval import score,failed_score,aggregate
from .recovery077_runtime import development_rows,decode_fast
from .eval077 import load_checkpoint

ALPHAS=(0.,.25,.5,.75,1.)


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--checkpoint',required=True)
    p.add_argument('--cache');p.add_argument('--out',required=True);p.add_argument('--threads',type=int,default=2)
    a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(a.threads)
    model,saved=load_checkpoint(a.checkpoint)
    if saved['manifest_sha256']!=sha(a.manifest):raise ValueError('Use the frozen development manifest')
    if a.cache:entries=[e for e in development_rows(a.manifest,saved['grid'],a.cache) if e['row']['split']=='validation']
    else:entries=load_rows(a.manifest,{'validation'},saved['grid'])
    if not entries:raise ValueError('Explicit validation split required')
    rows={alpha:[] for alpha in ALPHAS}
    with torch.inference_mode():
        for number,e in enumerate(entries):
            if e['sample'] is not None:
                b=pack([e['sample']]);output=model(b)
            for alpha in ALPHAS:
                boxes={};error=None
                if e['sample'] is None:metrics=failed_score();status='acquisition_failed'
                else:
                    energy=output['fixed_energy']+alpha*output['correction']
                    candidate={'log_prob':energy.log_softmax(-1)}
                    boxes=decode_fast(candidate,b,40,32)[0];metrics=score(boxes,e['truth']);status='ok'
                row={k:e['row'][k] for k in ('id','group','coverage_target','contacts_requested')}
                row.update(arm='learned',usable=e['sample'] is not None,status=status,error=error,boxes=boxes,**metrics)
                rows[alpha].append(row)
            if (number+1)%200==0:print(json.dumps({'validation_cells_done':number+1,'total':len(entries)}),flush=True)
    metrics={alpha:aggregate(values) for alpha,values in rows.items()}
    selected=max(ALPHAS,key=lambda alpha:(metrics[alpha]['whole_room'],metrics[alpha]['whole_footprint'],metrics[alpha]['f1'],-alpha))
    result={'scope':'validation model selection; not independent performance confirmation',
            'alpha_candidates':ALPHAS,'selected_strength':selected,'epoch':saved['epoch'],
            'selection':'whole-room centre, then footprint, then mean F1, then smaller residual strength',
            'metrics':metrics,'base_checkpoint_sha256':sha(a.checkpoint),'manifest_sha256':sha(a.manifest),
            'source_sha256':sha(__file__),'test_opened':False}
    dump(out/'calibration.json',result)
    for alpha in ALPHAS:dump(out/f'validation-strength-{alpha:g}.json',{'strength':alpha,'summary':metrics[alpha],'rows':rows[alpha]})
    saved.update(score_strength=selected,calibration=result)
    torch.save(saved,out/'calibrated.pt')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
