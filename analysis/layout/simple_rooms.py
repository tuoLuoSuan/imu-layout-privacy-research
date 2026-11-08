"""Controlled four-object rectangular rooms, frozen before reconstruction.

This is a declared simple layout family, not new independent ProcTHOR houses.
Seeds change room dimensions, assets, gaps, offsets and global orientation.
No reconstruction score participates in generation or eligibility.
"""
import argparse,copy,gzip,hashlib,json
from pathlib import Path
import numpy as np

LIMITS={'Bed':(.9,1.6,1.7,2.3),'Desk':(.4,.8,.8,1.8),
        'Dresser':(.3,.7,.7,1.6),'Chair':(.35,.65,.35,.65)}
ROLES={'bed':'Bed','desk':'Desk','cab':'Dresser','chair':'Chair'}


def overlap(a,b):
    return float(np.prod(np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2]))))


def rotate(p,k,W,L):
    x,y=p
    return [(x,y),(L-y,x),(W-x,L-y),(y,W-x)][k]


def draw_geometry(seed,pools=None):
    rng=np.random.default_rng(seed);assets={};sizes={};rotations={}
    defaults={'bed':(1.2,2.),'desk':(.6,1.2),'cab':(.5,1.),'chair':(.48,.48)}
    for role,typ in ROLES.items():
        if pools is None:
            size=np.array(defaults[role])*rng.uniform(.9,1.1,size=2);rotations[role]=0
        else:
            asset=pools[typ][int(rng.integers(len(pools[typ])))];assets[role]=asset
            b=asset['boundingBox'];raw=np.array([b['x'],b['z']]);theta=270 if role=='chair' else (0 if raw[0]<=raw[1] else 90)
            size=raw[::-1] if theta%180 else raw;rotations[role]=theta
        sizes[role]=size
    bw,bl=sizes['bed'];dd,dl=sizes['desk'];cd,cl=sizes['cab'];cw,ch=sizes['chair']
    gap_d,gap_b=rng.uniform(.05,.15,2);seat_gap=float(rng.uniform(.08,.30))
    W=float(max(dd,cd)+bw+cw+seat_gap+gap_d+gap_b+.75+rng.uniform(0,.35))
    L=float(max(3.7,bl+1.1,cl+dl+.5)+rng.uniform(0,1.))
    cab_y=float(rng.uniform(.05,.18));desk_y=float(cab_y+cl+rng.uniform(.06,.18))
    # All boxes are independent of the decoder. The whole-family rule is visible.
    gt={'bed':[W-gap_b-bw,L-bl-.08,W-gap_b,L-.08],
        'cab':[gap_d,cab_y,gap_d+cd,cab_y+cl],
        'desk':[gap_d,desk_y,gap_d+dd,desk_y+dl]}
    cy=desk_y+dl/2+float(rng.uniform(-.20,.20)*dl);cx=gap_d+dd+seat_gap+cw/2
    gt['chair']=[cx-cw/2,cy-ch/2,cx+cw/2,cy+ch/2]
    k=int(rng.integers(4));transformed={}
    for role,b in gt.items():
        points=np.array([rotate(q,k,W,L) for q in [(b[0],b[1]),(b[0],b[3]),(b[2],b[1]),(b[2],b[3])]])
        transformed[role]=np.r_[points.min(axis=0),points.max(axis=0)].tolist()
    return {'scene':'simple-'+str(seed),'seed':seed,'W':L if k%2 else W,'L':W if k%2 else L,
            'S':list(rotate((W/2,.40),k,W,L)),'gt':transformed,
            'assets':assets,'rotations':{o:(r+90*k)%360 for o,r in rotations.items()},
            'desk_seat_protocol':'This chair is used for sitting at the desk; max anchor-to-desk distance 0.90m',
            'family':'opposite bed and desk/storage walls; one of each; open corridor'}


