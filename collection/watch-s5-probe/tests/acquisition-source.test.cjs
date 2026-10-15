const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const root = path.join(__dirname, '..');
const target = path.join(root, 'tools/build_acquisition_source.cjs');

test('source staging produces an upgrade with matching exported version and leaves original inputs unchanged', () => {
  assert.ok(fs.existsSync(target), '源码采集版专用构建尚未实现');
  const {prepareStage} = require(target);
  const originalManifest = fs.readFileSync(path.join(root, 'src/manifest.json'));
  const originalCore = fs.readFileSync(path.join(root, 'src/common/recorder.js'));
  const stage = fs.mkdtempSync(path.join(os.tmpdir(), 'imus5-source-test-'));
  try {
    prepareStage(stage);
    const m = JSON.parse(fs.readFileSync(path.join(stage, 'src/manifest.json')));
    assert.equal(m.package, 'org.imuresearch.s5probe');
    assert.equal(m.versionName, '0.1.1');
    assert.equal(m.versionCode, 2);
    assert.deepEqual(m.features.map(x => x.name).sort(), ['system.file', 'system.sensor']);
    assert.equal(m.config.designWidth, 466);
    assert.deepEqual(require(path.join(stage, 'quickapp.config.js')), {cli: {enableJsc: false, enableProtobuf: false}});
    const core = require(path.join(stage, 'src/common/recorder.js'));
    const r = core.createRecorder();
    r.start(); r.append({x: 1.234567890123, y: -2, z: 3});
    const record = r.stop('manual');
    assert.equal(record.metadata.app_version, '0.1.1');
    assert.equal(record.metadata.hardware_timestamp, false);
    assert.equal(record.metadata.acceleration_unit, 'unknown');
    assert.equal(record.rows[0][1], 1.234567890123);
    assert.deepEqual(fs.readFileSync(path.join(root, 'src/manifest.json')), originalManifest);
    assert.deepEqual(fs.readFileSync(path.join(root, 'src/common/recorder.js')), originalCore);
    assert.deepEqual(fs.readFileSync(path.join(stage, 'src/Probe/index.ux')), fs.readFileSync(path.join(root, 'src/Probe/index.ux')));
    assert.equal(fs.existsSync(path.join(stage, 'sign')), false, 'prepareStage must not copy signing material');
  } finally {
    const resolved = fs.realpathSync(stage);
    assert.equal(path.dirname(resolved), fs.realpathSync(os.tmpdir()));
    assert.match(path.basename(resolved), /^imus5-source-test-[A-Za-z0-9]+$/);
    fs.rmSync(resolved, {recursive: true, force: true});
  }
});

test('source staging refuses an occupied source directory instead of replacing earlier inputs', () => {
  assert.ok(fs.existsSync(target), '源码采集版专用构建尚未实现');
  const {prepareStage} = require(target);
  const stage = fs.mkdtempSync(path.join(os.tmpdir(), 'imus5-source-test-'));
  try {
    fs.mkdirSync(path.join(stage, 'src'));
    fs.writeFileSync(path.join(stage, 'src/preserved.txt'), 'keep');
    assert.throws(() => prepareStage(stage), /occupied/);
    assert.equal(fs.readFileSync(path.join(stage, 'src/preserved.txt'), 'utf8'), 'keep');
  } finally {
    const resolved = fs.realpathSync(stage);
    assert.equal(path.dirname(resolved), fs.realpathSync(os.tmpdir()));
    assert.match(path.basename(resolved), /^imus5-source-test-[A-Za-z0-9]+$/);
    fs.rmSync(resolved, {recursive: true, force: true});
  }
});
