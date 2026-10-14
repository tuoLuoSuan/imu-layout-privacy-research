import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {parseCsv} from './data.mjs';
const $=id=>document.getElementById(id);
let rows=[],original=[],phonePreview=null,selected=0,drawScene=()=>{};
function openTab(name){
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.id===name));
  document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.tab===name));
  requestAnimationFrame(()=>{plot();drawScene();});
}
document.querySelectorAll('[data-tab]').forEach(x=>x.addEventListener('click',()=>openTab(x.dataset.tab)));
document.querySelectorAll('[data-open-tab]').forEach(x=>x.addEventListener('click',e=>{e.preventDefault();openTab(x.dataset.openTab);}));
function updateRecord(data,source,imported=false,info={}){
  rows=data;selected=0;$('sample-slider').value=0;$('sample-slider').max=rows.length-1;
  $('signal-source').textContent=source;
  $('signal-badge').textContent=imported?'本地导入 · 来源待核':info.badge||'真实记录';
  $('signal-unit').textContent=info.unit||'待确认';
  $('channel-title').textContent=info.title||'三轴数值';
  $('count-label').textContent=info.event?'事件条数':'回调条数';
  $('span-label').textContent=info.event?'首末事件跨度':'首末回调跨度';
  $('rate-label').textContent=info.event?'平均事件率':'平均回调率';
  $('signal-context').textContent=info.context||'当前时间来自CSV的callback_elapsed_ms列。来源、单位与时间基准仍需核验；导入不会自动验证或补齐数据。';
  const span=rows.at(-1)[0]-rows[0][0];
  $('count').textContent=rows.length;$('span').textContent=span>=10000?`${(span/1000).toFixed(3)} s`:`${Number(span.toFixed(3))} ms`;
  $('rate').textContent=`${((rows.length-1)*1000/span).toFixed(3)} /s`;
  updateSelected();plot();
}
function updateSelected(){
  const r=rows[selected];if(!r)return;
  $('sample-value').textContent=`第 ${selected+1} 条  ·  t = ${r[0]} ms  ·  X ${r[1].toFixed(4)}  Y ${r[2].toFixed(4)}  Z ${r[3].toFixed(4)}`;
}
$('sample-slider').addEventListener('input',()=>{selected=Number($('sample-slider').value);updateSelected();plot();});
function showDataset(){
  const choice=$('signal-dataset').value;
  $('import-message').textContent='';
  if(choice==='band'){
    if(!original.length)return;
    updateRecord(original,'小米手环9 Pro · 2026-10-13首个真实会话 · Date.now回调到达时间',false,{unit:'待确认',title:'腕部三轴加速度',badge:'真实历史样例',context:'30条历史腕部样例；使用回调到达时间，单位待核。没有同步手机，不提供活动标签或布局预测。'});
    return;
  }
  if(!phonePreview)return;
  const gyro=choice==='phone-gyro',channel=gyro?'gyroscope':'accelerometer';
  updateRecord(phonePreview.channels[channel].rows,`小米17 Pro · App ${phonePreview.version} · 会话88aded49 · 请求120Hz / 8333µs`,false,{event:true,unit:gyro?'rad/s':'m/s²',title:gyro?'角速度':'含重力加速度',badge:'真实记录 · 功能短试',context:'各通道首个原始事件为零点，仅将纳秒差换算为毫秒；XYZ保留原值，不插值或重采样。约11秒短试基线不足，不证明长期稳定、活动识别或跨设备同步。'});
}
$('restore-sample').addEventListener('click',showDataset);
$('signal-dataset').addEventListener('change',showDataset);
$('choose-file').addEventListener('click',()=>$('csv-file').click());
$('csv-file').addEventListener('change',async e=>{
  const file=e.target.files[0];if(!file)return;
  try{
    if(file.size>12*1024*1024)throw Error('文件超过 12 MB，请先按会话分块。');
    updateRecord(parseCsv(await file.text()),`本地导入：${file.name} · 单位与来源待核`,true);
    $('import-message').textContent='已在浏览器内读取。导入只展示数值，不验证设备来源、动作标签或硬件时钟。';
  }catch(error){$('import-message').textContent=error.message;}
  e.target.value='';
});
function plot(){
  const canvas=$('wave'),width=canvas.clientWidth,height=canvas.clientHeight;
  if(!width||!height||!rows.length)return;
  const dpr=Math.min(devicePixelRatio||1,2);canvas.width=width*dpr;canvas.height=height*dpr;
  const c=canvas.getContext('2d');c.scale(dpr,dpr);
  const pad={l:52,r:18,t:22,b:35};const w=width-pad.l-pad.r,h=height-pad.t-pad.b;
  const vals=rows.flatMap(r=>r.slice(1,4));let low=Math.min(...vals.slice(0,20000)),high=Math.max(...vals.slice(0,20000));
  for(const r of rows){low=Math.min(low,r[1],r[2],r[3]);high=Math.max(high,r[1],r[2],r[3]);}
  const range=high-low||1;low-=range*.12;high+=range*.12;
  const start=rows[0][0],end=rows.at(-1)[0];
  const x=t=>pad.l+(t-start)/(end-start)*w,y=v=>pad.t+(high-v)/(high-low)*h;
  c.font='10px Consolas, monospace';c.textBaseline='middle';
  for(let i=0;i<=4;i++){
    const value=low+(high-low)*i/4,py=y(value);c.strokeStyle='#e9edf4';c.beginPath();c.moveTo(pad.l,py);c.lineTo(width-pad.r,py);c.stroke();
    c.fillStyle='#8291a6';c.textAlign='right';c.fillText(value.toFixed(2),pad.l-9,py);
    const t=start+(end-start)*i/4;c.textAlign=i===0?'left':i===4?'right':'center';c.fillText(`${Math.round(t)} ms`,x(t),height-13);
  }
  ['#286dca','#24a68a','#cf8e47'].forEach((color,axis)=>{
    c.strokeStyle=color;c.lineWidth=1.8;c.beginPath();
    const step=Math.max(1,Math.ceil(rows.length/5000));
    for(let i=0;i<rows.length;i+=step){const r=rows[i];i?c.lineTo(x(r[0]),y(r[axis+1])):c.moveTo(x(r[0]),y(r[axis+1]));}
    const last=rows.at(-1);c.lineTo(x(last[0]),y(last[axis+1]));c.stroke();
    c.fillStyle=color;c.beginPath();c.arc(x(rows[selected][0]),y(rows[selected][axis+1]),3.5,0,Math.PI*2);c.fill();
  });
  c.setLineDash([3,4]);c.strokeStyle='#a6b4c5';c.lineWidth=1;c.beginPath();c.moveTo(x(rows[selected][0]),pad.t);c.lineTo(x(rows[selected][0]),pad.t+h);c.stroke();c.setLineDash([]);
}
function initRoom(){
  const host=$('scene');
  try{
    const scene=new THREE.Scene();scene.background=new THREE.Color('#f7f9fc');
    const camera=new THREE.PerspectiveCamera(38,1,.1,100);camera.position.set(10,10,12);
    const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));host.append(renderer.domElement);
    const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,.3,0);controls.minDistance=5;controls.maxDistance=27;controls.maxPolarAngle=Math.PI*.48;
    scene.add(new THREE.AmbientLight(0xffffff,2));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(5,12,7);scene.add(light);
    const material=color=>new THREE.MeshStandardMaterial({color,roughness:.8,metalness:0});
    function box(parent,w,h,d,x,y,z,color){const geo=new THREE.BoxGeometry(w,h,d);const mesh=new THREE.Mesh(geo,material(color));mesh.position.set(x,y,z);parent.add(mesh);const edge=new THREE.LineSegments(new THREE.EdgesGeometry(geo),new THREE.LineBasicMaterial({color:'#b1c1d4',transparent:true,opacity:.7}));edge.position.copy(mesh.position);parent.add(edge);return mesh;}
    box(scene,8,.08,6,0,-.06,0,'#eaf0f7');
    const grid=new THREE.GridHelper(8,16,'#c6d3e2','#dde5ef');grid.position.y=.002;grid.scale.z=.75;scene.add(grid);
    const corners=[[-4,0,-3],[-4,2.4,-3],[4,2.4,-3],[4,0,-3],[-4,0,-3],[-4,0,3],[-4,2.4,3],[-4,2.4,-3],[4,2.4,-3],[4,2.4,3],[4,0,3],[-4,0,3]];
    scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(corners.map(p=>new THREE.Vector3(...p))),new THREE.LineBasicMaterial({color:'#b8c8dc',transparent:true,opacity:.65})));
    const objects=new THREE.Group();scene.add(objects);
    box(objects,1.8,.12,.8,-2,.82,-2,'#c8d8e9');for(const x of [-2.7,-1.3])box(objects,.08,.76,.08,x,.38,-2,'#b2c4d9');
    box(objects,.7,.1,.7,-2,.46,-.95,'#e3edf6');box(objects,.08,.75,.7,-2.32,.75,-.95,'#cad8e6');for(const x of [-2.27,-1.73])for(const z of [-1.2,-.7])box(objects,.05,.43,.05,x,.21,z,'#b8c9db');
    box(objects,2.2,.42,.85,2,.25,.8,'#dce6f1');box(objects,2.2,.65,.16,2,.62,1.15,'#cbd9e8');box(objects,.15,.65,1,1,.48,.8,'#cad8e6');box(objects,.15,.65,1,3,.48,.8,'#cad8e6');
    box(objects,1.25,1.5,.45,2.8,.75,-2.45,'#d6e2ef');
    const pathGroup=new THREE.Group();scene.add(pathGroup);
    const route=[[-3.7,.04,2.5],[-2.5,.04,1.6],[-2,.04,-.95],[-.7,.04,-.6],[.5,.04,.3],[1.8,.04,.35]];
    pathGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(route.map(p=>new THREE.Vector3(...p))),new THREE.LineBasicMaterial({color:'#286dca'})));
    for(const p of [route[2],route.at(-1)]){const ring=new THREE.Mesh(new THREE.RingGeometry(.14,.23,32),new THREE.MeshBasicMaterial({color:'#24a68a',side:THREE.DoubleSide}));ring.rotation.x=-Math.PI/2;ring.position.set(...p);pathGroup.add(ring);}
    const marker=new THREE.Mesh(new THREE.SphereGeometry(.085,16,16),material('#286dca'));marker.position.set(...route[0]);pathGroup.add(marker);
    drawScene=()=>{if(!host.clientWidth)return;renderer.setSize(host.clientWidth,host.clientHeight);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();renderer.render(scene,camera);};
    controls.addEventListener('change',drawScene);
    $('show-objects').addEventListener('change',e=>{objects.visible=e.target.checked;drawScene();});
    $('show-path').addEventListener('change',e=>{pathGroup.visible=e.target.checked;drawScene();});
    $('reset-view').addEventListener('click',()=>{camera.position.set(10,10,12);controls.target.set(0,.3,0);controls.update();drawScene();});
    new ResizeObserver(drawScene).observe(host);drawScene();
  }catch(e){host.textContent='三维视图无法启动，请检查浏览器的图形支持。真实信号与其他页面仍可查看。';console.error(e);}
}
new ResizeObserver(plot).observe($('wave'));
initRoom();
Promise.all(['./data/first-session.json','./data/phone-config-smoke.json'].map(url=>fetch(url).then(r=>{if(!r.ok)throw Error('未取得样例');return r.json();}))).then(([band,phone])=>{
  original=band.rows.map(r=>r.slice(0,4));phonePreview=phone;showDataset();
}).catch(e=>{$('signal-source').textContent=`样例读取失败：${e.message}`;});