def prepare(asset_database,house_template,out,n=1000,seed=61108000):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);(out/'scenes').mkdir(exist_ok=True)
    db=json.loads(Path(asset_database).read_text());pools={}
    for typ,(lo,hi,ln,hn) in LIMITS.items():
        pools[typ]=[a for a in db[typ] if lo<=min(a['boundingBox']['x'],a['boundingBox']['z'])<=hi and ln<=max(a['boundingBox']['x'],a['boundingBox']['z'])<=hn]
        if not pools[typ]:raise ValueError('Empty asset pool: '+typ)
    template=json.loads(Path(house_template).read_text());rows=[];fingerprints=set()
    with gzip.open(out/'houses.jsonl.gz','wt',encoding='utf-8') as f:
        for i in range(n):
            sc=draw_geometry(seed+i,pools);key='simple-'+str(i).zfill(5);W,L=sc['W'],sc['L'];sc['scene']=key
            for role,b in sc['gt'].items():
                assert min(b[:2])>=0 and b[2]<=W and b[3]<=L
                for o,c in sc['gt'].items():
                    if role!=o:assert overlap(b,c)<1e-8
            fingerprint=hashlib.sha256(json.dumps({k:sc[k] for k in ['W','L','gt']},sort_keys=True).encode()).hexdigest();assert fingerprint not in fingerprints;fingerprints.add(fingerprint)
            split='train' if i<700 else 'val' if i<850 else 'test';poly=[[0,0],[0,L],[W,L],[W,0]]
            sel={'house_id':key,'source_split':split,'seed':seed+i,'room_id':'room|2','room_type':'Bedroom',
                 'rectangular':True,'floor_polygon_xz':poly,'selected_object_ids':{o:ROLES[o]+'|2|'+str(j) for j,o in enumerate(sc['gt'])}}
            house={'rooms':[{'id':'room|2','roomType':'Bedroom','floorPolygon':[{'x':x,'y':0,'z':y} for x,y in poly],'ceilings':[],'children':[],'floorMaterial':copy.deepcopy(template['rooms'][0]['floorMaterial'])}],
                   'walls':[],'doors':[],'windows':[],'objects':[],
                   'proceduralParameters':copy.deepcopy(template['proceduralParameters']),
                   'metadata':{'schema':'1.0.0','agent':{'position':{'x':sc['S'][0],'y':.95,'z':sc['S'][1]},'rotation':{'x':0,'y':0,'z':0},'horizon':0,'standing':True}}}
            for j,(a,b) in enumerate(zip(poly,poly[1:]+poly[:1])):
                house['walls'].append({'id':'wall|2|'+str(j),'roomId':'room|2','material':{'name':'PureWhite'},
                     'polygon':[{'x':p[0],'y':z,'z':p[1]} for z,p in [(0,a),(0,b),(2.7,a),(2.7,b)]]})
            for role,box in sc['gt'].items():
                asset=sc['assets'][role];cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
                house['objects'].append({'id':sel['selected_object_ids'][role],'assetId':asset['assetId'],'kinematic':True,
                    'position':{'x':cx,'y':asset['boundingBox']['y']/2,'z':cy},'rotation':{'x':0,'y':sc['rotations'][role],'z':0},'children':[]})
            f.write(json.dumps({'selection':sel,'house':house},separators=(',',':'))+'\n');rows.append(sel)
            objects=[{'type':'Cabinet' if role=='cab' else ROLES[role],
                      'center':{'x':(b[0]+b[2])/2,'z':(b[1]+b[3])/2},'size':{'x':b[2]-b[0],'z':b[3]-b[1]}} for role,b in sc['gt'].items()]
            (out/'scenes'/('FloorPlan_'+key+'.json')).write_text(json.dumps({'floor':[W/2,L/2,W,L],'agent':{'x':sc['S'][0],'z':sc['S'][1]},'objects':objects}),encoding='utf-8')
    manifest={'dataset':'Controlled simple rectangular room generator v1','n_selected':n,'rows':rows,
        'seed_start':seed,'independent_seeds':n,'unique_geometry_hashes':len(fingerprints),'outcome_filtering':False,
        'frozen_before_reconstruction':True,'split_counts':{'train':min(n,700),'val':max(0,min(n-700,150)),'test':max(0,n-850)},
        'family':'One bed, desk, floor-standing storage, chair; desk/storage share wall, bed opposite, chair at desk; no clutter',
        'warning':'Own controlled geometry, not independent ProcTHOR or real homes; surface contacts are ideal, not raw IMU',
        'asset_database_sha256':hashlib.sha256(Path(asset_database).read_bytes()).hexdigest(),
        'houses_gz_sha256':hashlib.sha256((out/'houses.jsonl.gz').read_bytes()).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=1),encoding='utf-8');return manifest


