import unittest
import os
from pathlib import Path

from retention.checkpoint_retention_sources import (
    REQUIRED as CHECKPOINT_RETENTION_REQUIRED,
    SNAPSHOT_TARGET as CHECKPOINT_RETENTION_TARGET,
)
from retention.pilot_retention_sources import (
    REQUIRED as PILOT_RETENTION_REQUIRED,
    SNAPSHOT_TARGET as PILOT_RETENTION_TARGET,
)
from retention.retention_sources import (
    REQUIRED as NATIVE_CACHE_RETENTION_REQUIRED,
    SNAPSHOT_TARGET as NATIVE_CACHE_RETENTION_TARGET,
)
from training_execution.sustained_controller_sources import (
    REQUIRED as CONTROLLER_REQUIRED,
    SNAPSHOT_TARGET as CONTROLLER_TARGET,
)
from training_execution.sustained_sources import SNAPSHOT_TARGET as SUSTAINED_RUN_TARGET
from training_execution.sustained_sources import source_paths as sustained_source_paths
from evidence.source_snapshot import label_to_path
from resources.sources import SNAPSHOT_TARGET as RESOURCE_TARGET
from resources.sources import source_paths as resource_source_paths
from studies.architecture.experiment_runner import ARCHITECTURE_SOURCE_SNAPSHOT_TARGET
from studies.scientific_cohort import SCIENTIFIC_COHORT_TARGET


PACKAGE = Path(__file__).resolve().parent
SUSTAINED_EVALUATION_WORKERS = {
    "evaluation/prepare_sustained_v3.py",
    "evaluation/audit_proposals_sustained_v3.py",
    "evaluation/metrics_sustained_v3.py",
    "evaluation/audit_metrics_sustained_v3.py",
}


