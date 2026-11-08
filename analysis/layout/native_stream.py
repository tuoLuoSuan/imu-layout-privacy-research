"""Resume-safe SSH/SCP acquisition and bounded local evaluation of frozen IDs.

Credentials are provided by existing OpenSSH configuration/key paths, never
embedded here. Only complete atomic native JSON files are archived. No source
or credential deletion, remote installation, training or outcome filtering.
"""
import argparse,concurrent.futures,hashlib,json,shlex,subprocess,tarfile,time
from pathlib import Path
from .expansion_eval import evaluate_room


def run(host,key,known_hosts,remote,new,out,batch=250,workers=10):
    new,out=map(Path,(new,out));out.mkdir(parents=True,exist_ok=True);(new/'native').mkdir(exist_ok=True)
    manifest=json.loads((new/'manifest.json').read_text(encoding='utf-8'));names=[r['house_id'] for r in manifest['rows']]
    if len(names)!=len(set(names)):raise ValueError('Duplicate frozen IDs')
    ssh=['ssh','-i',str(key),'-o','UserKnownHostsFile='+str(known_hosts),'-o','StrictHostKeyChecking=yes','-o','BatchMode=yes','-o','ConnectTimeout=15',host]
    scp=['scp','-i',str(key),'-o','UserKnownHostsFile='+str(known_hosts),'-o','StrictHostKeyChecking=yes','-o','BatchMode=yes']
    batches=[names[i:i+batch] for i in range(0,len(names),batch)];downloaded=set();submitted=set();completed=set();pending={};start=time.time()
    protocol={'manifest_sha256':hashlib.sha256((new/'manifest.json').read_bytes()).hexdigest(),'n_frozen':len(names),
        'primary':'New-seed paired all-instance recovery at100%/14, same0.5m tolerance',
        'rows_per_room':90,'policies':['legacy','outline'],'source_code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('expansion_eval.py'),Path(__file__).with_name('selection_diagnostics.py')]}}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=1),encoding='utf-8')
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        while len(completed)<len(names):
            progress=False
            for bi,group in enumerate(batches):
                if bi in downloaded:continue
                if all((new/'native'/(name+'.json')).exists() for name in group):downloaded.add(bi)
                else:
                    archive='batch-'+str(bi).zfill(2)+'.tar.gz'
                    script="from pathlib import Path;import tarfile,json;p=Path("+repr(remote)+");names="+repr(group)+";files=[p/'native'/(n+'.json') for n in names];ready=all(f.exists() for f in files);print(json.dumps({'ready':ready,'count':sum(f.exists() for f in files)}));\nif ready:\n with tarfile.open(p/"+repr(archive)+",'w:gz') as a:\n  for f in files:a.add(f,arcname=f.name)"
                    response=subprocess.run(ssh+['python3 -c '+shlex.quote(script)],capture_output=True,text=True,timeout=60)
                    if response.returncode:raise RuntimeError('SSH acquisition failed without exposing credential output')
                    info=json.loads(response.stdout)
                    if not info['ready']:break
                    target=new/archive
                    subprocess.run(scp+[host+':'+remote+'/'+archive,str(target)],check=True,timeout=120)
                    with tarfile.open(target) as a:
                        expected={n+'.json' for n in group}
                        if set(a.getnames())!=expected:raise ValueError('Unexpected archive members')
                        a.extractall(new/'native',filter='data')
                    downloaded.add(bi);progress=True
                for name in group:
                    if name in submitted:continue
                    dst=out/'rooms'/(name+'.json')
                    if dst.exists():completed.add(name)
                    else:pending[pool.submit(evaluate_room,(str(new/'native'/(name+'.json')),str(dst)))]=name
                    submitted.add(name)
                # Let export run ahead while one new batch is transferred.
                if progress:break
            for future in [f for f in pending if f.done()]:
                result=future.result();completed.add(result['scene']);del pending[future];progress=True
            state={'downloaded':sum(len(batches[i]) for i in downloaded),'submitted':len(submitted),'completed':len(completed),'total':len(names),'elapsed_s':round(time.time()-start,1)}
            (out/'progress.json').write_text(json.dumps(state),encoding='utf-8')
            if progress:print(json.dumps(state),flush=True)
            if len(completed)<len(names):time.sleep(3 if progress else 10)
    result={'n_completed':len(completed),'elapsed_s':time.time()-start};(out/'run.json').write_text(json.dumps(result,indent=1),encoding='utf-8');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--key',required=True);p.add_argument('--known-hosts',required=True);p.add_argument('--remote',required=True);p.add_argument('--new',required=True);p.add_argument('--out',required=True);p.add_argument('--batch',type=int,default=250);p.add_argument('--workers',type=int,default=10);a=p.parse_args();print(json.dumps(run(a.host,a.key,a.known_hosts,a.remote,a.new,a.out,a.batch,a.workers)))
