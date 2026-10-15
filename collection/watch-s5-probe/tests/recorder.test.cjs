const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = path.join(__dirname, '../src/common/recorder.js');
const core = fs.existsSync(source) ? require(source) : {};

function fixture(options = {}) {
  assert.equal(typeof core.createRecorder, 'function', '采集核心尚未实现');
  let time = 10000;
  const recorder = core.createRecorder(Object.assign({ now: () => time }, options));
  recorder.start();
  return { recorder, at: (value) => { time = value; } };
}

test('记录字段保留未知单位与真实时间来源，标签来自人为指令', () => {
  const { recorder, at } = fixture({ label: 'walk' });
  at(10020);
  recorder.append({ x: 1.234567890123, y: -2, z: 9.1 }, 'visible');
  const data = recorder.stop('manual');
  assert.equal(data.metadata.acceleration_unit, 'unknown');
  assert.equal(data.metadata.hardware_timestamp, false);
  assert.equal(data.metadata.time_source, 'Date.now_callback_arrival');
  assert.equal(data.metadata.label_source, 'manual_instruction');
  assert.equal(data.metadata.activity_instruction, 'walk');
  assert.equal(data.rows[0][1], 1.234567890123);
});

test('无效读数被计数而非补成零', () => {
  const { recorder } = fixture();
  recorder.append({ x: NaN, y: 1, z: 2 });
  recorder.append({ x: 0, y: Infinity, z: 2 });
  recorder.append({ x: '1', y: 1, z: 2 });
  const data = recorder.stop();
  assert.equal(data.rows.length, 0);
  assert.equal(data.diagnostics.invalid_samples, 3);
});

test('达到样本上限后不继续增加内存记录', () => {
  const { recorder, at } = fixture({ maxSamples: 2 });
  at(10020); recorder.append({ x: 1, y: 2, z: 3 });
  at(10040); const decision = recorder.append({ x: 4, y: 5, z: 6 });
  assert.equal(decision.stopReason, 'sample_limit');
  at(10060); recorder.append({ x: 7, y: 8, z: 9 });
  assert.equal(recorder.snapshot().rows.length, 2);
});

test('超过录制时长的回调不会进入规定窗口', () => {
  const { recorder, at } = fixture({ durationMs: 2000 });
  at(10020); recorder.append({ x: 1, y: 2, z: 3 });
  at(12100); const result = recorder.append({ x: 4, y: 5, z: 6 });
  assert.equal(result.stopReason, 'duration');
  assert.equal(recorder.snapshot().rows.length, 1);
});

test('系统时钟倒退保留样本并显式计数', () => {
  const { recorder, at } = fixture();
  at(10040); recorder.append({ x: 1, y: 2, z: 3 });
  at(10010); recorder.append({ x: 2, y: 3, z: 4 });
  const data = recorder.stop();
  assert.equal(data.rows[1][0], 10);
  assert.equal(data.diagnostics.clock_regressions, 1);
});

test('记录页面隐藏状态，不通过程序主动丢弃这些回调', () => {
  const { recorder, at } = fixture();
  recorder.event('page_hide');
  at(10030); recorder.append({ x: 1, y: 2, z: 3 }, 'hidden');
  const data = recorder.stop();
  assert.equal(data.rows[0][4], 'hidden');
  assert.equal(data.events[0].type, 'page_hide');
});

test('快照由独立副本组成', () => {
  const { recorder } = fixture();
  recorder.append({ x: 1, y: 2, z: 3 });
  const snapshot = recorder.snapshot();
  snapshot.rows[0][1] = 100;
  assert.equal(recorder.snapshot().rows[0][1], 1);
});

test('CRC32 使用标准测试向量', () => {
  assert.equal(typeof core.crc32, 'function', '导出校验尚未实现');
  assert.equal(core.crc32('123456789'), 'cbf43926');
});

test('二维码分片可无损重组且不含非 ASCII 字符', () => {
  const { recorder } = fixture();
  recorder.event('note', '中文标签');
  recorder.append({ x: 1.123456789012345, y: -2, z: 3 });
  const record = recorder.stop();
  assert.equal(typeof core.encodeChunks, 'function', '二维码分片尚未实现');
  const chunks = core.encodeChunks(record, 80);
  let serialized = '';
  chunks.forEach((chunk, index) => {
    assert.match(chunk, /^[\x00-\x7f]+$/);
    const parts = chunk.split('|');
    assert.equal(parts[0], 'IMU9P');
    assert.equal(Number(parts[3]), index + 1);
    assert.equal(Number(parts[4]), chunks.length);
    const body = parts.slice(6).join('|');
    assert.ok(body.length <= 80);
    serialized += body;
  });
  assert.equal(core.crc32(serialized), chunks[0].split('|')[5]);
  assert.deepEqual(JSON.parse(serialized), record);
});

test('无数据时不能生成貌似有效的导出', () => {
  const { recorder } = fixture();
  const record = recorder.stop();
  assert.equal(typeof core.encodeChunks, 'function', '二维码分片尚未实现');
  assert.throws(() => core.encodeChunks(record), /没有样本/);
});
