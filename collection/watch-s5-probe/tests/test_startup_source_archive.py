import importlib.util
import io
import json
from pathlib import Path
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def checker():
    p=ROOT/'tools/check_startup_source.py'
    assert p.exists(), '源码格式检查器尚未实现'
    spec=importlib.util.spec_from_file_location('source_check',p)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod.check_source_format

def fixture(extra=None,omit=None):
    files={'manifest.json':json.dumps({'package':'org.imuresearch.s5start','versionName':'0.0.2','versionCode':2,'features':[]}),
           'app.js':'export default function(){} /* synthetic fixture */',
           'Probe/index.js':'export default function(){ return {template:function(){},style:[]}; } /* synthetic inline-layout fixture */'}
    files.update(extra or {})
    if omit:files.pop(omit)
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        for name,text in files.items():z.writestr(name,text)
    return buf.getvalue()

class SourceArchiveTest(unittest.TestCase):
    def test_accepts_source_shape(self):
        self.assertEqual(checker()(fixture())['version'],'0.0.2')
    def test_rejects_bytecode_or_protobuf_even_with_valid_source(self):
        check=checker()
        for name in ['app.jsc','Probe/index.template.bin']:
            with self.assertRaises(ValueError):check(fixture({name:'fixture'}))
    def test_rejects_missing_source_and_sensor_permission(self):
        check=checker()
        with self.assertRaises(ValueError):check(fixture(omit='app.js'))
        manifest={'package':'org.imuresearch.s5start','versionName':'0.0.2','versionCode':2,'features':[{'name':'system.sensor'}]}
        with self.assertRaises(ValueError):check(fixture({'manifest.json':json.dumps(manifest)}))

if __name__=='__main__':unittest.main()
