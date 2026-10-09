import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import LocalSnapshotStore, copy_source_snapshot, file_sha256
from training_execution.sustained_controller_sources import (
    REQUIRED,
    SNAPSHOT_TARGET,
    freeze_host_sources,
    validate_host_sources,
)

HISTORICAL_REQUIRED = (
    "detection/sustained_contract.py",
    "evidence/source_snapshot.py",
    "insula/entry.py",
    "insula/runtime_identity.py",
    "resources/backend.py",
    "resources/checkpoint.py",
    "resources/command.py",
    "resources/execute_worker.py",
    "resources/kernel_scope.py",
    "resources/process_lifecycle.py",
    "resources/resource_archive.py",
    "resources/resource_archive_cli.py",
    "resources/resource_rehydrate.py",
    "resources/resource_release_plan.py",
    "resources/scientific_budget.py",
    "resources/scientific_payload.py",
    "resources/scoped_stage.py",
    "resources/sources.py",
    "resources/stage.py",
    "resources/stage_accounting.py",
    "resources/sustained_scoring_budget.py",
    "retention/checkpoint_retention_audit.py",
    "retention/checkpoint_retention_policy.py",
    "retention/checkpoint_retention_sources.py",
    "retention/publish_sustained_checkpoint.py",
    "retention/sustained_checkpoint_inventory.py",
    "retention/sustained_controller_lock.py",
    "studies/architecture/experiment_runner.py",
    "training_execution/run_sustained.py",
    "training_execution/sustained_admission.py",
    "training_execution/sustained_control.py",
    "training_execution/sustained_controller_backend.py",
    "training_execution/sustained_controller_sources.py",
    "training_execution/sustained_sources.py",
    "training_execution/sustained_stage_inputs.py",
    "training_execution/sustained_workflow.py",
)
HISTORICAL_TARGET = "//autonomy:sustained-controller-host"


class SustainedControllerSourceTests(unittest.TestCase):
    def write_checkout(self, repo):
        for name in REQUIRED:
            path = repo / "autonomy" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name + "\n")
        return repo / "autonomy"

    def query_runner(self, names):
        def run(command, **kwargs):
            self.assertIn("query", command)

            class Result:
                pass

            result = Result()
            result.stdout = "".join(
                "//" + name.rsplit("/", 1)[0] + ":" + name.rsplit("/", 1)[1] + "\n"
                for name in sorted(names)
            )
            return result

        return run

    def write_historical_checkout(self, root):
        for name in HISTORICAL_REQUIRED:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name + "\n")

    def test_repo_checkout_uses_executable_target_snapshot_and_descriptor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            autonomy = self.write_checkout(repo)
            names = ["autonomy/" + name for name in REQUIRED]
            receipt = freeze_host_sources(
                autonomy,
                root / "host-source",
                store=LocalSnapshotStore(root / "store"),
                repo_root=repo,
                bazel=repo / "bazelw",
                runner=self.query_runner(names),
            )
            self.assertEqual(receipt["schema_version"], 2)
            self.assertEqual(receipt["source_snapshot_target"], SNAPSHOT_TARGET)
            self.assertEqual(
                receipt["source_snapshot_store"],
                {"kind": "local", "root": str(root / "store")},
            )
            self.assertEqual(
                receipt["source_snapshot_blob"]["key"],
                "artifacts/source-snapshots/" + receipt["source_snapshot_sha256"],
            )
            self.assertIn("autonomy/training_execution/run_sustained.py", receipt["source_pins"])
            validate_host_sources(autonomy, receipt)
            (autonomy / "training_execution/run_sustained.py").write_text("changed checkout\n")
            validate_host_sources(autonomy, receipt)

    def test_legacy_component_relative_receipt_remains_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "legacy"
            self.write_historical_checkout(repo)
            receipt = copy_source_snapshot(
                repo,
                HISTORICAL_REQUIRED,
                root / "legacy-host",
                LocalSnapshotStore(root / "legacy-store"),
                target=HISTORICAL_TARGET,
            )
            self.assertEqual(validate_host_sources(repo, receipt)["source_files"], len(HISTORICAL_REQUIRED))
            self.assertNotIn("retention/publisher_runtime.py", receipt["source_pins"])

    def test_historical_schema1_receipt_rehydrates_deleted_materialization_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "legacy"
            self.write_historical_checkout(repo)
            receipt = copy_source_snapshot(
                repo,
                HISTORICAL_REQUIRED,
                root / "legacy-host",
                LocalSnapshotStore(root / "legacy-store"),
                target=HISTORICAL_TARGET,
            )
            before = copy.deepcopy(receipt)
            archive = LocalSnapshotStore(receipt["source_snapshot_store"]["root"]).path_for(receipt["source_snapshot_sha256"])
            archive_before = file_sha256(archive)
            shutil.rmtree(receipt["source_snapshot_root"])
            result = validate_host_sources(repo, receipt)
            self.assertEqual(result["source_files"], len(HISTORICAL_REQUIRED))
            self.assertTrue((Path(receipt["source_snapshot_root"]) / "training_execution/run_sustained.py").is_file())
            self.assertEqual(receipt, before)
            self.assertEqual(file_sha256(archive), archive_before)

    def test_malformed_historical_schema1_receipt_still_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "legacy"
            self.write_historical_checkout(repo)
            receipt = copy_source_snapshot(
                repo,
                HISTORICAL_REQUIRED,
                root / "legacy-host",
                LocalSnapshotStore(root / "legacy-store"),
                target=HISTORICAL_TARGET,
            )
            bad = copy.deepcopy(receipt)
            bad["source_pins"].pop(HISTORICAL_REQUIRED[0])
            with self.assertRaises(ValueError):
                validate_host_sources(repo, bad)

    def test_new_creation_without_target_context_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "legacy"
            for name in REQUIRED:
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name + "\n")
            with self.assertRaises(ValueError):
                freeze_host_sources(repo, root / "host-source")


if __name__ == "__main__":
    unittest.main()
