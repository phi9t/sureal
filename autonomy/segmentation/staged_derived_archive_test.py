import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from segmentation.staged_derived_archive import staged_derived_archive
from insula.staging_lease import staging_lease

class DerivedArchiveStageTests(unittest.TestCase):
    def fixture(self,root,corrupt=False):
        data=b'immutable-derived-archive'
        record={'archive_hdfs_uri':'hdfs://fixture/derived/scene.tar','archive_bytes':len(data),'archive_sha256':hashlib.sha256(data).hexdigest()}
        script=root/'transfer.py';script.write_text("from pathlib import Path\nimport sys\nPath(sys.argv[-1]).write_bytes("+repr(b'x'*len(data) if corrupt else data)+")\n")
        return record,[sys.executable,str(script)]
    def test_verified_lifetime_and_consumer_failure_clean_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,command=self.fixture(root);cache=root/'cache'
            for fail in [False,True]:
                try:
                    with staged_derived_archive(record,cache,working_limit_bytes=10000,transfer_command=command) as (path,evidence):
                        saved=path;self.assertEqual(evidence['sha256'],record['archive_sha256'])
                        if fail:raise RuntimeError('consumer failed')
                except RuntimeError:
                    self.assertTrue(fail)
                self.assertFalse(saved.exists())
    def test_corrupt_archive_refused_and_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,command=self.fixture(root,True);cache=root/'cache'
            with self.assertRaises(ValueError):
                with staged_derived_archive(record,cache,working_limit_bytes=10000,transfer_command=command):pass
            self.assertFalse(list((cache/'scientific-processing/semantic-recovery-staging').glob('stage-*')))
    def test_queue_owner_and_capacity_refuse_transfer(self):
        for busy in [False,True]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);record,command=self.fixture(root);cache=root/'cache';working=cache/'scientific-processing';working.mkdir(parents=True)
                if busy:
                    with staging_lease(working/'cohort-queue.lock'):
                        with self.assertRaises(ValueError):
                            with staged_derived_archive(record,cache,working_limit_bytes=10000,transfer_command=command):pass
                else:
                    with self.assertRaises(ValueError):
                        with staged_derived_archive(record,cache,working_limit_bytes=1,transfer_command=command):pass

    def test_transfer_cannot_write_beyond_declared_archive_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,command=self.fixture(root)
            script=root/'transfer.py'
            script.write_text("from pathlib import Path\nimport sys\nPath(sys.argv[-1]).write_bytes(b'x'*10000)\n")
            cache=root/'cache'
            with self.assertRaises(ValueError):
                with staged_derived_archive(record,cache,working_limit_bytes=10000,transfer_command=command):pass
            self.assertFalse(list((cache/'scientific-processing/semantic-recovery-staging').glob('stage-*')))

if __name__ == '__main__':
    unittest.main()
