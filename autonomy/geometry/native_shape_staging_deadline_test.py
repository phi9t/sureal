import hashlib
import tempfile
import unittest
from pathlib import Path

from blob_store.core import BlobStore, InMemoryBlobAdapter
from geometry.native_shape_transfer import fetch_blob


class StagingDeadlineTests(unittest.TestCase):
    def test_blob_store_deadline_failure_leaves_no_final_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = "datasets/native-shapes/scene-a/source/source.parquet"
            store = BlobStore(
                InMemoryBlobAdapter({key: b"x" * 64}, delay_seconds=1.0),
                deadline_base_seconds=0.0,
                minimum_throughput_bytes_per_second=1024 * 1024,
                max_attempts=1,
                backoff_seconds=(),
            )
            destination = Path(tmp) / "source.parquet"

            with self.assertRaisesRegex(ValueError, "native shape blob fetch failed"):
                fetch_blob(key, destination, hashlib.sha256(b"x" * 64).hexdigest(), blob_store=store)

            self.assertFalse(destination.exists())

    def test_success_admits_exact_bytes(self):
        data = b"native-source-transfer-fixture"
        with tempfile.TemporaryDirectory() as tmp:
            key = "datasets/native-shapes/scene-a/source/source.parquet"
            store = BlobStore(InMemoryBlobAdapter({key: data}), backoff_seconds=())
            destination = Path(tmp) / "source.parquet"

            result = fetch_blob(key, destination, hashlib.sha256(data).hexdigest(), blob_store=store)

            self.assertEqual(destination.read_bytes(), data)
            self.assertEqual(result["blob_key"], key)


if __name__ == "__main__":
    unittest.main()
