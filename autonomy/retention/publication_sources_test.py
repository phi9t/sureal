import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import LocalSnapshotStore, copy_source_snapshot, file_sha256
from retention.publication_sources import (
    CHECKPOINT_REQUIRED,
    CHECKPOINT_TARGET,
    HISTORICAL_CHECKPOINT_REQUIRED,
    HISTORICAL_NATIVE_CACHE_REQUIRED,
    HISTORICAL_PILOT_REQUIRED,
    NATIVE_CACHE_REQUIRED,
    NATIVE_CACHE_TARGET,
    PILOT_REQUIRED,
    PILOT_TARGET,
    freeze_checkpoint_sources,
    freeze_native_cache_sources,
    freeze_pilot_sources,
    validate_checkpoint_sources,
    validate_native_cache_sources,
    validate_pilot_sources,
)


def _write_files(root, names):
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)


def _query_runner(names):
    def run(command, **kwargs):
        assert "query" in command
        class Result:
            pass

        result = Result()
        result.returncode = 0
        result.stdout = "".join("//" + name.rsplit("/", 1)[0] + ":" + name.rsplit("/", 1)[1] + "\n" for name in sorted(names))
        result.stderr = ""
        return result

    return run


class PublicationSourceSnapshotTests(unittest.TestCase):
    def assert_freezes_active_target(self, required, target, freezer, validator):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            repo = base / "repo"
            root = repo / "autonomy"
            _write_files(root, required)
            names = ["autonomy/" + name for name in required]

            receipt = freezer(
                root,
                base / "frozen",
                store=LocalSnapshotStore(base / "store"),
                repo_root=repo,
                bazel=repo / "bazelw",
                runner=_query_runner(names),
            )

            self.assertEqual(receipt["schema_version"], 2)
            self.assertEqual(receipt["source_snapshot_target"], target)
            self.assertEqual(set(receipt["source_pins"]), set(names))
            shutil.rmtree(receipt["source_snapshot_root"])
            verified = validator(root, receipt)
            self.assertEqual(verified["source_files"], len(required))

    def test_current_publication_entrypoints_freeze_target_source_snapshots(self):
        self.assert_freezes_active_target(
            CHECKPOINT_REQUIRED,
            CHECKPOINT_TARGET,
            freeze_checkpoint_sources,
            validate_checkpoint_sources,
        )
        self.assert_freezes_active_target(
            NATIVE_CACHE_REQUIRED,
            NATIVE_CACHE_TARGET,
            freeze_native_cache_sources,
            validate_native_cache_sources,
        )
        self.assert_freezes_active_target(
            PILOT_REQUIRED,
            PILOT_TARGET,
            freeze_pilot_sources,
            validate_pilot_sources,
        )

    def assert_historical_receipt_resolves_from_snapshot(self, required, target, validator):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "legacy"
            _write_files(root, required)
            receipt = copy_source_snapshot(
                root,
                required,
                base / "legacy-host",
                LocalSnapshotStore(base / "legacy-store"),
                target=target,
            )
            before = copy.deepcopy(receipt)

            (root / required[0]).write_text("changed current checkout")
            (root / "retention/unrelated.py").write_text("new helper")
            verified = validator(root, receipt)

            self.assertEqual(verified["source_files"], len(required))
            self.assertEqual(receipt, before)
            shutil.rmtree(receipt["source_snapshot_root"])
            rematerialized = validator(root, receipt)
            self.assertEqual(rematerialized["source_files"], len(required))
            self.assertTrue((Path(receipt["source_snapshot_root"]) / required[0]).is_file())

    def test_historical_retention_receipts_keep_resolving_from_snapshots(self):
        self.assert_historical_receipt_resolves_from_snapshot(
            HISTORICAL_CHECKPOINT_REQUIRED,
            "//autonomy:sustained-checkpoint-retention-host",
            validate_checkpoint_sources,
        )
        self.assert_historical_receipt_resolves_from_snapshot(
            HISTORICAL_NATIVE_CACHE_REQUIRED,
            "//autonomy:native-cache-retention-host",
            validate_native_cache_sources,
        )
        self.assert_historical_receipt_resolves_from_snapshot(
            HISTORICAL_PILOT_REQUIRED,
            "//autonomy:sustained-pilot-retention-host",
            validate_pilot_sources,
        )

    def test_historical_snapshot_corruption_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "legacy"
            _write_files(root, HISTORICAL_NATIVE_CACHE_REQUIRED)
            receipt = copy_source_snapshot(
                root,
                HISTORICAL_NATIVE_CACHE_REQUIRED,
                base / "legacy-host",
                LocalSnapshotStore(base / "legacy-store"),
                target="//autonomy:native-cache-retention-host",
            )
            archive = LocalSnapshotStore(receipt["source_snapshot_store"]["root"]).path_for(
                receipt["source_snapshot_sha256"]
            )
            before = file_sha256(archive)
            archive.write_bytes(b"altered snapshot")

            with self.assertRaises(ValueError):
                validate_native_cache_sources(root, receipt)

            self.assertNotEqual(file_sha256(archive), before)


if __name__ == "__main__":
    unittest.main()
