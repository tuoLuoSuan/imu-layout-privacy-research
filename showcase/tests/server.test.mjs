import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, writeFile, rm, symlink} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createShowcaseServer} from '../server.mjs';

async function fixture(t) {
  const root=await mkdtemp(path.join(tmpdir(),'imu-showcase-'));
  for(const name of ['simulation.mjs','simulation.css','research/simulation-index.json','research/simulation-dorm.json','research/simulation-dorm-1.json','research/simulation-dorm-2.json',
    'index.html','style.css','app.mjs','data.mjs','data/first-session.json',
    'data/phone-config-smoke.json','assets/recorder-0.2.2-records.png',
    'data/dorm-room-20261027.json','assets/room-semantics-20261027.png','assets/room-stability-20261027.png','data/dorm-points-full-20261027.json',
    'data/latest-signal-catalog-20261026.json','data/signal-20261025-bed-phone-accel.json','radar.mjs','radar-data.mjs','dorm-units.mjs','dorm-unit-view.mjs','data/dorm-room-20261026.json','data/dorm-points-20261026.json','assets/room-polygon-20261026.png',
    'node_modules/three/build/three.module.js','node_modules/three/build/three.core.js',
    'node_modules/three/examples/jsm/controls/OrbitControls.js','README.md','验证记录.md',
    'server.mjs','package.json','data/private.json']) {
    await mkdir(path.dirname(path.join(root,name)),{recursive:true});
    await writeFile(path.join(root,name),name);
  }
  const server=createShowcaseServer({root});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  t.after(async()=>{await new Promise(resolve=>server.close(resolve));await rm(root,{recursive:true,force:true});});
  return {root,url:`http://127.0.0.1:${server.address().port}`};
}

test('serves required page, private previews and exact Three dependencies with MIME',async t=>{
  const {url}=await fixture(t);
  for(const [name,type] of [['/simulation.mjs','text/javascript'],['/simulation.css','text/css'],['/research/simulation-index.json','application/json'],['/research/simulation-dorm-1.json','application/json'],['/research/simulation-dorm-2.json','application/json'],
    ['/','text/html'],['/app.mjs','text/javascript'],['/dorm-units.mjs','text/javascript'],['/dorm-unit-view.mjs','text/javascript'],
    ['/data/phone-config-smoke.json','application/json'],['/data/dorm-room-20261027.json','application/json'],['/data/dorm-points-full-20261027.json','application/json'],['/assets/room-semantics-20261027.png','image/png'],['/assets/room-stability-20261027.png','image/png'],['/assets/recorder-0.2.2-records.png','image/png'],
    ['/data/latest-signal-catalog-20261026.json','application/json'],['/data/signal-20261025-bed-phone-accel.json','application/json'],['/radar.mjs','text/javascript'],['/data/dorm-room-20261026.json','application/json'],['/data/dorm-points-20261026.json','application/json'],['/assets/room-polygon-20261026.png','image/png'],
    ['/node_modules/three/build/three.core.js','text/javascript'],
    ['/node_modules/three/examples/jsm/controls/OrbitControls.js','text/javascript']]) {
    const r=await fetch(url+name);assert.equal(r.status,200,name);
    assert.ok(r.headers.get('content-type').startsWith(type),name);
    assert.equal(r.headers.get('x-content-type-options'),'nosniff');
  }
  const r=await fetch(url+'/index.html',{method:'HEAD'});
  assert.equal(r.status,200);assert.equal(await r.text(),'');
});

test('blocks internal notes, server sources, unreviewed data and path aliases',async t=>{
  const {url}=await fixture(t);
  for(const name of ['/README.md','/'+encodeURIComponent('验证记录.md'),'/server.mjs','/package.json',
    '/data/private.json','/data/signals.json','/data/raw/lidar/bag_0.db3','/secrets/private.pem','/node_modules/three/package.json',
    '/data/../README.md','/%00','/..%5cPROJECT_STATE.md']) {
    const r=await fetch(url+name);assert.equal(r.status,404,name);
  }
  const post=await fetch(url+'/',{method:'POST',body:'private'});assert.equal(post.status,405);
});

test('a permitted asset path cannot redirect through a linked directory',async t=>{
  const {root,url}=await fixture(t);
  const outside=await mkdtemp(path.join(tmpdir(),'imu-outside-'));
  t.after(()=>rm(outside,{recursive:true,force:true}));
  await writeFile(path.join(outside,'phone-config-smoke.json'),'outside content');
  await rm(path.join(root,'data'),{recursive:true});
  await symlink(outside,path.join(root,'data'),process.platform==='win32'?'junction':'dir');
  const r=await fetch(url+'/data/phone-config-smoke.json');assert.equal(r.status,404);
});
