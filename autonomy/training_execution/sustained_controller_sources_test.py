import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import LocalSnapshotStore, copy_source_snapshot
from training_execution.sustained_controller_sources import (
    REQUIRED,
    SNAPSHOT_TARGET,
    freeze_host_sources,
    validate_host_sources,
)


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
                {"schema_version": 1, "kind": "local", "root": str(root / "store")},
            )
            self.assertIn("autonomy/training_execution/run_sustained.py", receipt["source_pins"])
            validate_host_sources(autonomy, receipt)
            (autonomy / "training_execution/run_sustained.py").write_text("changed checkout\n")
            validate_host_sources(autonomy, receipt)

    def test_legacy_component_relative_receipt_remains_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "legacy"
            for name in REQUIRED:
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name + "\n")
            receipt = copy_source_snapshot(
                repo,
                REQUIRED,
                root / "legacy-host",
                LocalSnapshotStore(root / "legacy-store"),
                target="legacy:sustained-controller-host",
            )
            self.assertEqual(validate_host_sources(repo, receipt)["source_files"], len(REQUIRED))


if __name__ == "__main__":
    unittest.main()
