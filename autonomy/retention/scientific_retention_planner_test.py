import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence.source_snapshot import file_sha256
from retention import scientific_retention_planner as planner


class ScientificRetentionPlannerTests(unittest.TestCase):
    def fixture(self, root):
        cache = root / "cache"
        working = cache / "scientific-processing"
        insula = cache / "insula"
        research = root / "research"
        working.mkdir(parents=True)
        insula.mkdir(parents=True)
        research.mkdir()
        return cache, working, insula, research

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True) + "\n")
        return path

    def child(self, working, name, content=b"payload"):
        path = working / name
        path.mkdir()
        (path / "payload.bin").write_bytes(content)
        return path

    def release_receipts(self, insula, child, paths):
        receipt_dir = insula / ("hdfs-retention-" + child.name + "-abc")
        verified = self.write_json(
            receipt_dir / "verified-publication.json",
            {
                "blobs": {
                    "manifest": {
                        "key": "runs/perception-closed-scientific-processing/"
                        + child.name
                        + "/scientific-directory/manifest.json",
                        "sha256": "a" * 64,
                        "bytes": 1,
                    }
                }
            },
        )
        released = []
        for path in paths:
            released.append(
                {
                    "path": path.name,
                    "local_path": str(path),
                    "sha256": file_sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
        self.write_json(
            receipt_dir / "release-completed.json",
            {
                "publication_receipt_sha256": file_sha256(verified),
                "released": released,
            },
        )
        return receipt_dir

    def test_plan_classifies_every_scientific_processing_child_class(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, working, insula, research = self.fixture(root)
            protected = self.child(working, "balanced16-native-v2")
            live = self.child(working, "live-state")
            released = self.child(working, "released-run")
            published = self.child(working, "published-run")
            unpublished = self.child(working, "unpublished-run")
            log = working / "stray.log"
            log.write_text("debug\n")
            self.write_json(insula / "controller" / "state.json", {"output": str(live / "payload.bin")})
            self.release_receipts(insula, released, [released / "payload.bin"])
            self.write_json(
                insula / "hdfs-retention-published-run-xyz" / "verified-publication.json",
                {
                    "blobs": {
                        "manifest": {
                            "key": "runs/perception-closed-scientific-processing/published-run/scientific-directory/manifest.json",
                            "sha256": "b" * 64,
                            "bytes": 1,
                        }
                    }
                },
            )

            plans = {
                child.name: child
                for child in planner.plan(
                    scientific_processing=working,
                    cache_root=cache,
                    receipt_roots=(insula, research),
                )
            }

            self.assertEqual(plans[protected.name].classification, planner.CLASS_PROTECTED)
            self.assertEqual(plans[live.name].classification, planner.CLASS_LIVE_REFERENCED)
            self.assertEqual(plans[released.name].classification, planner.CLASS_RELEASED_LEFTOVERS)
            self.assertEqual(plans[published.name].classification, planner.CLASS_PUBLISHED_UNRELEASED)
            self.assertEqual(plans[unpublished.name].classification, planner.CLASS_UNPUBLISHED)
            self.assertEqual(plans[log.name].classification, planner.CLASS_STRAY_LOG)
            self.assertIn("retention.publish_scientific_directory", plans[published.name].release_command)
            self.assertIn("--release", plans[published.name].release_command)

    def test_reference_forms_keep_children(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, working, insula, research = self.fixture(root)
            state = self.child(working, "state-child")
            admission = self.child(working, "admission-child")
            receipt = self.child(working, "receipt-child")
            self.write_json(insula / "run" / "state.json", {"path": str(state)})
            self.write_json(research / "case-admitted.json", {"output_directory": str(admission)})
            self.write_json(research / "other-receipt.json", {"artifact": str(receipt / "payload.bin")})

            plans = {
                child.name: child
                for child in planner.plan(
                    scientific_processing=working,
                    cache_root=cache,
                    receipt_roots=(insula, research),
                )
            }

            self.assertEqual(plans[state.name].classification, planner.CLASS_LIVE_REFERENCED)
            self.assertEqual(plans[state.name].reason, "state reference")
            self.assertEqual(plans[admission.name].classification, planner.CLASS_LIVE_REFERENCED)
            self.assertEqual(plans[admission.name].reason, "admission reference")
            self.assertEqual(plans[receipt.name].classification, planner.CLASS_LIVE_REFERENCED)
            self.assertEqual(plans[receipt.name].reason, "receipt reference")

    def test_default_dry_run_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, working, insula, research = self.fixture(root)
            log = working / "stray.log"
            log.write_text("debug\n")

            with patch.object(
                planner,
                "default_receipt_roots",
                return_value=(insula, research),
            ):
                result = planner.main(["--cache-root", str(cache), "--top", "1"])

            self.assertEqual(result, 0)
            self.assertTrue(log.exists())

    def test_apply_deletes_only_stray_logs_and_digest_verified_released_leftovers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, working, insula, research = self.fixture(root)
            released = self.child(working, "released-run")
            leftover = released / "payload.bin"
            keep = self.child(working, "unpublished-run") / "payload.bin"
            log = working / "stray.log"
            log.write_text("debug\n")
            self.release_receipts(insula, released, [leftover])
            plans = planner.plan(scientific_processing=working, cache_root=cache, receipt_roots=(insula, research))

            receipt = planner.apply_plan(
                plans,
                scientific_processing=working,
                cache_root=cache,
                receipt_roots=(insula, research),
                receipt_dir=insula / "retention-planner-receipts",
                lock_path=insula / "architecture-experiments.lock",
            )

            self.assertFalse(log.exists())
            self.assertFalse(leftover.exists())
            self.assertTrue(keep.exists())
            self.assertTrue(receipt.exists())
            self.assertFalse(str(receipt).startswith(str(working)))

    def test_apply_refuses_protected_or_referenced_children_even_with_bad_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, working, insula, research = self.fixture(root)
            protected = self.child(working, "balanced16-native-v2")
            referenced = self.child(working, "referenced-run")
            self.write_json(research / "referenced-admitted.json", {"path": str(referenced / "payload.bin")})
            protected_plan = planner.ChildPlan(
                name=protected.name,
                path=protected / "payload.bin",
                classification=planner.CLASS_STRAY_LOG,
                reason="bad plan",
                evidence="test",
                bytes=7,
                reclaimable_bytes=7,
                projected_total_bytes=0,
            )
            referenced_plan = planner.ChildPlan(
                name=referenced.name,
                path=referenced / "payload.bin",
                classification=planner.CLASS_STRAY_LOG,
                reason="bad plan",
                evidence="test",
                bytes=7,
                reclaimable_bytes=7,
                projected_total_bytes=0,
            )

            with self.assertRaisesRegex(ValueError, "protected"):
                planner.apply_plan(
                    [protected_plan],
                    scientific_processing=working,
                    cache_root=cache,
                    receipt_roots=(insula, research),
                    receipt_dir=insula / "receipts-a",
                    lock_path=insula / "architecture-experiments.lock",
                )
            with self.assertRaisesRegex(ValueError, "referenced"):
                planner.apply_plan(
                    [referenced_plan],
                    scientific_processing=working,
                    cache_root=cache,
                    receipt_roots=(insula, research),
                    receipt_dir=insula / "receipts-b",
                    lock_path=insula / "architecture-experiments.lock",
                )
            self.assertTrue((protected / "payload.bin").exists())
            self.assertTrue((referenced / "payload.bin").exists())

    def test_apply_refuses_paths_outside_scientific_processing_or_under_evidence_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, working, insula, research = self.fixture(root)
            outside = root / "outside.log"
            outside.write_text("outside\n")
            bad = planner.ChildPlan(
                name="outside",
                path=outside,
                classification=planner.CLASS_STRAY_LOG,
                reason="bad plan",
                evidence="test",
                bytes=outside.stat().st_size,
                reclaimable_bytes=outside.stat().st_size,
                projected_total_bytes=0,
            )

            with self.assertRaisesRegex(ValueError, "outside scientific-processing"):
                planner.apply_plan(
                    [bad],
                    scientific_processing=working,
                    cache_root=cache,
                    receipt_roots=(insula, research),
                    receipt_dir=insula / "receipts",
                    lock_path=insula / "architecture-experiments.lock",
                )
            self.assertTrue(outside.exists())

    def test_digest_mismatch_blocks_released_leftover_apply(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, working, insula, research = self.fixture(root)
            released = self.child(working, "released-run")
            leftover = released / "payload.bin"
            self.release_receipts(insula, released, [leftover])
            leftover.write_bytes(b"changed")
            plans = planner.plan(scientific_processing=working, cache_root=cache, receipt_roots=(insula, research))

            with self.assertRaisesRegex(ValueError, "digest differs"):
                planner.apply_plan(
                    plans,
                    scientific_processing=working,
                    cache_root=cache,
                    receipt_roots=(insula, research),
                    receipt_dir=insula / "receipts",
                    lock_path=insula / "architecture-experiments.lock",
                )
            self.assertTrue(leftover.exists())


if __name__ == "__main__":
    unittest.main()
