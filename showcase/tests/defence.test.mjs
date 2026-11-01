import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {evidenceRows, evidenceSvg, evidenceCsv} from '../defence.mjs';
const d=JSON.parse(await readFile(new URL('../research/defence-evidence.json',import.meta.url),'utf8'));

test('all frozen coordinate conditions and cohorts remain visible without cherry picking',()=>{
  assert.equal(d.rows.length,351);
  for(const cohort of new Set(d.rows.map(r=>r.cohort))) {
    assert.equal(d.rows.filter(r=>r.cohort===cohort).length,39);
    for(const visits of [8,16,32])for(const sigma of [.3,.5,1,1.5]) {
      const rows=evidenceRows(d,cohort,visits,sigma);
      assert.deepEqual(rows.map(r=>r.structure),['none','common','brownian','iid']);
      assert.equal(rows[0].top1.rate.value,rows[1].top1.rate.value);
      assert.ok(rows[1].invariant_control);
    }
  }
});
test('source, replication unit, and undeployed defence remain explicit',()=>{
  assert.equal(d.provenance.ranking_scores_recomputed,false);
  assert.equal(d.provenance.stored_query_scores_reaggregated,true);
  assert.equal(d.condition.common_scores_reused_from_noiseless_by_original_runner,true);
  assert.equal(d.condition.raw_imu_defence_implemented,false);
  assert.equal(d.condition.adaptive_scorer_validated,false);
  assert.equal(d.flags.physical_clock_accepted,false);
  assert.match(d.uncertainty.unit,/house/);
});
test('exports retain score provenance, paired controls, and geometry proxy labels',()=>{
  const rows=evidenceRows(d,'all',32,.5);
  assert.ok(Math.abs(rows[2].top1.rate.value-.4233488756613759)<1e-12);
  const csv=evidenceCsv(rows);
  assert.match(csv,/ranking_scores_recomputed/);
  assert.match(csv,/invariance_control/);
  assert.equal(csv.split('\r\n').length,5);
  const svg=evidenceSvg(d,'all',32,.5);
  assert.match(svg,/冻结/);assert.match(svg,/λ=0/);
  assert.doesNotMatch(svg,/NaN|undefined/);
});
