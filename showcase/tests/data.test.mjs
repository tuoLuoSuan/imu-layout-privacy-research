import test from 'node:test';
import assert from 'node:assert/strict';
import {parseCsv} from '../data.mjs';
test('retains callback times and values without creating spatial or activity predictions',()=>{
  const rows=parseCsv('callback_elapsed_ms,x,y,z,page_state\n46,0.1,-0.2,1,visible\n110,0.2,-0.1,1,visible');
  assert.deepEqual(rows,[[46,.1,-.2,1],[110,.2,-.1,1]]);
});
test('rejects unusable values and decreasing clocks instead of silently repairing observations',()=>{
  assert.throws(()=>parseCsv('callback_elapsed_ms,x,y,z\n64,1,2,3\n32,1,2,3'),/时间/);
  assert.throws(()=>parseCsv('callback_elapsed_ms,x,y,z\n0,1,,3\n64,1,2,3'),/数值/);
});
test('does not accept unlabeled positional columns or a single callback as a time series',()=>{
  assert.throws(()=>parseCsv('a,b,c,d\n0,1,2,3\n64,1,2,3'),/列/);
  assert.throws(()=>parseCsv('callback_elapsed_ms,x,y,z\n0,1,2,3'),/至少/);
});
