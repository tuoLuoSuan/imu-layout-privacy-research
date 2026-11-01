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
test('restored raw replay and failed radius eligibility stay explicit',()=>{
  assert.equal(data.action_raw_replay_available.T2,true);
  assert.equal(data.action_raw_replay_available.T3,true);
  assert.equal(data.restored_originals.files,47);
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
test('labels-only arithmetic is a channel check, spatial intervention stays separate',()=>{
  const a=data.radar.automatic_interface;
  assert.equal(a.label_channel_consistency_check.methods.fixed.expected_pairs,7);
  assert.equal(a.label_channel_consistency_check.methods.density.observed_relabelled_false_pairs,7);
  assert.match(a.label_channel_consistency_check.scope,/excluded from negative-control/);
  assert.equal(a.spatial_counterfactual.fixed.fp,0);
  assert.equal(a.spatial_counterfactual.density.fp,21);
});
test('automatic grouping integration retains every query and the real-world limits',()=>{
  const s=data.simulation.automatic_group_ranking;
  assert.equal(s.verification_passed,true);
  assert.equal(s.automatic_raw_IMU_pipeline_validated,false);
  assert.equal(s.validation.replay_files,7);
  const rows=s.rows.filter(r=>r.cohort==='all');assert.equal(rows.length,3);
  for(const r of rows){assert.equal(r.queries,2400);assert.equal(r.metrics.identity_top1.rate.denominator,2400);}
  assert.equal(s.flags.real_candidate_rank,null);
});
