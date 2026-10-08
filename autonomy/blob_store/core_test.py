import tempfile
import unittest
from pathlib import Path

from blob_store.core import BlobStore, Corrupt, InMemoryBlobAdapter, Unavailable


class ManualClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class BlobStoreCoreTests(unittest.TestCase):
    def write_file(self, root, name, data):
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_put_readback_mismatch_is_reported_as_corrupt(self):
        class CorruptingReadbackAdapter(InMemoryBlobAdapter):
            def _download_blob(self, key, destination, context):
                super()._download_blob(key, destination, context)
                Path(destination).write_bytes(b"corrupted readback")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.write_file(root, "source.bin", b"trusted bytes")
            store = BlobStore(CorruptingReadbackAdapter())

            with self.assertRaises(Corrupt):
                store.put("runs/readback/run-20261008/output/blob.bin", source)

    def test_unexpected_adapter_errors_are_not_retried_and_chain_the_cause(self):
        class ExplodingAdapter:
            def __init__(self):
                self.calls = 0

            def _blob_exists(self, key, context):
                self.calls += 1
                raise RuntimeError("backend exit code 13: secret stderr")

        clock = ManualClock()
        adapter = ExplodingAdapter()
        store = BlobStore(
            adapter,
            backoff_seconds=(0.1, 0.2),
            clock=clock.time,
            sleep=clock.sleep,
        )

        with self.assertRaises(Unavailable) as caught:
            store.exists("runs/wrapped/run-20261008/output/blob.bin")

        self.assertNotIn("secret stderr", str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(clock.sleeps, [])


if __name__ == "__main__":
    unittest.main()
