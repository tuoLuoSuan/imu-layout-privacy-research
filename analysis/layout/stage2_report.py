"""Compact, source-linked summaries of the second activity audit."""
import argparse
import json
from pathlib import Path
import numpy as np
from . import evidence_space as ES


def run(package,session,output):
    p=Path(package)
    def read(name):return json.loads((p/name).read_text(encoding='utf-8'))
    ablation=read('span-ablation.json');risk=read('radius-audit.json')
    semantics=read('semantics.json');desk=read('desk-corrected.json')
    curves=read('budget-corrected.json');scan={}
    for label,file in [('central_seed1','span-sweep.json'),('central_seed2','span-sweep-seed2.json'),
                       ('offset_seed1','span-offset-seed1.json'),('offset_seed2','span-offset-seed2.json')]:
        d=read(file);thresholds={}
        for obj in ['bed','cab']:
            rows=[]
            for span in [0.,.25,.5,.75,1.,1.5]:
                v=d['summary'].get(f'{obj}:{span:.2f}')
                if v is None:continue
                rows.append({'span_m':span,'success_rate':v['hit_rate'] if v['n']==v['total_rooms'] else 0.})
            thresholds[obj]=ES.stable_threshold(rows,x_key='span_m')
        scan[label]={'scope':d['scope'],'position_mode':d['position_mode'],'seed':d['seed'],
                     'summary':d['summary'],'conditional_point_thresholds':thresholds,
                     'threshold_note':'Requires all 14 rooms eligible, >=80% point success and two later tested passes; not raw IMU'}
    for name in {r['scene'] for r in semantics['rows']}:
        for budget in [32.,96.]:
            selected=[r for r in semantics['rows'] if r['scene']==name and r['budget_m']==budget]
            assert len({r['path_sha256'] for r in selected})==1
            assert len({r['event_positions_sha256'] for r in selected})==1
    prediction=json.loads((Path(session)/'prediction.json').read_text(encoding='utf-8'))
    resolution={}
    for label,file in [('seed1','bed-resolution-seed1.json'),('seed2','bed-resolution-seed2.json')]:
        d=read(file);resolution[label]={k:d[k] for k in ['scope','seed','padding_m','target_error_m','summary','threshold','threshold_protocol','assumptions']}
    reference={'bed':[1.17,1.96,2.695,4.045],'desk':[.05,1.05,.65,2.10],
               'cab':[.05,0,.65,1.05],'chair':[1.11,.92,1.55,1.36]}
    error={o:float(np.linalg.norm((np.asarray(b[:2])+b[2:])/2-
          (np.asarray(reference[o][:2])+reference[o][2:])/2)) for o,b in prediction['boxes'].items()}
    prefix=read('real-prefix.json')
    record={'schema_version':2,'scope':'14 geometric development rooms and one existing controlled real room',
      'paired_ablation':ablation['matched_comparisons'],'contact_scans':scan,'continuous_bed_resolution':resolution,
      'radius_audit':risk,'budget_curves':curves,
      'semantics':{k:semantics[k] for k in ['scope','A','control','seed','scene_count','summary']},
      'semantic_path_and_position_hashes_matched':True,
      'desk':{k:desk[k] for k in ['budget_m','oracle_bearing_scope','summary']},
      'real':{'center_error_to_frozen_reference_m':error,'rotation_deg':prediction['rot_deg'],
              'prefix_rows':[{k:r[k] for k in ['T','status','err','estimated_prefix_coverage']} for r in prefix['rows']],
              'reference_scope':'Mixed provided references; chair provenance includes anchor/user confirmation, not independent scanned truth'},
      'limitations':['Conditional envelope radius does not verify truth inclusion at runtime',
       'A carries spatial coordinates and localisation information; it is not action labels alone',
       'K is leave-room-out position density, not true wall identity or room-type revelation',
       'Oracle direction is a bearing to the true desk centre, stronger than observed body facing',
       'Counterfactual span scans do not establish an achievable natural-activity or raw-IMU threshold',
       'No new real room, new sensor, model retraining or raw-IMU simulation validation in this audit']}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8')
    print('source-linked summary written',output);return record


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('package');a.add_argument('--session',required=True);a.add_argument('--output',required=True)
    v=a.parse_args();run(v.package,v.session,v.output)
