import test from 'node:test';
import assert from 'node:assert/strict';
import {pointRegion,validateRadarSummary} from '../radar-data.mjs';

test('transparent-balcony returns do not become room geometry',()=>{
  const bounds={x:[-1.4,3.55],y:[-1.6,1.66]};
  assert.equal(pointRegion([3.56,0,1],bounds),'balcony');
  assert.equal(pointRegion([0,0,1],bounds),'room');
  assert.equal(pointRegion([-2,0,1],bounds),'other_outside');
  assert.equal(pointRegion([3.55,0,1],bounds),'room');
});

test('summary must partition all points and retain unverified geometry',()=>{
  const summary={total_points:84909,counts:{room:68451,balcony:13029,other_outside:3429},room:{x:[-1.4,3.55],y:[-1.6,1.66]},geometry_verified:false,formal_score:null};
  assert.equal(validateRadarSummary(summary),summary);
  assert.throws(()=>validateRadarSummary({...summary,counts:{...summary.counts,balcony:9323}}),/point counts/);
  assert.throws(()=>validateRadarSummary({...summary,geometry_verified:true}),/candidate/);
});
