"""Build development-only complete-layout graph caches from frozen077."""
import argparse
import json
from collections import Counter,defaultdict
from pathlib import Path
import time
import torch

from .recovery076_data import pack,sha,dump
from .recovery077_runtime import development_rows
from .eval077 import load_checkpoint
from .recovery078_candidates import hypotheses,unique_hypotheses,diverse_hypotheses,sampled_hypotheses,with_analytic_proposals,graph_features,label_hypotheses


SOURCE=('build078.py','recovery078_candidates.py','recovery078_model.py','recovery077_model.py',
        'recovery077_runtime.py','recovery076_data.py','recovery076_eval.py',
        'analytic077.py','multi_instance.py','continuous_regions.py')


def summarize(entries):
    result=[]
    for split in sorted({e['meta']['split'] for e in entries}):
        for cov in (.25,.5,1.):
            for k in (0,2,6,10,14):
                rows=[e for e in entries if e['meta']['split']==split and e['meta']['coverage_target']==cov and e['meta']['contacts_requested']==k]
                if not rows:continue
                usable=[e for e in rows if e['features'] is not None]
                result.append({'split':split,'coverage':cov,'contacts':k,'n_requested':len(rows),'n_usable':len(usable),
                               'base_hits':sum(int(e['labels']['whole'][0]) for e in usable),
                               'oracle_hits':sum(int(e['labels']['whole'].max()) for e in usable),
                               'hypotheses_mean':sum(len(e['features']['base_score']) for e in usable)/max(1,len(usable))})
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--cache',required=True)
    p.add_argument('--checkpoint',required=True);p.add_argument('--out',required=True)
    p.add_argument('--candidates',type=int,default=80);p.add_argument('--beam',type=int,default=64)
    p.add_argument('--diverse',action='store_true');p.add_argument('--max-layouts',type=int,default=128)
    p.add_argument('--sampled',action='store_true');p.add_argument('--draws',type=int,default=8)
    p.add_argument('--analytic',action='store_true',help='Observation-only corrected-static proposals, projected to the same grid')
    p.add_argument('--only-cell',help='Explicit development specialization, e.g. 1,2; not full-surface training')
    p.add_argument('--only-contacts',type=int,help='Train one supplied-contact budget across ALL coverage conditions')
    p.add_argument('--threads',type=int,default=4);a=p.parse_args()
    if a.only_cell and a.only_contacts is not None:p.error('Use either --only-cell or --only-contacts')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(a.threads)
    model,saved=load_checkpoint(a.checkpoint)
    if sha(a.manifest)!=saved['manifest_sha256']:raise ValueError('Development manifest mismatch')
    rows=development_rows(a.manifest,saved['grid'],a.cache);entries=[];started=time.monotonic()
    if a.only_cell:
        cov,k=map(float,a.only_cell.split(','))
        rows=[e for e in rows if e['row']['coverage_target']==cov and e['row']['contacts_requested']==k]
    if a.only_contacts is not None:rows=[e for e in rows if e['row']['contacts_requested']==a.only_contacts]
    protocol={'schema':'graphs078-v1','manifest_sha256':sha(a.manifest),'teacher_checkpoint_sha256':sha(a.checkpoint),
              'teacher_checkpoint':str(Path(a.checkpoint).resolve()),'source_sha256':{s:sha(Path(__file__).with_name(s)) for s in SOURCE},
              'args':vars(a),'splits':dict(Counter(e['row']['split'] for e in rows)),
              'scope':'development candidates; post-hoc oracle is NOT deployment performance','test_opened':False,
              'labels_in_features':False,'walk_input':'unordered observed point set; no speed, time or invented headings'}
    dump(out/'protocol.json',protocol)
    with torch.inference_mode():
        for i,e in enumerate(rows):
            if e['sample'] is None:
                entries.append({'meta':e['row'],'features':None,'labels':None,'hypotheses':None});continue
            b=pack([e['sample']]);prediction=model(b,strength=saved.get('score_strength',1.))
            h=(sampled_hypotheses(prediction,b,a.candidates,a.beam,a.max_layouts,a.draws) if a.sampled else
               diverse_hypotheses(prediction,b,a.candidates,a.beam,a.max_layouts) if a.diverse else
               unique_hypotheses(hypotheses(prediction,b,a.candidates,a.beam)))
            analytic_status='not_requested'
            if a.analytic and e['sample']['observation']['events']:
                from .analytic077 import corrected_static
                raw=corrected_static(e['sample']['observation']);analytic_status=raw['status']
                if raw['status']=='ok':h=with_analytic_proposals(h,b,prediction,raw['boxes'],a.max_layouts)
            features=graph_features(e['sample']['observation'],b,h)
            labels=label_hypotheses(h,e['truth'])
            features['nodes']=features['nodes'].astype('float16');features['edges']=features['edges'].astype('float16')
            entries.append({'meta':e['row'],'features':features,'labels':labels,'analytic_status':analytic_status,
                            'hypotheses':{'boxes':h['boxes'],'category':h['category']}})
            if (i+1)%100==0:print(json.dumps({'done':i+1,'total':len(rows),'seconds':time.monotonic()-started}),flush=True)
    torch.save({'protocol':protocol,'entries':entries},out/'graphs.pt')
    dump(out/'oracle-summary.json',{'scope':protocol['scope'],'cells':summarize(entries),'seconds':time.monotonic()-started,
                                   'cache_sha256':sha(out/'graphs.pt')})
    print(json.dumps({'status':'built','rows':len(entries),'seconds':time.monotonic()-started}),flush=True)

if __name__=='__main__':main()
