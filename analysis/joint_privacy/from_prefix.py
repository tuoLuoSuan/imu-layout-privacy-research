"""Bridge one already validated phone prefix to phone/oracle evaluation.

No real wrist probabilities are synthesized. Later paired inference replaces
the empty prediction streams, with checked pairing and held-out provenance.
"""
import argparse,csv,hashlib,json
from pathlib import Path
from .attack import run_attack
from .output import write_json

def phone_attack(directory,index,pair_id,*,task_start_s=0.):
    directory=Path(directory);report=json.loads((directory/'prefixes.json').read_text(encoding='utf-8'))
    summary=report['prefixes'][index]
    rows=[]
    if summary['status']=='adapted_arrival_prefix_only':
        with (directory/('prefix-%03d'%index)/'velocity.csv').open(encoding='utf-8',newline='') as f:
            for r in csv.DictReader(f):
                end=float(r['target_end_s']);rows.append({'center_s':float(r['center_s']),
                    'target_end_s':end,'available_s':max(end,float(summary['last_raw_arrival_s'])),
                    'vx':float(r['vx_m_s_model']),'vy':float(r['vy_m_s_model'])})
    support=report['source'].get('recorded_stop_s')
    if support is None:raise ValueError('Authoritative recorded stop required for saved-prefix bridge')
    document={'schema_version':2,'synthetic':False,'paired_session_id':pair_id,
        'observation_start_s':task_start_s,
        'budget_s':summary['budget_s'],'support_end_s':support,'phone_predictions':rows,
        'probability_streams':{'phone':[],'joint':[]},'probability_provenance':{},
        'clock_contract':None,'gate_policy':{'mode':'soft'},'seed':58}
    result=run_attack(document)
    result['phone_source']={'prefix_directory':str(directory),'prefix_index':index,'native_source':report['source'],
        'prefix_report_sha256':hashlib.sha256((directory/'prefixes.json').read_bytes()).hexdigest(),
        'processing_completion_latency_measured':False}
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--index',type=int,required=True)
    p.add_argument('--pair-id',required=True);p.add_argument('--task-start',type=float,default=0.)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=phone_attack(args.directory,args.index,args.pair_id,task_start_s=args.task_start);write_json(args.output,result)
    print(json.dumps({'status':result['status'],'variants':list(result['variants']),'output':str(args.output)}))

if __name__=='__main__':main()
