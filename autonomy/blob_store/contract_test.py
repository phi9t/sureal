import contextlib
import hashlib
import inspect
import tempfile
import unittest
from pathlib import Path


class ManualClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class BlobStoreContractTests(unittest.TestCase):
    def api(self):
        try:
            from blob_store.core import (
                BlobStore,
                BlobStoreError,
                Conflict,
                Corrupt,
                InMemoryBlobAdapter,
                LocalFileBlobAdapter,
                Missing,
                Unauthenticated,
                Unavailable,
            )
        except ImportError:
            self.fail("blob_store core module must provide the blob store interface and adapters")
        return {
            "BlobStore": BlobStore,
            "BlobStoreError": BlobStoreError,
            "Conflict": Conflict,
            "Corrupt": Corrupt,
            "InMemoryBlobAdapter": InMemoryBlobAdapter,
            "LocalFileBlobAdapter": LocalFileBlobAdapter,
            "Missing": Missing,
            "Unauthenticated": Unauthenticated,
            "Unavailable": Unavailable,
        }

    @contextlib.contextmanager
    def store_cases(self, api):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            yield [
                ("memory", api["BlobStore"](api["InMemoryBlobAdapter"]())),
                ("local", api["BlobStore"](api["LocalFileBlobAdapter"](root / "store"))),
            ]

    def write_file(self, root, name, data):
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_store_interface_exposes_only_put_get_and_exists_operations(self):
        api = self.api()
        store = api["BlobStore"](api["InMemoryBlobAdapter"]())

        public_callables = {
            name
            for name, member in inspect.getmembers(store)
            if callable(member) and not name.startswith("_")
        }

        self.assertEqual(public_callables, {"put", "get", "exists"})

    def test_put_returns_key_digest_and_size_then_get_roundtrips_blob(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as directory, self.store_cases(api) as stores:
            root = Path(directory)
            source = self.write_file(root, "source.bin", b"alpha blob\n")
            expected_sha = hashlib.sha256(b"alpha blob\n").hexdigest()
            key = "runs/resource-closures/run-20261008/checkpoint/archive-000.tar.gz"

            for name, store in stores:
                with self.subTest(adapter=name):
                    result = store.put(key, source)
                    destination = root / name / "out.bin"
                    store.get(key, destination, expected_sha)

                    self.assertEqual(
                        result,
                        {"key": key, "sha256": expected_sha, "bytes": len(b"alpha blob\n")},
                    )
                    self.assertEqual(destination.read_bytes(), b"alpha blob\n")

    def test_repeated_put_of_identical_bytes_is_a_noop_success(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as directory, self.store_cases(api) as stores:
            root = Path(directory)
            first = self.write_file(root, "first.bin", b"same bytes")
            second = self.write_file(root, "second.bin", b"same bytes")
            key = "artifacts/source-snapshots/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

            for name, store in stores:
                with self.subTest(adapter=name):
                    first_result = store.put(key, first)
                    second_result = store.put(key, second)

                    self.assertEqual(second_result, first_result)

    def test_repeated_put_of_different_bytes_raises_conflict_and_keeps_original_blob(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as directory, self.store_cases(api) as stores:
            root = Path(directory)
            original = self.write_file(root, "original.bin", b"original bytes")
            replacement = self.write_file(root, "replacement.bin", b"replacement bytes")
            original_sha = hashlib.sha256(b"original bytes").hexdigest()
            key = "datasets/scientific-cohort/run-20261008/components/scene.tar"

            for name, store in stores:
                with self.subTest(adapter=name):
                    store.put(key, original)
                    with self.assertRaises(api["Conflict"]):
                        store.put(key, replacement)
                    destination = root / name / "original.bin"
                    store.get(key, destination, original_sha)
                    self.assertEqual(destination.read_bytes(), b"original bytes")

    def test_get_rejects_wrong_digest_as_corrupt_without_publishing_bad_destination(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as directory, self.store_cases(api) as stores:
            root = Path(directory)
            source = self.write_file(root, "source.bin", b"trusted bytes")
            wrong_sha = hashlib.sha256(b"other bytes").hexdigest()
            key = "checkpoints/child/run-20261008/model/checkpoint.pt"

            for name, store in stores:
                with self.subTest(adapter=name):
                    store.put(key, source)
                    destination = root / name / "bad.bin"
                    with self.assertRaises(api["Corrupt"]):
                        store.get(key, destination, wrong_sha)
                    self.assertFalse(destination.exists())

    def test_missing_blob_fetch_raises_missing_and_exists_is_false(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as directory, self.store_cases(api) as stores:
            root = Path(directory)
            key = "runs/missing/run-20261008/output/archive.tar"

            for name, store in stores:
                with self.subTest(adapter=name):
                    self.assertFalse(store.exists(key))
                    with self.assertRaises(api["Missing"]):
                        store.get(key, root / name / "missing.bin", "0" * 64)

    def test_source_and_destination_under_symlinked_caller_directories_succeed(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as directory, self.store_cases(api) as stores:
            root = Path(directory)
            real_caller = root / "real-caller"
            real_caller.mkdir()
            caller = root / "caller-link"
            caller.symlink_to(real_caller, target_is_directory=True)
            source = self.write_file(caller, "source.bin", b"symlinked caller bytes")
            expected_sha = hashlib.sha256(b"symlinked caller bytes").hexdigest()
            key = "runs/symlinked-caller/run-20261008/output/blob.bin"

            for name, store in stores:
                with self.subTest(adapter=name):
                    result = store.put(key, source)
                    destination = caller / name / "dest.bin"
                    store.get(key, destination, expected_sha)

                    self.assertEqual(result["sha256"], expected_sha)
                    self.assertEqual(destination.read_bytes(), b"symlinked caller bytes")

    def test_exists_reports_true_only_after_put(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as directory, self.store_cases(api) as stores:
            root = Path(directory)
            source = self.write_file(root, "source.bin", b"existence")
            key = "runs/existence/run-20261008/output/blob.bin"

            for name, store in stores:
                with self.subTest(adapter=name):
                    self.assertFalse(store.exists(key))
                    store.put(key, source)
                    self.assertTrue(store.exists(key))

    def test_invalid_blob_keys_are_rejected_before_any_adapter_can_escape_the_root(self):
        api = self.api()
        invalid_keys = [
            "",
            "/absolute",
            "runs//double-empty",
            "runs/./dot",
            "runs/../escape",
            "../escape",
            "runs/space key/blob",
            "runs/back\\slash/blob",
            "runs/percent%2f/blob",
        ]
        with tempfile.TemporaryDirectory() as directory, self.store_cases(api) as stores:
            root = Path(directory)
            source = self.write_file(root, "source.bin", b"payload")

            for name, store in stores:
                for key in invalid_keys:
                    with self.subTest(adapter=name, key=key, operation="put"):
                        with self.assertRaises(ValueError):
                            store.put(key, source)
                    with self.subTest(adapter=name, key=key, operation="get"):
                        with self.assertRaises(ValueError):
                            store.get(key, root / name / "out.bin", "0" * 64)
                    with self.subTest(adapter=name, key=key, operation="exists"):
                        with self.assertRaises(ValueError):
                            store.exists(key)

    def test_local_adapter_refuses_symlinked_blob_path_without_writing_outside_root(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store_root = root / "store"
            outside = root / "outside"
            outside.mkdir()
            (store_root / "runs").mkdir(parents=True)
            (store_root / "runs" / "link").symlink_to(outside, target_is_directory=True)
            source = self.write_file(root, "source.bin", b"payload")
            store = api["BlobStore"](api["LocalFileBlobAdapter"](store_root), backoff_seconds=(0.0, 0.0))

            with self.assertRaises(api["Unavailable"]):
                store.put("runs/link/blob.bin", source)

            self.assertFalse((outside / "blob.bin").exists())

    def test_deadline_uses_blob_size_and_retries_timeout_before_unavailable(self):
        api = self.api()
        clock = ManualClock()
        store = api["BlobStore"](
            api["InMemoryBlobAdapter"](delay_seconds=1.5),
            deadline_base_seconds=1.0,
            minimum_throughput_bytes_per_second=4.0,
            backoff_seconds=(0.1, 0.2),
            clock=clock.time,
            sleep=clock.sleep,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.write_file(root, "source.bin", b"1234")
            key = "runs/deadline/run-20261008/output/blob.bin"

            result = store.put(key, source)
            self.assertEqual(result["bytes"], 4)

            slow_clock = ManualClock()
            slow_store = api["BlobStore"](
                api["InMemoryBlobAdapter"](delay_seconds=2.1),
                deadline_base_seconds=1.0,
                minimum_throughput_bytes_per_second=4.0,
                backoff_seconds=(0.1, 0.2),
                clock=slow_clock.time,
                sleep=slow_clock.sleep,
            )
            with self.assertRaises(api["Unavailable"]):
                slow_store.put(key, source)
            self.assertEqual(slow_clock.sleeps.count(2.1), 3)
            self.assertEqual([sleep for sleep in slow_clock.sleeps if sleep != 2.1], [0.1, 0.2])

    def test_transient_failures_retry_then_succeed_and_exhaust_as_unavailable(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.write_file(root, "source.bin", b"retry me")
            key = "runs/retry/run-20261008/output/blob.bin"

            success_clock = ManualClock()
            retrying = api["BlobStore"](
                api["InMemoryBlobAdapter"](transient_failures=2),
                backoff_seconds=(0.1, 0.2),
                clock=success_clock.time,
                sleep=success_clock.sleep,
            )
            retrying.put(key, source)
            self.assertEqual(success_clock.sleeps, [0.1, 0.2])

            failing_clock = ManualClock()
            failing = api["BlobStore"](
                api["InMemoryBlobAdapter"](transient_failures=3),
                backoff_seconds=(0.1, 0.2),
                clock=failing_clock.time,
                sleep=failing_clock.sleep,
            )
            with self.assertRaises(api["Unavailable"]):
                failing.put(key, source)
            self.assertEqual(failing_clock.sleeps, [0.1, 0.2])

    def test_authentication_failure_is_not_retried_and_names_refresh_script(self):
        api = self.api()
        clock = ManualClock()
        store = api["BlobStore"](
            api["InMemoryBlobAdapter"](
                unauthenticated=True,
                authentication_action="run fixture-blob-auth-refresh",
            ),
            backoff_seconds=(0.1, 0.2),
            clock=clock.time,
            sleep=clock.sleep,
        )

        with self.assertRaises(api["Unauthenticated"]) as caught:
            store.exists("runs/auth/run-20261008/output/blob.bin")

        self.assertIn("run fixture-blob-auth-refresh", str(caught.exception))
        self.assertIsNotNone(caught.exception.__cause__)
        self.assertEqual(clock.sleeps, [])

if __name__ == "__main__":
    unittest.main()
