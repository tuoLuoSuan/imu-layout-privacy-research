"""076 inference whitelist, full-room candidates and immutable split manifests.

This module never imports a prior network or opens evaluation-only files.
The frame is explicitly declared-room. Bounds/sizes are side information,
not quantities estimated from IMU. Walking observations and contact counts
are separate acquisition axes; selecting contacts is not time truncation.
"""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

CATEGORIES = ('bed', 'cab', 'desk', 'chair')
EVENTS = ('chair', 'bed', 'cab')
FIELDS = ('centres', 'sizes', 'category', 'valid', 'events', 'event_valid',
          'walk_cost', 'desk_relation', 'candidate_valid')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def observation_budget(observation, keep):
    """Selection on an already acquired, independently specified walk field."""
    if not isinstance(keep, int) or keep < 0:
        raise ValueError('Nonnegative integer contact budget required')
    result = copy.deepcopy(observation)
    result['events'] = result['events'][:keep]
    return result


def _points(value, name):
    a = np.asarray(value, dtype=np.float32)
    if a.size == 0:
        return a.reshape(0, 2)
    if a.ndim != 2 or a.shape[1] != 2 or not np.isfinite(a).all():
        raise ValueError('Invalid ' + name)
    return a


def prepare(observation, grid=24):
    allowed = {'schema','frame','room','inventory','events','walk','desk_relation'}
    if set(observation) != allowed:
        raise ValueError('Unexpected or missing observation fields: ' + str(set(observation)^allowed))
    if observation['schema'] != 'evidence076-v1' or observation['frame'] != 'declared-room':
        raise ValueError('Explicit declared-room contract required')
    if not isinstance(observation['desk_relation'],bool):
        raise ValueError('desk_relation must declare a protocol, not an inferred truth association')
    room = np.asarray(observation['room'],np.float32)
    if room.shape != (2,) or not np.isfinite(room).all() or np.any(room<=0):
        raise ValueError('Invalid declared room')
    if not 8 <= grid <= 64:
        raise ValueError('Grid must be in [8,64]')
    inventory=[]
    for entry in observation['inventory']:
        if set(entry) != {'category','dimensions'} or entry['category'] not in CATEGORIES:
            raise ValueError('Unexpected inventory fields/category; no IDs accepted')
        size=np.asarray(entry['dimensions'],np.float32)
        if size.shape!=(2,) or not np.isfinite(size).all() or np.any(size<=0):
            raise ValueError('Invalid declared furniture dimensions')
        if not (np.all(size<=room) or np.all(size[::-1]<=room)):
            raise ValueError('Declared furniture does not fit')
        inventory.append((CATEGORIES.index(entry['category']),tuple(sorted(size.tolist()))))
    if not 1<=len(inventory)<=16:
        raise ValueError('Explicit capacity is 1..16 objects; nothing silently truncated')
    inventory.sort()
    if len(observation['events'])>32:
        raise ValueError('Explicit capacity is 32 contacts')
    events=[]
    for e in observation['events']:
        if set(e)-{'object','pos','heading','spread'} or not {'object','pos'}<=set(e):
            raise ValueError('Unexpected event fields; instance identities are forbidden')
        if e['object'] not in EVENTS:
            raise ValueError('Unsupported activity-derived category')
        point=_points([e['pos']],'contact')[0]
        direction=np.zeros(2,np.float32); has_heading=0.
        if 'heading' in e:
            direction=_points([e['heading']],'heading')[0]
            if np.linalg.norm(direction)<1e-6:raise ValueError('Invalid heading')
            direction=direction/np.linalg.norm(direction); has_heading=1.
        spread=float(e.get('spread',0.))
        if not np.isfinite(spread) or spread<0:raise ValueError('Invalid contact spread')
        events.append(np.r_[point,np.eye(3)[EVENTS.index(e['object'])],direction,has_heading,spread])
    events=np.asarray(events,np.float32).reshape(-1,9)
    walk=_points(observation['walk'],'walk')
    uv=np.stack(np.meshgrid(np.linspace(0,1,grid),np.linspace(0,1,grid),indexing='xy'),-1).reshape(-1,2)
    centres=[];sizes=[];candidate_valid=[];cost=[]
    for _, size_tuple in inventory:
        size=np.asarray(size_tuple,np.float32)
        extent=np.repeat(np.stack([size,size[::-1]]),len(uv),axis=0)
        cv=np.all(extent<=room,axis=-1)
        c=extent/2+np.tile(uv,(2,1))*np.maximum(room-extent,0)
        penalty=np.zeros(len(c),np.float32)
        # Same fixed metre-valued walking-clearance contract for every arm.
        # Outside points remain outside. No scale fitting, clipping or row removal.
        for block in np.array_split(walk,max(1,int(np.ceil(len(walk)/128)))):
            if not len(block):continue
            signed=(extent[:,None]/2+.10-np.abs(block[None]-c[:,None])).min(-1)
            penalty=np.maximum(penalty,np.clip(signed.max(-1)/.15,0,1))
        centres.append(c);sizes.append(extent);candidate_valid.append(cv);cost.append(penalty)
    outside=np.any((walk<0)|(walk>room),axis=-1) if len(walk) else np.empty(0,bool)
    return {'centres':np.asarray(centres,np.float32),'sizes':np.asarray(sizes,np.float32),
            'candidate_valid':np.asarray(candidate_valid,bool),
            'category':np.asarray([x[0] for x in inventory],np.int64),
            'valid':np.ones(len(inventory),bool),'events':events,
            'event_valid':np.ones(len(events),bool),'walk_cost':np.asarray(cost,np.float32),
            'desk_relation':np.asarray(observation['desk_relation'],bool),
            'observation':copy.deepcopy(observation),
            'diagnostics':{'outside_walk_fraction':float(outside.mean()) if len(walk) else 0.,
                           'n_walk':len(walk),'n_contacts':len(events),
                           'scope':'positions conditional on declared room and dimensions'}}


