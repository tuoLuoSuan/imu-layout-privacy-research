"""Build/test locally, using task-local Rust when present; never installs/runs a device app."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from check_async_component import check_async_component

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]

def configuration():
    env=os.environ.copy()
    cache=REPO/'.cache/s5-transfer-research'
    local=cache/'cargo/bin/cargo.exe'
    if local.exists():
        env['RUSTUP_HOME']=str(cache/'rustup');env['CARGO_HOME']=str(cache/'cargo')
        env['RUSTUP_TOOLCHAIN']='stable-x86_64-pc-windows-gnu'
        env['CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER']=str(cache/'rustup/toolchains/stable-x86_64-pc-windows-gnu/lib/rustlib/x86_64-pc-windows-gnu/bin/rust-lld.exe')
        env['CARGO_TARGET_X86_64_PC_WINDOWS_GNU_RUSTFLAGS']='-C linker-flavor=ld.lld -C link-self-contained=yes'
        cargo=str(local);native='x86_64-pc-windows-gnu'
    else:
        cargo=shutil.which('cargo')
        if not cargo:raise RuntimeError('Rust is unavailable; install the documented toolchain first')
        native=None
    env['CARGO_TARGET_DIR']=str(cache/'receiver-target')
    return cargo,env,native

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--test',action='store_true');parser.add_argument('--package',action='store_true');parser.add_argument('--output-dir');args=parser.parse_args()
    cargo,env,native=configuration()
    base=[cargo,'--offline']
    if args.test:
        subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p','test_*.py','-v'],env=env,check=True)
        command=base+['test','--locked','--manifest-path',str(ROOT/'Cargo.toml')]
        if native:command+=['--target',native]
        subprocess.run(command,env=env,check=True)
        command=base+['build','--locked','--manifest-path',str(ROOT/'Cargo.toml'),'--bin','receiver_sim']
        if native:command+=['--target',native]
        subprocess.run(command,env=env,check=True)
    if args.package:
        subprocess.run(base+['build','--locked','--manifest-path',str(ROOT/'Cargo.toml'),'--target','wasm32-wasip2','--lib','--features','astrobox','--release'],env=env,check=True)
        manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
        version=manifest['version']
        output=Path(args.output_dir).resolve() if args.output_dir else ROOT/('dist/receiver-'+version)
        if not output.is_relative_to((ROOT/'dist').resolve()):raise ValueError('Output must stay in this module dist directory')
        output.mkdir(parents=True,exist_ok=False)
        wasm=Path(env['CARGO_TARGET_DIR'])/'wasm32-wasip2/release/imus5_receiver.wasm'
        assets={'manifest.json':(ROOT/'manifest.json').read_bytes(),'imus5_receiver.wasm':wasm.read_bytes(),
          'THIRD_PARTY_LICENSES.txt':(ROOT/'wit/LICENSE').read_bytes(),
          'icon.png':(REPO/'collection/watch-s5-probe/variants/research-ui/src/common/icon.png').read_bytes()}
        assert assets['imus5_receiver.wasm'][:8]==b'\x00asm\x0d\x00\x01\x00','not a WebAssembly component'
        async_abi=check_async_component(assets['imus5_receiver.wasm'])
        package=output/('IMU-S5-Receiver-'+version+'.abp')
        with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as archive:
            for name,data in assets.items():archive.writestr(name,data)
        report={'sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'bytes':package.stat().st_size,
          'files':{n:hashlib.sha256(b).hexdigest() for n,b in assets.items()},'manifest':manifest,
          'async_abi':async_abi,'device_or_host_installation':'not_performed','actual_wireless_transfer':'not_verified'}
        (output/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(package)

if __name__=='__main__':main()
