"""Small public interface; scientific implementations remain byte-exact."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/'reproducibility/frozen088-lock.json'
PRIMARY=ROOT/'output/layout-recon/recovery088/confirmation50-98001/manifest.json'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while data:=f.read(1024*1024):h.update(data)
    return h.hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def install_archive(archive,root=ROOT):
    """Only verified release members under output/layout-recon may be installed."""
    root=Path(root).resolve()
    with zipfile.ZipFile(archive) as z:
        index=json.loads(z.read('release-files.json'))
        wanted={x['path'] for x in index}
        if len(wanted)!=len(index) or set(z.namelist())!=wanted|{'release-files.json'}:
            raise ValueError('Unexpected or duplicate release members')
        for item in index:
            name=item['path'];parts=PurePosixPath(name).parts
            if not name.startswith('output/layout-recon/') or '\\'in name or ':'in name or '..'in parts:
                raise ValueError('Unsafe release path')
            target=(root/Path(*parts)).resolve()
            if root not in target.parents:raise ValueError('Release escapes destination')
            if target.exists():
                if digest(target)!=item['sha256']:raise ValueError('Different local artifact: '+name)
                continue
            target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+'.download-part')
            h=hashlib.sha256();size=0
            try:
                with z.open(name) as src,temp.open('wb') as dst:
                    while data:=src.read(1024*1024):h.update(data);size+=len(data);dst.write(data)
                if h.hexdigest()!=item['sha256'] or size!=item['bytes']:
                    raise ValueError('Release member hash mismatch: '+name)
                temp.replace(target)
            finally:
                if temp.exists():temp.unlink()
    return len(index)

def download(args):
    spec=read(ROOT/'reproducibility/assets.json');cache=ROOT/'output/downloads';cache.mkdir(parents=True,exist_ok=True)
    for asset in spec['assets']:
        if not asset['default'] and not args.training:continue
        path=(Path(args.from_dir)/asset['name']) if args.from_dir else cache/asset['name']
        if not path.exists():
            if args.from_dir:raise FileNotFoundError(path)
            temp=path.with_suffix('.part')
            try:
                with urllib.request.urlopen(asset['url'],timeout=120) as src,temp.open('wb') as dst:
                    while chunk:=src.read(1024*1024):dst.write(chunk)
                if digest(temp)!=asset['sha256']:raise ValueError('Downloaded archive hash mismatch')
                temp.replace(path)
            finally:
                if temp.exists():temp.unlink()
        if digest(path)!=asset['sha256']:raise ValueError('Archive hash mismatch: '+str(path))
        print(json.dumps({'asset':asset['name'],'verified_files':install_archive(path)}),flush=True)

def models(threads):
    import torch
    from analysis.layout.recovery088_spatial_runtime import load_models
    torch.set_num_threads(threads)
    return load_models(ROOT/'output/layout-recon',LOCK)

def predict(args):
    from analysis.layout.recovery088_spatial_runtime import predict as infer
    from analysis.layout.analytic077 import corrected_static
    result={'RoomTrace':infer(read(args.input),models(args.threads))}
    if args.baseline:result['geometry_only']=corrected_static(read(args.input))
    write(args.out,result);print(args.out)

def evaluate(args):
    command=[sys.executable,str(ROOT/'tools/eval_spatial088_locked.py'),'--manifest',str(Path(args.manifest).resolve()),
             '--lock',str(LOCK),'--out',str(Path(args.out).resolve()),'--split','confirmation','--threads',str(args.threads)]
    subprocess.run(command,cwd=ROOT,check=True)

def summarize(args):
    import numpy as np
    from analysis.layout.recovery076_data import validate_manifest
    from analysis.layout.recovery076_eval import score,failed_score,aggregate
    from tools.eval082_locked import paired
    path=Path(args.manifest).resolve();manifest=validate_manifest(read(path));meta={r['id']:r for r in manifest['rows']}
    rows=[];seen=set()
    for line in Path(args.rows).read_text(encoding='utf-8').splitlines():
        r=json.loads(line);key=(r['arm'],r['id'])
        if key in seen:raise ValueError('Duplicate arm/request row')
        seen.add(key);m=meta[r['id']]
        if m['status']=='ok':
            tp=path.parent/m['target']
            if digest(tp)!=m['target_sha256']:raise ValueError('Target hash mismatch')
            value=score(r['boxes'],read(tp)['boxes'])
        else:value=failed_score()
        for field in ['whole_room','whole_footprint','f1','footprint_f1']:
            if not np.isclose(r[field],value[field],atol=1e-10,rtol=0):raise ValueError('Archived score mismatch: '+r['id'])
        rows.append(r)
    arms=sorted({r['arm'] for r in rows})
    for arm in arms:
        if {r['id'] for r in rows if r['arm']==arm}!=set(meta):raise ValueError('Incomplete requested denominator')
    result={'requested':len(meta),'groups':len({m['group'] for m in meta.values()}),
            'table':{a:aggregate([r for r in rows if r['arm']==a]) for a in arms},
            'paired':[paired(rows,'spatial_zero088',a,4000) for a in arms if a!='spatial_zero088']}
    write(args.out,result);print(json.dumps(result['table'],indent=2))

def verify(args):
    import numpy as np
    from analysis.layout.recovery088_spatial_runtime import predict as infer
    from analysis.layout.analytic077 import corrected_static
    path=PRIMARY;manifest=read(path);mod=models(args.threads)
    rows=[json.loads(l) for l in (path.parent.parent/'confirmation50-98001-eval/rows.jsonl').read_text(encoding='utf-8').splitlines()]
    old={(r['arm'],r['id']):r for r in rows};selected=[]
    for coverage in [.25,.5,1.]:
        for budget in [0,2,6,10,14]:
            eligible=sorted([m for m in manifest['rows'] if m['status']=='ok' and m['coverage_target']==coverage and m['contacts_requested']==budget],key=lambda x:x['id'])
            selected.append(eligible[0])
    maximum=0.
    for m in selected:
        ip=path.parent/m['input']
        if digest(ip)!=m['input_sha256']:raise ValueError('Input hash mismatch')
        obs=read(ip)
        for arm,got in [('spatial_zero088',infer(obs,mod)),('corrected_static',corrected_static(obs))]:
            reference=old[(arm,m['id'])]['boxes'];boxes=got.get('boxes',{})
            if set(reference)!=set(boxes):raise ValueError('Prediction inventory mismatch')
            for key,b in boxes.items():
                delta=float(np.max(np.abs(np.asarray(b)-reference[key])));maximum=max(maximum,delta)
                if delta>1e-6:raise ValueError('Archived prediction differs: '+m['id'])
    result={'checked_inputs':len(selected),'coverage_contact_conditions':15,'max_coordinate_delta_m':maximum,'status':'PASS'}
    if args.out:write(args.out,result)
    print(json.dumps(result,indent=2))

def cache(args):
    import torch
    from analysis.layout.recovery076_data import load_rows
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError(path)
    rows=load_rows(args.manifest,{'train','validation'},24)
    torch.save({'rows':rows,'key':{'manifest_sha256':digest(args.manifest),'grid':24}},path)
    print(json.dumps({'rows':len(rows),'cache':str(path),'bytes':path.stat().st_size}))

def actions(args):
    from analysis.layout.action_model import load_model,load_phone,predict_timeline
    channels=load_phone(args.session);ta,A,aa=channels['accelerometer'];tg,G,ga=channels['gyroscope']
    result=predict_timeline(load_model(),ta,A,tg,G,budget_s=args.budget,accel_arrivals=aa,gyro_arrivals=ga)
    write(args.out,result);print(args.out)

def main():
    p=argparse.ArgumentParser(description='RoomTrace frozen reproduction: actions, geometry, spatial decoding and paired evaluation.')
    sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('download',help='Download SHA-256-pinned models and synthetic evidence')
    d.add_argument('--training',action='store_true');d.add_argument('--from-dir',help='Install already downloaded release archives');d.set_defaults(fn=download)
    d=sub.add_parser('predict');d.add_argument('--input',required=True);d.add_argument('--out',required=True);d.add_argument('--baseline',action='store_true');d.add_argument('--threads',type=int,default=4);d.set_defaults(fn=predict)
    d=sub.add_parser('evaluate');d.add_argument('--manifest',default=str(PRIMARY));d.add_argument('--out',required=True);d.add_argument('--threads',type=int,default=4);d.set_defaults(fn=evaluate)
    d=sub.add_parser('summarize');d.add_argument('--manifest',default=str(PRIMARY));d.add_argument('--rows',default=str(PRIMARY.parent.parent/'confirmation50-98001-eval/rows.jsonl'));d.add_argument('--out',required=True);d.set_defaults(fn=summarize)
    d=sub.add_parser('verify');d.add_argument('--threads',type=int,default=4);d.add_argument('--out');d.set_defaults(fn=verify)
    d=sub.add_parser('cache');d.add_argument('--manifest',required=True);d.add_argument('--out',required=True);d.set_defaults(fn=cache)
    d=sub.add_parser('actions');d.add_argument('--session',required=True);d.add_argument('--out',required=True);d.add_argument('--budget',type=float);d.set_defaults(fn=actions)
    args=p.parse_args();args.fn(args)