class SourceSnapshotTargetTests(unittest.TestCase):
    def assert_executable_target(self, actual, expected):
        self.assertEqual(
            actual,
            expected,
            "new source receipts must bind to the executable target, not a helper library",
        )

    def query_paths(self, filename):
        path = self.query_file(filename)
        self.assertTrue(path.is_file(), f"missing genquery output: {filename}")
        paths = []
        for line in path.read_text().splitlines():
            if not line:
                continue
            relative = label_to_path(line)
            prefix = "autonomy/"
            self.assertTrue(relative.startswith(prefix), relative)
            paths.append(relative[len(prefix) :])
        return sorted(paths)

    def query_file(self, filename):
        candidates = [PACKAGE / filename]
        runfiles = os.environ.get("RUNFILES_DIR")
        if runfiles:
            candidates.extend(
                [
                    Path(runfiles) / "_main" / "autonomy" / filename,
                    Path(runfiles) / "autonomy" / filename,
                ]
            )
        for path in candidates:
            if path.is_file():
                return path
        return candidates[0]

    def assert_target_contains_required_sources(self, target, query_filename, required):
        self.assertTrue(target.startswith("//autonomy"), target)
        paths = self.query_paths(query_filename)
        missing = sorted(set(required) - set(paths))
        self.assertEqual(missing, [])
        self.assertFalse([name for name in paths if name.endswith("_test.py") or name.startswith("tests/")])
        return paths

    def test_sustained_run_sources_target_declares_required_execution_sources(self):
        self.assert_executable_target(
            SUSTAINED_RUN_TARGET,
            "//autonomy/training_execution:train_sustained",
        )
        self.assert_target_contains_required_sources(
            SUSTAINED_RUN_TARGET,
            "sustained_run_sources_query",
            set(sustained_source_paths(PACKAGE)) | SUSTAINED_EVALUATION_WORKERS,
        )

    def test_resource_source_layer_target_declares_required_execution_sources(self):
        self.assert_executable_target(
            RESOURCE_TARGET,
            "//autonomy/resources:execute_worker",
        )
        self.assert_target_contains_required_sources(
            RESOURCE_TARGET,
            "resource_source_layer_query",
            resource_source_paths(PACKAGE / "resources"),
        )

    def test_sustained_controller_host_target_declares_required_execution_sources(self):
        self.assert_executable_target(
            CONTROLLER_TARGET,
            "//autonomy/training_execution:run_sustained",
        )
        self.assert_target_contains_required_sources(
            CONTROLLER_TARGET,
            "sustained_controller_host_query",
            set(CONTROLLER_REQUIRED) | SUSTAINED_EVALUATION_WORKERS,
        )

    def test_sustained_checkpoint_retention_host_target_declares_required_execution_sources(self):
        self.assert_executable_target(
            CHECKPOINT_RETENTION_TARGET,
            "//autonomy/retention:publish_sustained_checkpoint",
        )
        self.assert_target_contains_required_sources(
            CHECKPOINT_RETENTION_TARGET,
            "sustained_checkpoint_retention_host_query",
            CHECKPOINT_RETENTION_REQUIRED,
        )

    def test_sustained_pilot_retention_host_target_declares_required_execution_sources(self):
        self.assert_executable_target(
            PILOT_RETENTION_TARGET,
            "//autonomy/retention:publish_sustained_pilot",
        )
        self.assert_target_contains_required_sources(
            PILOT_RETENTION_TARGET,
            "sustained_pilot_retention_host_query",
            PILOT_RETENTION_REQUIRED,
        )

    def test_native_cache_retention_host_target_declares_required_execution_sources(self):
        self.assert_executable_target(
            NATIVE_CACHE_RETENTION_TARGET,
            "//autonomy/retention:publish_native_cache",
        )
        self.assert_target_contains_required_sources(
            NATIVE_CACHE_RETENTION_TARGET,
            "native_cache_retention_host_query",
            NATIVE_CACHE_RETENTION_REQUIRED,
        )

    def test_architecture_runner_target_declares_required_execution_sources(self):
        self.assert_executable_target(
            ARCHITECTURE_SOURCE_SNAPSHOT_TARGET,
            "//autonomy/studies:architecture_experiment_runner",
        )
        paths = self.assert_target_contains_required_sources(
            ARCHITECTURE_SOURCE_SNAPSHOT_TARGET,
            "architecture_experiment_runner_query",
            {
                "studies/architecture/experiment_runner.py",
                "studies/architecture/registry.json",
                "studies/architecture/harness/files.json",
                "research/architecture-retention-controls-spec.md",
                "detection/pillar_detector.py",
                "evaluation/prepare_sustained_v3.py",
            },
        )
        self.assertIn("studies/architecture/harness/run-architecture-learning-curve.py", paths)

    def test_scientific_cohort_target_declares_point_and_camera_execution_sources(self):
        self.assert_executable_target(
            SCIENTIFIC_COHORT_TARGET,
            "//autonomy/studies:scientific_cohort",
        )
        self.assert_target_contains_required_sources(
            SCIENTIFIC_COHORT_TARGET,
            "scientific_cohort_query",
            {
                "studies/scientific_cohort.py",
                "geometry/scientific_scene_command.py",
                "geometry/scientific_scene_validate.py",
                "geometry/scientific_reconstruction.py",
                "geometry/reconstruction_validate.py",
                "geometry/geometry.py",
                "geometry/geometry_foundation.py",
                "dataset/scientific-preprocess.py",
                "dataset/publish-scientific-scene.py",
                "dataset/verify-scientific-replay.py",
                "dataset/publish-scientific-sidecars.py",
                "dataset/scientific-acquisition.candidate.json",
                "dataset/scientific-cohort.candidate.json",
                "dataset/scientific_admission.py",
                "dataset/cohort_resume.py",
                "dataset/verified_eviction.py",
                "dataset/sidecar_eviction.py",
                "camera/scientific-camera-preprocess.py",
                "camera/publish-scientific-camera.py",
                "camera/verify-camera-replay.py",
                "camera/camera_eviction.py",
                "insula/entry.py",
            },
        )


if __name__ == "__main__":
    unittest.main()
