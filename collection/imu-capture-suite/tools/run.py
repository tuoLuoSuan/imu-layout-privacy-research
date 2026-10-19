"""Cached toolchains, fresh logs, no device actions."""
import importlib.util,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1];E=REPO/'docs/reviews/evidence/2026-10-19-unified-imu-suite'
def config():
    p=REPO/'collection/astrobox-imu-receiver/tools/build_local.py';sys.path.insert(0,str(p.parent));s=importlib.util.spec_from_file_location('suite_build_base',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    cargo,env,target=m.configuration();env['CARGO_TARGET_DIR']=str(REPO/'.cache/imu-capture-suite/target');return cargo,env,target
def run(cmd,label,env=None,cwd=None):
    log=E/(label+'.txt')
    with log.open('xb')as f:r=subprocess.run([str(x)for x in cmd],cwd=cwd or REPO,env=env,stdout=f,stderr=subprocess.STDOUT)
    print(json.dumps({'log':label,'exit':r.returncode}),flush=True)
    if r.returncode:print(log.read_text(encoding='utf-8',errors='replace')[-9000:].encode('ascii','backslashreplace').decode(),flush=True)
    return r.returncode
if __name__=='__main__':
    mode,label=sys.argv[1:3]
    if mode=='native':
        alias=Path('D:/Project/imu-recorder-local');assert alias.resolve()==REPO.resolve();project=alias/'collection/imu-capture-suite/native'
        env=os.environ.copy();env['JAVA_HOME']='C:/Program Files/Java/latest/jdk-21';env['ANDROID_HOME']=str(alias/'.cache/android-sdk');env['GRADLE_USER_HOME']=str(alias/'.cache/gradle-home');env['PATH']=env['JAVA_HOME']+'/bin'+os.pathsep+env['PATH']
        code=run([alias/'.cache/android-native/gradle-9.6.1/bin/gradle.bat','--offline','--no-daemon','-p',project,*(sys.argv[3:]or['testDebugUnitTest','assembleDebug'])],label,env,project)
    elif mode=='node':code=run(['node','--test',*sorted((ROOT/'tests').glob('*.test.cjs'))],label)
    elif mode=='python':code=run([sys.executable,'-m','unittest','discover','-s',ROOT/'tests','-p','test_*.py','-v'],label)
    elif mode in['rust','wasm']:
        cargo,env,target=config()
        cmd=[cargo,'--offline','test','--manifest-path',ROOT/'plugin/Cargo.toml','--target',target]if mode=='rust'else[cargo,'--offline','build','--manifest-path',ROOT/'plugin/Cargo.toml','--target','wasm32-wasip2','--features','astrobox','--release']
        code=run(cmd,label,env)
    else:raise ValueError(mode)
    sys.exit(code)