def draw_multi_geometry(seed,counts,pools=None):
    """One bed, independently one/two desks, storage pieces and chairs."""
    if counts.get('bed')!=1 or any(counts.get(k) not in [1,2] for k in ['desk','cab','chair']):raise ValueError('Unsupported simple-room inventory')
    rng=np.random.default_rng(seed);assets={};sizes={};angles={}
    defaults={'bed':(1.2,2.),'desk':(.6,1.65),'cab':(.5,1.),'chair':(.48,.48)}
    for role in ['bed','chair','cab','desk']:
        for i in range(counts[role]):
            key=role+'#'+str(i)
            if pools is None:sizes[key]=np.array(defaults[role])*rng.uniform(.95,1.05,2);angles[key]=0;continue
            pool=pools[ROLES[role]]
            if role=='desk' and counts['desk']==1 and counts['chair']==2:
                required=2*max(s[1] for k,s in sizes.items() if k.startswith('chair#'))+.25
                pool=[a for a in pool if max(a['boundingBox']['x'],a['boundingBox']['z'])>=required]
            if not pool:raise ValueError('No sufficiently long two-seat desk asset')
            a=pool[int(rng.integers(len(pool)))];assets[key]=a;b=a['boundingBox'];raw=np.array([b['x'],b['z']])
            theta=270 if role=='chair' else (0 if raw[0]<=raw[1] else 90)
            sizes[key]=raw[::-1] if theta%180 else raw;angles[key]=theta
    gap=float(rng.uniform(.06,.15));b_gap=float(rng.uniform(.06,.15));seat_gap=float(rng.uniform(.08,.25))
    bw,bl=sizes['bed#0'];depth=max(s[0] for k,s in sizes.items() if k.split('#')[0] in ['desk','cab'])
    W=float(depth+bw+max(s[0] for k,s in sizes.items() if k.startswith('chair#'))+seat_gap+gap+b_gap+.75+rng.uniform(0,.35))
    gt={};cursor=float(rng.uniform(.08,.18))
    for role in ['cab','desk']:
        for i in range(counts[role]):
            key=role+'#'+str(i);w,l=sizes[key];gt[key]=[gap,cursor,gap+w,cursor+l];cursor+=l+float(rng.uniform(.10,.20))
    L=float(max(3.7,bl+1.1,cursor+.25)+rng.uniform(0,.75));gt['bed#0']=[W-b_gap-bw,L-bl-.10,W-b_gap,L-.10]
    association={}
    for i in range(counts['chair']):
        dk='desk#'+str(int(rng.integers(counts['desk'])) if counts['chair']==1 else i%counts['desk'])
        d=gt[dk];cw,ch=sizes['chair#'+str(i)]
        fraction=(.25 if i==0 else .75) if counts['chair']==2 and counts['desk']==1 else float(rng.uniform(.35,.65))
        cy=d[1]+fraction*(d[3]-d[1]);cx=d[2]+seat_gap+cw/2
        key='chair#'+str(i);gt[key]=[cx-cw/2,cy-ch/2,cx+cw/2,cy+ch/2];association[key]=dk
    k=int(rng.integers(4));transformed={}
    for key,b in gt.items():
        pts=np.array([rotate(q,k,W,L) for q in [(b[0],b[1]),(b[0],b[3]),(b[2],b[1]),(b[2],b[3])]])
        transformed[key]=np.r_[pts.min(axis=0),pts.max(axis=0)].tolist()
    return {'seed':seed,'W':L if k%2 else W,'L':W if k%2 else L,'S':list(rotate((W/2,.4),k,W,L)),
        'gt':transformed,'assets':assets,'rotations':{o:(a+90*k)%360 for o,a in angles.items()},
        'counts':counts,'chair_to_desk_truth_only':association}


