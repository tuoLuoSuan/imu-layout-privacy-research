import hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from roomtrace.cli import install_archive

class ReleaseBoundaryTests(unittest.TestCase):
    def archive(self,base,name,data,digest=None):
        path=base/'asset.zip'
        record={'path':name,'bytes':len(data),'sha256':digest or hashlib.sha256(data).hexdigest()}
        with zipfile.ZipFile(path,'w') as z:
            z.writestr(name,data);z.writestr('release-files.json',json.dumps([record]))
        return path

    def test_refuses_path_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);z=self.archive(root,'output/layout-recon/../../../escape.txt',b'x')
            with self.assertRaises(ValueError):install_archive(z,root/'dest')
            self.assertFalse((root/'escape.txt').exists())

    def test_hash_mismatch_never_installs(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);z=self.archive(root,'output/layout-recon/model.pt',b'bad','0'*64)
            with self.assertRaises(ValueError):install_archive(z,root/'dest')
            self.assertFalse((root/'dest/output/layout-recon/model.pt').exists())

    def test_different_local_artifact_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);name='output/layout-recon/model.pt';z=self.archive(root,name,b'new')
            target=root/'dest'/name;target.parent.mkdir(parents=True);target.write_bytes(b'old')
            with self.assertRaises(ValueError):install_archive(z,root/'dest')
            self.assertEqual(target.read_bytes(),b'old')

    def test_verified_artifact_installs(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);name='output/layout-recon/model.pt';z=self.archive(root,name,b'exact')
            self.assertEqual(install_archive(z,root/'dest'),1)
            self.assertEqual((root/'dest'/name).read_bytes(),b'exact')

if __name__=='__main__':unittest.main()
