import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from blob_store.core import BlobStore, Conflict, InMemoryBlobAdapter
from evidence.source_snapshot import file_sha256

STORE_DESCRIPTOR = {"kind": "in-memory", "project": "unit"}
TOOL_DIGEST = {"waystone-cli": "a" * 64}


def fake_host_admitter(receipt_path, current_package, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / "marker.py"
    marker.write_text("admitted\n")
    return {
        "schema_version": 2,
        "source_snapshot_root": str(destination.parent),
        "source_pins": {"autonomy/marker.py": file_sha256(marker)},
    }, Path(current_package)


class SymlinkAuditPublisherTests(unittest.TestCase):
    def make_audit(self, root):
        working = Path(root) / "scientific-processing"
        payload = working / "motion-current-geometry-audit-v3"
        (payload / "red" / "mutants").mkdir(parents=True)
        (payload / "green").mkdir()
        (payload / "green" / "report.json").write_text('{"ok": true}\n')
        (payload / "red" / "mutants" / "frame.bin").symlink_to("/source/training/frame.bin")
        return working, payload

    def make_store(self):
        return BlobStore(InMemoryBlobAdapter(), backoff_seconds=())

    def make_pinned_store(self):
        class PinnedAdapter(InMemoryBlobAdapter):
            @property
            def tool_sha256(self):
                return {"waystone-cli": "a" * 64}

        return BlobStore(PinnedAdapter(), backoff_seconds=())

    def test_archive_preserves_symlink_members_through_in_memory_blob_store(self):
        from retention.publish_symlink_audit import audit, publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_audit(directory)
            store = self.make_store()
            receipt = publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-motion",
                evidence=Path(directory) / "evidence",
                preserve_symlinks=True,
                readback=True,
                write_receipt=True,
                scientific_processing=working,
                store=store,
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                host_source_admitter=fake_host_admitter,
                identifier="motion-audit-test",
            )

            self.assertEqual(set(receipt), {"schema_version", "store_descriptor", "tool_sha256", "verified_by_readback", "blobs"})
            self.assertEqual(receipt["store_descriptor"], STORE_DESCRIPTOR)
            self.assertEqual(
                receipt["blobs"]["archive"]["key"],
                "runs/perception-motion/motion-audit-test/symlink-audit/audit.tar.gz",
            )
            self.assertEqual(
                receipt["blobs"]["manifest"]["key"],
                "runs/perception-motion/motion-audit-test/symlink-audit/manifest.json",
            )
            audit_result = audit(receipt, store=store)
            self.assertIn(
                {
                    "path": "red/mutants/frame.bin",
                    "kind": "symlink",
                    "link_text": "/source/training/frame.bin",
                },
                audit_result["listing"],
            )
            archive_path = Path(directory) / "audit-readback.tar.gz"
            store.get(
                receipt["blobs"]["archive"]["key"],
                archive_path,
                receipt["blobs"]["archive"]["sha256"],
                expected_bytes=receipt["blobs"]["archive"]["bytes"],
            )
            archive_bytes = archive_path.read_bytes()
            with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
                member = archive.getmember("red/mutants/frame.bin")
                self.assertTrue(member.issym())
                self.assertEqual(member.linkname, "/source/training/frame.bin")
            self.assertNotIn("archive_hdfs_uri", json.dumps(receipt, sort_keys=True))
            self.assertTrue((payload / "red" / "mutants" / "frame.bin").is_symlink())

    def test_requires_tool_digest_when_store_adapter_does_not_provide_one(self):
        from retention.publish_symlink_audit import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_audit(directory)
            with self.assertRaisesRegex(ValueError, "tool digest"):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-motion",
                    evidence=Path(directory) / "evidence",
                    preserve_symlinks=True,
                    readback=True,
                    write_receipt=True,
                    scientific_processing=working,
                    store=self.make_store(),
                    store_descriptor=STORE_DESCRIPTOR,
                    host_source_admitter=fake_host_admitter,
                    identifier="missing-tool-digest",
                )

    def test_publish_does_not_require_legacy_noop_flags(self):
        from retention.publish_symlink_audit import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_audit(directory)
            receipt = publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-motion",
                evidence=Path(directory) / "evidence",
                scientific_processing=working,
                store=self.make_store(),
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                host_source_admitter=fake_host_admitter,
                identifier="motion-audit-noop-flags",
            )

            self.assertTrue(receipt["verified_by_readback"])

    def test_explicit_tool_digest_must_match_adapter_pins(self):
        from retention.publish_symlink_audit import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_audit(directory)
            with self.assertRaisesRegex(ValueError, "tool digest"):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-motion",
                    evidence=Path(directory) / "evidence",
                    preserve_symlinks=True,
                    readback=True,
                    write_receipt=True,
                    scientific_processing=working,
                    store=self.make_pinned_store(),
                    store_descriptor=STORE_DESCRIPTOR,
                    tool_digest={"waystone-cli": "b" * 64},
                    host_source_admitter=fake_host_admitter,
                    identifier="mismatched-tool-digest",
                )

    def test_move_to_renames_same_filesystem_and_verifies_listing_again(self):
        from retention.publish_symlink_audit import audit, publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_audit(directory)
            destination = Path(directory) / "retired-audits" / payload.name
            destination.parent.mkdir()
            store = self.make_store()
            receipt = publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-motion",
                evidence=Path(directory) / "evidence",
                preserve_symlinks=True,
                readback=True,
                write_receipt=True,
                move_to=destination,
                scientific_processing=working,
                store=store,
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                host_source_admitter=fake_host_admitter,
                identifier="motion-audit-move",
            )

            self.assertFalse(payload.exists())
            completed = json.loads((Path(directory) / "evidence" / "blob-publication-motion-audit-move" / "move-completed.json").read_text())
            self.assertEqual(completed["moved_to"], str(destination))
            self.assertEqual(completed["listing"], audit(receipt, store=store)["listing"])
            self.assertEqual((destination / "red" / "mutants" / "frame.bin").readlink(), Path("/source/training/frame.bin"))

    def test_refuses_cross_device_move_without_deleting_source(self):
        from retention.publish_symlink_audit import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_audit(directory)
            destination = Path(directory) / "retired-audits" / payload.name
            destination.parent.mkdir()
            with self.assertRaisesRegex(OSError, "cross-device"):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-motion",
                    evidence=Path(directory) / "evidence",
                    preserve_symlinks=True,
                    readback=True,
                    write_receipt=True,
                    move_to=destination,
                    scientific_processing=working,
                    store=self.make_store(),
                    store_descriptor=STORE_DESCRIPTOR,
                    tool_digest=TOOL_DIGEST,
                    host_source_admitter=fake_host_admitter,
                    identifier="motion-audit-cross-device",
                    same_device=lambda source, target: False,
                )
            self.assertTrue(payload.exists())
            self.assertFalse(destination.exists())

    def test_repeat_publication_with_different_archive_bytes_is_refused_by_blob_store(self):
        from retention.publish_symlink_audit import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_audit(directory)
            store = self.make_store()
            publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-motion",
                evidence=Path(directory) / "evidence-a",
                preserve_symlinks=True,
                readback=True,
                write_receipt=True,
                scientific_processing=working,
                store=store,
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                host_source_admitter=fake_host_admitter,
                identifier="motion-audit-repeat",
            )
            (payload / "green" / "report.json").write_text('{"ok": false}\n')
            with self.assertRaises(Conflict):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-motion",
                    evidence=Path(directory) / "evidence-b",
                    preserve_symlinks=True,
                    readback=True,
                    write_receipt=True,
                    scientific_processing=working,
                    store=store,
                    store_descriptor=STORE_DESCRIPTOR,
                    tool_digest=TOOL_DIGEST,
                    host_source_admitter=fake_host_admitter,
                    identifier="motion-audit-repeat",
                )

    def test_symlink_audit_receipt_refuses_generic_publication_blob_shapes(self):
        from retention.publish_symlink_audit import audit

        for shape, blobs in {
            "chunks": {
                "manifest": {"key": "runs/perception-motion/case/symlink-audit/manifest.json", "sha256": "1" * 64, "bytes": 10},
                "chunks": [{"key": "runs/perception-motion/case/symlink-audit/archive-000.tar.gz", "sha256": "2" * 64, "bytes": 20}],
            },
            "files": {
                "manifest": {"key": "runs/perception-motion/case/symlink-audit/manifest.json", "sha256": "1" * 64, "bytes": 10},
                "files": [{"key": "runs/perception-motion/case/symlink-audit/file.json", "sha256": "2" * 64, "bytes": 20}],
            },
        }.items():
            with self.subTest(shape=shape):
                receipt = {
                    "schema_version": 1,
                    "store_descriptor": STORE_DESCRIPTOR,
                    "tool_sha256": TOOL_DIGEST,
                    "verified_by_readback": True,
                    "blobs": blobs,
                }
                with self.assertRaisesRegex(ValueError, "symlink audit blob records"):
                    audit(receipt, store=self.make_store())


if __name__ == "__main__":
    unittest.main()
