// Independent diagnostic overlay. Preserved 0.3.0/1/2 profiles are never patched.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),version='0.3.3',artifactName='org.imuresearch.s5probe.release.'+version+'.rpk';
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
function replaceOne(source,from,to){if(source.split(from).length!==2)throw Error('Preserved source marker missing or duplicated: '+from.slice(0,65));return source.replace(from,to);}
function prepareStage(stage){
 require('./build_transfer_round_source.cjs').prepareStage(stage);
 const mp=path.join(stage,'src/manifest.json'),m=JSON.parse(fs.readFileSync(mp));m.versionName=version;m.versionCode=7;fs.writeFileSync(mp,JSON.stringify(m,null,2)+'\n');
 const core=path.join(stage,'src/common/research.js');fs.writeFileSync(core,replaceOne(fs.readFileSync(core,'utf8'),"app_version:'0.3.2'","app_version:'0.3.3'"));
 fs.copyFileSync(path.join(root,'variants/storage-diagnostic/src/common/storage-diagnostic.js'),path.join(stage,'src/common/storage-diagnostic.js'));
 const up=path.join(stage,'src/Probe/index.ux');let ux=fs.readFileSync(up,'utf8');
 ux=replaceOne(ux,'v0.3.2','v0.3.3');
 ux=replaceOne(ux,"import interconnect from '@system.interconnect'","import interconnect from '@system.interconnect'\nimport storageDiagnostic from '../common/storage-diagnostic.js'");
 ux=replaceOne(ux,"    exportChoice:false,","    diagnosticMode:false,diagnosticRunning:false,diagnosticTitle:'',diagnosticDetail:'',diagnosticPosition:'0 / 0',\n    exportChoice:false,");
 ux=replaceOne(ux,'  onInit(){','  onInit(){\n    this._diagnosticGeneration=0;this._diagnosticPages=[];this._diagnosticIndex=0;');
 ux=replaceOne(ux,'  onHide(){','  onHide(){if(this.diagnosticMode)this.closeStorage();');
 ux=replaceOne(ux,'  onDestroy(){','  onDestroy(){this._diagnosticGeneration++;');
 ux=replaceOne(ux,'return this.recording||this.saving||this.loading||this.transferring;','return this.recording||this.saving||this.loading||this.transferring||this.diagnosticRunning;');
 ux=replaceOne(ux,'  openSettings(){',`  inspectStorage(){
    if(this.busy())return;
    if(!this.diagnosticMode)this._preDiagnosticStatus=this.status;
    const generation=++this._diagnosticGeneration;
    this.diagnosticMode=true;this.diagnosticRunning=true;this._diagnosticPages=[];this._diagnosticIndex=0;
    this.diagnosticTitle='读取本机文件';this.diagnosticDetail='只读 list / get，每项最多8秒';this.diagnosticPosition='…';this.status='文件检查中 · 不会录制或删除';
    storageDiagnostic.inspect(file).then(result=>{
      if(this._destroyed||generation!==this._diagnosticGeneration)return;
      this._diagnosticPages=result.pages;this.diagnosticRunning=false;this.status='文件检查完成 · 下一页查看原始URI';this.renderStorage();
    }).catch(e=>{
      if(this._destroyed||generation!==this._diagnosticGeneration)return;
      this.diagnosticRunning=false;this.diagnosticTitle='检查异常';this.diagnosticDetail=String(e.message||e);this.status='检查失败 · 原记录保留';
    });
  },
  renderStorage(){
    const page=this._diagnosticPages[this._diagnosticIndex];if(!page)return;
    this.diagnosticTitle=page.title;this.diagnosticDetail=page.detail;this.diagnosticPosition=String(this._diagnosticIndex+1)+' / '+this._diagnosticPages.length;
  },
  nextStorage(){if(this.diagnosticRunning||!this._diagnosticPages.length)return;this._diagnosticIndex=(this._diagnosticIndex+1)%this._diagnosticPages.length;this.renderStorage();},
  closeStorage(){this._diagnosticGeneration++;this.diagnosticRunning=false;this.diagnosticMode=false;this.status=this._preDiagnosticStatus||'原记录保留';},
  openSettings(){`);
 ux=replaceOne(ux,'!settingsMode &amp;&amp; !confirmMode &amp;&amp; !exportChoice &amp;&amp; !transferMode','!settingsMode &amp;&amp; !confirmMode &amp;&amp; !exportChoice &amp;&amp; !transferMode &amp;&amp; !diagnosticMode');
 const previous='<div class="retry" onclick="extraAction"><text class="parameter-text">{{trashMode ? \'永久删除…\' : \'恢复旧版最近一条（只读）\'}}</text></div>';
 ux=replaceOne(ux,previous,`<div class="diagnostic-actions"><div class="diagnostic-link" onclick="extraAction"><text class="diagnostic-link-text">{{trashMode ? '永久删除…' : '恢复旧版（只读）'}}</text></div><div class="diagnostic-link" onclick="inspectStorage"><text class="diagnostic-link-text">文件检查（只读）</text></div></div>`);
 ux=replaceOne(ux,'      <div if="{{exportChoice}}"',`      <div if="{{diagnosticMode}}" class="body">
        <div class="card diagnostic-card"><text class="caption">文件检查 {{diagnosticPosition}}</text><text class="diagnostic-heading">{{diagnosticTitle}}</text><text class="diagnostic-detail">{{diagnosticDetail}}</text></div>
        <div class="row"><div class="button secondary" onclick="closeStorage"><text class="button-text">返回记录</text></div><div class="button primary" onclick="nextStorage"><text class="button-text light">下一页</text></div></div>
        <div class="retry" onclick="inspectStorage"><text class="parameter-text">{{diagnosticRunning ? '正在检查，请稍等' : '重新检查（只读）'}}</text></div>
      </div>
      <div if="{{exportChoice}}"`);
 ux=replaceOne(ux,'</style>',`.diagnostic-actions { width: 310px; height: 30px; flex-direction: row; justify-content: center; align-items: center; }
.diagnostic-link { width: 154px; height: 30px; align-items: center; justify-content: center; }
.diagnostic-link-text { width: 154px; font-size: 16px; color: #176B6D; text-align: center; }
.diagnostic-card { height: 180px; }
.diagnostic-heading { width: 296px; height: 34px; font-size: 18px; color: #102A43; text-align: center; }
.diagnostic-detail { width: 296px; height: 112px; font-size: 16px; color: #52677C; text-align: left; }
</style>`);
 fs.writeFileSync(up,ux);
}
async function main(){
 const output=path.resolve(process.argv[2]||path.join(root,'dist/storage-diagnostic-0.3.3'));
 if(!output.startsWith(path.join(root,'dist')+path.sep)||fs.existsSync(output))throw Error('Output must be a fresh directory inside module dist');
 const modules=fs.existsSync(path.join(root,'node_modules/aiot-toolkit'))?path.join(root,'node_modules'):path.resolve(root,'../band9pro-probe/node_modules');
 const sign=process.env.S5_SIGN_DIR||(fs.existsSync(path.join(root,'sign/private.pem'))?path.join(root,'sign'):path.resolve(root,'../band9pro-probe/sign'));
 if(!fs.existsSync(path.join(modules,'aiot-toolkit'))||!fs.existsSync(path.join(sign,'private.pem')))throw Error('Existing toolkit/signature unavailable');
 const tmp=fs.realpathSync(os.tmpdir());if(/[^\x00-\x7f]/.test(tmp))throw Error('ASCII temporary path required');const stage=fs.mkdtempSync(path.join(tmp,'imus5-diag-'));
 try{
  prepareStage(stage);fs.cpSync(sign,path.join(stage,'sign'),{recursive:true});fs.symlinkSync(modules,path.join(stage,'node_modules'),'junction');
  const names=['manifest.json','app.ux','Probe/index.ux','common/icon.png','common/research.js','common/recorder.js','common/transfer.js','common/storage-diagnostic.js'];
  const inputs=Object.fromEntries(names.map(n=>[n,sha(fs.readFileSync(path.join(stage,'src',n)))]));
  const Builder=require(path.join(modules,'aiot-toolkit/lib/builder/VelaUxBuilder')).default;await new Builder().build(stage,{mode:'production',enableJsc:false,enableProtobuf:false});
  const artifact=path.join(stage,'dist',artifactName);if(!fs.existsSync(artifact))throw Error('RPK missing');fs.mkdirSync(output);fs.copyFileSync(artifact,path.join(output,artifactName),fs.constants.COPYFILE_EXCL);
  fs.writeFileSync(path.join(output,'build-report.json'),JSON.stringify({version,version_code:7,artifact:artifactName,bytes:fs.statSync(artifact).size,sha256:sha(fs.readFileSync(artifact)),enable_jsc:false,enable_protobuf:false,staged_source_sha256:inputs,device_installation:'not_performed',record_list_root_cause:'not_hardware_observed',wireless_transfer:'not_hardware_verified'},null,2)+'\n',{flag:'wx'});
  console.log(path.join(output,artifactName));
 }finally{const resolved=fs.realpathSync(stage);if(path.dirname(resolved)!==tmp||!/^imus5-diag-[A-Za-z0-9]+$/.test(path.basename(resolved)))throw Error('Cleanup boundary');const link=path.join(resolved,'node_modules');if(fs.existsSync(link)&&fs.lstatSync(link).isSymbolicLink())fs.unlinkSync(link);fs.rmSync(resolved,{recursive:true,force:true});}
}
module.exports={prepareStage};if(require.main===module)main().catch(e=>{console.error(e.stack);process.exitCode=1;});
