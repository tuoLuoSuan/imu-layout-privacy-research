"""No-motion classic-template prior control, given room and inventory only.

This deliberately stronger P-K sampler knows the declared arrangement family
(desk/storage wall, opposite bed, chairs at desks), but not the true wall,
object coordinates or class-instance correspondence. It is a stochastic
baseline, not an optimal Bayesian bound. Draws never count as extra rooms.
"""
import argparse,concurrent.futures,json
from pathlib import Path
import numpy as np
from . import multi_instance as M
from .simple_rooms import rotate,overlap


def sample_family(room,inventory,seed,draws=64):
    rng=np.random.default_rng(seed);predictions=[];W,L=room
    for _ in range(draws):
        k=int(rng.integers(4));width,length=(L,W) if k%2 else (W,L);by={};sizes={}
        for entry in inventory:
            cls=entry['category'];by.setdefault(cls,[]).append(entry['id']);d=np.sort(entry['dimensions'])
            if cls=='chair' and rng.integers(2):d=d[::-1]
            sizes[entry['id']]=d
        for names in by.values():rng.shuffle(names)
        gap=float(rng.uniform(.06,.15));b_gap=float(rng.uniform(.06,.15));seat_gap=float(rng.uniform(.08,.25));cursor=float(rng.uniform(.08,.18));boxes={}
        for cls in ['cab','desk']:
            for name in by[cls]:
                w,h=sizes[name];boxes[name]=np.array([gap,cursor,gap+w,cursor+h]);cursor+=h+float(rng.uniform(.1,.2))
        name=by['bed'][0];w,h=sizes[name];boxes[name]=np.array([width-b_gap-w,length-h-.1,width-b_gap,length-.1])
        for i,name in enumerate(by['chair']):
            desk=by['desk'][int(rng.integers(len(by['desk']))) if len(by['chair'])==1 else i%len(by['desk'])];d=boxes[desk];cw,ch=sizes[name]
            f=(.25 if i==0 else .75) if len(by['chair'])==2 and len(by['desk'])==1 else float(rng.uniform(.35,.65))
            cx=d[2]+seat_gap+cw/2;cy=d[1]+f*(d[3]-d[1]);boxes[name]=np.array([cx-cw/2,cy-ch/2,cx+cw/2,cy+ch/2])
        if any(np.any(b[:2]<0) or np.any(b[2:]>[width,length]) for b in boxes.values()):continue
        if any(overlap(a,b)>1e-8 for i,(name,a) in enumerate(boxes.items()) for other,b in list(boxes.items())[i+1:] if {M.category(name),M.category(other)}!={'desk','chair'}):continue
        transformed={}
        for name,b in boxes.items():
            pts=np.array([rotate(q,k,width,length) for q in [(b[0],b[1]),(b[0],b[3]),(b[2],b[1]),(b[2],b[3])]])
            transformed[name]=np.r_[pts.min(axis=0),pts.max(axis=0)]
        predictions.append(transformed)
    return predictions


def one(task):
    source,out=map(Path,task);scene=M.load_native(source);seed=71900000+int(scene['scene'].split('-')[-1]);predictions=sample_family([scene['W'],scene['L']],scene['inventory'],seed)
    scores=[M.score_instances(p,scene['gt']) for p in predictions]
    r={'scene':scene['scene'],'split':scene['split'],'draws_attempted':64,'valid_prior_layouts':len(scores),
        'room_expected_f1':float(np.mean([s['f1'] for s in scores])) if scores else 0.,
        'room_expected_whole_success':float(np.mean([s['all_instances_hit'] for s in scores])) if scores else 0.}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r),encoding='utf-8');return r


def run(old,new,out,workers=8):
    old,new,out=map(Path,(old,new,out));files=sorted(old.glob('*.json'))+sorted(new.glob('*.json'))
    if len(files)!=5000:raise ValueError('Wait for all5000 native rooms')
    rows=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(one,[(str(f),str(out/'rooms'/f.name)) for f in files]):rows.append(r)
    result={'scope':__doc__,'input':'Room rectangle, category/count/nominal dimensions; NO path, contact, direction, true instance matching or target position','n_rooms':len(rows),'draws_per_room':64,'summary':{}}
    for name,selected in [('all5000',rows),('confirmation4000',[r for r in rows if r['split']=='confirmation'])]:
        result['summary'][name]={'n_rooms':len(selected),'expected_f1':float(np.mean([r['room_expected_f1'] for r in selected])),'expected_whole_success':float(np.mean([r['room_expected_whole_success'] for r in selected])),'no_template_fit':sum(not r['valid_prior_layouts'] for r in selected)}
    (out/'results.json').write_text(json.dumps(result,indent=1),encoding='utf-8');print(json.dumps(result,indent=1));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--old',required=True);p.add_argument('--new',required=True);p.add_argument('--out',required=True);p.add_argument('--workers',type=int,default=8);a=p.parse_args();run(a.old,a.new,a.out,a.workers)
