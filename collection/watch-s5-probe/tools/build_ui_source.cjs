// Compatibility candidate for the existing acquisition app; never installs or launches it.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const artifactName = 'org.imuresearch.s5probe.release.0.2.0.rpk';

function prepareStage(stage) {
  require('./build_acquisition_source.cjs').prepareStage(stage);
  const manifestPath = path.join(stage, 'src/manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  manifest.versionName = '0.2.0'; manifest.versionCode = 3;
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  const corePath = path.join(stage, 'src/common/recorder.js');
  const core = fs.readFileSync(corePath, 'utf8');
  if (core.split("app_version: '0.1.1'").length !== 2) throw Error('Unexpected staged record version');
  fs.writeFileSync(corePath, core.replace("app_version: '0.1.1'", "app_version: '0.2.0'"));
  const profile = path.join(root, 'variants/research-ui/src');
  fs.copyFileSync(path.join(profile, 'Probe/index.ux'), path.join(stage, 'src/Probe/index.ux'));
  fs.copyFileSync(path.join(profile, 'common/icon.png'), path.join(stage, 'src/common/icon.png'));
}

async function main() {
  const output = path.join(root, 'dist/ui-0.2.0');
  const reportPath = path.join(output, 'build-report.json');
  if (fs.existsSync(path.join(output, artifactName)) || fs.existsSync(reportPath)) throw Error('Source candidate output exists; refusing overwrite');
  const sibling = path.resolve(root, '../band9pro-probe');
  const modules = fs.existsSync(path.join(root, 'node_modules/aiot-toolkit')) ? path.join(root, 'node_modules') : path.join(sibling, 'node_modules');
  const sign = process.env.S5_SIGN_DIR || (fs.existsSync(path.join(root, 'sign/private.pem')) ? path.join(root, 'sign') : path.join(sibling, 'sign'));
  if (!fs.existsSync(path.join(modules, 'aiot-toolkit')) || !fs.existsSync(path.join(sign, 'certificate.pem')) || !fs.existsSync(path.join(sign, 'private.pem'))) {
    throw Error('Existing local toolkit/signing material unavailable; no installation or new identity generated');
  }
  const tempRoot = fs.realpathSync(os.tmpdir());
  if (/[^\x00-\x7f]/.test(tempRoot)) throw Error('Vendor toolkit requires an ASCII temporary path');
  const stage = fs.mkdtempSync(path.join(tempRoot, 'imus5-ui-'));
  try {
    prepareStage(stage);
    const sourceFiles = ['manifest.json', 'app.ux', 'Probe/index.ux', 'common/icon.png', 'common/recorder.js'];
    const inputs = Object.fromEntries(sourceFiles.map(name => [name, {
      preserved_source_sha256: sha(fs.readFileSync(path.join(root, 'src', name))),
      staged_source_sha256: sha(fs.readFileSync(path.join(stage, 'src', name)))
    }]));
    fs.cpSync(sign, path.join(stage, 'sign'), {recursive: true});
    fs.symlinkSync(modules, path.join(stage, 'node_modules'), 'junction');
    const Builder = require(path.join(modules, 'aiot-toolkit/lib/builder/VelaUxBuilder')).default;
    await new Builder().build(stage, {mode: 'production', enableJsc: false, enableProtobuf: false});
    const artifact = path.join(stage, 'dist', artifactName);
    if (!fs.existsSync(artifact) || fs.statSync(artifact).size < 1000) throw Error('No acquisition source candidate produced');
    fs.mkdirSync(output, {recursive: true});
    fs.copyFileSync(artifact, path.join(output, artifactName), fs.constants.COPYFILE_EXCL);
    const report = {artifact: artifactName, bytes: fs.statSync(artifact).size,
      sha256: sha(fs.readFileSync(artifact)), built_at: new Date().toISOString(),
      package: 'org.imuresearch.s5probe', version: '0.2.0', version_code: 3,
      enable_jsc: false, enable_protobuf: false, aiot_toolkit: '2.0.5', node: process.version,
      features: ['system.sensor', 'system.file'], source_inputs: inputs,
      intentional_source_changes: ['temporary manifest/export version', 'approved UI profile', 'phone vector derived PNG icon'],
      unchanged_behavior: 'existing three-axis, bounded recording, save and QR export',
      installation_gate: 'hold until existing 0.1.1 raw export is received; no automatic installation',
      device_installation: 'not_performed', device_launch: 'not_performed', sensor_data: 'not_obtained'};
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
    console.log('Offline acquisition source candidate:', path.join(output, artifactName));
  } finally {
    const resolved = fs.realpathSync(stage);
    if (path.dirname(resolved) !== tempRoot || !/^imus5-ui-[A-Za-z0-9]+$/.test(path.basename(resolved))) throw Error('Temporary cleanup boundary failed');
    const link = path.join(resolved, 'node_modules');
    if (fs.existsSync(link) && fs.lstatSync(link).isSymbolicLink()) fs.unlinkSync(link);
    fs.rmSync(resolved, {recursive: true, force: true});
  }
}

module.exports = {prepareStage};
if (require.main === module) main().catch(error => {console.error(error.message); process.exitCode = 1;});
