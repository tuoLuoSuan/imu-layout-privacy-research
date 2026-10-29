import * as THREE from 'three';
import {makeFourUnitDraft} from './dorm-units.mjs';

function label(text,detail,color='#314C62'){
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=240;
  const c=canvas.getContext('2d');c.fillStyle='#ffffff';c.beginPath();c.roundRect(6,6,500,228,28);c.fill();
  c.strokeStyle=color;c.lineWidth=5;c.stroke();c.textAlign='center';c.fillStyle=color;
  c.font='700 112px "Microsoft YaHei",sans-serif';c.fillText(text,256,132);
  c.font='500 40px "Microsoft YaHei",sans-serif';c.fillStyle='#556B7A';c.fillText(detail,256,201);
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
  const object=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false,depthWrite:false}));
  object.scale.set(1.1,.52,1);object.renderOrder=10;return object;
}

export function createNumberedDorm(summary){
  const draft=makeFourUnitDraft(summary),group=new THREE.Group(),meshes=new Map();
  const [x0,x1]=draft.room.x,[y0,y1]=draft.room.y,cx=(x0+x1)/2,cy=(y0+y1)/2;
  function box(width,height,depth,x,y,z,color){
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(width,height,depth),new THREE.MeshStandardMaterial({color,roughness:.8}));
    mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);return mesh;
  }
  box(x1-x0+.12,.08,y1-y0+.12,cx,-.07,-cy,'#DCE5E8');
  box(x1-x0,.025,draft.corridor_m,cx,-.012,-cy,'#F7FAFB');
  for(const yy of [y0,y1])box(x1-x0,.18,.05,cx,.05,-yy,'#9AAEB9');
  for(const xx of [x0,x1])box(.05,.18,y1-y0,xx,.05,-cy,'#9AAEB9');
  const arrow=new THREE.ArrowHelper(new THREE.Vector3(1,0,0),new THREE.Vector3(x0+.55,.025,-cy),x1-x0-1.1,0x7993A4,.25,.12);group.add(arrow);
  const entry=label('入户','从这里面朝阳台');entry.scale.set(1.25,.58,1);entry.position.set(x0-.65,.12,-cy);group.add(entry);
  const balcony=label('阳台','朝向参照');balcony.scale.set(1.25,.58,1);balcony.position.set(x1+.65,.12,-cy);group.add(balcony);
  for(const unit of draft.units){
    const [a,b,c,d]=unit.illustrative_bounds_m,[x,y]=unit.center_xy_m;
    let mesh;
    if(unit.kind==='desk'){
      mesh=box(c-a,.065,d-b,x,.75,-y,'#E6C99E');
      for(const xx of [a+.09,c-.09])for(const yy of [b+.09,d-.09])box(.055,.72,.055,xx,.36,-yy,'#637788');
    }else{
      box(c-a,.20,d-b,x,.10,-y,'#A7B7C4');
      mesh=box(c-a-.06,.17,d-b-.04,x,.285,-y,'#F8FAFB');
      box((c-a)*.64,.025,d-b-.07,x-.18,.384,-y,'#D5E5ED');
      box(.35,.10,d-b-.18,c-.25,.415,-y,'#FFFFFF');
    }
    const edge=new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry),new THREE.LineBasicMaterial({color:unit.color}));mesh.add(edge);
    const tag=label(`${unit.id} ${unit.kind==='desk'?'桌':'床'}`,unit.name,unit.color);tag.position.set(x,unit.kind==='desk'?1.12:.84,-y);group.add(tag);meshes.set(unit.id,mesh);
  }
  // Chair pairing follows user labels; positions and shapes are still illustrative.
  for(const [index,chair] of draft.aisle_objects.entries()){
    const [chairX,chairY]=chair.center_xy_m;
    box(.46,.065,.46,chairX,.46,-chairY,'#D2AB6C');
    box(.46,.42,.055,chairX,.69,-chairY+(chair.facing_side==='left'?.20:-.20),'#D2AB6C');
    for(const dx of [-.17,.17])for(const dy of [-.17,.17])box(.045,.42,.045,chairX+dx,.21,-chairY+dy,'#526875');
    const chairTag=label(`椅${chair.associated_unit_id}`,`配${chair.associated_unit_id}号桌`,'#8C6B35');chairTag.scale.set(.70,.33,1);chairTag.position.set(chairX+.18,1.08,-chairY);group.add(chairTag);
  }
  group.add(new THREE.HemisphereLight('#FFFFFF','#CBD6DF',2.4));
  const sun=new THREE.DirectionalLight('#FFFFFF',3.0);sun.position.set(cx-2,6,4);sun.castShadow=true;
  sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-6;sun.shadow.camera.right=6;sun.shadow.camera.top=6;sun.shadow.camera.bottom=-6;sun.shadow.normalBias=.04;group.add(sun);
  return {group,draft,select(id){
    for(const unit of draft.units){const mesh=meshes.get(unit.id);mesh.material.emissive.set(unit.id===id?unit.color:'#000000');mesh.material.emissiveIntensity=.22;}
  }};
}
