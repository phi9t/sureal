import hashlib
import tempfile
import unittest
from pathlib import Path

from blob_store.core import BlobStore, InMemoryBlobAdapter, Unauthenticated, WaystoneBlobAdapter
from evidence.source_snapshot import file_sha256
from geometry.native_shape_transfer import fetch_blob


class TransferTests(unittest.TestCase):
    def test_fetches_blob_key_through_blob_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = b"native shape source"
            key = "datasets/native-shapes/scene-a/source/source.parquet"
            store = BlobStore(InMemoryBlobAdapter({key: data}), backoff_seconds=())
            dest = Path(tmp) / "source.parquet"
            result = fetch_blob(key, dest, hashlib.sha256(data).hexdigest(), blob_store=store)
            self.assertEqual(dest.read_bytes(), data)
            self.assertEqual(result["blob_key"], key)

    def test_expected_byte_count_is_passed_to_blob_store(self):
        class RecordingStore:
            def __init__(self, data):
                self.data = data
                self.calls = []

            def get(self, key, destination, sha256, *, expected_bytes=None):
                self.calls.append((key, sha256, expected_bytes))
                Path(destination).write_bytes(self.data)

        with tempfile.TemporaryDirectory() as tmp:
            data = b"native shape source"
            key = "datasets/native-shapes/scene-a/source/source.parquet"
            expected = hashlib.sha256(data).hexdigest()
            store = RecordingStore(data)
            dest = Path(tmp) / "source.parquet"
            result = fetch_blob(key, dest, expected, expected_bytes=len(data), blob_store=store)
            self.assertEqual(result["bytes"], len(data))
            self.assertEqual(store.calls, [(key, expected, len(data))])

    def test_legacy_hdfs_uri_is_resolved_before_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = b"legacy native shape source"
            key = "datasets/native-shapes/scene-a/source/source.parquet"
            store = BlobStore(InMemoryBlobAdapter({key: data}), backoff_seconds=())
            tool = root / "waystone"
            tool.write_text("not executed")
            resolver = WaystoneBlobAdapter(
                project="sureal",
                command_prefix=[str(tool)],
                tool_pins={str(tool): file_sha256(tool)},
            )
            resolver._layout = {
                "project": "sureal",
                "storage_root": "hdfs://fixture/root",
                "project_root": "hdfs://fixture/root/sureal",
            }
            dest = root / "source.parquet"
            result = fetch_blob(
                "hdfs://fixture/root/sureal/" + key,
                dest,
                hashlib.sha256(data).hexdigest(),
                blob_store=store,
                blob_adapter=resolver,
            )
            self.assertEqual(dest.read_bytes(), data)
            self.assertEqual(result["blob_key"], key)

    def test_digest_mismatch_is_refused_without_final_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = "datasets/native-shapes/scene-a/source/source.parquet"
            store = BlobStore(InMemoryBlobAdapter({key: b"other"}), backoff_seconds=())
            dest = Path(tmp) / "source.parquet"
            with self.assertRaises(ValueError):
                fetch_blob(key, dest, "0" * 64, blob_store=store)
            self.assertFalse(dest.exists())

    def test_blob_store_typed_authentication_error_propagates(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = "datasets/native-shapes/scene-a/source/source.parquet"
            store = BlobStore(InMemoryBlobAdapter({key: b"x"}, unauthenticated=True), backoff_seconds=())
            with self.assertRaises(Unauthenticated):
                fetch_blob(key, Path(tmp) / "source.parquet", hashlib.sha256(b"x").hexdigest(), blob_store=store)


if __name__ == "__main__":
    unittest.main()
