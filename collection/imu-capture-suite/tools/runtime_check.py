"""Actual WASM under a simulated AstroBox host, including the new archive endpoint."""
import json,os,sys,uuid
from run import ROOT,REPO,E,config,run
c,env,target=config();cache=REPO/'.cache/s5-transfer-research/runtime-probe';compiler=cache/'compiler/zig-x86_64-windows-0.14.1'
env['PATH']=str(compiler)+os.pathsep+env['PATH'];env['CC']=str(cache/'cc-proxy.exe');env['AR']=str(cache/'ar-proxy.exe');env['ZIG_LOCAL_CACHE_DIR']=str(cache/'zig-local-cache');env['ZIG_GLOBAL_CACHE_DIR']=str(cache/'zig-global-cache');env['CARGO_TARGET_X86_64_PC_WINDOWS_GNU_RUSTFLAGS']+=' -C dlltool='+str(cache/'dlltool-proxy.exe');env['CARGO_PROFILE_DEV_DEBUG']='0';env['CARGO_TARGET_DIR']=str(cache/'target')
label=sys.argv[1]
code=run([c,'--offline','build','--manifest-path',ROOT/'runtime-tests/Cargo.toml','--target',target],'runtime-build-'+label,env)
if code:sys.exit(code)
exe=cache/'target'/target/'debug/imu-joint-runtime-check.exe';wasm=REPO/'.cache/imu-capture-suite/target/wasm32-wasip2/release/imu_joint_bridge.wasm'
results=[]
for name,flags in[('success',[]),('registration-denied',['deny']),('cancel-pending',['busy']),('HTTP-permission-denied',['http-denied']),('journal-collision',['collision']),('reply-denied',['reply-denied']),('save-cancelled',['save-cancelled'])]:
    folder=REPO/'.cache/imu-capture-suite'/('runtime-'+name+'-'+uuid.uuid4().hex)
    code=run([exe,wasm,folder,*flags],'runtime-'+name+'-'+label,env)
    if code:sys.exit(code)
    results.append({'scenario':name,'passed':True,'directory':str(folder)})
with(E/('runtime-result-'+label+'.json')).open('x',encoding='utf-8')as f:json.dump({'scenarios':results,'new_export_endpoint_raw_bytes_headers_and_rejections_tested':True,'next_session_preserves_previous_journal_tested':True,'Android_HTTP_BLE_or_system_dialog_verified':False},f,ensure_ascii=False,indent=2)
