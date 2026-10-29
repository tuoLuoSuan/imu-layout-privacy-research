import test from 'node:test';
import assert from 'node:assert/strict';
import {makeFourUnitDraft,projectDormPlan} from '../dorm-units.mjs';

const summary={room:{x:[-1.385,3.545],y:[-1.595,1.665],length_m:4.93,width_m:3.26},corridor_m:1.32};
test('user labels two desks and two beds without claiming measured furniture geometry',()=>{
  const original=structuredClone(summary),draft=makeFourUnitDraft(summary);
  assert.deepEqual(draft.units.map(u=>u.id),[1,2,3,4]);
  assert.deepEqual(draft.units.map(u=>u.kind),['desk','bed','desk','bed']);
  assert.ok(draft.units.every(u=>u.assignment_status==='user_confirmed'&&u.furniture_geometry_measured===false));
  assert.equal(draft.real_object_detection,false);
  assert.equal(draft.formal_score,null);
  assert.deepEqual(summary,original);
});
test('numbering agrees with facing balcony: left near/far 1/2 and right near/far 3/4',()=>{
  const [a,b,c,d]=makeFourUnitDraft(summary).units;
  assert.equal(a.side,'left');assert.equal(b.side,'left');
  assert.equal(c.side,'right');assert.equal(d.side,'right');
  assert.ok(a.center_xy_m[0]<b.center_xy_m[0]&&c.center_xy_m[0]<d.center_xy_m[0]);
  assert.ok(a.center_xy_m[1]>c.center_xy_m[1]);
  assert.equal(a.center_xy_m[0],c.center_xy_m[0]);
  assert.equal(b.center_xy_m[0],d.center_xy_m[0]);
});
test('illustrative areas stay in the registered outer frame without covering the aisle',()=>{
  for(const unit of makeFourUnitDraft(summary).units){
    const [x0,y0,x1,y1]=unit.illustrative_bounds_m;
    assert.ok(x0>=summary.room.x[0]&&x1<=summary.room.x[1]&&x1>x0);
    assert.ok(y0>=summary.room.y[0]&&y1<=summary.room.y[1]&&y1>y0);
    assert.ok(unit.side==='left'?y0>=.695-1e-9:y1<=-.625+1e-9);
  }
});
test('two illustrative chairs pair with the two user-labelled desks',()=>{
  const draft=makeFourUnitDraft(summary);
  assert.deepEqual(draft.planned_program,{bed:2,desk:2,chair:2});
  assert.equal(draft.aisle_objects.length,2);
  assert.ok(draft.aisle_objects.every(o=>o.kind==='chair'&&o.geometry_measured===false));
  assert.deepEqual(draft.aisle_objects.map(o=>o.associated_unit_id),[1,3]);
  assert.ok(draft.aisle_objects[0].center_xy_m[1]>draft.aisle_objects[1].center_xy_m[1]);
  assert.equal(draft.aisle_clutter_hidden_in_schematic,true);
  assert.equal(draft.usable_as_attack_observation,false);
});
test('horizontal plan keeps entry left, balcony right and the registered aspect ratio',()=>{
  const plan=projectDormPlan(makeFourUnitDraft(summary));
  assert.ok(Math.abs(plan.aspect_ratio-4.93/3.26)<1e-12);
  const [a,b,c,d]=plan.units;
  assert.ok(a.left<b.left&&c.left<d.left);
  assert.ok(a.top<c.top&&b.top<d.top);
  assert.equal(a.left,c.left);assert.equal(b.left,d.left);
  assert.ok(plan.chairs.every(x=>x.left<50));
  assert.ok(plan.chairs[0].top<50&&plan.chairs[1].top>50);
});
