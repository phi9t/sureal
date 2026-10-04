"""Catch exact-size direct-write failure and unaccounted alignment padding."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from pipeline.staged_derived_archive_aligned import staged_derived_archive
from pipeline.staging_lease import staging_lease


class AlignedStageTests(unittest.TestCase):
    def fixture(self, root, *, truncate=True, oversize=False):
        record = {'archive_bytes': 2048,
                  'archive_sha256': hashlib.sha256(b'\0' * 2048).hexdigest(),
                  'archive_hdfs_uri': 'hdfs://fixture/scene.tar'}
        script = root / 'transfer.py'
        script.write_text('import mmap,os,sys\n'
                          'fd=os.open(sys.argv[-1],os.O_WRONLY|os.O_CREAT|os.O_DIRECT,0o600)\n'
                          'buffer=mmap.mmap(-1,4096)\n'
                          'assert os.write(fd,buffer)==4096\n'
                          + ('os.write(fd,buffer)\n' if oversize else '')
                          + ('os.ftruncate(fd,2048)\n' if truncate else '')
                          + 'os.close(fd)\n')
        return record, [sys.executable, str(script)]

    def test_direct_write_then_exact_truncate_is_admitted_and_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); record, command = self.fixture(root)
            with staged_derived_archive(record, root/'cache', working_limit_bytes=4096,
                                        transfer_command=command) as (path, evidence):
                self.assertEqual(path.stat().st_size, 2048)
                self.assertEqual(evidence['file_size_limit_bytes'], 4096)
                self.assertEqual(evidence['transfer_padding_bytes'], 2048)
                self.assertEqual(evidence['working_peak_bound_bytes'], 4096)
                self.assertEqual(evidence['working_peak_bytes_before_consumer'], 2048)
            self.assertFalse(path.exists())

    def test_padding_capacity_is_reserved_before_transfer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); record, command = self.fixture(root)
            marker = root/'started'
            (root/'transfer.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n')
            with self.assertRaises(ValueError):
                with staged_derived_archive(record, root/'cache', working_limit_bytes=4095,
                                            transfer_command=command): pass
            self.assertFalse(marker.exists())

    def test_untruncated_padding_and_write_beyond_alignment_are_refused(self):
        for truncate, oversize in [(False, False), (True, True)]:
            with self.subTest(truncate=truncate, oversize=oversize), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); record, command = self.fixture(root, truncate=truncate, oversize=oversize)
                cache = root/'cache'
                with self.assertRaises(ValueError):
                    with staged_derived_archive(record, cache, working_limit_bytes=10000,
                                                transfer_command=command): pass
                self.assertFalse(list((cache/'scientific-processing/semantic-recovery-staging').glob('stage-*')))

    def test_queue_owner_prevents_transfer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,command=self.fixture(root);cache=root/'cache'
            working=cache/'scientific-processing';working.mkdir(parents=True)
            with staging_lease(working/'cohort-queue.lock'):
                with self.assertRaises(ValueError):
                    with staged_derived_archive(record,cache,working_limit_bytes=10000,
                                                transfer_command=command):pass

if __name__ == '__main__': unittest.main()
