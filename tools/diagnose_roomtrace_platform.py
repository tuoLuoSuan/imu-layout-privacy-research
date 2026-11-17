"""Compare a synthetic case's intermediate scores across numerical platforms."""
import argparse,json,sys,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from roomtrace.cli import models,PRIMARY,read
from analysis.layout.recovery076_data import prepare,pack
from analysis.layout.recovery088_spatial_runtime import residual_field

def main():
    p=argparse.ArgumentParser();p.add_argument('--write-reference',action='store_true');a=p.parse_args()
    mod=models(2);m=next(x for x in read(PRIMARY)['rows'] if x['status']=='ok' and x['coverage_target']==.25 and x['contacts_requested']==0)
    b=pack([prepare(read(PRIMARY.parent/m['input']))]);parent=mod['parents']
    with torch.inference_mode():
        o=parent['teacher'](b,strength=parent['teacher_saved']['score_strength'])
        add=residual_field(read(PRIMARY.parent/m['input']),b,mod['cnn'])
        prob=(o['log_prob']+add).log_softmax(-1)
    arrays={'centres':b['centres'].numpy(),'walk_cost':b['walk_cost'].numpy(),
            'teacher_log_prob':o['log_prob'].numpy(),'spatial_residual':add.numpy(),'combined_log_prob':prob.numpy()}
    current={'case_id':m['id'],'arrays':{k:v.tolist() for k,v in arrays.items()}}
    path=ROOT/'reproducibility/platform-reference-zero-cell.json'
    if a.write_reference:
        path.write_text(json.dumps(current,separators=(',',':')),encoding='utf-8');return
    reference=read(path)
    report={'platform':platform.platform(),'torch':torch.__version__,'numpy':np.__version__,
            'cpu_dispatch':torch.backends.cpu.get_cpu_capability(),'case_id':m['id'],
            'max_absolute_delta':{k:float(np.abs(v-np.asarray(reference['arrays'][k],dtype=v.dtype)).max()) for k,v in arrays.items()},
            'slot_top10':[]}
    for slot in range(prob.shape[1]):
        v=prob[0,slot].numpy();idx=np.argsort(-v,kind='stable')[:10]
        report['slot_top10'].append({'slot':slot,'category':int(b['category'][0,slot]),'indices':idx.tolist(),'scores':v[idx].tolist()})
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
