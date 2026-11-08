"""Summarise fixed-grid activity studies without dropping unreached rooms."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.stats import beta


def coverage_bounds(rows, level, tolerance='0.5'):
    """First *tested* prefix above level; unreached rooms remain in denominator."""
    names=sorted({r['scene'] for r in rows})
    reached=[]
    for name in names:
        candidates=sorted([r for r in rows if r['scene']==name and r['coverage']>=level],
                          key=lambda r:r['budget_m'])
        if candidates:reached.append(candidates[0])
    n=len(names);k=sum(r['scores'][tolerance]['full_point_hit'] for r in reached)
    return {'coverage_query':level,'n_rooms':n,'reached':len(reached),'successes':int(k),
            'unreached':n-len(reached),'success_lower':k/n if n else None,
            'success_upper':(k+n-len(reached))/n if n else None,
            'endpoint':'First tested distance prefix reaching coverage; unreached outcomes unknown, not failures'}


def binomial_interval(k,n):
    return [float(beta.ppf(.025,k,n-k+1)) if k else 0.,
            float(beta.ppf(.975,k+1,n-k)) if k<n else 1.]


def summarise(package,output):
    package=Path(package)
    experiments={}
    for label,name in [('development','frontier-development.json'),('matched_noise','frontier-noise-matched.json'),
                       ('new_route_seed','frontier-seed-confirm.json'),('new_seed_noise','frontier-noise-010.json')]:
        record=json.loads((package/name).read_text(encoding='utf-8'))
        queries=[]
        for policy in ['local_repeat','dispersed']:
            for arm in ['P-U','P-K','T-U','A-U','TA-U','TA-K','P-prototype']:
                rows=[r for r in record['rows'] if r['policy']==policy and r['arm']==arm]
                queries.extend(dict(coverage_bounds(rows,c),policy=policy,arm=arm) for c in [.1,.2,.3,.4,.5,.6])
        experiments[label]={k:record[k] for k in ['scope','seed','noise_bound_m','scene_count','protocol','thresholds',
                                                   'per_object_protocol_thresholds','summary','failures']}
        experiments[label]['coverage_queries']=queries
        experiments[label]['n_evaluations']=len(record['rows'])
    original=json.loads((package/'frontier-development.json').read_text(encoding='utf-8'))
    paired=[];rng=np.random.default_rng(90210)
    for obj in ['bed','desk','cab','chair']:
        def values(policy):
            return {r['scene']:float(r['scores']['0.5']['center_error_m'][obj] is not None and
                       r['scores']['0.5']['center_error_m'][obj]<=.5) for r in original['rows']
                       if r['arm']=='TA-U' and r['policy']==policy and r['budget_m']==96.}
        a,b=values('local_repeat'),values('dispersed');names=sorted(set(a)&set(b))
        delta=np.array([b[n]-a[n] for n in names]);boot=rng.choice(delta,(10000,len(delta)),replace=True).mean(axis=1)
        paired.append({'object':obj,'n_rooms':len(names),'local_successes':int(sum(a.values())),
                       'dispersed_successes':int(sum(b.values())),'paired_rate_gain':float(delta.mean()),
                       'room_bootstrap_95_interval':np.quantile(boot,[.025,.975]).tolist(),
                       'scope':'Exploratory matched development-room comparison, not new-room confirmation'})
    fine=json.loads((package/'fine-prefix.json').read_text(encoding='utf-8'))
    rows=fine['rows'];passed=[r for r in rows if len(r['err'])==4 and max(r['err'].values())<=.5]
    first=passed[0];before=rows[rows.index(first)-1]
    fine_summary={'criterion':'All four emitted and each Euclidean centre error <=0.50 m',
                  'last_failing_budget_s':before['T'],'first_passing_budget_s':first['T'],
                  'coverage_previous_estimated':before['estimated_prefix_coverage'],
                  'coverage_passing_estimated':first['estimated_prefix_coverage'],'errors_m':first['err'],
                  'all_subsequent_tested_points_pass':all(len(r['err'])==4 and max(r['err'].values())<=.5 for r in rows if r['T']>=first['T']),
                  'scope':'Post-development single-record grid localisation; not prospective or cross-room threshold'}
    (package/'fine-trigger-summary.json').write_text(json.dumps(fine_summary,ensure_ascii=False,indent=2),encoding='utf-8')
    diagnostics=json.loads((package/'activity-diagnostics.json').read_text(encoding='utf-8'))
    # Public summary omits the long route; its construction is reproducible in source.
    witness={k:v for k,v in diagnostics['witness'].items() if k!='walk'}
    physics=json.loads((package.parent.parent/'layout-recon/2026-11-08-activity-simulation-final/sim-check.json').read_text(encoding='utf-8'))
    real_prediction=json.loads((package.parent.parent/'layout-recon/2026-11-08-activity-regression-final/prediction.json').read_text(encoding='utf-8'))
    reference={'bed':[1.17,1.96,2.695,4.045],'desk':[.05,1.05,.65,2.10],
               'cab':[.05,0,.65,1.05],'chair':[1.11,.92,1.55,1.36]}
    real_errors={o:float(np.linalg.norm((np.asarray(b[:2])+b[2:])/2-
                     (np.asarray(reference[o][:2])+reference[o][2:])/2)) for o,b in real_prediction['boxes'].items()}
    record={'schema_version':1,'unit':'Independent geometric development room; route/noise repetitions do not increase n',
            'experiments':experiments,'fine_prefix':fine_summary,
            'fine_prefix_rows':[{k:r[k] for k in ['T','err','status','estimated_prefix_coverage']} for r in rows],
            'paired_policy_comparison':paired,'witness':witness,'real_activity':diagnostics['real'],
            'real_full':{'center_error_m':real_errors,'rotation_deg':real_prediction['rot_deg'],
                         'scope':'Controlled single development room; supplied room/start and nominal furniture dimensions'},
            'simulation':{k:physics[k] for k in ['generator_verdict','frontend_compatibility','physics','frontend','events','checks']},
            'inference_limits':['Development-room empirical fractions, not population probabilities',
                 'Coverage queries are coarsely sampled and censored, not exact crossing thresholds',
                 'Exact target sizes in geometric study are side information',
                 'K is a positional density prior, not an isolated known-room-type treatment',
                 'Candidate support is not a calibrated posterior or exhaustive joint search']}
    Path(output).write_text(json.dumps(record,ensure_ascii=False,indent=1),encoding='utf-8')
    print('fine',fine_summary)
    print('policy',paired)
    for label,e in experiments.items():
        print(label,e['thresholds'],e['per_object_protocol_thresholds'])
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package');p.add_argument('--output',required=True);a=p.parse_args()
    summarise(a.package,a.output)
