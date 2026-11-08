"""Evaluation-only crossed truth/prediction diagnosis after synthetic IMU runs.

Truth-assisted arms are never raw-IMU inference results. They test whether
trajectory, action recognition or incompatible contact semantics explain a
failure. Existing raw inputs, predictions and model weights remain untouched.
"""
import argparse,json
from pathlib import Path
import numpy as np
from . import multi_instance as M,sim_motion as SM,layout_solver as LS


def truth_runs(time,labels):
    starts=np.r_[0,np.flatnonzero(labels[1:]!=labels[:-1])+1];ends=np.r_[starts[1:],len(labels)];dt=float(np.median(np.diff(time)))
    return [[str(labels[a]),float(time[a]),float(time[b-1]+dt)] for a,b in zip(starts,ends)]


def run(source,out):
    source,out=map(Path,(source,out));out.mkdir(parents=True,exist_ok=True);result=[]
    for case in sorted(p for p in source.iterdir() if p.is_dir() and (p/'result.json').exists()):
        truth=np.load(case/'evaluation-truth.npz');estimate=np.load(case/'input/ronin-xy.npy');centres=estimate[:,0]-.5
        phone=np.c_[np.interp(centres,truth['time'],truth['position'][:,0]),np.interp(centres,truth['time'],truth['position'][:,1])]
        body=np.c_[np.interp(centres,truth['time'],truth['body'][:,0]),np.interp(centres,truth['time'],truth['body'][:,1])]
        labels_true={'runs':truth_runs(truth['time'],truth['labels'])};labels_pred=json.loads((case/'input/actions.json').read_text(encoding='utf-8'))
        rows=[]
        for name,positions,actions in [('predicted_both',estimate[:,1:3],labels_pred),('truth_device_path_predicted_actions',phone,labels_pred),('predicted_path_truth_actions',estimate[:,1:3],labels_true),('truth_device_path_truth_actions',phone,labels_true),('truth_body_path_truth_actions',body,labels_true)]:
            dst=out/case.name/name;dst.mkdir(parents=True,exist_ok=True)
            np.save(dst/'ronin-xy.npy',np.c_[estimate[:,0],positions,estimate[:,3]])
            (dst/'actions.json').write_text(json.dumps(actions),encoding='utf-8')
            r=LS.solve(str(dst));prediction=r[0] if isinstance(r,tuple) else r
            rows.append({'arm':name,'oracle_assisted':name!='predicted_both','status':prediction['status'],'score':M.score_instances(prediction.get('boxes',{}),SM.FURN)})
        result.append({'case':case.name,'rows':rows});print(json.dumps({'case':case.name,'tp_by_arm':{r['arm']:r['score']['tp'] for r in rows}}),flush=True)
    record={'n_cases':len(result),'n_rooms':1,'scope':__doc__,'rows':result};(out/'results.json').write_text(json.dumps(record,indent=1),encoding='utf-8');return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.source,a.out)
