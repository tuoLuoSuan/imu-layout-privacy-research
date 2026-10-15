const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
test('round-icon build preserves acquisition, storage, transport and legacy data paths',()=>{
 const parent=fs.realpathSync(os.tmpdir()),temp=fs.mkdtempSync(path.join(parent,'imus5-round-test-'));
 try{
  const a=path.join(temp,'before'),b=path.join(temp,'after');
  require('../tools/build_transfer_source.cjs').prepareStage(a);
  require('../tools/build_transfer_round_source.cjs').prepareStage(b);
  for(const name of ['app.ux','common/recorder.js','common/transfer.js'])assert.deepEqual(fs.readFileSync(path.join(a,'src',name)),fs.readFileSync(path.join(b,'src',name)),name);
  const read=(base,name)=>fs.readFileSync(path.join(base,'src',name),'utf8');
  assert.equal(read(a,'common/research.js').replace("app_version:'0.3.1'","app_version:'0.3.2'"),read(b,'common/research.js'));
  assert.equal(read(a,'Probe/index.ux').replace('v0.3.1','v0.3.2'),read(b,'Probe/index.ux'));
  const before=JSON.parse(read(a,'manifest.json')),after=JSON.parse(read(b,'manifest.json'));
  assert.equal(after.versionName,'0.3.2');assert.equal(after.versionCode,6);
  before.versionName='0.3.2';before.versionCode=6;assert.deepEqual(after,before);
  assert.notDeepEqual(fs.readFileSync(path.join(a,'src/common/icon.png')),fs.readFileSync(path.join(b,'src/common/icon.png')));
 }finally{assert.equal(path.dirname(fs.realpathSync(temp)),parent);fs.rmSync(temp,{recursive:true,force:true});}
});