def pack(samples):
    slots=max(len(s['valid']) for s in samples)
    contacts=max(1,max(len(s['events']) for s in samples))
    out={}
    for key in FIELDS:
        rows=[]
        for sample in samples:
            a=sample[key]
            if key=='desk_relation':rows.append(a);continue
            length=contacts if key in ('events','event_valid') else slots
            pad=[(0,length-len(a))]+[(0,0)]*(a.ndim-1)
            rows.append(np.pad(a,pad))
        out[key]=torch.from_numpy(np.stack(rows))
    return out


def validate_manifest(manifest):
    if manifest.get('schema')!='manifest076-v1':raise ValueError('Unknown manifest')
    ids=set();groups={};fingerprints={}
    for row in manifest['rows']:
        if row['id'] in ids:raise ValueError('Duplicate explicit ID')
        ids.add(row['id'])
        if row['split'] not in ('train','validation','test','confirmation'):
            raise ValueError('Unknown split')
        for field,seen in [('group',groups),('fingerprint',fingerprints)]:
            if row[field] in seen and seen[row[field]]!=row['split']:
                raise ValueError(field+' appears in multiple splits')
            seen[row[field]]=row['split']
    return manifest


def check_confirmation(manifest, seen_groups, seen_fingerprints):
    """A new directory/ID does not make previously used geometry independent."""
    for row in validate_manifest(manifest)['rows']:
        if row['split']!='confirmation':continue
        if row['group'] in set(seen_groups) or row['fingerprint'] in set(seen_fingerprints):
            raise ValueError('Confirmation overlaps model development groups/fingerprints')


def load_rows(manifest_path, splits, grid=24):
    """Read only explicitly selected rows, never enumerate dataset directories."""
    path=Path(manifest_path); manifest=validate_manifest(read(path)); selected=[]
    for row in manifest['rows']:
        if row['split'] not in splits:continue
        if row.get('status')!='ok':
            selected.append({'row':row,'sample':None,'truth':None});continue
        source=path.parent/row['input']; target=path.parent/row['target']
        if sha(source)!=row['input_sha256'] or sha(target)!=row['target_sha256']:
            raise ValueError('Frozen data hash mismatch: '+row['id'])
        sample=prepare(read(source),grid)
        selected.append({'row':row,'sample':sample,'truth':read(target)['boxes']})
    return selected
