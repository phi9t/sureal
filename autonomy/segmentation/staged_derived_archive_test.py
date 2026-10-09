import hashlib
import tempfile
import unittest
from pathlib import Path
from blob_store.core import BlobStore, InMemoryBlobAdapter, WaystoneBlobAdapter
from evidence.source_snapshot import file_sha256
from segmentation.staged_derived_archive import staged_derived_archive
from insula.staging_lease import staging_lease

class DerivedArchiveStageTests(unittest.TestCase):
    def fixture(self,corrupt=False,oversize=False):
        data=b'immutable-derived-archive'
        key='runs/derived-archive/scene-a/archive/scene.tar'
        blob=b'x'*10000 if oversize else b'x'*len(data) if corrupt else data
        record={'archive_blob_key':key,'archive_bytes':len(data),'archive_sha256':hashlib.sha256(data).hexdigest()}
        store=BlobStore(InMemoryBlobAdapter({key:blob}),backoff_seconds=())
        return record,store
    def test_verified_lifetime_and_consumer_failure_clean_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,store=self.fixture();cache=root/'cache'
            for fail in [False,True]:
                try:
                    with staged_derived_archive(record,cache,working_limit_bytes=10000,blob_store=store) as (path,evidence):
                        saved=path;self.assertEqual(evidence['sha256'],record['archive_sha256'])
                        self.assertEqual(evidence['blob_key'],record['archive_blob_key'])
                        if fail:raise RuntimeError('consumer failed')
                except RuntimeError:
                    self.assertTrue(fail)
                self.assertFalse(saved.exists())

    def test_legacy_hdfs_uri_resolves_through_descriptor_factory(self):
        data=b'immutable-derived-archive'
        key='runs/derived-archive/scene-a/archive/scene.tar'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache'
            tool=root/'waystone';tool.write_text('not executed')
            resolver=WaystoneBlobAdapter(project='sureal',command_prefix=[str(tool)],
                                         tool_pins={str(tool):file_sha256(tool)})
            resolver._layout={'project':'sureal','storage_root':'hdfs://fixture/root',
                              'project_root':'hdfs://fixture/root/sureal'}
            record={'archive_hdfs_uri':'hdfs://fixture/root/sureal/'+key,
                    'store_descriptor':{'kind':'waystone','project':'sureal'},
                    'archive_bytes':len(data),'archive_sha256':hashlib.sha256(data).hexdigest()}
            store=BlobStore(InMemoryBlobAdapter({key:data}),backoff_seconds=())
            with staged_derived_archive(record,cache,working_limit_bytes=10000,
                                        blob_store=store,blob_adapter=resolver) as (path,evidence):
                self.assertEqual(path.read_bytes(),data)
                self.assertEqual(evidence['blob_key'],key)
                self.assertEqual(evidence['hdfs_uri'],record['archive_hdfs_uri'])

    def test_corrupt_archive_refused_and_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,store=self.fixture(True);cache=root/'cache'
            with self.assertRaises(ValueError):
                with staged_derived_archive(record,cache,working_limit_bytes=10000,blob_store=store):pass
            self.assertFalse(list((cache/'scientific-processing/semantic-recovery-staging').glob('stage-*')))
    def test_queue_owner_and_capacity_refuse_transfer(self):
        for busy in [False,True]:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);record,store=self.fixture();cache=root/'cache';working=cache/'scientific-processing';working.mkdir(parents=True)
                if busy:
                    with staging_lease(working/'cohort-queue.lock'):
                        with self.assertRaises(ValueError):
                            with staged_derived_archive(record,cache,working_limit_bytes=10000,blob_store=store):pass
                else:
                    with self.assertRaises(ValueError):
                        with staged_derived_archive(record,cache,working_limit_bytes=1,blob_store=store):pass

    def test_transfer_cannot_write_beyond_declared_archive_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,store=self.fixture(oversize=True)
            cache=root/'cache'
            with self.assertRaises(ValueError):
                with staged_derived_archive(record,cache,working_limit_bytes=10000,blob_store=store):pass
            self.assertFalse(list((cache/'scientific-processing/semantic-recovery-staging').glob('stage-*')))

    def test_oversized_blob_refused_before_download(self):
        class CountingAdapter(InMemoryBlobAdapter):
            downloads=0
            def _download_blob(self,key,destination,context):
                type(self).downloads+=1
                return super()._download_blob(key,destination,context)
        with tempfile.TemporaryDirectory() as tmp:
            record,_=self.fixture()
            key=record['archive_blob_key']
            store=BlobStore(CountingAdapter({key:b'x'*10000}),backoff_seconds=())
            with self.assertRaises(ValueError):
                with staged_derived_archive(record,Path(tmp)/'cache',working_limit_bytes=10000,blob_store=store):pass
            self.assertEqual(CountingAdapter.downloads,0)

if __name__ == '__main__':
    unittest.main()
