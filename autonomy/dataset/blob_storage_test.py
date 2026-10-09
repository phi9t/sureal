import unittest

from dataset.blob_storage import blob_transfer_check


class BlobStorageTests(unittest.TestCase):
    def test_blob_transfer_check_records_readback_without_fake_exit_code(self):
        check = blob_transfer_check(
            "archive-blob-fetch",
            {
                "key": "datasets/scene-records-v1/scene/scientific/archive.tar",
                "sha256": "a" * 64,
                "bytes": 12,
                "verified_by_readback": True,
            },
        )

        self.assertEqual(check["stage"], "archive-blob-fetch")
        self.assertEqual(check["verified_by_readback"], True)
        self.assertNotIn("exit_code", check)


if __name__ == "__main__":
    unittest.main()
