import importlib.util
import io
import json
from pathlib import Path
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def checker():
    p = ROOT / 'tools/check_acquisition_source.py'
    assert p.exists(), '采集版源码归档检查尚未实现'
    spec = importlib.util.spec_from_file_location('acquisition_source_check', p)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result.check_acquisition_source


def fixture(extra=None, omit=None, version='0.1.1'):
    files = {'manifest.json': json.dumps({'package': 'org.imuresearch.s5probe', 'versionName': version,
        'versionCode': 2, 'minAPILevel': 2, 'config': {'designWidth': 466},
        'features': [{'name': 'system.sensor'}, {'name': 'system.file'}]}),
        'app.js': 'export default function(){} /* synthetic module */',
        'Probe/index.js': "export default function(){ return {metadata: {app_version: '0.1.1'}}; } /* synthetic module */"}
    files.update(extra or {})
    if omit:
        files.pop(omit)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()


class AcquisitionSourceTest(unittest.TestCase):
    def test_accepts_expected_source_upgrade(self):
        self.assertEqual(checker()(fixture())['version'], '0.1.1')

    def test_rejects_old_format_and_unexpected_private_material(self):
        check = checker()
        for name in ['app.jsc', 'Probe/index.template.bin', 'sign/private.pem']:
            with self.assertRaises(ValueError):
                check(fixture({name: 'fixture'}))

    def test_rejects_wrong_identity_or_stale_export_version(self):
        check = checker()
        for data in [fixture(version='0.1.0'), fixture(omit='app.js'),
                     fixture({'Probe/index.js': "export default function(){return {app_version:'0.1.0'};}"})]:
            with self.assertRaises(ValueError):
                check(data)


if __name__ == '__main__':
    unittest.main()
