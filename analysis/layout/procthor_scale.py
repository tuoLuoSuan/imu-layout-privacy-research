"""Freeze public ProcTHOR houses, then export native engine bounding boxes.

The adapter does not run the reconstruction algorithm or filter its outcomes.
One preselected four-role bedroom per independent house; official splits remain.
Storage here is Dresser, explicitly a new domain, not Cabinet/Shelf relabelled
as an unchanged benchmark. Native AABBs are projected footprint approximations.
This file also runs standalone in the isolated Ubuntu engine directory.
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
from pathlib import Path
import time

ROLES={'Bed':'bed','Desk':'desk','Chair':'chair','Dresser':'cab'}
ENGINE_COMMIT='f0825767cd50d69f666c7f282e54abfe58f1e917'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(2**20):h.update(b)
    return h.hexdigest()


def object_room(object_id):
    parts=object_id.split('|')
    return parts[2] if len(parts)>2 and parts[1]=='surface' else parts[1]


def is_rectangle(poly):
    area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1])))/2
    bounds=[min(p[a] for p in poly) for a in [0,1]]+[max(p[a] for p in poly) for a in [0,1]]
    return abs(area-(bounds[2]-bounds[0])*(bounds[3]-bounds[1]))<1e-6


def engine_box(obj):
    """Never mix object.position (pivot) with bounding-box dimensions."""
    b=obj['axisAlignedBoundingBox'];c=b['center'];s=b['size']
    return [c['x']-s['x']/2,c['z']-s['z']/2,c['x']+s['x']/2,c['z']+s['z']/2]


def prepare(external, out):
    external=Path(external);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    assets=json.loads((external/'asset-database.json').read_text())
    by_asset={a['assetId']:a for group in assets.values() for a in group}
    rows=[];counts={};eligible_rooms=collections.Counter();source={}
    # Same selection is applied to every house before any solver is called.
    with gzip.open(out/'houses.jsonl.gz','wt',encoding='utf-8') as dst:
        for split in ['train','val','test']:
            f=external/(split+'.jsonl.gz');source[split]={'sha256':sha(f),'bytes':f.stat().st_size}
            n_house=0
            with gzip.open(f,'rt',encoding='utf-8') as src:
                for i,line in enumerate(src):
                    h=json.loads(line);by_room=collections.defaultdict(lambda:collections.defaultdict(list))
                    for obj in h['objects']:
                        asset=by_asset[obj['assetId']];typ=asset['objectType']
                        if typ in ROLES:by_room[object_room(obj['id'])][typ].append(obj)
                    options=[]
                    for room in h['rooms']:
                        rid=room['id'].split('|')[-1];types=by_room[rid]
                        if not set(ROLES)<=set(types):continue
                        poly=[[p['x'],p['z']] for p in room['floorPolygon']]
                        selected={ROLES[typ]:max(objs,key=lambda o:
                            by_asset[o['assetId']]['boundingBox']['x']*by_asset[o['assetId']]['boundingBox']['z'])['id']
                            for typ,objs in types.items()}
                        options.append({'room_id':room['id'],'room_type':room['roomType'],
                            'floor_polygon_xz':poly,'rectangular':is_rectangle(poly),'selected_object_ids':selected})
                        eligible_rooms[split]+=1
                    if not options:continue
                    # Independent unit = source house. No additional rooms count as replicas.
                    room=min(options,key=lambda r:hashlib.sha256(r['room_id'].encode()).hexdigest())
                    key='procthor-'+split+'-'+str(i).zfill(5)
                    house_sha=hashlib.sha256(line.encode()).hexdigest()
                    rec={'house_id':key,'source_split':split,'source_index':i,'source_line_sha256':house_sha,**room}
                    rows.append(rec);dst.write(json.dumps({'selection':rec,'house':h},separators=(',',':'))+'\n');n_house+=1
            counts[split]=n_house
    manifest={'dataset':'Official ProcTHOR-10K (12,000 houses including val/test)',
        'source_url':'https://github.com/allenai/procthor-10k','source_files':source,
        'asset_database_sha256':sha(external/'asset-database.json'),
        'eligible_four_role_rooms':dict(eligible_rooms),'independent_houses':counts,
        'n_selected':len(rows),'rectangular_selected':sum(r['rectangular'] for r in rows),
        'selection_frozen_before_decoding':True,'outcome_filtering':False,
        'role_mapping':ROLES,'warning':'Dresser storage and arbitrary floor polygons extend the old iTHOR domain; no raw IMU supplied',
        'rows':rows,'houses_gz_sha256':sha(out/'houses.jsonl.gz')}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=1),encoding='utf-8')
    return manifest


def export_native(houses, out, executable, limit=None, offset=0):
    """Create independent official houses in Unity; retain failures and resume."""
    from ai2thor.controller import Controller
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    os.environ['DISPLAY']=':0';c=None;done=0;started=time.time()
    try:
        c=Controller(local_executable_path=executable,scene='Procedural',
                     width=64,height=64,quality='Very Low',x_display='0',gridSize=.20)
        with gzip.open(houses,'rt',encoding='utf-8') as src:
            for index,line in enumerate(src):
                if index<offset:continue
                if limit is not None and index>=offset+limit:break
                item=json.loads(line);sel=item['selection'];key=sel['house_id'];f=out/(key+'.json')
                if f.exists():done+=1;continue
                t=time.time();rec={'selection':sel,'engine_commit':ENGINE_COMMIT,'stage':'started'}
                try:
                    c.reset(scene='Procedural')
                    e=c.step(action='CreateHouse',house=item['house'],raise_for_failure=True)
                    objects=[]
                    for obj in e.metadata['objects']:
                        objects.append({'id':obj['objectId'],'type':obj['objectType'],
                            'axisAlignedBoundingBox':obj['axisAlignedBoundingBox'],
                            'box_xz':engine_box(obj),'rotation':obj['rotation'],
                            'openable':obj.get('openable'), 'parent_receptacles':obj.get('parentReceptacles')})
                    e=c.step(action='GetReachablePositions',raise_for_failure=False)
                    rec.update(stage='exported',objects=objects,
                        reachable_positions=e.metadata.get('actionReturn') if e.metadata.get('lastActionSuccess') else None,
                        reachability_error=e.metadata.get('errorMessage'))
                except Exception as exc:
                    rec.update(stage='failed',error=repr(exc))
                rec['elapsed_s']=time.time()-t
                tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(rec,separators=(',',':')),encoding='utf-8');tmp.replace(f)
                done+=1
                if done<=3 or done%10==0:print(json.dumps({'done':done,'house':key,'stage':rec['stage'],'seconds':round(time.time()-started,1)}),flush=True)
    finally:
        if c is not None:c.stop()
    return {'completed':done,'seconds':time.time()-started}


def audit_native(manifest, native, out):
    """Audit completion and geometry, preserving every preselected house."""
    manifest=json.loads(Path(manifest).read_text(encoding='utf-8'))
    native=Path(native);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    expected={s['house_id'] for s in manifest['rows']};files={p.stem:p for p in native.glob('*.json')}
    missing=sorted(expected-files.keys());unexpected=sorted(files.keys()-expected)
    counts=collections.Counter();split_counts=collections.Counter();issues=[];file_sha={};scenes=[]
    for sel in manifest['rows']:
        key=sel['house_id']
        if key not in files:continue
        f=files[key];d=json.loads(f.read_text(encoding='utf-8'));file_sha[key]=sha(f)
        counts[d['stage']]+=1
        if d['stage']!='exported':issues.append({'house_id':key,'issue':'native_export_failed','error':d.get('error')});continue
        split_counts[sel['source_split']]+=1
        objects={o['id']:o for o in d['objects']};poly=sel['floor_polygon_xz']
        lo=[min(p[a] for p in poly) for a in [0,1]];hi=[max(p[a] for p in poly) for a in [0,1]]
        gt={};problems=[]
        for role,oid in sel['selected_object_ids'].items():
            if oid not in objects:problems.append(role+':missing_native_id');continue
            obj=objects[oid];b=engine_box(obj)
            if any(abs(a-c)>1e-7 for a,c in zip(b,obj['box_xz'])):raise AssertionError('AABB contract changed')
            if b[2]<=b[0] or b[3]<=b[1]:problems.append(role+':nonpositive_dimension')
            if b[0]<lo[0]-1e-4 or b[1]<lo[1]-1e-4 or b[2]>hi[0]+1e-4 or b[3]>hi[1]+1e-4:problems.append(role+':outside_room_envelope')
            gt[role]=[b[0]-lo[0],b[1]-lo[1],b[2]-lo[0],b[3]-lo[1]]
        scenes.append({'scene':key,'source_split':sel['source_split'],'room_id':sel['room_id'],
            'rectangular':sel['rectangular'],'W':hi[0]-lo[0],'L':hi[1]-lo[1],'gt':gt,
            'floor_polygon':[[p[0]-lo[0],p[1]-lo[1]] for p in poly],
            'geometry_issues':problems,'storage_type':'Dresser','native_sha256':file_sha[key]})
        if problems:issues.append({'house_id':key,'issue':'geometry','details':problems})
    with (out/'native-scenes.jsonl').open('w',encoding='utf-8') as f:
        for s in scenes:f.write(json.dumps(s,separators=(',',':'))+'\n')
    r={'n_frozen':len(expected),'n_files':len(files),'stages':dict(counts),
       'exported_by_official_split':dict(split_counts),'missing':missing,'unexpected':unexpected,
       'geometry_issue_houses':len([i for i in issues if i['issue']=='geometry']),
       'rectangular_exported':sum(s['rectangular'] for s in scenes),'issues':issues,
       'native_file_sha256':file_sha,'native_scenes_sha256':sha(out/'native-scenes.jsonl'),
       'warning':'This audits geometry acquisition, not reconstruction accuracy, interaction recognition, or raw IMU',
       'outcome_filtering':False,'complete':not missing and not unexpected and counts['exported']==len(expected)}
    (out/'native-audit.json').write_text(json.dumps(r,indent=1),encoding='utf-8')
    return r


if __name__=='__main__':
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--external',required=True);p.add_argument('--out',required=True)
    p=sub.add_parser('export');p.add_argument('--houses',required=True);p.add_argument('--out',required=True)
    p.add_argument('--executable',required=True);p.add_argument('--limit',type=int);p.add_argument('--offset',type=int,default=0)
    p=sub.add_parser('audit');p.add_argument('--manifest',required=True);p.add_argument('--native',required=True);p.add_argument('--out',required=True)
    a=ap.parse_args()
    if a.command=='prepare':
        m=prepare(a.external,a.out);print(json.dumps({k:v for k,v in m.items() if k!='rows'},indent=1))
    elif a.command=='export':print(json.dumps(export_native(a.houses,a.out,a.executable,a.limit,a.offset)))
    else:
        m=audit_native(a.manifest,a.native,a.out);print(json.dumps({k:v for k,v in m.items() if k not in ['native_file_sha256','issues']},indent=1))
