import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {groupView, sceneSvg, aggregateRows, defenceRows, chartSvg, relationMatrixSvg} from '../simulation.mjs';

const index=JSON.parse(await readFile(new URL('../research/simulation-index.json',import.meta.url),'utf8'));
async function familyData(file){const manifest=JSON.parse(await readFile(new URL('../research/'+file,import.meta.url),'utf8'));const parts=await Promise.all(manifest.parts.map(p=>readFile(new URL('../research/'+p.file,import.meta.url),'utf8').then(JSON.parse)));return {houses:parts.flatMap(p=>p.houses)};}
const dorm=await familyData('simulation-dorm.json');

test('complete exported library contains 600 generated test houses and no physical claims',async()=>{
  assert.equal(index.houses,600);assert.equal(index.routes_per_house,4);
  assert.equal(index.scope.raw_imu_simulated,false);assert.equal(index.scope.procthor_generated,false);
  assert.equal(index.flags.real_candidate_rank,null);assert.equal(index.flags.physical_clock_accepted,false);
  let count=0;
  for(const family of index.families){
    const data=await familyData(family.file);
    assert.equal(data.houses.length,100);count+=data.houses.length;
    for(const house of data.houses){assert.equal(house.routes.length,4);for(const r of house.routes){assert.equal(r.observed.length,32);assert.equal(r.truth.length,32);assert.equal(r.methods.length,3);}}
  }
  assert.equal(count,600);
});
test('group view keeps noise proposals separate and never labels replay as prefix inference',()=>{
  const r=dorm.houses[0].routes[0];
  for(let mode=0;mode<3;mode++){
    const v=groupView(r,mode,12);
    assert.equal(v.shownVisits,12);assert.equal(v.totalVisits,32);
    assert.equal(v.inferenceScope,'full_record_offline');
    assert.equal(v.groups.length,r.methods[mode].group_count);
    assert.equal(v.shownPoints.length,12);
  }
});
test('cohort chart uses the matching upper reference and exact numerator/denominator',()=>{
  const all=aggregateRows(index,'all'),alias=aggregateRows(index,'alias');
  assert.equal(all.length,3);assert.equal(all[0].ceiling,.82);
  assert.ok(Math.abs(alias[0].ceiling-71/179)<1e-12);
  assert.equal(all[1].answer.numerator,2396);assert.equal(all[1].answer.denominator,2400);
  assert.equal(all[1].retained.value,1107/2400);
  assert.equal(all[2].retained.value,494/2400);
});
test('defence evidence distinguishes common offset control from destructive independent noise',()=>{
  const rows=defenceRows(index);
  assert.equal(rows.length,4);
  assert.equal(rows.find(r=>r.structure==='common').top1,rows.find(r=>r.structure==='none').top1);
  assert.ok(rows.find(r=>r.structure==='iid').top1<rows.find(r=>r.structure==='brownian').top1);
  assert.equal(index.defence.deployed_defence_validated,false);
});
test('SVG export preserves metric geometry, accessible labels and selected observation scope',()=>{
  const h=dorm.houses[0],r=h.routes[0],svg=sceneSvg(h,r,{mode:1,visits:12,kind:'observed'});
  assert.match(svg,/<svg/);assert.match(svg,/role="img"/);assert.match(svg,/合成/);
  assert.match(svg,/完整32访/);assert.doesNotMatch(svg,/undefined|NaN|Infinity/);
  const chart=chartSvg(aggregateRows(index,'all'));
  assert.match(chart,/52\.46/);assert.match(chart,/28\.38/);assert.match(chart,/7\.24/);
  assert.match(chart,/0/);assert.match(chart,/100/);
});
test('relationship diagram evaluates all 496 pairs without counting replay frames as samples',()=>{
  const r=dorm.houses[0].routes[0];
  for(let mode=0;mode<3;mode++){
    assert.equal(Object.values(r.methods[mode].relation).reduce((a,b)=>a+b,0),496);
    const svg=relationMatrixSvg(r,mode);
    assert.match(svg,/496/);assert.match(svg,/评价侧/);assert.doesNotMatch(svg,/NaN|undefined/);
  }
});
