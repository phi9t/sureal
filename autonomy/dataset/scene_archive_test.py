import contextlib,hashlib,io,json,tarfile
from pathlib import Path
import tempfile,unittest
from dataset.scene_archive import create_scene_archive
from evidence.source_snapshot import file_sha256

class SceneArchiveTests(unittest.TestCase):
    def fixture(self,root):
        points=root/'points';points.mkdir();data=b'point-record-fixture';(points/'a.npz').write_bytes(data)
        report={'schema_version':1,'rows':[{'artifact':'a.npz','sha256':hashlib.sha256(data).hexdigest(),'return_present':True,'points':1}]}
        (points/'report.json').write_text(json.dumps(report));digest=file_sha256(points/'report.json')
        return points,digest

    def test_deterministic_members_and_working_set_accounting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);points,digest=self.fixture(root)
            a=create_scene_archive(points,root/'a.tar',expected_report_sha256=digest,sidecar_bytes=100,budget_bytes=100000)
            b=create_scene_archive(points,root/'b.tar',expected_report_sha256=digest,sidecar_bytes=100,budget_bytes=100000)
            self.assertEqual(a['sha256'],b['sha256'])
            self.assertFalse(a['scientific_working_cap']['exceeded'])
            self.assertEqual(a['scientific_working_cap']['where'],'dataset.scene_archive.create_scene_archive')
            self.assertEqual(a['archive_bytes'],(root/'a.tar').stat().st_size)
            self.assertEqual(a['working_set_bytes'],100+sum(p.stat().st_size for p in points.iterdir())+a['archive_bytes'])
            with tarfile.open(root/'a.tar') as tar:
                self.assertEqual(tar.getnames(),['report.json','a.npz'])
                for member in tar:
                    self.assertEqual(member.mtime,0);self.assertEqual(member.uid,0);self.assertEqual(member.gid,0)

    def test_capacity_hash_inventory_and_overwrite_rejected(self):
        for mutation in ('source','manifest','extra','existing'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);points,digest=self.fixture(root);out=root/'a.tar'
                if mutation=='source':(points/'a.npz').write_bytes(b'changed')
                if mutation=='manifest':(points/'report.json').write_text('{}')
                if mutation=='extra':(points/'extra').write_text('unexpected')
                if mutation=='existing':out.write_bytes(b'retained')
                with self.assertRaises(ValueError):create_scene_archive(points,out,expected_report_sha256=digest,sidecar_bytes=100,budget_bytes=100000)
                if mutation=='existing':self.assertEqual(out.read_bytes(),b'retained')
                else:self.assertFalse(out.exists())

    def test_capacity_alert_is_recorded_without_refusing_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);points,digest=self.fixture(root);out=root/'a.tar'
            stderr=io.StringIO()
            with contextlib.redirect_stderr(stderr):
                meta=create_scene_archive(points,out,expected_report_sha256=digest,sidecar_bytes=100,budget_bytes=1)
            self.assertTrue(out.exists())
            self.assertIn('WARNING: scientific working cap exceeded',stderr.getvalue())
            record=meta['scientific_working_cap']
            self.assertEqual(record['where'],'dataset.scene_archive.create_scene_archive')
            self.assertEqual(record['used_bytes'],100)
            self.assertEqual(record['new_bytes'],meta['working_set_bytes']-100)
            self.assertEqual(record['limit_bytes'],1)
            self.assertEqual(record['over_by_bytes'],meta['working_set_bytes']-1)
            self.assertTrue(record['exceeded'])
            print('scene over-cap record',json.dumps(record,sort_keys=True),flush=True)

if __name__=='__main__':unittest.main()
