import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {pointRegion,validateRadarSummary} from './radar-data.mjs';
const $=id=>document.getElementById(id);
async function init(){
  const host=$('radar-scene');if(!host)return;
  try{
    const [summary,preview]=await Promise.all(['./data/dorm-room-20261026.json','./data/dorm-points-20261026.json'].map(async u=>{const r=await fetch(u);if(!r.ok)throw Error('本机雷达素材暂不可用；源码仓库不含私人点云。');return r.json();}));
    validateRadarSummary(summary);
    $('radar-count').textContent=summary.total_points.toLocaleString('en-US');
    $('radar-size').textContent='4.95 × 3.26 m';$('radar-aisle').textContent='1.29 m';
    $('radar-excluded').textContent=summary.counts.balcony.toLocaleString('en-US');
    $('radar-status').textContent=`真实三站点云 · 显示 ${preview.points.length.toLocaleString('en-US')} / ${summary.total_points.toLocaleString('en-US')} 点 · 仅几何参考，功能区待确认`;
    $('radar-count-note').textContent=`当前完整点云复算：阳台外点 ${summary.counts.balcony.toLocaleString('en-US')}（${(summary.counts.balcony/summary.total_points*100).toFixed(1)}%）；其他候选轮廓外点 ${summary.counts.other_outside.toLocaleString('en-US')}。交接曾写9,323，当前文件口径不同；原文件均保留。`;
    const scene=new THREE.Scene();scene.background=new THREE.Color('#101d2b');
    const camera=new THREE.PerspectiveCamera(42,1,.05,100);camera.position.set(7,6,7);
    const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));host.append(renderer.domElement);
    const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(.6,.6,0);controls.minDistance=2;controls.maxDistance=22;controls.maxPolarAngle=Math.PI*.93;
    const groups={room:[],balcony:[],other_outside:[]};
    for(const p of preview.points)groups[pointRegion(p,summary.room)].push(p);
    const objects={};
    for(const [name,points] of Object.entries(groups)){
      const position=[],colors=[];
      for(const [x,y,z] of points){position.push(x,z,-y);const color=name==='room'?new THREE.Color().setHSL(.55-Math.min(1,Math.max(0,(z+1)/4))*.3,.7,.59):new THREE.Color(name==='balcony'?'#ff9a55':'#8395aa');colors.push(color.r,color.g,color.b);}
      const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(position,3));geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
      const object=new THREE.Points(geometry,new THREE.PointsMaterial({size:.035,vertexColors:true,sizeAttenuation:true}));object.visible=name==='room';scene.add(object);objects[name]=object;
    }
    const [x0,x1]=summary.room.x,[y0,y1]=summary.room.y;
    const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([[x0,0,-y0],[x1,0,-y0],[x1,0,-y1],[x0,0,-y1],[x0,0,-y0]].map(p=>new THREE.Vector3(...p))),new THREE.LineDashedMaterial({color:'#f5ce7b',dashSize:.15,gapSize:.08}));line.computeLineDistances();scene.add(line);
    const axes=new THREE.AxesHelper(.65);axes.position.set(x0,0,-y0);scene.add(axes);
    function draw(){if(host.clientWidth<2||host.clientHeight<2)return;renderer.setSize(host.clientWidth,host.clientHeight);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();renderer.render(scene,camera);host.dataset.camera=camera.position.toArray().map(v=>v.toFixed(3)).join(',');}
    controls.addEventListener('change',draw);new ResizeObserver(draw).observe(host);
    $('radar-balcony').addEventListener('change',e=>{objects.balcony.visible=e.target.checked;draw();});
    $('radar-other').addEventListener('change',e=>{objects.other_outside.visible=e.target.checked;draw();});
    $('radar-outline').addEventListener('change',e=>{line.visible=e.target.checked;draw();});
    $('radar-reset').addEventListener('click',()=>{camera.position.set(7,6,7);controls.target.set(.6,.6,0);controls.update();draw();});
    $('radar-top').addEventListener('click',()=>{camera.position.set(1,10,.001);controls.target.set(1,0,0);controls.update();draw();});
    host.dataset.ready='true';draw();
  }catch(error){$('radar-status').textContent=error.message;host.textContent='雷达视图尚未载入。下方保留数据边界与原图说明。';}
}
init();
