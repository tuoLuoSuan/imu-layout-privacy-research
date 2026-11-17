"""Locked zero-spatial/D router vs D/static, keeping every requested cell."""
import argparse
from pathlib import Path
import json
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import torch
from analysis.layout.recovery076_data import read,dump,sha,validate_manifest,check_confirmation
from analysis.layout.recovery076_eval import score,failed_score,aggregate
from analysis.layout.recovery081_runtime import predict as predict081,refine_boxes
from analysis.layout.recovery088_spatial_runtime import load_models,predict
from analysis.layout.analytic077 import corrected_static
from tools.eval082_locked import paired


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--lock',required=True);p.add_argument('--out',required=True)
    p.add_argument('--split',choices=('validation','confirmation'),default='confirmation');p.add_argument('--threads',type=int,default=4)
    p.add_argument('--smoke-limit',type=int);p.add_argument('--used-manifest',action='append');a=p.parse_args()
    if a.smoke_limit is not None and (a.split!='validation' or a.smoke_limit<1):p.error('Smoke only on old validation')
    torch.set_num_threads(a.threads);mp=Path(a.manifest);manifest=validate_manifest(read(mp));models=load_models(ROOT/'output/layout-recon',a.lock)
    used=a.used_manifest or ['output/layout-recon/recovery076/main400/manifest.json','output/layout-recon/recovery082/confirmation-50-v2/manifest.json']
    if a.split=='confirmation':
        groups=set();prints=set()
        for file in used:
            old=validate_manifest(read(file));groups.update(r['group'] for r in old['rows']);prints.update(r['fingerprint'] for r in old['rows'])
        check_confirmation(manifest,groups,prints)
    elif sha(mp)!=models['lock']['manifest_sha256']:raise ValueError('Different data require new confirmation')
    metas=[r for r in manifest['rows'] if r['split']==a.split]
    if a.smoke_limit is not None:metas=metas[:a.smoke_limit]
    if not metas:raise ValueError('Empty cohort')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    files={'manifest':mp,'lock':Path(a.lock),'evaluator':Path(__file__)}
    for name in ('analytic077.py','multi_instance.py','continuous_regions.py','recovery076_eval.py','sim_eval.py'):files[name]=ROOT/'analysis/layout'/name
    hashes={k:sha(v) for k,v in files.items()};protocol={'args':vars(a),'frozen_sha256':hashes,'requested_ids':[r['id'] for r in metas],
        'rule':'actual events0: frozen spatial083 plus, otherwise frozen D','is_smoke_only':a.smoke_limit is not None,
        'fresh_confirmation':a.split=='confirmation','failure_policy':'all requested; acquisition/decoder failures zero',
        'scope':'conditional synthetic geometry; no raw IMU or real generalization claim','model_lock':models['lock']}
    dump(out/'protocol.json',protocol);rows=[];started=time.monotonic()
    with (out/'rows.jsonl').open('w',encoding='utf-8') as file:
        for i,meta in enumerate(metas):
            outputs={};truth={}
            if meta['status']=='ok':
                ip=mp.parent/meta['input'];tp=mp.parent/meta['target']
                if sha(ip)!=meta['input_sha256'] or sha(tp)!=meta['target_sha256']:raise ValueError('Frozen data hash mismatch')
                obs=read(ip)
                try:
                    raw=predict081(obs,models['parents'],policy='none');K=len(obs['events'])
                    box,_=refine_boxes(obs,raw['boxes'],models['refiners'][2] if K==2 else models['refiners'][6],'nonzero')
                    outputs['frozen_D']=(box,'ok',None)
                except Exception as exc:outputs['frozen_D']=({},'decoder_failed',repr(exc))
                try:outputs['spatial_zero088']=outputs['frozen_D'] if obs['events'] else (predict(obs,models)['boxes'],'ok',None)
                except Exception as exc:outputs['spatial_zero088']=({},'decoder_failed',repr(exc))
                try:
                    s=corrected_static(obs);outputs['corrected_static']=(s.get('boxes',{}),s['status'],None)
                except Exception as exc:outputs['corrected_static']=({},'decoder_failed',repr(exc))
                # Evaluation targets enter after all observation-only predictions.
                truth=read(tp)['boxes']
            for arm in ('frozen_D','spatial_zero088','corrected_static'):
                if meta['status']=='ok':box,status,error=outputs[arm];value=score(box,truth)
                else:box,status,error={},'acquisition_failed',meta.get('error');value=failed_score()
                r={k:meta[k] for k in ('id','group','coverage_target','contacts_requested')}
                r.update(arm=arm,usable=meta['status']=='ok',status=status,error=error,boxes=box,**value)
                rows.append(r);file.write(json.dumps(r)+'\n')
            if (i+1)%100==0:print({'done':i+1,'total':len(metas),'seconds':time.monotonic()-started},flush=True)
    if hashes!={k:sha(v) for k,v in files.items()}:raise ValueError('Frozen files changed')
    result={'protocol':protocol,'table':{arm:aggregate([r for r in rows if r['arm']==arm]) for arm in ('frozen_D','spatial_zero088','corrected_static')},
        'paired':[paired(rows,'spatial_zero088',b,4000) for b in ('frozen_D','corrected_static')],
        'surface':[{'arm':arm,'coverage_target':c,'contacts_requested':k,**aggregate([r for r in rows if r['arm']==arm and r['coverage_target']==c and r['contacts_requested']==k])} for arm in ('frozen_D','spatial_zero088','corrected_static') for c in sorted({r['coverage_target'] for r in metas}) for k in sorted({r['contacts_requested'] for r in metas})],
        'elapsed_seconds':time.monotonic()-started}
    dump(out/'summary.json',result);print(result['table'],flush=True)


if __name__=='__main__':main()
