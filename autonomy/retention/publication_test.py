import copy
import hashlib
import json
import tempfile
import tarfile
import unittest
from unittest.mock import patch
from pathlib import Path

from blob_store.core import BlobStore, Conflict, Corrupt, InMemoryBlobAdapter, Missing, Unauthenticated
from evidence.journal import append_entry


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
            from retention.publication import (
                audit,
                publish,
                research_journal_spec,
                resource_bundle_spec,
                write_research_journal_receipt,
            )
        except ImportError:
            self.fail(
                "retention publication module must expose publish, audit, "
                "resource_bundle_spec, research_journal_spec and write_research_journal_receipt"
            )
        return publish, audit, resource_bundle_spec, research_journal_spec, write_research_journal_receipt

    def sustained_api(self):
        try:
            from retention.publication import audit, publish, sustained_checkpoint_spec
        except ImportError:
            self.fail("retention publication module must expose sustained_checkpoint_spec")
        return publish, audit, sustained_checkpoint_spec

    def native_and_pilot_api(self):
        try:
            from retention.publication import audit, native_cache_spec, publish, sustained_pilot_spec
        except ImportError:
            self.fail("retention publication module must expose native_cache_spec and sustained_pilot_spec")
        return publish, audit, native_cache_spec, sustained_pilot_spec

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
        _, _, resource_bundle_spec, _, _ = self.api()
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
        publish, audit, _, _, _ = self.api()
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
        publish, _, _, _, _ = self.api()
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
        publish, audit, _, _, _ = self.api()
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
        publish, _, _, _, _ = self.api()
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
        publish, audit, _, _, _ = self.api()
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
        publish, audit, _, _, _ = self.api()
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

    def journal_fixture(self, root):
        research = root / "research"
        research.mkdir()
        (research / "experiment-registry.json").write_text('{"runs":[]}\n')
        (research / "experiments.json").write_text('{"experiments":[]}\n')
        (research / "experiment-tracker.md").write_text("# Experiment tracker\n")
        (research / "research-journal.md").write_text("# Research journal\n")
        append_entry(
            research / "research-journal.jsonl",
            "observation",
            ["journal-fixture"],
            "Journal direct publication fixture.",
            [research / "experiment-registry.json"],
        )
        return research

    def test_research_journal_publishes_direct_files_and_audits_by_readback(self):
        publish, audit, _, research_journal_spec, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            research = self.journal_fixture(root)
            adapter = InMemoryBlobAdapter()
            store = BlobStore(adapter, backoff_seconds=())
            reservations = []
            spec = research_journal_spec(
                research_root=research,
                run_id="journal-run-001",
                store=store,
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                staging_root=root / "stage",
                reserve=lambda path, maximum_new_bytes: reservations.append((Path(path), maximum_new_bytes)),
            )

            self.assertEqual(spec.area, "runs")
            self.assertEqual(spec.child, "perception-research-journal")
            self.assertEqual(spec.kind, "snapshot")
            self.assertEqual(spec.mode, "direct")
            self.assertEqual(spec.staging_style, "copy")
            self.assertFalse(spec.release)

            receipt = publish(spec)
            file_records = receipt["blobs"]["files"]
            expected_names = sorted([
                "experiment-registry.json",
                "experiment-tracker.md",
                "experiments.json",
                "research-journal.jsonl",
                "research-journal.md",
                *("journal-evidence/" + path.name for path in sorted((research / "journal-evidence").iterdir())),
            ])
            self.assertEqual(
                [blob["key"] for blob in file_records],
                ["runs/perception-research-journal/journal-run-001/snapshot/" + name for name in expected_names],
            )
            self.assertEqual(
                receipt["blobs"]["manifest"]["key"],
                "runs/perception-research-journal/journal-run-001/snapshot/manifest.json",
            )
            for blob in [receipt["blobs"]["manifest"], *file_records]:
                self.assertEqual(set(blob), {"key", "sha256", "bytes"})
            rendered = json.dumps(receipt, sort_keys=True)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("hdfs://", rendered)
            self.assertNotIn("command", rendered)
            self.assert_no_receipt_path_strings(receipt)

            result = audit(receipt, store=store)
            self.assertEqual(result["files"], len(expected_names))
            self.assertEqual(result["chunks"], 0)
            self.assertEqual(
                result["payload_bytes"],
                sum((research / name).stat().st_size for name in expected_names),
            )
            self.assertEqual(reservations, [(root / "stage", result["payload_bytes"])])

            manifest_path = root / "manifest-readback.json"
            store.get(
                receipt["blobs"]["manifest"]["key"],
                manifest_path,
                receipt["blobs"]["manifest"]["sha256"],
                expected_bytes=receipt["blobs"]["manifest"]["bytes"],
            )
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["mode"], "direct")
            self.assertEqual(manifest["files"], file_records)
            self.assertEqual(set(manifest["inventory"]), set(expected_names))

            adapter._blobs[file_records[0]["key"]] = b"changed direct file"
            with self.assertRaises(Corrupt):
                audit(receipt, store=store)

    def test_research_journal_receipt_writer_preserves_legacy_record_bytes_before_replace(self):
        _, _, _, _, write_research_journal_receipt = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            active = root / "research-journal-hdfs-verified.json"
            legacy = root / "research-journal-hdfs-legacy-verified.json"
            old_bytes = b'{"all_results_uploaded_and_readback_exact":true}\n'
            receipt = {
                "schema_version": 1,
                "store_descriptor": STORE_DESCRIPTOR,
                "tool_sha256": RECEIPT_TOOL_DIGEST,
                "verified_by_readback": True,
                "blobs": {
                    "manifest": {"key": "runs/perception-research-journal/r/snapshot/manifest.json", "sha256": "1" * 64, "bytes": 2},
                    "files": [{"key": "runs/perception-research-journal/r/snapshot/research-journal.jsonl", "sha256": "2" * 64, "bytes": 3}],
                },
            }
            active.write_bytes(old_bytes)

            write_research_journal_receipt(active, receipt, legacy_path=legacy)

            self.assertEqual(legacy.read_bytes(), old_bytes)
            self.assertEqual(json.loads(active.read_text()), receipt)

    def test_sustained_checkpoint_spec_publishes_under_checkpoints_and_releases_after_audit(self):
        publish, audit, sustained_checkpoint_spec = self.sustained_api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "checkpoint"
            source.mkdir()
            checkpoint = source / "checkpoint.pt"
            report = source / "check.json"
            checkpoint.write_bytes(b"checkpoint bytes")
            report.write_text('{"ok": true}\n')
            inventory = {
                "checkpoint.pt": {
                    "path": str(checkpoint),
                    "sha256": sha(checkpoint),
                    "bytes": checkpoint.stat().st_size,
                },
                "check.json": {
                    "path": str(report),
                    "sha256": sha(report),
                    "bytes": report.stat().st_size,
                },
            }
            store = BlobStore(InMemoryBlobAdapter(), backoff_seconds=())
            reservations = []
            spec = sustained_checkpoint_spec(
                payload=inventory,
                run_id="balanced16-sustained-baseline-run1-step1000",
                kind="checkpoint",
                release=True,
                store=store,
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                staging_root=root / "stage",
                reserve=lambda path, maximum_new_bytes: reservations.append((Path(path), maximum_new_bytes)),
                chunk_size_bytes=1024,
            )

            receipt = publish(spec)

            self.assertTrue(spec.release)
            self.assertEqual(spec.area, "checkpoints")
            self.assertEqual(spec.child, "perception-sustained-checkpoints")
            self.assertEqual(receipt["blobs"]["manifest"]["key"], "checkpoints/perception-sustained-checkpoints/balanced16-sustained-baseline-run1-step1000/checkpoint/manifest.json")
            self.assertFalse(checkpoint.exists())
            self.assertFalse(report.exists())
            self.assert_no_receipt_path_strings(receipt)
            result = audit(receipt, store=store)
            self.assertEqual(result["files"], 2)
            self.assertEqual(reservations, [(root / "stage", sum(item["bytes"] for item in inventory.values()))])

    def test_sustained_checkpoint_audit_failure_releases_nothing(self):
        class CorruptOnAuditSize(InMemoryBlobAdapter):
            def __init__(self):
                super().__init__()
                self._puts = 0
                self._corrupted = False

            def _upload_blob(self, key, source, context):
                super()._upload_blob(key, source, context)
                self._puts += 1

            def _blob_size(self, key, context):
                if self._puts >= 2 and not self._corrupted:
                    self._blobs[key] = b"corrupted after publication readback"
                    self._corrupted = True
                return super()._blob_size(key, context)

        publish, _, sustained_checkpoint_spec = self.sustained_api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "checkpoint"
            source.mkdir()
            checkpoint = source / "checkpoint.pt"
            report = source / "check.json"
            checkpoint.write_bytes(b"checkpoint bytes")
            report.write_text("report\n")
            inventory = {
                "checkpoint.pt": {"path": str(checkpoint), "sha256": sha(checkpoint), "bytes": checkpoint.stat().st_size},
                "check.json": {"path": str(report), "sha256": sha(report), "bytes": report.stat().st_size},
            }
            spec = sustained_checkpoint_spec(
                payload=inventory,
                run_id="run-with-audit-failure",
                kind="checkpoint",
                release=True,
                store=BlobStore(CorruptOnAuditSize(), backoff_seconds=()),
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                staging_root=root / "stage",
                reserve=lambda path, maximum_new_bytes: None,
                chunk_size_bytes=1024,
            )

            with self.assertRaises(Corrupt):
                publish(spec)

            self.assertTrue(checkpoint.exists())
            self.assertTrue(report.exists())

    def test_native_cache_spec_publishes_archived_cache_with_in_memory_store(self):
        publish, audit, native_cache_spec, _ = self.native_and_pilot_api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = root / "cache"
            cache.mkdir()
            tensor = cache / "scene-001.bin"
            receipt = cache / "scene-001-receipt.json"
            tensor.write_bytes(b"native cache bytes")
            receipt.write_text('{"admitted": true}\n')
            inventory = {
                "scene-001.bin": {"path": str(tensor), "sha256": sha(tensor), "bytes": tensor.stat().st_size},
                "scene-001-receipt.json": {
                    "path": str(receipt),
                    "sha256": sha(receipt),
                    "bytes": receipt.stat().st_size,
                },
            }
            store = BlobStore(InMemoryBlobAdapter(), backoff_seconds=())
            reservations = []
            spec = native_cache_spec(
                payload=inventory,
                run_id="overfit-native-cache-v1",
                release=False,
                store=store,
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                staging_root=root / "stage",
                reserve=lambda path, maximum_new_bytes: reservations.append((Path(path), maximum_new_bytes)),
                chunk_size_bytes=1024,
            )

            self.assertEqual(spec.area, "runs")
            self.assertEqual(spec.child, "perception-native-cache")
            self.assertEqual(spec.kind, "cache")
            self.assertEqual(spec.mode, "archive")
            self.assertEqual(spec.staging_style, "copy")

            publication = publish(spec)

            self.assertEqual(
                publication["blobs"]["manifest"]["key"],
                "runs/perception-native-cache/overfit-native-cache-v1/cache/manifest.json",
            )
            self.assertEqual(
                [chunk["key"] for chunk in publication["blobs"]["chunks"]],
                ["runs/perception-native-cache/overfit-native-cache-v1/cache/archive-000.tar.gz"],
            )
            self.assert_no_receipt_path_strings(publication)
            result = audit(publication, store=store)
            self.assertEqual(result["files"], 2)
            self.assertEqual(reservations, [(root / "stage", sum(item["bytes"] for item in inventory.values()))])

    def test_sustained_pilot_spec_publishes_archived_pilot_with_in_memory_store(self):
        publish, audit, _, sustained_pilot_spec = self.native_and_pilot_api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pilot = root / "pilot"
            update = pilot / "update-19"
            heads = update / "heads"
            heads.mkdir(parents=True)
            checkpoint = update / "checkpoint.pt"
            report = update / "check.json"
            head = heads / "heads-00.npz"
            checkpoint.write_bytes(b"checkpoint")
            report.write_text('{"updates": 19}\n')
            head.write_bytes(b"head")
            inventory = {
                "update-19/checkpoint.pt": {
                    "path": str(checkpoint),
                    "sha256": sha(checkpoint),
                    "bytes": checkpoint.stat().st_size,
                },
                "update-19/check.json": {"path": str(report), "sha256": sha(report), "bytes": report.stat().st_size},
                "update-19/heads/heads-00.npz": {
                    "path": str(head),
                    "sha256": sha(head),
                    "bytes": head.stat().st_size,
                },
            }
            store = BlobStore(InMemoryBlobAdapter(), backoff_seconds=())
            spec = sustained_pilot_spec(
                payload=inventory,
                run_id="balanced16-sustained-admission-native20261003a",
                release=False,
                store=store,
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                staging_root=root / "stage",
                reserve=lambda path, maximum_new_bytes: None,
                chunk_size_bytes=1024,
            )

            self.assertEqual(spec.area, "runs")
            self.assertEqual(spec.child, "perception-sustained-pilot")
            self.assertEqual(spec.kind, "pilot")
            self.assertEqual(spec.mode, "archive")
            self.assertEqual(spec.staging_style, "copy")

            publication = publish(spec)

            self.assertEqual(
                publication["blobs"]["manifest"]["key"],
                "runs/perception-sustained-pilot/balanced16-sustained-admission-native20261003a/pilot/manifest.json",
            )
            self.assertEqual(
                [chunk["key"] for chunk in publication["blobs"]["chunks"]],
                [
                    "runs/perception-sustained-pilot/balanced16-sustained-admission-native20261003a/pilot/archive-000.tar.gz"
                ],
            )
            self.assert_no_receipt_path_strings(publication)
            result = audit(publication, store=store)
            self.assertEqual(result["files"], 3)


if __name__ == "__main__":
    unittest.main()
