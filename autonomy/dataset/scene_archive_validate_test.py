import hashlib,io,json,tarfile
from pathlib import Path
import tempfile,unittest
from pipeline.scene_archive_validate import validate_archive

class ArchiveValidationTests(unittest.TestCase):
    def make_archive(self,root,mutation):
        data=b'point-record-fixture'; name='..' if mutation=='dotdot' else 'a.npz'; report=json.dumps({'schema_version':1,'rows':[{'artifact':name,'sha256':hashlib.sha256(data).hexdigest(),'return_present':True,'points':1}]}).encode();archive=root/'scene.tar'
        with tarfile.open(archive,'w',format=tarfile.USTAR_FORMAT) as tar:
            items=[('report.json',report),(name,b'changed' if mutation=='content' else data)]
            if mutation=='missing':items=items[:1]
            if mutation=='duplicate':items.append(('a.npz',data))
            for name,payload in items:
                header=tarfile.TarInfo('../a.npz' if mutation=='path' and name=='a.npz' else name);header.size=len(payload);header.mode=0o644
                if mutation=='time':header.mtime=7
                if mutation=='link' and name=='a.npz':header.type=tarfile.SYMTYPE;header.linkname='/outside';header.size=0
                tar.addfile(header,io.BytesIO(payload))
        return archive,hashlib.sha256(report).hexdigest(),hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_valid_stream_and_adversarial_members(self):
        for mutation in ('none','content','missing','duplicate','path','dotdot','link','time'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                archive,manifest,digest=self.make_archive(Path(tmp),mutation)
                if mutation=='none':
                    self.assertEqual(validate_archive(archive,expected_report_sha256=manifest,expected_archive_sha256=digest)['members'],2)
                    with self.assertRaises(ValueError):validate_archive(archive,expected_report_sha256='0'*64,expected_archive_sha256=digest)
                    with self.assertRaises(ValueError):validate_archive(archive,expected_report_sha256=manifest,expected_archive_sha256='0'*64)
                else:
                    with self.assertRaises(ValueError):validate_archive(archive,expected_report_sha256=manifest,expected_archive_sha256=digest)

if __name__=='__main__':unittest.main()
