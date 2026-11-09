"""Existing real phone+watch case, with explicit nominal-clock qualification.

The phone trajectory must be a fresh frozen-model raw replay. Cabinet events
are then replaced solely by the wrist classifier. No target position is used
to choose a clock offset; all declared offsets are evaluated and preserved.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
import numpy as np
from . import layout_solver as LS,multi_instance as M
from .watch_channel import read_watch,clock_interval,zero_wall_ms
from .watch_cabinet import fuse
from .wrist_binary import predict


def run(replay,baseline,wrist_model,out):
    replay,baseline,wrist_model,out=map(Path,(replay,baseline,wrist_model,out));out.mkdir(parents=True,exist_ok=True)
    phone=json.loads((replay/'actions.json').read_text(encoding='utf-8'));old=json.loads((baseline/'prediction.json').read_text());fresh=json.loads((replay/'prediction.json').read_text())
    t,A,obs=read_watch(replay/'watch.jsonl');lo,hi=clock_interval(obs)
    if hi<=lo:raise ValueError('Nominal clock interval inconsistent')
    aligned=(t+(lo+hi)/2000.-zero_wall_ms(str(replay)))/1000;halfwidth=(hi-lo)/2000./1000.
    truth={'bed':[1.17,1.96,2.695,4.045],'desk':[.05,1.05,.65,2.1],'cab':[.05,0,.65,1.05],'chair':[1.11,.92,1.55,1.36]};rows=[]
    for shift in [-2.,-.5,-halfwidth,0.,halfwidth,.5,2.]:
        d=out/('shift-'+str(round(shift,6)));d.mkdir(exist_ok=True);shutil.copyfile(replay/'ronin-xy.npy',d/'ronin-xy.npy');watch=predict(aligned+shift,A,wrist_model);joint=fuse(phone,watch)
        (d/'actions.json').write_text(json.dumps(joint),encoding='utf-8');r=LS.solve(str(d));pred=r[0] if isinstance(r,tuple) else r
        # The legacy optional watch summary sees no copied raw file in each
        # shift directory. Record the actual wrist-driven inference here.
        pred['watch']={'status':'used_as_cabinet_event_source','axes':3,'gyro_used':False,
                       'cabinet_runs':watch['runs'],'phone_cabinet_used':False,
                       'raw_sha256':hashlib.sha256((replay/'watch.jsonl').read_bytes()).hexdigest(),
                       'physical_clock_accepted':False}
        (d/'prediction.json').write_text(json.dumps(pred,indent=1),encoding='utf-8')
        rows.append({'shift_s':shift,'watch_runs':watch['runs'],'cabinet_source':'watch_only','prediction':pred,'score':M.score_instances(pred.get('boxes',{}),truth)})
    result={'real_session':'s-59d570ee','raw_watch_sha256':hashlib.sha256((replay/'watch.jsonl').read_bytes()).hexdigest(),'phone_trajectory_exactly_equal_previous_replay':bool(np.array_equal(np.load(replay/'ronin-xy.npy'),np.load(baseline/'ronin-xy.npy'))),'phone_baseline_max_box_delta_m':{k:float(np.max(abs(np.asarray(v)-old['boxes'][k]))) for k,v in fresh['boxes'].items()},'software_clock_halfwidth_s':halfwidth,'physical_clock_accepted':False,'label_source':'Classifier trained on r1/r2 cue/software-clock data; real main room used previously in development, not an untouched external test','rows':rows}
    (out/'results.json').write_text(json.dumps(result,indent=1),encoding='utf-8');print(json.dumps({'baseline_identical':result['phone_trajectory_exactly_equal_previous_replay'],'rows':[(r['shift_s'],r['score']['tp']) for r in rows]}));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--replay',required=True);p.add_argument('--baseline',required=True);p.add_argument('--wrist-model',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.replay,a.baseline,a.wrist_model,a.out)
