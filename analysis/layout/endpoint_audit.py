"""Independent footprint matching audit, separate from frozen centre endpoints.

At most two objects per class in this experiment, so exhaustive permutations
can check the Hungarian footprint tally using a separately written IoU.
No proposal, ranking or deployment code is modified by this evaluator.
"""
import argparse, collections, itertools, json
from pathlib import Path
from . import multi_instance as M
from .expansion_report import original_record
from .fig_main_activity3d import pareto


def overlap(a, b):
    w=max(0,min(a[2],b[2])-max(a[0],b[0]))
    h=max(0,min(a[3],b[3])-max(a[1],b[1]))
    intersection=w*h
    return intersection/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)


def run(package, repo):
    package,repo=map(Path,(package,repo))
    old=repo/'output/research-sync/2026-11-08-procthor-rescue-005/multi/native'
    counts={m:collections.Counter() for m in ['legacy','outline']};examples=[]
    for i in range(5000):
        name=f'multi-{i:05d}.json';new=i>=1000
        record=json.loads((package/'new4000/evaluation/rooms'/name).read_text(encoding='utf-8')) if new else original_record(repo,name)
        truth=M.load_native((package/'new4000/native' if new else old)/name)['gt']
        for method in counts:
            row=next(r for r in record['rows'] if r['method']==method and r['contact_mode']=='dispersed' and r['coverage']==1 and r['visits']==14)
            ok=True;details={}
            for cls in ['bed','desk','cab','chair']:
                ps=[v for k,v in row['boxes'].items() if M.category(k)==cls]
                ts=[v for k,v in truth.items() if M.category(k)==cls]
                counts[method][cls+'_truth']+=len(ts)
                hit=int(max((sum(overlap(ps[a],ts[b])>=.5 for a,b in enumerate(perm)) for perm in itertools.permutations(range(len(ts)),len(ps))),default=0)) if len(ps)<=len(ts) else 0
                counts[method][cls+'_iou_hits']+=hit;ok &= hit==len(ts);details[cls]=hit
            counts[method]['whole_iou_hits']+=int(ok)
            if method=='outline' and row['score']['all_instances_hit'] and not ok and len(examples)<4:
                examples.append({'scene':record['scene'],'centre_score':row['score'],'iou_hits':details,'boxes':row['boxes'],'truth':{k:v.tolist() for k,v in truth.items()}})
    out={'independent_iou_formula_and_exhaustive_same_class_permutations':True,'n_rooms':5000,'counts':{m:dict(c) for m,c in counts.items()},'examples_center_hit_iou_fail':examples}
    summary=json.loads((package/'summary5000.json').read_text(encoding='utf-8'))
    for method in counts:
        assert counts[method]['whole_iou_hits']==summary['best']['all5000'][method]['whole_iou0_5_hits']
    (package/'endpoint-independent-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding='utf-8')
    front={}
    for cohort,rows in summary['cells'].items():
        q=[r for r in rows if r['method']=='outline' and r['contact_mode']=='dispersed']
        xs=sorted({r['coverage']*100 for r in q});ys=sorted({r['visits'] for r in q});look={(r['coverage']*100,r['visits']):r for r in q}
        front[cohort]={metric:pareto([[look[x,y][metric]*100 if (x,y) in look else float('nan') for x in xs] for y in ys],xs,ys) for metric in ['f1','whole_rate']}
        front[cohort]['f1_lower_ci']=pareto([[look[x,y]['f1_bootstrap_ci'][0]*100 if (x,y) in look else float('nan') for x in xs] for y in ys],xs,ys)
    (package/'frontiers5000.json').write_text(json.dumps(front,indent=1),encoding='utf-8')
    print(json.dumps({'counts':out['counts'],'frontiers':front},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--repo',default='.')
    a=p.parse_args();run(a.package,a.repo)
