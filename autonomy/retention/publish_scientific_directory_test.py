import json
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


class ScientificDirectoryPublisherTests(unittest.TestCase):
    def make_payload(self, root, case="cohort16-baseline-fit20261002a"):
        working = Path(root) / "scientific-processing"
        payload = working / case
        (payload / "nested").mkdir(parents=True)
        (payload / "nested" / "checkpoint.pt").write_bytes(b"checkpoint")
        (payload / "metrics.json").write_text('{"loss": 1.25}\n')
        return working, payload

    def make_store(self):
        return BlobStore(InMemoryBlobAdapter(), backoff_seconds=())

    def test_publish_uses_publication_module_receipt_and_in_memory_blob_store(self):
        from retention.publication import audit
        from retention.publish_scientific_directory import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            evidence = Path(directory) / "evidence"
            store = self.make_store()
            reservations = []

            receipt = publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-closed-scientific-processing",
                evidence=evidence,
                release=False,
                scientific_processing=working,
                store=store,
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                reserve=lambda path, maximum_new_bytes: reservations.append((Path(path), maximum_new_bytes)),
                host_source_admitter=fake_host_admitter,
                identifier="cohort16-baseline-fit20261002a-run",
                max_bytes=8,
            )

            self.assertEqual(set(receipt), {"schema_version", "store_descriptor", "tool_sha256", "verified_by_readback", "blobs"})
            self.assertEqual(receipt["store_descriptor"], STORE_DESCRIPTOR)
            self.assertEqual(
                receipt["blobs"]["manifest"]["key"],
                "runs/perception-closed-scientific-processing/cohort16-baseline-fit20261002a-run/scientific-directory/manifest.json",
            )
            self.assertEqual(
                [chunk["key"] for chunk in receipt["blobs"]["chunks"]],
                [
                    "runs/perception-closed-scientific-processing/cohort16-baseline-fit20261002a-run/scientific-directory/archive-000.tar.gz",
                    "runs/perception-closed-scientific-processing/cohort16-baseline-fit20261002a-run/scientific-directory/archive-001.tar.gz",
                ],
            )
            self.assertNotIn("archive_hdfs_uri", json.dumps(receipt, sort_keys=True))
            self.assertEqual(audit(receipt, store=store)["files"], 2)
            self.assertEqual(reservations, [(evidence / "blob-publication-cohort16-baseline-fit20261002a-run" / "stage", 25)])

    def test_release_after_blob_store_audit_unlinks_only_planned_files(self):
        from retention.publish_scientific_directory import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            sibling = working / "balanced16-native-v2"
            sibling.mkdir()
            (sibling / "keep.pt").write_bytes(b"protected")
            evidence = Path(directory) / "evidence"
            store = self.make_store()

            receipt = publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-closed-scientific-processing",
                evidence=evidence,
                release=True,
                scientific_processing=working,
                store=store,
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                reserve=lambda path, maximum_new_bytes: None,
                host_source_admitter=fake_host_admitter,
                identifier="cohort16-baseline-fit20261002a-release",
            )

            self.assertTrue(receipt["verified_by_readback"])
            self.assertFalse((payload / "nested" / "checkpoint.pt").exists())
            self.assertFalse((payload / "metrics.json").exists())
            self.assertTrue((sibling / "keep.pt").exists())
            release_receipt = evidence / "blob-publication-cohort16-baseline-fit20261002a-release" / "release-completed.json"
            self.assertEqual(json.loads(release_receipt.read_text())["released_count"], 2)

    def test_without_release_leaves_source_tree(self):
        from retention.publish_scientific_directory import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            receipt = publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-closed-scientific-processing",
                evidence=Path(directory) / "evidence",
                release=False,
                scientific_processing=working,
                store=self.make_store(),
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                reserve=lambda path, maximum_new_bytes: None,
                host_source_admitter=fake_host_admitter,
                identifier="dry-run",
            )

            self.assertTrue(receipt["verified_by_readback"])
            self.assertTrue((payload / "nested" / "checkpoint.pt").exists())
            self.assertFalse((Path(directory) / "evidence" / "blob-publication-dry-run" / "release-completed.json").exists())

    def test_refuses_protected_names(self):
        from retention.publish_scientific_directory import publish

        with tempfile.TemporaryDirectory() as directory:
            for case in [
                "balanced16-native-v2",
                "resource-retention-balanced16-sustained-baseline-controller20261003a-shared-abc",
            ]:
                working, payload = self.make_payload(directory, case=case)
                with self.assertRaisesRegex(ValueError, "protected"):
                    publish(
                        case=case,
                        root=payload,
                        hdfs_namespace="perception-closed-scientific-processing",
                        evidence=Path(directory) / ("evidence-" + case),
                        scientific_processing=working,
                        store=self.make_store(),
                        store_descriptor=STORE_DESCRIPTOR,
                        tool_digest=TOOL_DIGEST,
                        reserve=lambda path, maximum_new_bytes: None,
                        host_source_admitter=fake_host_admitter,
                        identifier=case + "-test",
                    )

    def test_refuses_root_outside_scientific_processing(self):
        from retention.publish_scientific_directory import publish

        with tempfile.TemporaryDirectory() as directory:
            working = Path(directory) / "scientific-processing"
            working.mkdir()
            payload = Path(directory) / "elsewhere" / "cohort16-baseline-fit20261002a"
            payload.mkdir(parents=True)
            (payload / "file.bin").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "direct child"):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-closed-scientific-processing",
                    evidence=Path(directory) / "evidence",
                    scientific_processing=working,
                    store=self.make_store(),
                    store_descriptor=STORE_DESCRIPTOR,
                    tool_digest=TOOL_DIGEST,
                    reserve=lambda path, maximum_new_bytes: None,
                    host_source_admitter=fake_host_admitter,
                    identifier="outside-test",
                )

    def test_repeat_publication_with_different_bytes_is_refused_by_blob_store(self):
        from retention.publish_scientific_directory import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            store = self.make_store()
            publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-closed-scientific-processing",
                evidence=Path(directory) / "evidence-a",
                scientific_processing=working,
                store=store,
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                reserve=lambda path, maximum_new_bytes: None,
                host_source_admitter=fake_host_admitter,
                identifier="repeat-run",
            )
            (payload / "metrics.json").write_text('{"loss": 9.75}\n')
            with self.assertRaises(Conflict):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-closed-scientific-processing",
                    evidence=Path(directory) / "evidence-b",
                    scientific_processing=working,
                    store=store,
                    store_descriptor=STORE_DESCRIPTOR,
                    tool_digest=TOOL_DIGEST,
                    reserve=lambda path, maximum_new_bytes: None,
                    host_source_admitter=fake_host_admitter,
                    identifier="repeat-run",
                )
            self.assertTrue((payload / "nested" / "checkpoint.pt").exists())

    def test_release_plan_escape_is_rejected_before_any_unlink(self):
        from retention.publish_scientific_directory import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            outside = Path(directory) / "outside.bin"
            outside.write_bytes(b"outside")
            inside = payload / "metrics.json"

            def bad_release_plan(root, publication):
                del publication
                return [
                    {
                        "path": "metrics.json",
                        "bytes": inside.stat().st_size,
                        "sha256": file_sha256(inside),
                        "local_path": str(inside),
                        "blob_key": "runs/test/inside/archive.tar.gz",
                    },
                    {
                        "path": "outside.bin",
                        "bytes": outside.stat().st_size,
                        "sha256": file_sha256(outside),
                        "local_path": str(outside),
                        "blob_key": "runs/test/outside/archive.tar.gz",
                    },
                ]

            with self.assertRaisesRegex(ValueError, "escapes"):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-closed-scientific-processing",
                    evidence=Path(directory) / "evidence",
                    release=True,
                    scientific_processing=working,
                    store=self.make_store(),
                    store_descriptor=STORE_DESCRIPTOR,
                    tool_digest=TOOL_DIGEST,
                    reserve=lambda path, maximum_new_bytes: None,
                    host_source_admitter=fake_host_admitter,
                    release_planner=bad_release_plan,
                    identifier="escape-test",
                )
            self.assertTrue(inside.exists())
            self.assertTrue(outside.exists())

    def test_release_uses_blob_store_audit_before_release_plan(self):
        from retention.publish_scientific_directory import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            calls = []

            def release_planner(root, audit_result):
                calls.append((Path(root), audit_result["whole_member_union_exact"], audit_result["files"]))
                return []

            publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-closed-scientific-processing",
                evidence=Path(directory) / "evidence",
                release=True,
                scientific_processing=working,
                store=self.make_store(),
                store_descriptor=STORE_DESCRIPTOR,
                tool_digest=TOOL_DIGEST,
                reserve=lambda path, maximum_new_bytes: None,
                host_source_admitter=fake_host_admitter,
                release_planner=release_planner,
                identifier="audit-before-release-test",
            )

            self.assertEqual(calls, [(payload, True, 2)])


if __name__ == "__main__":
    unittest.main()
