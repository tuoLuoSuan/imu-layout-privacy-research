import importlib.util
import io
import json
from pathlib import Path
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transfer_check',ROOT/'tools/check_transfer_source.py')
check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)

def fixture(extra=None,features=None):
    entries={'manifest.json':json.dumps({'package':'org.imuresearch.s5probe','versionName':'0.3.1','versionCode':5,
      'features':[{'name':n} for n in (features if features is not None else ['system.sensor','system.file','system.interconnect'])]}),
      'app.js':'export default function(){}','Probe/index.js':"export default function(){return {app_version:'0.3.1'}} // S5TX1 S5ACK1",'common/icon.png':b'fixture'}
    entries.update(extra or {});buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        for n,t in entries.items():z.writestr(n,t)
    return buf.getvalue()

class TransferArchive(unittest.TestCase):
    def test_only_ordinary_expected_capabilities(self):
        self.assertEqual(check.check_transfer_source(fixture())['code'],5)
        with self.assertRaises(ValueError):check.check_transfer_source(fixture(features=['system.sensor','system.file']))
        with self.assertRaises(ValueError):check.check_transfer_source(fixture(features=['system.sensor','system.file','system.interconnect','system.bluetooth']))
    def test_private_key_and_bytecode_are_refused(self):
        for n in ['app.jsc','Probe/index.template.bin','sign/private.pem']:
            with self.assertRaises(ValueError):check.check_transfer_source(fixture({n:b'x'}))

if __name__=='__main__':unittest.main()
