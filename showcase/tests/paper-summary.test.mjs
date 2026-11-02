import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const d=JSON.parse(await readFile(new URL('../research/paper-20261102-summary.json',import.meta.url),'utf8'));

test('main action display is the native eight-class T3 task with its own metric provenance',()=>{
  const a=d.actions.main_display;
  assert.equal(a.task,'T3 native eight-class');
  assert.equal(a.cabinet_open_close_merged,true);
  assert.deepEqual([a.joint.numerator,a.phone.numerator,a.watch.numerator],[67,60,62]);
  assert.ok(Math.abs(a.macro_f1_joint-0.9041666666666667)<1e-12);
  assert.equal(a.paired[0].only_a,7);
  assert.equal(a.paired[0].only_b,0);
  assert.equal(a.paired[0].p_holm,0.046875);
  assert.equal(a.historical_nine_class_result_retained,true);
});
test('paper snapshot keeps synthetic identity and action confirmation as separate endpoints',()=>{
  assert.equal(d.identity.top1.denominator,2400);
  assert.equal(d.identity.representation_reference.numerator,492);
  assert.equal(d.identity.representation_reference.denominator,600);
  assert.equal(d.actions.confirmatory.numerator,65);
  assert.equal(d.actions.second_look.numerator,67);
  assert.match(d.actions.second_look_selection,/same T evaluated again/i);
});
test('pilot coverage never becomes independent location truth or physical synchronization',()=>{
  assert.deepEqual(d.pilot.coverage.map(r=>r.denominator),[64,64]);
  assert.equal(d.pilot.reference,'cue-declared windows, independent station truth unavailable');
  assert.equal(d.pilot.records,2);
  assert.equal(d.pilot.people,1);
  assert.equal(d.pilot.rooms,1);
  assert.equal(d.pilot.seven_arm_completed,false);
  assert.equal(d.pilot.spatial_20hz_completed,false);
  assert.equal(d.scope.physical_clock_accepted,false);
  assert.equal(d.scope.real_room_ranking,null);
  assert.equal(d.scope.collection_open,false);
});
test('all ratio fields reconcile and marker baseline uses self-excluded label frequencies',()=>{
  function visit(x){
    if(Array.isArray(x)){x.forEach(visit);return;}
    if(!x||typeof x!=='object')return;
    if('numerator'in x&&'denominator'in x&&'value'in x)assert.ok(Math.abs(x.value-x.numerator/x.denominator)<1e-9);
    Object.values(x).forEach(visit);
  }
  visit(d);
  assert.equal(d.pilot.random_marker_reference.numerator,54);
  assert.equal(d.pilot.random_marker_reference.denominator,240);
  assert.deepEqual(Object.values(d.pilot.nearest_marker).map(r=>r.numerator),[8,3,7]);
  assert.ok(d.pilot.raw_phone_duration_s.every(t=>t>240));
});
