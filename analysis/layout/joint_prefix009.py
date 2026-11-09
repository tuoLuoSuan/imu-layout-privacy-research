"""Raw joint-input prefix curve, with all future sensor rows removed first.

This is exploratory sensitivity for the working synthetic-domain wrist rule,
not confirmation of the real-trained wrist RF transfer (which failed on the
synthetic cohort). Coverage is evaluation-only; never fed to the estimator.
"""
import argparse,csv,json,concurrent.futures
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .joint009 import infer
from .sim_handset import generate
from .exp_walk_range import coverage_route
from .fig_main_activity3d import interval

FRACTIONS=[.5,.6,.65,.7,.75,.8,.9,1.]


def one(task):
    source,target,native,wrist_model=map(Path,task[:4]);fractions=task[4] if len(task)>4 else FRACTIONS
    target.mkdir(parents=True,exist_ok=True);resultfile=target/'results.json'
    if resultfile.exists():return json.loads(resultfile.read_text())
    original=json.loads((source/'results.json').read_text());scene=M.load_native(native);scene['S']=np.array(original['priors']['start']);truth={k.split('#')[0]:b for k,b in scene['gt'].items()};gen=generate(scene,original['seed']);grid=coverage_route(scene);free=grid['points'][grid['free_ids']]
    channels={}
    for device,sensor in [('phone','accelerometer'),('phone','gyroscope'),('watch','accelerometer')]:
        with (source/'input'/device/(sensor+'.csv')).open(encoding='utf-8',newline='') as file:r=csv.DictReader(file);channels[device,sensor]=(list(r.fieldnames),list(r))
    rows=[]
    for fraction in fractions:
        T=original['duration_s']*fraction;session=target/('prefix-'+str(fraction));origin=1700000000000000000;cut=origin+int(T*1e9)
        for (device,sensor),(fields,records) in channels.items():
            output=session/device;output.mkdir(parents=True,exist_ok=True)
            picked=[r for r in records if int(r['sensor_timestamp_ns'])<=cut and int(r.get('received_elapsed_realtime_ns',r['sensor_timestamp_ns']))<=cut]
            with (output/(sensor+'.csv')).open('w',encoding='utf-8',newline='') as file:w=csv.DictWriter(file,fieldnames=fields);w.writeheader();w.writerows(picked)
        prediction=infer(session,original['priors'],wrist_model,budget_s=T,watch_mode='rule');score=M.score_instances(prediction.get('boxes',{}),truth)
        truewalk=gen['truth']['pos'][(gen['t']<=T)&(np.array(gen['truth']['label'])=='walk'),:2][::4]
        covered=np.zeros(len(free),bool)
        for start in range(0,len(truewalk),200):covered|=np.any(np.sum((free[:,None,:]-truewalk[None,start:start+200,:])**2,axis=2)<=.25**2,axis=1)
        contacts=len(prediction.get('candidates',[{}])[0].get('contact_inputs',{})) if prediction.get('candidates') else 0
        rows.append({'fraction':fraction,'budget_s':T,'coverage_free':float(covered.mean()),'recognized_anchor_types':contacts,'whole':score['all_instances_hit'],'f1':score['f1'],'score':score})
    result={'scene':source.name,'rows':rows};resultfile.write_text(json.dumps(result,indent=1),encoding='utf-8');return result


def run(source,native,out,wrist_model,workers=3,fractions=None):
    source,native,out,wrist_model=map(Path,(source,native,out,wrist_model));out.mkdir(exist_ok=True);cases=sorted(p for p in source.glob('multi-*') if (p/'results.json').exists())
    fractions=FRACTIONS if fractions is None else fractions
    if len(cases)!=100:raise ValueError('All100 predefined room cases required')
    protocol={'n_rooms':100,'fractions':fractions,'arm':'joint_rule_watch','exploratory':True,'not_the_real_trained_RF_arm':True,'prefix':'Remove future event and callback-receipt rows before ANY inference; wrist has ideal zero-latency shared simulation clock','coverage':'Evaluation only,0.25m walk-neighbourhood coverage of body-clear floor','metric':'Four centres within0.5m, separate from mean instanceF1','reference_whole':.8,'reference_f1':.8,'independent_unit':'room; same room repeated across prefixes'}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=1),encoding='utf-8');records=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for i,r in enumerate(pool.map(one,[(str(p),str(out/p.name),str(native/(p.name+'.json')),str(wrist_model),fractions) for p in cases]),1):
            records.append(r)
            if i%10==0:print(json.dumps({'prefix_rooms':i,'total':100}),flush=True)
    cells=[]
    for f in fractions:
        rows=[r for case in records for r in case['rows'] if r['fraction']==f];rate,lo,hi=interval([r['whole'] for r in rows],True)
        cells.append({'fraction':f,'n_rooms':100,'whole_hits':sum(r['whole'] for r in rows),'whole_rate':rate,'whole_wilson_ci':[lo,hi],'mean_f1':float(np.mean([r['f1'] for r in rows])),'median_budget_s':float(np.median([r['budget_s'] for r in rows])),'median_coverage_free':float(np.median([r['coverage_free'] for r in rows])),'median_anchor_types':float(np.median([r['recognized_anchor_types'] for r in rows]))})
    result={'protocol':protocol,'cells':cells,'first_sampled_whole80':next((r for r in cells if r['whole_rate']>=.8),None),'scope':'Conditional exploratory within-protocol boundary, not a universalIMU threshold or a guarantee for an individual room','rows':records}
    (out/'summary.json').write_text(json.dumps(result,indent=1),encoding='utf-8');print(json.dumps(cells));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--native',required=True);p.add_argument('--out',required=True);p.add_argument('--wrist-model',required=True);p.add_argument('--workers',type=int,default=3);p.add_argument('--fractions',type=float,nargs='+');a=p.parse_args();run(a.source,a.native,a.out,a.wrist_model,a.workers,a.fractions)
