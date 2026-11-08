"""Fixed-threshold geometry stress tests; no raw-IMU or frequency-of-risk claim."""
import argparse,json
from pathlib import Path
import numpy as np
from . import evidence_space as ES,sim_eval as SE,paths

MAGNITUDES=(.05,.10,.20,.30,.50)
SPREADS=(.90,1.)
SEEDS=(18031,18032)
DIRECTIONS=16


def distance_to_box(points,box):
    return np.linalg.norm(np.maximum(box[:2]-points,points-box[2:]).clip(min=0),axis=1)


def infer_case(room,dimensions,observed,max_bad):
    r=ES.bed_outlier_envelope(room,dimensions,observed,.20,max_bad)
    if r['bounds'] is None:return {'status':'conflict','allow':False,'radius_upper_m':None,'point':None}
    b=np.asarray(r['bounds']);point=(b[:2]+b[2:])/2
    cert=ES.envelope_certificate(b,point,.5)
    return {'status':'conditional','allow':cert['allow'],'radius_upper_m':cert['radius_upper_m'],
            'point':point.tolist(),'bounds':b.tolist()}


def summarize(rows):
    out=[]
    keys=sorted({(r['spread_fraction'],r['scenario'],r['max_bad_events']) for r in rows})
    for spread,scenario,budget in keys:
        selected=[r for r in rows if (r['spread_fraction'],r['scenario'],r['max_bad_events'])==(spread,scenario,budget)]
        allowed=[r for r in selected if r['allow']]
        names=sorted({r['scene'] for r in selected})
        wrong=[r for r in allowed if r['error_m']>.5+1e-8]
        points=[r for r in selected if r['error_m'] is not None]
        out.append({'spread_fraction':spread,'scenario':scenario,'max_bad_events':budget,'n_cases':len(selected),
            'n_independent_rooms':len(names),'allowed':len(allowed),'wrong_allowed':len(wrong),
            'allowed_share':len(allowed)/len(selected),'wrong_given_allowed':len(wrong)/len(allowed) if allowed else None,
            'point_outputs':len(points),'point_hits':sum(r['error_m']<=.5 for r in points),
            'point_hit_share_all':sum(r['error_m']<=.5 for r in points)/len(selected),
            'median_point_error_m':float(np.median([r['error_m'] for r in points])) if points else None,
            'conflicts':sum(r['status']=='conflict' for r in selected),
            'model_condition_failures':sum(not r['model_condition_holds'] for r in selected),
            'rooms_all_tested_cases_allowed':sum(all(r['allow'] for r in selected if r['scene']==name) for name in names),
            'rooms_with_any_wrong_allowed':len({r['scene'] for r in wrong})})
    return out


