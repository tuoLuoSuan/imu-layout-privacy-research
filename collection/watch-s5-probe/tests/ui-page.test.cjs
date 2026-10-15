const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const core = require('../src/common/recorder.js');
const root = path.join(__dirname, '..');

function page() {
  const filename = path.join(root, 'variants/research-ui/src/Probe/index.ux');
  assert.ok(fs.existsSync(filename), '统一UI工作副本尚未实现');
  const ux = fs.readFileSync(filename, 'utf8');
  const script = ux.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'result =');
  const writes = [], reads = [];
  const sensor = {subscribeAccelerometer(o) {this.options = o;}, unsubscribeAccelerometer() {}};
  const context = {sensor, file: {writeText(o) {writes.push(o);}, readText(o) {reads.push(o);}}, recorderModule: core,
    Date, Math, JSON, isFinite, setInterval: () => 1, clearInterval() {}, setTimeout: () => 2, clearTimeout() {}};
  vm.createContext(context); vm.runInContext(script, context);
  const p = Object.assign({}, context.result.private, context.result); p.onInit();
  return {p, sensor, writes, reads};
}

test('tab navigation does not start or reset a session and busy conditions keep controls reachable', () => {
  const {p, sensor} = page();
  assert.equal(p.tab, 'collect'); p.showRecords(); assert.equal(p.tab, 'records');
  assert.equal(sensor.options, undefined); p.showCollect();
  p.startRecording(); const session = p._recorder.snapshot().session_id;
  p.showRecords(); p.openSettings(); p.openExport();
  assert.equal(p.tab, 'collect'); assert.equal(p.settingsMode, false); assert.equal(p.exportMode, false);
  assert.equal(p._recorder.snapshot().session_id, session);
  p.choose30(); assert.equal(p.durationSeconds, 2);
});

test('failed save stays visibly retryable and moving pages cannot discard the raw record', () => {
  const {p, sensor, writes} = page(); p.startRecording();
  sensor.options.callback({x: 1.234567890123, y: -2, z: 3}); p.stopRecording();
  p.showRecords(); assert.equal(p.tab, 'collect'); // drain/save gate
  writes[0].fail('disk full', 300); p.showRecords();
  assert.equal(p.tab, 'records'); assert.equal(p.hasRecord, true); assert.match(p.status, /保存失败/);
  const first = writes[0].text; p.showCollect(); p.showRecords(); p.saveRecord();
  assert.equal(writes[1].text, first); assert.equal(JSON.parse(first).rows[0][1], 1.234567890123);
  writes[1].success(); writes[2].success(); p.openExport();
  assert.equal(p.exportMode, true); assert.match(p.qrValue, /^IMU9P\|1\|/);
  p.closeExport(); assert.equal(p.tab, 'records');
});

test('old saved schema restores without relabeling app version or subscribing to sensors', () => {
  const {p, sensor, reads} = page(); p.showRecords(); p.loadLatest();
  reads[0].success({text: 'internal://files/imus5_legacy.json'});
  const r = core.createRecorder(); r.start(); r.append({x: 2, y: 3, z: 4});
  const old = r.stop('manual'); old.metadata.app_version = '0.1.1';
  reads[1].success({text: JSON.stringify(old)});
  assert.equal(p.hasRecord, true); assert.equal(p.samples, 1); assert.equal(sensor.options, undefined);
  p.openExport();
  const decoded = JSON.parse(p._frames.map(f => f.split('|').slice(6).join('|')).join(''));
  assert.equal(decoded.metadata.app_version, '0.1.1'); assert.equal(decoded.rows[0][1], 2);
});

test('UI staging keeps source-format configuration and upgrades both package and record metadata', () => {
  const tool = path.join(root, 'tools/build_ui_source.cjs');
  assert.ok(fs.existsSync(tool), '统一UI构建尚未实现');
  const {prepareStage} = require(tool);
  const os = require('node:os');
  const stage = fs.mkdtempSync(path.join(os.tmpdir(), 'imus5-ui-test-'));
  try {
    prepareStage(stage);
    const m = JSON.parse(fs.readFileSync(path.join(stage, 'src/manifest.json')));
    assert.equal(m.versionName, '0.2.0'); assert.equal(m.versionCode, 3);
    assert.equal(m.package, 'org.imuresearch.s5probe');
    assert.deepEqual(require(path.join(stage, 'quickapp.config.js')), {cli: {enableJsc: false, enableProtobuf: false}});
    const r = require(path.join(stage, 'src/common/recorder.js')).createRecorder();r.start();
    assert.equal(r.stop().metadata.app_version, '0.2.0');
    assert.deepEqual(fs.readFileSync(path.join(stage, 'src/common/icon.png')), fs.readFileSync(path.join(root, 'variants/research-ui/src/common/icon.png')));
  } finally {
    const resolved = fs.realpathSync(stage);
    assert.equal(path.dirname(resolved), fs.realpathSync(os.tmpdir()));
    assert.match(path.basename(resolved), /^imus5-ui-test-[A-Za-z0-9]+$/);
    fs.rmSync(resolved, {recursive: true, force: true});
  }
});
