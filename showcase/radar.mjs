import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {groupRadarPoints,validateRadarSummary} from './radar-data.mjs';
import {createNumberedDorm} from './dorm-unit-view.mjs';
import {projectDormPlan} from './dorm-units.mjs';
const $=id=>document.getElementById(id);
async function init(){
  const host=$('radar-scene');if(!host)return;
  try{
    const [summary,full,preview]=await Promise.all(['./data/dorm-room-20261027.json','./data/dorm-points-full-20261027.json','./data/dorm-points-20261026.json'].map(async u=>{const r=await fetch(u);if(!r.ok)throw Error('本机雷达素材暂不可用；源码仓库不含私人点云。');return r.json();}));
    validateRadarSummary(summary);
    if(full.count!==full.points.length||full.count!==summary.total_points||full.source_sha256!==summary.source_cloud_sha256)throw Error('完整点云与来源清单不一致，停止展示。');
    $('radar-count').textContent=summary.total_points.toLocaleString('en-US');
    $('radar-size').textContent=`${summary.room.length_m.toFixed(2)} × ${summary.room.width_m.toFixed(2)} m`;$('radar-aisle').textContent=`${summary.corridor_m.toFixed(2)} m`;
    $('radar-excluded').textContent=summary.counts.balcony.toLocaleString('en-US');
    $('radar-count-note').textContent=`当前完整点云复算：阳台外点 ${summary.counts.balcony.toLocaleString('en-US')}（${(summary.counts.balcony/summary.total_points*100).toFixed(1)}%）；其他候选轮廓外点 ${summary.counts.other_outside.toLocaleString('en-US')}。当前边界 x=3.545；历史 x>3.55 为13,029、x>4.3 为9,323，差异已查明；原文件均保留。`;
    const scene=new THREE.Scene();scene.background=new THREE.Color('#101d2b');
    const camera=new THREE.PerspectiveCamera(42,1,.05,100);
    const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;host.append(renderer.domElement);
    const controls=new OrbitControls(camera,renderer.domElement);controls.minDistance=1;controls.maxDistance=22;controls.maxPolarAngle=Math.PI*.93;
    const cx=(summary.room.x[0]+summary.room.x[1])/2,cy=(summary.room.y[0]+summary.room.y[1])/2;
    let viewMode='units';
    function clearView(){
      if(viewMode==='units'){camera.position.set(cx-4.7,5.5,-cy+3.8);controls.target.set(cx,.25,-cy);}
      else{camera.position.set(cx+5.2,4.2,5.0);controls.target.set(cx,1.1,-cy);}
      controls.update();
    }
    const numbered=createNumberedDorm(summary);scene.add(numbered.group);
    const plan=projectDormPlan(numbered.draft),planFrame=$('unit-plan-grid');
    planFrame.style.aspectRatio=String(plan.aspect_ratio);planFrame.dataset.orientation='entry-left-balcony-right';
    for(const unit of numbered.draft.units){
      const button=document.createElement('button');button.type='button';button.className=`unit-slot unit-${unit.id}`;
      const placement=plan.units.find(p=>p.id===unit.id);
      for(const key of ['left','top','width','height'])button.style[key]=`${placement[key]}%`;
      button.dataset.unitId=String(unit.id);button.style.setProperty('--unit-color',unit.color);button.setAttribute('aria-pressed','false');
      button.innerHTML=`<strong>${unit.id} <b class="unit-kind">${unit.kind==='desk'?'桌':'床'}</b></strong><span>${unit.detail}</span><small>用户已指定用途</small>`;
      button.addEventListener('click',()=>{
        numbered.select(unit.id);host.dataset.selectedUnit=String(unit.id);
        document.querySelectorAll('[data-unit-id]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
        $('dorm-unit-selected').textContent=`选中 ${unit.id} 号${unit.kind==='desk'?'桌':'床'}：${unit.detail}。用途按你指定，尺寸和边界仍是示意。`;draw();
      });$('unit-plan-grid').append(button);
    }
    for(const chair of plan.chairs){
      const marker=document.createElement('span');marker.className='unit-plan-chair';marker.textContent=`椅${chair.associated_unit_id}`;
      marker.setAttribute('aria-label',`配${chair.associated_unit_id}号桌的示意椅子`);
      for(const key of ['left','top','width','height'])marker.style[key]=`${chair[key]}%`;
      planFrame.append(marker);
    }
    const dotCanvas=document.createElement('canvas');dotCanvas.width=dotCanvas.height=32;
    const dotContext=dotCanvas.getContext('2d');dotContext.fillStyle='white';dotContext.beginPath();dotContext.arc(16,16,15,0,Math.PI*2);dotContext.fill();
    const dotTexture=new THREE.CanvasTexture(dotCanvas);
    const objects={};
    let displayGroups=null,loadedCount=0,hiddenUpper=0;
    function updateStatus(){
      let visible=0;for(const [name,object] of Object.entries(objects))if(object.visible)visible+=displayGroups[name].length;
      host.dataset.displayedPoints=String(visible);host.dataset.loadedPoints=String(loadedCount);host.dataset.hiddenUpper=String(hiddenUpper);
      host.dataset.viewMode=viewMode;host.dataset.unitCount=String(numbered.draft.units.length);host.dataset.chairCount=String(numbered.draft.aisle_objects.length);
      $('radar-status').textContent=viewMode==='units'?'面朝阳台：1、3号桌，2、4号床 · 两把椅子分别配1、3号桌':`${$('radar-density').value==='full'?'完整点云':'轻量预览'}载入 ${loadedCount.toLocaleString('en-US')} 点 · 当前显示 ${visible.toLocaleString('en-US')} 点${$('radar-hide-upper').checked?' · 顶部已隐藏':''} · 真实候选排名仍空`;
    }
    function rebuildPoints(){
      const data=$('radar-density').value==='full'?full:preview;
      const grouped=groupRadarPoints(data.points,summary.room,{hideUpper:$('radar-hide-upper').checked});
      displayGroups=grouped.groups;loadedCount=data.points.length;hiddenUpper=grouped.hiddenUpper;
      for(const [name,points] of Object.entries(displayGroups)){
        if(objects[name]){scene.remove(objects[name]);objects[name].geometry.dispose();objects[name].material.dispose();}
        const position=[],colors=[];
        for(const [x,y,z] of points){position.push(x,z,-y);const color=name==='room'?new THREE.Color().setHSL(.54-Math.min(1,Math.max(0,(z+.2)/3.8))*.18,.58,.65):new THREE.Color(name==='balcony'?'#ffad65':'#9aacc0');colors.push(color.r,color.g,color.b);}
        const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(position,3));geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
        const material=new THREE.PointsMaterial({size:2.1,map:dotTexture,alphaTest:.5,vertexColors:true,sizeAttenuation:false});
        const object=new THREE.Points(geometry,material);object.visible=viewMode==='points'&&(name==='room'||(name==='balcony'?$('radar-balcony').checked:$('radar-other').checked));scene.add(object);objects[name]=object;
      }
      updateStatus();draw();
    }
    const [x0,x1]=summary.room.x,[y0,y1]=summary.room.y;
    const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([[x0,0,-y0],[x1,0,-y0],[x1,0,-y1],[x0,0,-y1],[x0,0,-y0]].map(p=>new THREE.Vector3(...p))),new THREE.LineDashedMaterial({color:'#f5ce7b',dashSize:.15,gapSize:.08}));line.computeLineDistances();scene.add(line);
    const axes=new THREE.AxesHelper(.65);axes.position.set(x0,0,-y0);scene.add(axes);
    function setView(mode){
      viewMode=mode;const isUnits=mode==='units';numbered.group.visible=isUnits;
      host.setAttribute('aria-label',isUnits?'四单元编号示意，可拖动旋转':'真实宿舍点云，可拖动旋转和缩放');
      scene.background.set(isUnits?'#F0F5F8':'#101d2b');
      for(const [name,object] of Object.entries(objects))object.visible=!isUnits&&(name==='room'||(name==='balcony'?$('radar-balcony').checked:$('radar-other').checked));
      line.visible=!isUnits&&$('radar-outline').checked;axes.visible=!isUnits;
      $('dorm-unit-panel').hidden=!isUnits;$('radar-point-controls').hidden=isUnits;$('radar-old-view').hidden=isUnits;
      document.querySelector('.radar-stats').hidden=isUnits;$('radar-count-note').hidden=isUnits;
      $('radar-reset').textContent=isUnits?'立体':'清晰视角';
      $('radar-view-caption').textContent=isUnits?'1、3桌，2、4床，按用户指定。过道仅保留配两桌的两把椅子；白模边界、形状和椅子位置仍是示意，不是雷达识别结果。':'完整点云可切轻量版比较；隐藏顶部仅裁切显示，不改原件。蓝绿为轮廓内、橙色为阳台外回波。';
      document.querySelectorAll('[data-radar-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.radarView===mode)));
      updateStatus();clearView();draw();
    }
    function draw(){if(host.clientWidth<2||host.clientHeight<2)return;renderer.setSize(host.clientWidth,host.clientHeight);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();renderer.render(scene,camera);host.dataset.camera=camera.position.toArray().map(v=>v.toFixed(3)).join(',');}
    controls.addEventListener('change',draw);new ResizeObserver(draw).observe(host);
    $('radar-balcony').addEventListener('change',e=>{objects.balcony.visible=e.target.checked;updateStatus();draw();});
    $('radar-other').addEventListener('change',e=>{objects.other_outside.visible=e.target.checked;updateStatus();draw();});
    $('radar-outline').addEventListener('change',e=>{line.visible=viewMode==='points'&&e.target.checked;draw();});
    $('radar-reset').addEventListener('click',()=>{clearView();draw();});
    $('radar-old-view').addEventListener('click',()=>{camera.position.set(7,6,7);controls.target.set(.6,.6,0);controls.update();draw();});
    $('radar-top').addEventListener('click',()=>{camera.position.set(cx,8,-cy+.001);controls.target.set(cx,0,-cy);controls.update();draw();});
    $('radar-density').addEventListener('change',rebuildPoints);$('radar-hide-upper').addEventListener('change',rebuildPoints);
    document.querySelectorAll('[data-radar-view]').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.radarView)));
    rebuildPoints();setView('units');host.dataset.ready='true';draw();
  }catch(error){$('radar-status').textContent=error.message;host.textContent='雷达视图尚未载入。下方保留数据边界与原图说明。';}
}
init();
