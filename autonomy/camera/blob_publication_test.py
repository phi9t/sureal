import tempfile
import unittest
from pathlib import Path

from blob_store.core import BlobStore, InMemoryBlobAdapter
from camera.blob_publication import camera_blob_key, put_and_fetch_blob


class CameraBlobPublicationTests(unittest.TestCase):
    def test_put_and_fetch_blob_uses_store_interface_and_returns_blob_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "camera.tar"
            destination = root / "readback.tar"
            source.write_bytes(b"camera archive")
            store = BlobStore(InMemoryBlobAdapter(), backoff_seconds=())
            key = camera_blob_key("scene-a", "archive", "camera.tar")

            result = put_and_fetch_blob(store, key, source, destination)

            self.assertEqual(result["key"], "runs/scientific-camera/scene-a/archive/camera.tar")
            self.assertEqual(result["bytes"], len(b"camera archive"))
            self.assertTrue(result["verified_by_readback"])
            self.assertEqual(destination.read_bytes(), b"camera archive")


if __name__ == "__main__":
    unittest.main()
