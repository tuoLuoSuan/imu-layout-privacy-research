"""Continuous two-axis contact-resolution diagnostic, not a walking threshold."""
import argparse,json
from pathlib import Path
import numpy as np
from . import evidence_space as ES,sim_eval as SE,paths

FRACTIONS=(0.,.25,.5,.75,.8,.85,.9,.95,1.)


def run(output,seed=18031):
    scenes=[s for f in sorted(Path(paths.THOR).glob('FloorPlan*.json')) if (s:=SE.load_scene(str(f)))]
    rows=[]
    for index,scene in enumerate(scenes):
        b=np.asarray(scene['gt']['bed']);extent=b[2:]-b[:2]
        fractions=np.random.default_rng(np.random.SeedSequence([seed,index,31])).uniform(.1,.9,2)
        for spread in FRACTIONS:
            span=spread*extent
            lower=b[:2]+fractions*(extent-span)
            anchors=lower+np.linspace(0,1,3)[:,None]*span
            result=ES.bed_position_envelope([scene['W'],scene['L']],extent,anchors,.2)
            bounds=np.asarray(result['bounds']);point=(bounds[:2]+bounds[2:])/2
            cert=ES.envelope_certificate(bounds,point,.5)
            truth=(b[:2]+b[2:])/2;error=float(np.linalg.norm(point-truth))
            included=bool(np.all(truth>=bounds[:2]-1e-9) and np.all(truth<=bounds[2:]+1e-9))
            assert included and error<=cert['radius_upper_m']+1e-8
            rows.append({'scene':scene['scene'],'spread_fraction':spread,'contact_count':3,
               'contact_span_xy_m':span.tolist(),'radius_upper_m':cert['radius_upper_m'],
               'allow':cert['allow'],'error_m':error,'n_orientation_modes':len(result['modes'])})
    summary=[]
    for f in FRACTIONS:
        selected=[r for r in rows if r['spread_fraction']==f]
        summary.append({'spread_fraction':f,'n_rooms':len(selected),'success_rate':float(np.mean([r['allow'] for r in selected])),
            'certified':sum(r['allow'] for r in selected),'point_hit':sum(r['error_m']<=.5 for r in selected),
            'median_radius_upper_m':float(np.median([r['radius_upper_m'] for r in selected])),
            'median_span_xy_m':np.median([r['contact_span_xy_m'] for r in selected],axis=0).tolist()})
    record={'scope':'Continuous bed-only model: three ideal geometric contacts span both axes; no raw IMU/walk route claim',
       'seed':seed,'padding_m':.2,'target_error_m':.5,'summary':summary,'rows':rows,
       'threshold':ES.stable_threshold(summary,x_key='spread_fraction'),
       'threshold_protocol':'At least 80% of 14 rooms meet the conditional radius target; two subsequent tested fractions pass',
       'assumptions':['Exact room and bed dimensions; axis-aligned bed with either orientation',
                      'Correct bed labels and phone-in-bed observations bounded by padding',
                      'Proposed point is continuous-envelope midpoint, not the existing joint-layout output']}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8');print(json.dumps(summary));return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--seed',type=int,default=18031)
    a=p.parse_args();run(a.output,a.seed)
