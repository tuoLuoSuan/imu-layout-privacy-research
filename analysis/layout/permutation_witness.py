"""Centre-layout ambiguity in the quotient by same-class instance labels.

The bottleneck assignment distance is a standard matching/Winfinity metric,
not a new mathematical distance. For two feasible layouts farther than2eps,
the triangle inequality gives an eps-impossibility witness in the declared
fixed-frame model. Existence/absence of a bounded witness is not calibrated
probability. No target ground truth is accepted by this computation.
"""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from .multi_instance import category


def bottleneck_layout_distance(first,second):
    result=0.
    for cls in {category(k) for k in first}|{category(k) for k in second}:
        a=np.array([(np.asarray(v)[:2]+np.asarray(v)[2:])/2 for k,v in first.items() if category(k)==cls])
        b=np.array([(np.asarray(v)[:2]+np.asarray(v)[2:])/2 for k,v in second.items() if category(k)==cls])
        if len(a)!=len(b):return float('inf')
        if not len(a):continue
        distances=np.linalg.norm(a[:,None,:]-b[None,:,:],axis=2)
        if not np.isfinite(distances).all():raise ValueError('Finite centres required')
        levels=np.unique(distances);lo,hi=0,len(levels)-1
        while lo<hi:
            mid=(lo+hi)//2;valid=distances<=levels[mid];i,j=linear_sum_assignment((~valid).astype(int))
            if valid[i,j].all():hi=mid
            else:lo=mid+1
        result=max(result,float(levels[lo]))
    return result


def witness(first,second,tolerance=.5):
    distance=bottleneck_layout_distance(first,second)
    if not np.isfinite(distance):return {'certified':False,'reason':'Different object counts; this centre-matching endpoint requires fixed counts'}
    return {'certified':bool(distance>2*tolerance+1e-8),'matching_invariant_separation_m':distance,
        'conditional_minimax_error_lower_m':distance/2,'scope':'Same-class unordered centre sets in one fixed room frame; not a footprint/rotation certificate'}


def run(source,out):
    source,out=map(Path,(source,out));rows=[]
    for f in sorted(source.glob('*.json')):
        rec=json.loads(f.read_text(encoding='utf-8'))
        for row in rec['rows']:
            old=row.get('desk_witness',{})
            if 'separation_m' not in old:continue
            check=witness(old['layout_a'],old['layout_b'])
            rows.append({'scene':rec['scene'],'method':row['method'],'old_named_slot_displacement_m':old['separation_m'],**check})
    summary={m:{'old_named_slot_witnesses':sum(r['method']==m for r in rows),'revalidated_unordered_witnesses':sum(r['method']==m and r['certified'] for r in rows)} for m in ['legacy','outline']}
    result={'scope':'Revalidates the stored witness pairs; not an exhaustive search for all witnesses. Uses no room truth.','summary':summary,'rows':rows}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=1),encoding='utf-8');print(json.dumps(summary,indent=1));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.source,a.out)
