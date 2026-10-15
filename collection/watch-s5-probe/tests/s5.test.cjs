const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const core=require('../src/common/recorder.js');

test('S5 identity reports its own firmware while other unavailable provenance stays unknown',()=>{
 const r=core.createRecorder();r.start();const m=r.stop('manual').metadata;
 assert.equal(m.device_model_reported,'Xiaomi Watch S5');
 assert.equal(m.device_variant_reported,'standard');
 assert.equal(m.firmware_reported,'3.102.036');
 assert.equal(m.metadata_source,'user_report_not_device_query');
 assert.equal(m.mi_fitness_version_reported,'not_recorded');
 assert.equal(m.astrobox_version_reported,'not_recorded');
 assert.equal(m.acceleration_unit,'unknown');assert.equal(m.hardware_timestamp,false);
 assert.equal(m.app_package,'org.imuresearch.s5probe');
});

test('S5 QR record round trips through Python with exact values and missing pages rejected',()=>{
 let now=10000;const r=core.createRecorder({now:()=>now});r.start();
 now=10020;r.append({x:1.234567890123,y:-2,z:3},'visible');
 now=10040;r.append({x:4,y:5,z:6},'hidden');
 const record=r.stop('manual');const frames=core.encodeChunks(record,100);
 const decoder=path.join(__dirname,'../tools/decode_export.py');
 const py=`import importlib.util,json,sys
s=importlib.util.spec_from_file_location('decoder',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
frames=json.load(sys.stdin);r=m.decode_packets(frames)[0]
assert r['metadata']['device_model_reported']=='Xiaomi Watch S5'
assert r['rows'][0][1]==1.234567890123
assert r['rows'][1][4]=='hidden'
try:m.decode_packets(frames[:-1])
except ValueError:pass
else:raise AssertionError('incomplete export accepted')
print(json.dumps({'model':r['metadata']['device_model_reported'],'rows':len(r['rows']),'missing_rejected':True}))`;
 const p=spawnSync('python',['-c',py,decoder],{input:JSON.stringify(frames),encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'}});
 assert.equal(p.status,0,p.stderr);assert.equal(JSON.parse(p.stdout).rows,2);
});
