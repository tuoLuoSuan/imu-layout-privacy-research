import hashlib,importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path
from test_analyze import fixture,mod

def bundle(p,partial=False):
    fixture(p);items={'phone.zip':(p/'native.zip').read_bytes()}
    if not partial:items['watch.jsonl']=(p/'plugin.jsonl').read_bytes()
    manifest={'kind':'imu_capture_bundle_v1','schema_version':1,'native_sid':'native-session','watch_included':not partial,'watch_export_error':'missing plugin'if partial else'','files':[{'path':k,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}for k,b in items.items()]}
    target=p/'bundle.zip'
    with zipfile.ZipFile(target,'x')as z:
        for k,b in items.items():z.writestr(k,b)
        z.writestr('bundle-manifest.json',json.dumps(manifest))
    return target
class BundleTest(unittest.TestCase):
    def test_same_session_nested_archive_is_read_without_rewriting_sources(self):
        with tempfile.TemporaryDirectory()as d:
            p=Path(d);z=bundle(p);before=z.read_bytes();r=mod.analyze_bundle(z);self.assertEqual(r['watch_rows'],2);self.assertFalse(r['physical_clock_accepted']);self.assertEqual(before,z.read_bytes())
    def test_partial_archive_does_not_claim_paired_success(self):
        with tempfile.TemporaryDirectory()as d:
            z=bundle(Path(d),True);r=mod.analyze_bundle(z);self.assertEqual(r['status'],'phone_only_export_missing_watch_log');self.assertFalse(r['oracle_ready'])
    def test_unknown_outer_member_rejected(self):
        with tempfile.TemporaryDirectory()as d:
            z=bundle(Path(d))
            with zipfile.ZipFile(z,'a')as f:f.writestr('unlisted.txt','unknown')
            self.assertRaises(ValueError,mod.analyze_bundle,z)