def prepare_multi(asset_database,house_template,out,n=1000,seed=61109000):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);template=json.loads(Path(house_template).read_text());db=json.loads(Path(asset_database).read_text())
    pools={t:[a for a in db[t] if lo<=min(a['boundingBox']['x'],a['boundingBox']['z'])<=hi and ln<=max(a['boundingBox']['x'],a['boundingBox']['z'])<=hn] for t,(lo,hi,ln,hn) in LIMITS.items()}
    rows=[];patterns={};hashes=set()
    with gzip.open(out/'houses.jsonl.gz','wt',encoding='utf-8') as f:
        for i in range(n):
            counts={'bed':1,'desk':1+i%2,'cab':1+(i//2)%2,'chair':1+(i//4)%2};sc=draw_multi_geometry(seed+i,counts,pools)
            W,L=sc['W'],sc['L'];key='multi-'+str(i).zfill(5);poly=[[0,0],[0,L],[W,L],[W,0]]
            for name,b in sc['gt'].items():
                assert min(b[:2])>=0 and b[2]<=W and b[3]<=L
                for other,c in sc['gt'].items():
                    if name!=other:assert overlap(b,c)<1e-8
            digest=hashlib.sha256(json.dumps(sc['gt'],sort_keys=True).encode()).hexdigest();assert digest not in hashes;hashes.add(digest)
            split='train' if i<700 else 'val' if i<850 else 'test'
            ids={name:ROLES[name.split('#')[0]]+'|2|'+str(j) for j,name in enumerate(sc['gt'])}
            sel={'house_id':key,'source_split':split,'seed':seed+i,'rectangular':True,'room_id':'room|2','room_type':'Bedroom',
                 'floor_polygon_xz':poly,'selected_object_ids':ids,'counts':counts,'chair_to_desk_truth_only':sc['chair_to_desk_truth_only']}
            house={'rooms':[{'id':'room|2','roomType':'Bedroom','floorPolygon':[{'x':x,'y':0,'z':y} for x,y in poly],
                    'ceilings':[],'children':[],'floorMaterial':copy.deepcopy(template['rooms'][0]['floorMaterial'])}],
                'walls':[],'doors':[],'windows':[],'objects':[],'proceduralParameters':copy.deepcopy(template['proceduralParameters']),
                'metadata':{'schema':'1.0.0','agent':{'position':{'x':sc['S'][0],'y':.95,'z':sc['S'][1]},'rotation':{'x':0,'y':0,'z':0},'horizon':0,'standing':True}}}
            for j,(a,b) in enumerate(zip(poly,poly[1:]+poly[:1])):
                house['walls'].append({'id':'wall|2|'+str(j),'roomId':'room|2','material':{'name':'PureWhite'},
                    'polygon':[{'x':p[0],'y':z,'z':p[1]} for z,p in [(0,a),(0,b),(2.7,a),(2.7,b)]]})
            for name,b in sc['gt'].items():
                asset=sc['assets'][name];house['objects'].append({'id':ids[name],'assetId':asset['assetId'],'kinematic':True,'children':[],
                    'position':{'x':(b[0]+b[2])/2,'y':asset['boundingBox']['y']/2,'z':(b[1]+b[3])/2},'rotation':{'x':0,'y':sc['rotations'][name],'z':0}})
            f.write(json.dumps({'selection':sel,'house':house},separators=(',',':'))+'\n');rows.append(sel)
            pattern='/'.join(str(counts[k]) for k in ['bed','desk','cab','chair']);patterns[pattern]=patterns.get(pattern,0)+1
    rec={'dataset':'Controlled regular room family v2; variable inventory','n_selected':n,'rows':rows,'seed_start':seed,
         'inventory_patterns_bed_desk_storage_chair':patterns,'unique_geometry_hashes':len(hashes),
         'frozen_before_reconstruction':True,'outcome_filtering':False,'warning':'One bed; each other class 1-2. Generated controls, not external or real houses. No class is reduced to largest object.',
         'houses_gz_sha256':hashlib.sha256((out/'houses.jsonl.gz').read_bytes()).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(rec,indent=1),encoding='utf-8');return rec


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--assets',required=True);p.add_argument('--template',required=True);p.add_argument('--out',required=True);p.add_argument('--n',type=int,default=1000);p.add_argument('--multi',action='store_true');a=p.parse_args();r=(prepare_multi if a.multi else prepare)(a.assets,a.template,a.out,a.n);print(json.dumps({k:v for k,v in r.items() if k!='rows'},indent=1))
