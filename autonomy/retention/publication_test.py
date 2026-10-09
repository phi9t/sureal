import copy
import hashlib
import json
import tempfile
import tarfile
import unittest
from unittest.mock import patch
from pathlib import Path

from blob_store.core import BlobStore, Conflict, Corrupt, InMemoryBlobAdapter, Missing, Unauthenticated


TOOL_DIGEST = {
    "/opt/waystone/scripts/waystone": "a" * 64,
    "/opt/waystone/rust/target/debug/waystone": "b" * 64,
    "/opt/waystone/native/libhdfs_client/dist/lib/libhdfs_client.so": "c" * 64,
    "/opt/waystone/native/libhdfs_client/dist/bin/hdfs.bin": "d" * 64,
}
RECEIPT_TOOL_DIGEST = {
    "waystone-cli": "a" * 64,
    "waystone-binary": "b" * 64,
    "libhdfs-client": "c" * 64,
    "hdfs-bin": "d" * 64,
}
STORE_DESCRIPTOR = {
    "kind": "in-memory",
    "project": "unit",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PublicationModuleTests(unittest.TestCase):
    def api(self):
        try:
            from retention.publication import audit, publish, resource_bundle_spec
        except ImportError:
            self.fail("retention publication module must expose publish, audit and resource_bundle_spec")
        return publish, audit, resource_bundle_spec

    def assert_no_receipt_path_strings(self, value, *, blob_key=False):
        if isinstance(value, dict):
            for key, child in value.items():
                self.assertNotIn("/", str(key))
                self.assertNotIn("\\", str(key))
                self.assert_no_receipt_path_strings(child, blob_key=(key == "key"))
        elif isinstance(value, list):
            for child in value:
                self.assert_no_receipt_path_strings(child, blob_key=blob_key)
        elif isinstance(value, str) and not blob_key:
            self.assertNotIn("/", value)
            self.assertNotIn("\\", value)

    def fixture(self, root, *, run_id="run-007", chunk_size_bytes=8):
        files = root / "files"
        files.mkdir()
        alpha = files / "alpha.txt"
        beta = files / "nested" / "beta.txt"
        beta.parent.mkdir()
        alpha.write_bytes(b"alpha")
        beta.write_bytes(b"beta-beta")
        inventory = {
            "alpha.txt": {"path": str(alpha), "sha256": sha(alpha), "bytes": alpha.stat().st_size},
            "nested/beta.txt": {"path": str(beta), "sha256": sha(beta), "bytes": beta.stat().st_size},
        }
        adapter = InMemoryBlobAdapter()
        store = BlobStore(adapter, backoff_seconds=())
        reservations = []
        _, _, resource_bundle_spec = self.api()
        spec = resource_bundle_spec(
            payload=inventory,
            run_id=run_id,
            kind="checkpoint",
            store=store,
            store_descriptor=STORE_DESCRIPTOR,
            tool_digest=TOOL_DIGEST,
            staging_root=root / "stage",
            reserve=lambda path, maximum_new_bytes: reservations.append((Path(path), maximum_new_bytes)),
            chunk_size_bytes=chunk_size_bytes,
        )
        return spec, store, adapter, inventory, reservations

    def test_resource_bundle_publishes_manifest_and_chunks_with_small_receipt(self):
        publish, audit, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, store, _, inventory, reservations = self.fixture(root)
            receipt = publish(spec)

            self.assertEqual(receipt["schema_version"], 1)
            self.assertEqual(receipt["store_descriptor"], STORE_DESCRIPTOR)
            self.assertEqual(receipt["tool_sha256"], RECEIPT_TOOL_DIGEST)
            self.assertIs(receipt["verified_by_readback"], True)
            self.assertEqual(
                [chunk["key"] for chunk in receipt["blobs"]["chunks"]],
                [
                    "runs/perception-resource-closures/run-007/checkpoint/archive-000.tar.gz",
                    "runs/perception-resource-closures/run-007/checkpoint/archive-001.tar.gz",
                ],
            )
            self.assertEqual(
                receipt["blobs"]["manifest"]["key"],
                "runs/perception-resource-closures/run-007/checkpoint/manifest.json",
            )
            for blob in [receipt["blobs"]["manifest"], *receipt["blobs"]["chunks"]]:
                self.assertEqual(set(blob), {"key", "sha256", "bytes"})
            rendered = json.dumps(receipt, sort_keys=True)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("command", rendered)
            self.assertNotIn("log_path", rendered)
            self.assert_no_receipt_path_strings(receipt)

            result = audit(receipt, store=store)
            self.assertEqual(result["files"], 2)
            self.assertEqual(result["chunks"], 2)
            self.assertEqual(result["payload_bytes"], sum(item["bytes"] for item in inventory.values()))
            self.assertEqual(reservations, [(root / "stage", sum(item["bytes"] for item in inventory.values()))])

            manifest_path = root / "manifest-readback.json"
            store.get(
                receipt["blobs"]["manifest"]["key"],
                manifest_path,
                receipt["blobs"]["manifest"]["sha256"],
            )
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["chunks"], receipt["blobs"]["chunks"])
            self.assertEqual(
                manifest["inventory"],
                {name: {"sha256": item["sha256"], "bytes": item["bytes"]} for name, item in inventory.items()},
            )

    def test_publish_streams_staged_members_without_reading_each_file_whole(self):
        publish, _, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, _, _, _, _ = self.fixture(root, chunk_size_bytes=1024)
            original = Path.read_bytes

            def guarded_read_bytes(path):
                if path.name in {"alpha.txt", "beta.txt"}:
                    raise AssertionError("archive members must be streamed from open files")
                return original(path)

            with patch.object(Path, "read_bytes", guarded_read_bytes):
                publish(spec)

    def test_audit_hashes_archive_members_with_bounded_reads(self):
        publish, audit, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, store, _, _, _ = self.fixture(root, chunk_size_bytes=1024)
            receipt = publish(spec)
            original = tarfile.ExFileObject.read

            def guarded_read(stream, size=-1):
                if size is None or size < 0:
                    raise AssertionError("archive member audit must read fixed-size blocks")
                return original(stream, size)

            with patch.object(tarfile.ExFileObject, "read", guarded_read):
                audit(receipt, store=store)

    def test_repeat_publication_with_same_key_and_different_bytes_is_refused(self):
        publish, _, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, _, _, inventory, _ = self.fixture(root, chunk_size_bytes=1024)
            publish(spec)
            source = Path(inventory["alpha.txt"]["path"])
            source.write_bytes(b"changed alpha")
            changed = copy.deepcopy(inventory)
            changed["alpha.txt"] = {
                "path": str(source),
                "sha256": sha(source),
                "bytes": source.stat().st_size,
            }
            changed_spec = spec.with_payload(changed)

            with self.assertRaises(Conflict):
                publish(changed_spec)

    def test_audit_rejects_tampered_key_digest_size_and_missing_chunk(self):
        publish, audit, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, store, adapter, _, _ = self.fixture(root)
            receipt = publish(spec)

            for fault in ["key", "digest", "size"]:
                bad = copy.deepcopy(receipt)
                if fault == "key":
                    bad["blobs"]["chunks"][0]["key"] = "runs/perception-resource-closures/run-007/checkpoint/archive-999.tar.gz"
                elif fault == "digest":
                    bad["blobs"]["chunks"][0]["sha256"] = "0" * 64
                else:
                    bad["blobs"]["chunks"][0]["bytes"] += 1
                with self.subTest(fault=fault), self.assertRaises(ValueError):
                    audit(bad, store=store)

            adapter._blobs[receipt["blobs"]["chunks"][0]["key"]] = b"changed archive bytes"
            with self.assertRaises(Corrupt):
                audit(receipt, store=store)

            missing = copy.deepcopy(receipt)
            adapter._blobs.pop(receipt["blobs"]["chunks"][0]["key"])
            with self.assertRaises(Missing):
                audit(missing, store=store)

    def test_audit_propagates_blob_store_typed_failures(self):
        publish, audit, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec, _, _, _, _ = self.fixture(root)
            receipt = publish(spec)
            unauthenticated = BlobStore(
                InMemoryBlobAdapter(unauthenticated=True, authentication_action="run refresh"),
                backoff_seconds=(),
            )

            with self.assertRaises(Unauthenticated):
                audit(receipt, store=unauthenticated)

    def test_resource_bundle_spec_declares_hardlink_archive_without_release(self):
        with tempfile.TemporaryDirectory() as temp:
            spec, _, _, _, _ = self.fixture(Path(temp))
            self.assertEqual(spec.area, "runs")
            self.assertEqual(spec.child, "perception-resource-closures")
            self.assertEqual(spec.staging_style, "hardlink")
            self.assertEqual(spec.mode, "archive")
            self.assertFalse(spec.release)


if __name__ == "__main__":
    unittest.main()
