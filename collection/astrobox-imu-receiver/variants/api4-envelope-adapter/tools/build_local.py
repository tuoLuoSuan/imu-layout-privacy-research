"""Observe the actual receiver component with real isolated WASI files; no devices."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parents[1]
REPO=BASE.parents[1]
sys.path.insert(0,str(BASE/'tools'))
spec=importlib.util.spec_from_file_location('legacy_build',BASE/'tools/build_local.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)

def run(name,command,env,logs,timeout=180):
    result=subprocess.run(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    (logs/(name+'.txt')).write_bytes(result.stdout)
    if result.returncode:
        sys.stderr.buffer.write(result.stdout)
        raise RuntimeError(f'{name}: exit {result.returncode}')
    print(name+': passed',flush=True)
    return result.stdout.decode('utf-8','replace')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test',action='store_true');parser.add_argument('--package',action='store_true');parser.add_argument('--output-dir')
    args=parser.parse_args()
    if not(args.test or args.package):parser.error('choose --test or --package')
    cargo,env,native=legacy.configuration();cache=REPO/'.cache/s5-transfer-research/runtime-probe'
    logs=cache/'adapter-build-logs';logs.mkdir(parents=True,exist_ok=True)
    if native:
        compiler=cache/'compiler/zig-x86_64-windows-0.14.1'
        if not (cache/'cc-proxy.exe').exists():raise RuntimeError('Prepare the documented task-local API4 compiler helpers first')
        env['PATH']=str(compiler)+os.pathsep+env['PATH']
        env['ZIG_LOCAL_CACHE_DIR']=str(cache/'zig-local-cache');env['ZIG_GLOBAL_CACHE_DIR']=str(cache/'zig-global-cache')
        env['CC']=str(cache/'cc-proxy.exe');env['AR']=str(cache/'ar-proxy.exe')
        env['CARGO_TARGET_X86_64_PC_WINDOWS_GNU_RUSTFLAGS']+=' -C dlltool='+str(cache/'dlltool-proxy.exe')
    env['CARGO_PROFILE_DEV_DEBUG']='0'
    if args.test:
        for label,manifest in [('shared-protocol-and-ui',BASE/'Cargo.toml'),('observation-unit',ROOT/'Cargo.toml')]:
            command=[cargo,'test','--locked','--manifest-path',str(manifest)]
            if native:command+=['--target',native]
            run(label,command,env,logs)
    component_env=dict(env,CARGO_TARGET_DIR=str(cache/'candidate-target'))
    run('observation-component-build',[cargo,'build','--locked','--manifest-path',str(ROOT/'Cargo.toml'),'--target','wasm32-wasip2','--lib','--features','astrobox','--release'],component_env,logs)
    wasm=cache/'candidate-target/wasm32-wasip2/release/imus5_receiver_envelope_adapter.wasm'
    host_env=dict(env,CARGO_TARGET_DIR=str(cache/'target'))
    command=[cargo,'build','--locked','--manifest-path',str(ROOT/'runtime-tests/Cargo.toml')]
    if native:command+=['--target',native]
    run('observation-runtime-build',command,host_env,logs,timeout=900)
    binary=cache/'target'/(native or '')/'debug'/('imus5-observation-runtime-check'+('.exe' if os.name=='nt' else ''))
    parent=cache/'adapter-runs';parent.mkdir(exist_ok=True)
    scenarios={}
    for name,extra in [('success',[]),('registration-denied',['deny']),('busy',['busy']),('reply-denied',['reply-denied']),('v2-four-parts',['v2']),('unknown-envelope',['structure-only']),('v2-observed-envelope',['v2','enveloped'])]:
        directory=parent/(name+'-'+uuid.uuid4().hex)
        result=run('actual-component-'+name,[str(binary),str(wasm),str(directory),*extra],host_env,logs,timeout=100)
        if 'PASS actual component receive:' not in result:raise RuntimeError('Acceptance marker missing: '+name)
        scenarios[name]={'directory':str(directory),'passed':True}
    if args.package:
        manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
        old=json.loads((ROOT.parent/'api4/manifest.json').read_text(encoding='utf-8'))
        assert manifest['name']==old['name'] and manifest['permissions']==old['permissions']
        assert (manifest['api_level'],manifest['wasi_version'],manifest['version'])==(4,3,'0.2.3')
        assert (ROOT/'SDK_LICENSE.txt').read_bytes()==(ROOT.parent/'api4/SDK_LICENSE.txt').read_bytes()
        output=Path(args.output_dir).resolve() if args.output_dir else ROOT/'dist/receiver-0.2.3'
        if not output.is_relative_to((ROOT/'dist').resolve()):raise ValueError('Output must stay inside this variant dist')
        output.mkdir(parents=True,exist_ok=False)
        assets={'manifest.json':(ROOT/'manifest.json').read_bytes(),manifest['entry']:wasm.read_bytes(),
            'icon.png':(REPO/'collection/watch-s5-probe/variants/research-ui/src/common/icon.png').read_bytes(),
            'THIRD_PARTY_LICENSES.txt':(ROOT/'SDK_LICENSE.txt').read_bytes()}
        assert assets[manifest['entry']][:8]==b'\x00asm\x0d\x00\x01\x00'
        package=output/'IMU-S5-Receiver-0.2.3.abp'
        with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as archive:
            for name,data in assets.items():archive.writestr(name,data)
        report={'sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'bytes':package.stat().st_size,'manifest':manifest,
            'assets':{n:hashlib.sha256(v).hexdigest() for n,v in assets.items()},'actual_component_runtime_scenarios':scenarios,
            'engine':'48.0.2','filesystem':'real WASI p2/p3, fresh restricted synthetic directories',
            'android_bluetooth_and_system_save':'not_verified','new_device_recording':False}
        (output/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(package,flush=True)

if __name__=='__main__':main()
