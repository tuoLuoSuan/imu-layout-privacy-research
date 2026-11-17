"""Geometry-layer development corpus, not synthetic IMU or a real-room trial.

Room/inventory/start streams are independent of placement. Counterfactual
layouts share conditions and stay in one split, including every budget cell.
The existing geometric observation simulator supplies contacts without IDs.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from .recovery076_data import dump, sha, validate_manifest


def draw_scene(seed,copy_index,dimension_noise=0.):
    config=np.random.default_rng(np.random.SeedSequence([seed,760,0]))
    place=np.random.default_rng(np.random.SeedSequence([seed,760,copy_index+1]))
    start_rng=np.random.default_rng(np.random.SeedSequence([seed,761,0]))
    room=config.uniform([4.5,5.0],[7.0,8.0]);start=start_rng.uniform(.35,room-.35)
    family=('wall','mixed','free')[int(config.integers(3))]
    counts={'bed':int(config.integers(1,3)),'cab':int(config.integers(1,3)),
            'desk':int(config.integers(1,3))}
    counts['chair']=counts['desk']
    defaults={'bed':(1.2,1.95),'cab':(.5,.9),'desk':(.6,1.2),'chair':(.45,.45)}
    sizes={f'{cat}#{i}':np.array(defaults[cat])*config.uniform(.8,1.2,2)
           for cat,n in counts.items() for i in range(n)}
    inventory=[]
    for key,size in sizes.items():
        # Measurement noise is sampled independently, identical across the pair.
        declared=np.maximum(.2,size+config.uniform(-dimension_noise,dimension_noise,2))
        inventory.append({'id':key,'category':key.split('#')[0],
                          'dimensions':sorted(declared.tolist())})
    gt={}
    def fits(box,others):
        if np.any(box[:2]<.08) or np.any(box[2:]>room-.08):return False
        if np.all(start>box[:2]-.20) and np.all(start<box[2:]+.20):return False
        return not any(np.all(np.minimum(box[2:],b[2:])-np.maximum(box[:2],b[:2])>-.06)
                       for b in others)
    def candidate(size):
        extent=size[::-1] if place.integers(2) else size.copy()
        centre=place.uniform(extent/2+.12,room-extent/2-.12)
        if family=='wall' or (family=='mixed' and place.random()<.5):
            axis=int(place.integers(2));gap=float(place.uniform(.12,.65))
            centre[axis]=extent[axis]/2+gap if place.integers(2) else room[axis]-extent[axis]/2-gap
        return np.r_[centre-extent/2,centre+extent/2]
    # Desks retain a declared observable relation in wall/mixed families.
    # Free family has no seating-to-desk relation: it is deliberately harder.
    for i in range(counts['desk']):
        key=f'desk#{i}';ch=f'chair#{i}'
        for _ in range(1000):
            b=candidate(sizes[key])
            if not fits(b,list(gt.values())):continue
            if family=='free':chair=candidate(sizes[ch])
            else:
                extent=b[2:]-b[:2];axis=int(np.argmin(extent));sign=1 if place.integers(2) else -1
                cs=sizes[ch];centre=(b[:2]+b[2:])/2
                centre[axis]+=sign*(extent[axis]/2+cs[axis]/2+place.uniform(.10,.30))
                centre[1-axis]+=place.uniform(-.15,.15)*extent[1-axis]
                chair=np.r_[centre-cs/2,centre+cs/2]
            if fits(chair,[*gt.values(),b]):gt[key]=b;gt[ch]=chair;break
        else:raise ValueError('Placement failed; dimensions/room not resampled to fit')
    for key in [k for k in sizes if k.split('#')[0] in ('bed','cab')]:
        for _ in range(1000):
            b=candidate(sizes[key])
            if fits(b,list(gt.values())):gt[key]=b;break
        else:raise ValueError('Placement failed; retained as generation failure')
    return {'W':float(room[0]),'L':float(room[1]),'S':start,'gt':gt,
            'inventory':inventory,'counts':counts,'family':family,
            'desk_relation':family!='free','scene':f'076-{seed}-{copy_index}'}


def generate(out,groups=400,copies=2,seed=76000,coverages=(.25,.5,1.),budgets=(0,2,6,14),dimension_noise=0.,confirmation=False):
    from .exp_walk_range import coverage_route,survey_prefixes
    from .multi_instance import event_sequence
    out=Path(out);out.mkdir(parents=True,exist_ok=False);rows=[]
    started=time.monotonic()
    for group in range(groups):
        group_id=f'076-{seed+group}'
        fold=int(hashlib.sha256(group_id.encode()).hexdigest()[:8],16)%100
        split='confirmation' if confirmation else ('train' if fold<70 else 'validation' if fold<85 else 'test')
        for copy_index in range(copies):
            stem=f'{group_id}-v{copy_index}';scene=None;error=None
            try:
                scene=draw_scene(seed+group,copy_index,dimension_noise)
                ep=coverage_route(scene)
                ratio=len(ep['reachable_ids'])/len(ep['free_ids'])
                prefixes=survey_prefixes(ep,[c/ratio for c in coverages])
                fingerprint=hashlib.sha256(json.dumps({k:v.tolist() for k,v in sorted(scene['gt'].items())},sort_keys=True).encode()).hexdigest()
                dump(out/'targets'/f'{stem}.json',{'boxes':{k:v.tolist() for k,v in scene['gt'].items()},
                                                  'start':scene['S'].tolist(),'family':scene['family']})
            except ValueError as exc:
                error=str(exc);fingerprint=f'failed-{stem}';prefixes=[None]*len(coverages)
            for coverage,prefix in zip(coverages,prefixes):
                for k in budgets:
                    rid=f'{stem}-c{coverage:g}-k{k}'
                    row={'id':rid,'group':group_id,'fingerprint':fingerprint,'split':split,
                         'coverage_target':coverage,'contacts_requested':k,'status':'failed'}
                    try:
                        if error:raise ValueError(error)
                        if prefix is None or not prefix['reached']:raise ValueError('Requested survey coverage not reachable')
                        path=prefix['path'];events=event_sequence(scene,path,k)
                        if len(events)!=k:raise ValueError('Requested contacts not available on acquired walk')
                        observation={'schema':'evidence076-v1','frame':'declared-room',
                                     'room':[scene['W'],scene['L']],
                                     'inventory':[{key:entry[key] for key in ('category','dimensions')} for entry in scene['inventory']],
                                     'events':events,'walk':path.tolist(),'desk_relation':scene['desk_relation']}
                        inp=out/'observations'/f'{rid}.json';target=out/'targets'/f'{stem}.json'
                        dump(inp,observation)
                        row.update(status='ok',input=inp.relative_to(out).as_posix(),target=target.relative_to(out).as_posix(),
                                   input_sha256=sha(inp),target_sha256=sha(target),family=scene['family'],
                                   coverage_free=float(prefix['coverage_free']),coverage_room=float(prefix['coverage_room']),
                                   n_contacts=len(events),n_walk=len(path))
                    except ValueError as exc:row['error']=str(exc)
                    rows.append(row)
        if (group+1)%10==0:print(json.dumps({'groups_done':group+1,'rows':len(rows),'seconds':round(time.monotonic()-started,1)}),flush=True)
    manifest=validate_manifest({'schema':'manifest076-v1','rows':rows,
        'protocol':{'scope':'ideal geometric observations; no IMU, no real participants',
                    'known_room':True,'known_declared_sizes':True,'dimension_noise_m':dimension_noise,
                    'contact_ids_given':False,'copies_share_condition_and_split':True,
                    'coverage':'fraction of free floor within 0.25 m of surveyed path (existing geometry protocol)',
                    'desk_relation':'declared in wall/mixed; absent in free family',
                    'requested_groups':groups,'copies':copies,'seed':seed,'coverages':coverages,'budgets':budgets,
                    'source_sha256':{name:sha(Path(__file__).with_name(name)) for name in
                                     ('recovery076_generate.py','recovery076_data.py','exp_walk_range.py','multi_instance.py')}}})
    dump(out/'manifest.json',manifest)
    for split in ('train','validation','test','confirmation'):
        (out/f'{split}-ids.txt').write_text(''.join(r['id']+'\n' for r in rows if r['split']==split),encoding='utf-8')
    return manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--groups',type=int,default=400)
    p.add_argument('--copies',type=int,default=2);p.add_argument('--seed',type=int,default=76000)
    p.add_argument('--coverages',default='0.25,0.5,1');p.add_argument('--budgets',default='0,2,6,14')
    p.add_argument('--dimension-noise',type=float,default=0.)
    p.add_argument('--confirmation',action='store_true',help='Reserve every new condition group for final confirmation')
    a=p.parse_args();cover=tuple(map(float,a.coverages.split(',')));budgets=tuple(map(int,a.budgets.split(',')))
    if a.groups<1 or a.copies<2 or any(not 0<c<=1 for c in cover) or any(k<0 or k>32 for k in budgets) or not 0<=a.dimension_noise<=.2:
        p.error('Invalid geometry corpus parameters; at least two counterfactual copies required')
    m=generate(a.out,a.groups,a.copies,a.seed,cover,budgets,a.dimension_noise,a.confirmation)
    print(json.dumps({'requested':len(m['rows']),'usable':sum(r['status']=='ok' for r in m['rows'])}),flush=True)

if __name__=='__main__':main()
