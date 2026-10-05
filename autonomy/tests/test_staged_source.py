import base64,hashlib,json,sys
from pathlib import Path
import tempfile,unittest
from pipeline.staged_source import staged_source

class StagedSourceTests(unittest.TestCase):
    def fixture(self,root,*,corrupt=False,oversize=False):
        data=b'sensor-source-fixture';expected={'sha256':hashlib.sha256(data).hexdigest(),'hdfs_roundtrip_sha256':hashlib.sha256(data).hexdigest(),'hdfs_uri':'hdfs://cluster/mock','source_metadata':{'size':str(len(data)),'md5_hash':base64.b64encode(hashlib.md5(data).digest()).decode()}}
        script=root/'transfer.py';payload=b'x'*10000 if oversize else b'wrong' if corrupt else data
        script.write_text('from pathlib import Path\nimport sys\np=Path(sys.argv[-1])\ntry:\n p.write_bytes('+repr(payload)+')\nfinally:\n Path('+repr(str(root/'observed-size.txt'))+').write_text(str(p.stat().st_size))\n')
        return expected,[sys.executable,str(script)]

    def test_verified_source_lifetime_and_cleanup_after_consumer_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,command=self.fixture(root);cache=root/'cache'
            with staged_source(record,cache,retained_bytes=1000,limit_bytes=10000,transfer_command=command) as (path,evidence):
                self.assertEqual(path.read_bytes(),b'sensor-source-fixture');self.assertEqual(evidence['sha256'],record['sha256']);saved=path
            self.assertFalse(saved.exists())
            with self.assertRaises(RuntimeError):
                with staged_source(record,cache,retained_bytes=1000,limit_bytes=10000,transfer_command=command) as (path,evidence):
                    saved=path;raise RuntimeError('consumer failed')
            self.assertFalse(saved.exists())

    def test_bad_transfer_and_actual_oversize_cleanup(self):
        for kwargs in ({'corrupt':True},{'oversize':True}):
            with self.subTest(kwargs=kwargs),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);record,command=self.fixture(root,**kwargs);cache=root/'cache'
                with self.assertRaises(ValueError):
                    with staged_source(record,cache,retained_bytes=1000,limit_bytes=10000,transfer_command=command):pass
                self.assertLessEqual(int((root/'observed-size.txt').read_text()),9000)
                self.assertFalse(list((cache/'scientific-processing-staging').glob('stage-*')))

    def test_capacity_and_orphan_staging_rejected_before_transfer(self):
        for orphan in (False,True):
            with self.subTest(orphan=orphan),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);record,command=self.fixture(root);cache=root/'cache'
                if orphan:
                    old=cache/'scientific-source-audit/stage-orphan/input';old.mkdir(parents=True);(old/'source.parquet').write_bytes(b'preserve')
                with self.assertRaises(ValueError):
                    with staged_source(record,cache,retained_bytes=1000,limit_bytes=10000 if orphan else 1001,transfer_command=command):pass
                self.assertFalse((root/'observed-size.txt').exists())
                if orphan:self.assertEqual((old/'source.parquet').read_bytes(),b'preserve')

if __name__=='__main__':unittest.main()
