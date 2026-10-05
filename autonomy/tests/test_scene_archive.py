import hashlib,json,tarfile
from pathlib import Path
import tempfile,unittest
from pipeline.scene_archive import create_scene_archive

class SceneArchiveTests(unittest.TestCase):
    def fixture(self,root):
        points=root/'points';points.mkdir();data=b'point-record-fixture';(points/'a.npz').write_bytes(data)
        report={'schema_version':1,'rows':[{'artifact':'a.npz','sha256':hashlib.sha256(data).hexdigest(),'return_present':True,'points':1}]}
        (points/'report.json').write_text(json.dumps(report));digest=hashlib.sha256((points/'report.json').read_bytes()).hexdigest()
        return points,digest

    def test_deterministic_members_and_working_set_accounting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);points,digest=self.fixture(root)
            a=create_scene_archive(points,root/'a.tar',expected_report_sha256=digest,sidecar_bytes=100,budget_bytes=100000)
            b=create_scene_archive(points,root/'b.tar',expected_report_sha256=digest,sidecar_bytes=100,budget_bytes=100000)
            self.assertEqual(a['sha256'],b['sha256'])
            self.assertEqual(a['archive_bytes'],(root/'a.tar').stat().st_size)
            self.assertEqual(a['working_set_bytes'],100+sum(p.stat().st_size for p in points.iterdir())+a['archive_bytes'])
            with tarfile.open(root/'a.tar') as tar:
                self.assertEqual(tar.getnames(),['report.json','a.npz'])
                for member in tar:
                    self.assertEqual(member.mtime,0);self.assertEqual(member.uid,0);self.assertEqual(member.gid,0)

    def test_capacity_hash_inventory_and_overwrite_rejected(self):
        for mutation in ('budget','source','manifest','extra','existing'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);points,digest=self.fixture(root);out=root/'a.tar'
                if mutation=='source':(points/'a.npz').write_bytes(b'changed')
                if mutation=='manifest':(points/'report.json').write_text('{}')
                if mutation=='extra':(points/'extra').write_text('unexpected')
                if mutation=='existing':out.write_bytes(b'retained')
                with self.assertRaises(ValueError):create_scene_archive(points,out,expected_report_sha256=digest,sidecar_bytes=100,budget_bytes=1 if mutation=='budget' else 100000)
                if mutation=='existing':self.assertEqual(out.read_bytes(),b'retained')
                else:self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
