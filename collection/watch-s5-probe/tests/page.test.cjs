const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const recorderModule = require('../src/common/recorder.js');

function page() {
  const sourcePath = path.join(__dirname, '../src/Probe/index.ux');
  assert.ok(fs.existsSync(sourcePath), '采集页面尚未实现');
  let source = fs.readFileSync(sourcePath, 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
  source = source.replace(/^import .*$/gm, '').replace('export default', 'result =');
  const writes = [];
  const reads = [];
  const sensor = { subscribeAccelerometer(o) { this.options = o; },
    unsubscribeAccelerometer() { this.unsubscribed = true; } };
  const context = { sensor, file: {writeText(o) {writes.push(o);}, readText(o) {reads.push(o);}},
    recorderModule, Date, Math, JSON, isFinite, console,
    setInterval: () => 1, clearInterval() {}, setTimeout: () => 2, clearTimeout() {} };
  vm.createContext(context); vm.runInContext(source, context);
  const p = Object.assign({}, context.result.private, context.result);
  p.onInit();
  return {p, sensor, writes, reads};
}

test('采集 XYZ、标记隐藏状态并保存独立会话', () => {
  const {p, sensor, writes} = page();
  p.startRecording();
  assert.equal(sensor.options.interval, 'game');
  sensor.options.callback({x: 1.23456789, y: -2, z: 3});
  p.onHide();
  assert.equal(p.recording, true);
  sensor.options.callback({x: 2, y: 4, z: 5});
  p.stopRecording();
  assert.equal(sensor.unsubscribed, true);
  const record = JSON.parse(writes[0].text);
  assert.equal(record.rows[0][1], 1.23456789);
  assert.equal(record.rows[1][4], 'hidden');
  assert.equal(record.events[0].type, 'page_hide');
  assert.match(writes[0].uri, /internal:\/\/files\/imus5_.*\.json$/);
  assert.equal(p.saving, true);
  writes[0].success();
  assert.equal(writes.length, 2);
  writes[1].success();
  assert.equal(p.saving, false);
  assert.match(p.status, /已保存/);
});

test('写入失败保留内存数据、显示失败且可重试', () => {
  const {p, sensor, writes} = page(); p.startRecording();
  sensor.options.callback({x: 1, y: 2, z: 3}); p.stopRecording();
  writes[0].fail('disk full', 300);
  assert.match(p.status, /保存失败/);
  assert.equal(p.saving, false);
  p.saveRecord(); assert.equal(writes.length, 2);
  assert.equal(writes[1].text, writes[0].text);
  p.openExport(); assert.equal(p.exportMode, false); // wait until write completes
  writes[1].success(); writes[2].success();
  p.openExport(); assert.equal(p.exportMode, true);
  assert.match(p.qrValue, /^IMU9P\|1\|/);
});

test('接口报错时结束采集、保存错误事件而不生成样本', () => {
  const {p, sensor, writes} = page(); p.startRecording();
  sensor.options.fail('unsupported', 1000);
  assert.equal(p.recording, false);
  assert.match(p.status, /接口失败/);
  assert.equal(JSON.parse(writes[0].text).rows.length, 0);
  writes[0].success(); writes[1].success();
  assert.match(p.status, /接口失败/);
  p.openExport(); assert.equal(p.exportMode, false);
});

test('重新打开恢复最新保存会话，不自动订阅传感器', () => {
  const {p, sensor, reads} = page(); p.loadLatest();
  reads[0].success({text: 'internal://files/imus5_123_ab.json'});
  assert.equal(reads[1].uri, 'internal://files/imus5_123_ab.json');
  const r = recorderModule.createRecorder(); r.start(); r.append({x: 1, y: 2, z: 3});
  reads[1].success({text: JSON.stringify(r.stop('manual'))});
  assert.equal(p.samples, 1);
  assert.equal(sensor.options, undefined);
  p.openExport(); assert.equal(p.exportMode, true);
});

test('圆屏设置在采集和保存时锁定，空闲时保留所选参数', () => {
  const {p, sensor, writes} = page();
  assert.equal(typeof p.openSettings, 'function', 'S5设置页尚未实现');
  p.openSettings(); assert.equal(p.settingsMode, true);
  p.choose10(); p.chooseWalk(); p.closeSettings();
  p.startRecording(); p.openSettings();
  assert.equal(p.settingsMode, false);
  p.choose30(); p.chooseStill();
  assert.equal(p.durationSeconds, 10); assert.equal(p.label, 'walk');
  sensor.options.callback({x: 1, y: 2, z: 3}); p.stopRecording();
  p.openSettings(); assert.equal(p.settingsMode, false);
  writes[0].success(); writes[1].success();
  p.openSettings(); assert.equal(p.settingsMode, true);
  const record = JSON.parse(writes[0].text);
  assert.equal(record.metadata.requested_duration_ms, 10000);
  assert.equal(record.metadata.activity_instruction, 'walk');
  assert.equal(record.metadata.device_model_reported, 'Xiaomi Watch S5');
});
