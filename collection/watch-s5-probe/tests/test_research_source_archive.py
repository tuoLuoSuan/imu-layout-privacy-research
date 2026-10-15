import importlib.util
import io
import json
from pathlib import Path
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('research_check',ROOT/'tools/check_research_source.py')
checker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

def fixture(extra=None,version='0.3.0'):
    entries={'manifest.json':json.dumps({'package':'org.imuresearch.s5probe','versionName':version,'versionCode':4,
      'features':[{'name':'system.file'},{'name':'system.sensor'}],'minAPILevel':2,'config':{'designWidth':466}}),
      'app.js':'export default function(){}', 'Probe/index.js':"export default function(){return {app_version:'0.3.0'}}; // IMUS5 queue_overflow callback_epoch_ms",'common/icon.png':b'synthetic_fixture'}
    entries.update(extra or {})
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as archive:
        for name,content in entries.items():archive.writestr(name,content)
    return buf.getvalue()

class ResearchSource(unittest.TestCase):
    def test_accepts_only_matching_profile(self):
        self.assertEqual(checker.check_research_source(fixture())['version'],'0.3.0')
        with self.assertRaises(ValueError):checker.check_research_source(fixture(version='0.2.0'))
    def test_refuses_binary_format_private_key_or_missing_core(self):
        for extra in ({'app.jsc':b'x'},{'sign/private.pem':'x'},{'Probe/index.js':'export default function(){}'}):
            with self.assertRaises(ValueError):checker.check_research_source(fixture(extra))

if __name__=='__main__':unittest.main()
