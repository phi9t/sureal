import base64,hashlib,json
from pathlib import Path
import tempfile,unittest
from blob_store.core import BlobStore, InMemoryBlobAdapter
from dataset.staged_source import staged_source

class CountingInMemoryBlobAdapter(InMemoryBlobAdapter):
    def __init__(self, blobs):
        super().__init__(blobs)
        self.downloads = 0

    def _download_blob(self, key, destination, context):
        self.downloads += 1
        return super()._download_blob(key, destination, context)

class StagedSourceTests(unittest.TestCase):
    def fixture(self,root,*,stored=None):
        data=b'sensor-source-fixture'
        digest=hashlib.sha256(data).hexdigest()
        key='datasets/waymo-perception-v2.0.1/scene/raw-training-lidar/source.parquet'
        stored_data=data if stored is None else stored
        source=root/'stored.parquet';source.write_bytes(stored_data)
        blob={'key':key,'sha256':digest,'bytes':len(data),'verified_by_readback':True}
        record={'sha256':digest,'blob':blob,'source_metadata':{'size':str(len(data)),'md5_hash':base64.b64encode(hashlib.md5(data).digest()).decode()}}
        store=BlobStore(InMemoryBlobAdapter({key:stored_data}))
        return record,store,key

    def test_verified_source_lifetime_and_cleanup_after_consumer_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,store,_=self.fixture(root);cache=root/'cache'
            with staged_source(record,cache,retained_bytes=1000,limit_bytes=10000,blob_store=store) as (path,evidence):
                self.assertEqual(path.read_bytes(),b'sensor-source-fixture');self.assertEqual(evidence['sha256'],record['sha256']);saved=path
            self.assertFalse(saved.exists())
            with self.assertRaises(RuntimeError):
                with staged_source(record,cache,retained_bytes=1000,limit_bytes=10000,blob_store=store) as (path,evidence):
                    saved=path;raise RuntimeError('consumer failed')
            self.assertFalse(saved.exists())

    def test_fetches_source_with_in_memory_blob_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,store,key=self.fixture(root);cache=root/'cache'
            with staged_source(record,cache,retained_bytes=1000,limit_bytes=10000,blob_store=store) as (path,evidence):
                self.assertEqual(path.read_bytes(),b'sensor-source-fixture')
                self.assertEqual(evidence['blob']['key'],key)
                self.assertNotIn('transfer_command',evidence)
            self.assertFalse(path.exists())

    def test_bad_blob_cleanup(self):
        for payload in (b'wrong',b'x'*10000):
            with self.subTest(size=len(payload)),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);record,store,_=self.fixture(root,stored=payload);cache=root/'cache'
                with self.assertRaises(ValueError):
                    with staged_source(record,cache,retained_bytes=1000,limit_bytes=10000,blob_store=store):pass
                self.assertFalse(list((cache/'scientific-processing-staging').glob('stage-*')))

    def test_oversized_blob_is_rejected_before_staging_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record,_,key=self.fixture(root);cache=root/'cache'
            adapter=CountingInMemoryBlobAdapter({key:b'sensor-source-fixture with trailing bytes'})
            store=BlobStore(adapter)

            with self.assertRaises(ValueError):
                with staged_source(record,cache,retained_bytes=1000,limit_bytes=10000,blob_store=store):pass

            self.assertEqual(adapter.downloads,0)
            processing=cache/'scientific-processing-staging'
            self.assertFalse([path for path in processing.rglob('*') if path.is_file()])

    def test_capacity_and_orphan_staging_rejected_before_transfer(self):
        for orphan in (False,True):
            with self.subTest(orphan=orphan),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);record,store,_=self.fixture(root);cache=root/'cache'
                if orphan:
                    old=cache/'scientific-source-audit/stage-orphan/input';old.mkdir(parents=True);(old/'source.parquet').write_bytes(b'preserve')
                with self.assertRaises(ValueError):
                    with staged_source(record,cache,retained_bytes=1000,limit_bytes=10000 if orphan else 1001,blob_store=store):pass
                if orphan:self.assertEqual((old/'source.parquet').read_bytes(),b'preserve')

if __name__=='__main__':unittest.main()