def run(output,summary_output=None):
    scenes=[s for f in sorted(Path(paths.THOR).glob('FloorPlan*.json')) if (s:=SE.load_scene(str(f)))]
    rows=[]
    for index,scene in enumerate(scenes):
        box=np.asarray(scene['gt']['bed']);dimensions=box[2:]-box[:2];truth=(box[:2]+box[2:])/2
        room=np.array([scene['W'],scene['L']])
        for seed in SEEDS:
            fractions=np.random.default_rng(np.random.SeedSequence([seed,index,31])).uniform(.1,.9,2)
            # Geometry-placement and false-positive streams are independent.
            rng=np.random.default_rng(np.random.SeedSequence([seed,index,29031]))
            false_pool=rng.uniform(0,1,(2048,2))*room
            false_pool=false_pool[distance_to_box(false_pool,box)>.20+1e-8][:DIRECTIONS]
            if len(false_pool)<DIRECTIONS:raise ValueError('Frozen protocol lacks false-positive floor points')
            for spread in SPREADS:
                span=spread*dimensions;lower=box[:2]+fractions*(dimensions-span)
                clean=lower+np.linspace(0,1,3)[:,None]*span
                scenarios=[('clean',0,clean),('miss_endpoint',0,clean[1:]),('miss_middle',0,clean[[0,2]])]
                for magnitude in MAGNITUDES:
                    delta=clean.mean(axis=0)-clean;length=np.linalg.norm(delta,axis=1)
                    contraction=delta/np.maximum(length[:,None],1e-12)*np.minimum(length,magnitude)[:,None]
                    scenarios.append((f'contraction_{magnitude:.2f}',0,clean+contraction))
                    for j in range(DIRECTIONS):
                        shift=magnitude*np.array([np.cos(2*np.pi*j/DIRECTIONS),np.sin(2*np.pi*j/DIRECTIONS)])
                        scenarios.append((f'common_{magnitude:.2f}',j,clean+shift))
                repeated=clean[[0,0,2,2]]
                repeated_middle=clean[[0,1,1,2]]
                for j,false in enumerate(false_pool):
                    scenarios.append(('false_positive',j,np.vstack([clean,false])))
                    scenarios.append(('repeated_endpoints_false_positive',j,np.vstack([repeated,false])))
                    scenarios.append(('repeated_middle_false_positive',j,np.vstack([repeated_middle,false])))
                    shift=.10*np.array([np.cos(2*np.pi*j/DIRECTIONS),np.sin(2*np.pi*j/DIRECTIONS)])
                    scenarios.append(('repeated_false_common_0.10',j,np.vstack([repeated+shift,false])))
                    delta=repeated.mean(axis=0)-repeated;length=np.linalg.norm(delta,axis=1)
                    contraction=delta/np.maximum(length[:,None],1e-12)*np.minimum(length,.10)[:,None]
                    scenarios.append(('repeated_false_contraction_0.10',j,np.vstack([repeated+contraction,false])))
                for label,trial,observed in scenarios:
                    incompatible=int(np.sum(distance_to_box(observed,box)>.20+1e-8))
                    for max_bad in [0,1]:
                        result=infer_case(room,dimensions,observed,max_bad)
                        condition=incompatible<=max_bad
                        error=None if result['point'] is None else float(np.linalg.norm(np.asarray(result['point'])-truth))
                        if condition:
                            assert result['point'] is not None
                            b=np.asarray(result['bounds'])
                            assert np.all(truth>=b[:2]-1e-8) and np.all(truth<=b[2:]+1e-8)
                            assert error<=result['radius_upper_m']+1e-8
                        rows.append({'scene':scene['scene'],'seed':seed,'spread_fraction':spread,'scenario':label,
                           'trial':trial,'max_bad_events':max_bad,'event_count':len(observed),
                           'incompatible_events':incompatible,'model_condition_holds':condition,
                           'observed_span_xy_m':np.ptp(observed,axis=0).tolist(),
                           'status':result['status'],'allow':result['allow'],'radius_upper_m':result['radius_upper_m'],'error_m':error})
        print(scene['scene'],'done',flush=True)
    record={'scope':'Frozen bed-centre threshold stress; synthetic contact geometry, no raw IMU inference',
        'protocol':{'spread_fractions':list(SPREADS),'padding_m':.20,'target_error_m':.5,'magnitudes_m':list(MAGNITUDES),
          'spread_basis':'Generator truth before perturbation; observed spans are stored separately',
          'contact_placement_seeds':list(SEEDS),'common_offset_directions':DIRECTIONS,
          'fixed_furniture':True,'event_fault_budgets':[0,1],'false_positive_model':'Extra event outside the true padded bed footprint',
          'decoder':'Union over all potentially erroneous-event choices; never truth-selected',
          'statistical_unit':'14 independent development geometries; directions, visits and seeds are repeated stress conditions'},
        'scene_count':len(scenes),'summary':summarize(rows),'rows':rows}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8')
    if summary_output:
        import hashlib
        summary={k:v for k,v in record.items() if k!='rows'}
        summary['full_record_sha256']=hashlib.sha256(Path(output).read_bytes()).hexdigest()
        summary['evaluation_rows']=len(rows)
        groups={}
        for r in rows:
            key=(r['spread_fraction'],r['scenario'],r['max_bad_events'],r['scene'])
            group=groups.setdefault(key,{'n':0,'allowed':0,'wrong_allowed':0})
            group['n']+=1;group['allowed']+=int(r['allow'])
            group['wrong_allowed']+=int(r['allow'] and r['error_m']>.5+1e-8)
        summary['per_room']=[{'spread_fraction':key[0],'scenario':key[1],'max_bad_events':key[2],
             'scene':key[3],**value,'allowed_share':value['allowed']/value['n']} for key,value in sorted(groups.items())]
        summary['interpretation']=['Output share means radius <=0.5m, distinct from actual point accuracy',
             'Stress directions and synthetic false events do not estimate real-world error probabilities',
             'The one-bad-event bound is an assumption, not a validated action-recognition error rate',
             'Event redundancy means repeated visits, not overlapping windows from the same interaction']
        Path(summary_output).write_text(json.dumps(summary,ensure_ascii=False,indent=1),encoding='utf-8')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--summary-output')
    a=p.parse_args();r=run(a.output,a.summary_output)
    print(json.dumps({'rooms':r['scene_count'],'evaluation_rows':len(r['rows'])}))
