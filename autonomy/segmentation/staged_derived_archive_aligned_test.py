"""Catch exact-size direct-write failure and unaccounted alignment padding."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from blob_store.core import BlobStore, InMemoryBlobAdapter
from segmentation.staged_derived_archive_aligned import staged_derived_archive
from insula.staging_lease import staging_lease


class AlignedStageTests(unittest.TestCase):
    def fixture(self, *, truncate=True, oversize=False):
        record = {'archive_bytes': 2048,
                  'archive_sha256': hashlib.sha256(b'\0' * 2048).hexdigest(),
                  'archive_blob_key': 'runs/aligned-derived/scene-a/archive/scene.tar'}
        blob = b'\0' * (4096 if not truncate else 2048)
        if oversize:
            blob = b'\0' * 8192
        store = BlobStore(InMemoryBlobAdapter({record['archive_blob_key']: blob}), backoff_seconds=())
        return record, store

    def test_direct_write_then_exact_truncate_is_admitted_and_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); record, store = self.fixture()
            with staged_derived_archive(record, root/'cache', working_limit_bytes=4096,
                                        blob_store=store) as (path, evidence):
                self.assertEqual(path.stat().st_size, 2048)
                self.assertEqual(evidence['file_size_limit_bytes'], 4096)
                self.assertEqual(evidence['transfer_padding_bytes'], 2048)
                self.assertEqual(evidence['working_peak_bound_bytes'], 4096)
                self.assertEqual(evidence['working_peak_bytes_before_consumer'], 2048)
                self.assertEqual(evidence['blob_key'], record['archive_blob_key'])
            self.assertFalse(path.exists())

    def test_padding_capacity_is_reserved_before_transfer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); record, store = self.fixture()
            with self.assertRaises(ValueError):
                with staged_derived_archive(record, root/'cache', working_limit_bytes=4095,
                                            blob_store=store): pass

    def test_untruncated_padding_and_write_beyond_alignment_are_refused(self):
        for truncate, oversize in [(False, False), (True, True)]:
            with self.subTest(truncate=truncate, oversize=oversize), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); record, store = self.fixture(truncate=truncate, oversize=oversize)
                cache = root/'cache'
                with self.assertRaises(ValueError):
                    with staged_derived_archive(record, cache, working_limit_bytes=10000,
                                                blob_store=store): pass
                self.assertFalse(list((cache/'scientific-processing/semantic-recovery-staging').glob('stage-*')))

    def test_queue_owner_prevents_transfer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,store=self.fixture();cache=root/'cache'
            working=cache/'scientific-processing';working.mkdir(parents=True)
            with staging_lease(working/'cohort-queue.lock'):
                with self.assertRaises(ValueError):
                    with staged_derived_archive(record,cache,working_limit_bytes=10000,
                                                blob_store=store):pass

    def test_oversized_blob_refused_before_download(self):
        class CountingAdapter(InMemoryBlobAdapter):
            downloads = 0
            def _download_blob(self, key, destination, context):
                type(self).downloads += 1
                return super()._download_blob(key, destination, context)
        with tempfile.TemporaryDirectory() as tmp:
            record, _ = self.fixture()
            key = record['archive_blob_key']
            store = BlobStore(CountingAdapter({key: b'\0' * 8192}), backoff_seconds=())
            with self.assertRaises(ValueError):
                with staged_derived_archive(record, Path(tmp) / 'cache', working_limit_bytes=1 << 20, blob_store=store):
                    pass
            self.assertEqual(CountingAdapter.downloads, 0)


if __name__ == '__main__': unittest.main()
