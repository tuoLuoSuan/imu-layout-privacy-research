"""Same-observation comparisons for 077. Validation is the default split."""
import argparse
import csv
import json
from pathlib import Path

import torch

from .recovery076_data import read,dump,sha,load_rows,pack,check_confirmation
from .recovery076_eval import score,failed_score,static_decode,surfaces
from .recovery077_model import CandidateScorer077
from .recovery077_runtime import development_rows,decode_fast


def load_checkpoint(path):
    saved=torch.load(path,map_location='cpu',weights_only=True)
    if saved.get('architecture')!='candidate077-v1':raise ValueError('077 checkpoint required')
    for name in ('recovery077_model.py','recovery077_runtime.py','recovery076_model.py','recovery076_data.py'):
        if sha(Path(__file__).with_name(name))!=saved['source_sha256'][name]:
            raise ValueError('Inference source differs from the frozen checkpoint: '+name)
    model=CandidateScorer077(saved['width']);model.load_state_dict(saved['state_dict']);model.eval()
    return model,saved


def supported_object_metrics(rows,entries):
    by_id={e['row']['id']:e for e in entries};totals={}
    for r in rows:
        e=by_id[r['id']]
        if e['sample'] is None:continue
        obs=e['sample']['observation'];direct={v['object'] for v in obs['events']};protocol=set(direct)
        if obs['desk_relation'] and 'chair' in direct:protocol.add('desk')
        hit={m['truth'] for m in r['matches'] if m['hit']}
        for label,categories in [('direct_category_supported',direct),('protocol_category_supported',protocol)]:
            objects={k for k in e['truth'] if k.split('#')[0] in categories}
            key=r['arm']+'/'+label
            t=totals.setdefault(key,{'truth_objects':0,'hits':0,'eligible_cells':0,'all_hit_cells':0})
            t['truth_objects']+=len(objects);t['hits']+=len(hit&objects)
            if objects:t['eligible_cells']+=1;t['all_hit_cells']+=int(objects<=hit)
    return totals


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--checkpoint',required=True)
    p.add_argument('--out',required=True);p.add_argument('--split',choices=['validation','test','confirmation'],default='validation')
    p.add_argument('--cache');p.add_argument('--reference-076',help='Reuse frozen static results only when input manifest hash matches')
    p.add_argument('--include-corrected-static',dest='corrected_static',action='store_true',default=True,
                   help='Multi-bed analytic control (included by default)')
    p.add_argument('--skip-corrected-static',dest='corrected_static',action='store_false',
                   help='Profiling/smoke only; the resulting comparison is incomplete')
    p.add_argument('--threads',type=int,default=4);p.add_argument('--candidates',type=int,default=40);p.add_argument('--beam',type=int,default=32)
    a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(a.threads)
    model,saved=load_checkpoint(a.checkpoint)
    if a.split=='confirmation':check_confirmation(read(a.manifest),saved['seen_groups'],saved['seen_fingerprints'])
    elif saved['manifest_sha256']!=sha(a.manifest):raise ValueError('Different manifest requires a separately labelled confirmation')
    if a.cache:
        if a.split!='validation':raise ValueError('Development cache cannot be used for final test/confirmation')
        entries=[e for e in development_rows(a.manifest,saved['grid'],a.cache) if e['row']['split']=='validation']
    else:entries=load_rows(a.manifest,{a.split},saved['grid'])
    if not entries:raise ValueError('Empty explicit split')
    static={};reference_sha=None
    if a.reference_076:
        folder=Path(a.reference_076);meta=read(folder/'summary.json')
        if meta['manifest_sha256']!=sha(a.manifest):raise ValueError('Static reference has different observation manifest')
        for line in (folder/'rows.jsonl').read_text(encoding='utf-8').splitlines():
            r=json.loads(line)
            if r['arm'] in ('outline','unrestricted_static','corrected_static'):static[(r['id'],r['arm'])]=r
        expected={(e['row']['id'],arm) for e in entries for arm in ('outline','unrestricted_static')}
        if not expected<=set(static):raise ValueError('Static reference does not cover every requested ID')
        reference_sha=sha(folder/'rows.jsonl')
    rows=[]
    with torch.inference_mode(),(out/'rows.jsonl').open('w',encoding='utf-8') as f:
        for i,e in enumerate(entries):
            meta=e['row'];sample=e['sample']
            arms=['learned','fixed_kernel','no_contacts','outline','unrestricted_static']
            if a.corrected_static:arms.append('corrected_static')
            for arm in arms:
                boxes={};status='ok';error=None
                if (meta['id'],arm) in static:
                    row=static[(meta['id'],arm)].copy();row['reused_frozen_static']=True
                else:
                    try:
                        if sample is None:result=failed_score();status='acquisition_failed';error=meta.get('error')
                        elif arm in ('outline','unrestricted_static','corrected_static'):
                            if arm=='corrected_static':
                                from .analytic077 import corrected_static
                                raw=corrected_static(sample['observation'])
                            else:raw=static_decode(sample['observation'],arm=='unrestricted_static')
                            boxes=raw.get('boxes',{})
                            result=score(boxes,e['truth']);status=raw['status']
                        else:
                            b=pack([sample])
                            if arm=='no_contacts':b['event_valid'].zero_()
                            prediction=model(b,strength=0. if arm=='fixed_kernel' else saved.get('score_strength',1.))
                            boxes=decode_fast(prediction,b,a.candidates,a.beam)[0];result=score(boxes,e['truth'])
                    except Exception as exc:
                        result=failed_score();status='decoder_failed';error=repr(exc)
                    row={k:meta[k] for k in ('id','group','coverage_target','contacts_requested')}
                    row.update(arm=arm,usable=sample is not None,status=status,error=error,boxes=boxes,**result)
                rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
            if (i+1)%100==0:print(json.dumps({'cells_done':i+1,'total':len(entries)}),flush=True)
    result=surfaces(rows,draws=4000)
    dump(out/'summary.json',{'architecture':'candidate077-v1','split':a.split,'checkpoint_epoch':saved['epoch'],
                             'manifest_sha256':sha(a.manifest),'checkpoint_sha256':sha(a.checkpoint),
                             'selected_score_strength':saved.get('score_strength',1.),
                             'source_sha256':{name:sha(Path(__file__).with_name(name)) for name in
                                               ('eval077.py','recovery077_model.py','recovery077_runtime.py','recovery076_eval.py',
                                                'analytic077.py','multi_instance.py','continuous_regions.py')},
                             'corrected_analytic_included':a.corrected_static,
                             'scope':saved['scope'],'same_observations':True,
                             'common_search_budget_for_learned_and_fixed':{'candidates':a.candidates,'beam':a.beam},
                             'static_reference_sha256':reference_sha,
                             'supported_categories':supported_object_metrics(rows,entries),**result})
    with (out/'surface.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(result['cells'][0]));writer.writeheader();writer.writerows(result['cells'])
    print(json.dumps({'status':'complete','rows':len(rows),'split':a.split}),flush=True)

if __name__=='__main__':main()
