import test from 'node:test';
import assert from 'node:assert/strict';
import {groupRadarPoints} from '../radar-data.mjs';

const bounds={x:[0,5],y:[0,3]};
test('full display groups every source row without implicit sampling',()=>{
  const rows=[[1,1,0],[1,1,2.5],[6,1,1],[-1,1,1]];
  const original=structuredClone(rows);
  const result=groupRadarPoints(rows,bounds);
  assert.deepEqual(Object.values(result.groups).map(p=>p.length),[2,1,1]);
  assert.equal(result.hiddenUpper,0);
  assert.equal(result.displayable,rows.length);
  assert.deepEqual(rows,original);
});
test('upper hide is an explicit reversible display filter, not a source change',()=>{
  const rows=[[1,1,0],[1,1,2.5],[6,1,2.5]];
  const hidden=groupRadarPoints(rows,bounds,{hideUpper:true,upperLimit:2.2});
  assert.equal(hidden.hiddenUpper,2);
  assert.equal(hidden.displayable,1);
  assert.equal(groupRadarPoints(rows,bounds).displayable,3);
  assert.equal(rows.length,3);
});
