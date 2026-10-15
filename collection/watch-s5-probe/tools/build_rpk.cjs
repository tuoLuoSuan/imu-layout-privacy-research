// Build in an ASCII directory: the vendor Windows JSC uses narrow paths.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const sibling = path.resolve(root, '../band9pro-probe');
const modules = fs.existsSync(path.join(root, 'node_modules/aiot-toolkit')) ? path.join(root, 'node_modules') : path.join(sibling, 'node_modules');
const signDir = process.env.S5_SIGN_DIR || (fs.existsSync(path.join(root, 'sign/private.pem')) ? path.join(root, 'sign') : path.join(sibling, 'sign'));
if (!fs.existsSync(path.join(signDir, 'private.pem')) || !fs.existsSync(path.join(signDir, 'certificate.pem'))) throw new Error('本地签名材料缺失；设置S5_SIGN_DIR，不会覆盖既有身份');
const tempRoot = fs.realpathSync(os.tmpdir());
if (/[^\x00-\x7f]/.test(tempRoot)) throw new Error('构建工具需要英文临时路径；请先设置 TEMP 到英文目录。');
const stage = fs.mkdtempSync(path.join(tempRoot, 'imus5-build-'));
const expectedName = 'org.imuresearch.s5probe.release.0.1.0.rpk';
async function main() {
  try {
    for (const name of ['src', 'sign', 'package.json', 'quickapp.config.js']) {
      fs.cpSync(name === 'sign' ? signDir : path.join(root, name), path.join(stage, name), {recursive: true});
    }
    fs.symlinkSync(modules, path.join(stage, 'node_modules'), 'junction');
    const Builder = require(path.join(modules, 'aiot-toolkit/lib/builder/VelaUxBuilder')).default;
    const builder = new Builder();
    await builder.build(stage, {mode: 'production', enableJsc: true, enableProtobuf: true});
    const artifact = path.join(stage, 'dist', expectedName);
    if (!fs.existsSync(artifact) || fs.statSync(artifact).size < 1000) {
      throw new Error('构建未产生本轮 RPK；不能用工具退出码宣称成功。');
    }
    const output = path.join(root, 'dist'); fs.mkdirSync(output, {recursive: true});
    fs.copyFileSync(artifact, path.join(output, expectedName));
    const report = {artifact: expectedName, bytes: fs.statSync(artifact).size,
      sha256: crypto.createHash('sha256').update(fs.readFileSync(artifact)).digest('hex'),
      built_at: new Date().toISOString(), node: process.version, aiot_toolkit: '2.0.5',
      jsc: '1.0.9', dependency_directory: modules, signing_directory: signDir, enable_jsc: true, enable_protobuf: true,
      validation_scope: 'software build only; device installation and sensor validation pending'};
    fs.writeFileSync(path.join(output, 'build-report.json'), JSON.stringify(report, null, 2));
    console.log('RPK generated:', path.join(output, expectedName));
  } finally {
    // Validate the resolved recursive-delete target before removing staging.
    const resolved = fs.realpathSync(stage);
    if (path.dirname(resolved) !== tempRoot || !/^imus5-build-[A-Za-z0-9]+$/.test(path.basename(resolved))) {
      throw new Error('临时目录边界检查失败，未清理');
    }
    const link = path.join(stage, 'node_modules');
    if (fs.existsSync(link) && fs.lstatSync(link).isSymbolicLink()) fs.unlinkSync(link);
    fs.rmSync(resolved, {recursive: true, force: true});
  }
}
main().catch(error => {console.error(error.message); process.exitCode = 1;});
