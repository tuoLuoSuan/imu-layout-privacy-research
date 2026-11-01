import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {checkSnapshot,rateText} from '../research.mjs';
const data=JSON.parse(await readFile(new URL('../research/current-evidence.json',import.meta.url),'utf8'));
test('all three batches retain 71 declared events and both T3 tasks',()=>{
  assert.equal(checkSnapshot(data),data);
  assert.equal(data.batches.T3.tasks['9'].joint.accuracy.numerator,64);
  assert.equal(data.batches.T3.tasks['8'].joint.accuracy.numerator,67);
  assert.equal(data.batches.T.evaluation_status.includes('second look'),true);
});
test('the raw recount limitation and failed radius eligibility stay explicit',()=>{
  assert.equal(data.radar.run008.N4_radius_condition_met,false);
  assert.ok(data.radar.run008.N4_radius_m<data.radar.run008.N4_radius_required_m);
  assert.equal(data.flags.sensor_window_join_allowed,false);
  assert.equal(data.flags.real_candidate_rank,null);
});
test('McNemar keeps counts, exact p and within-family adjustment',()=>{
  const p=data.batches.T3.paired['9'].find(p=>p.arm_a==='joint'&&p.arm_b==='phone');
  assert.deepEqual([p.a_only,p.b_only],[6,0]);assert.equal(p.p_exact,.03125);assert.equal(p.p_holm_within_batch_task,.0625);
  assert.equal(data.combined_T2_T3.joint_vs_phone.p_exact,.2890625);
  assert.equal(rateText({numerator:64,denominator:71,value:64/71}),'64/71 · 90.14%');
});
