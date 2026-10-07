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


PACKAGE = Path(__file__).resolve().parent


class SourceSnapshotTargetTests(unittest.TestCase):
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

    def assert_target_paths(self, target, query_filename, expected):
        self.assertTrue(target.startswith("//autonomy"), target)
        self.assertEqual(self.query_paths(query_filename), sorted(expected))

    def test_sustained_run_sources_filegroup_matches_freezer_sources(self):
        self.assert_target_paths(
            SUSTAINED_RUN_TARGET,
            "sustained_run_sources_query",
            sustained_source_paths(PACKAGE),
        )

    def test_resource_source_layer_filegroup_matches_freezer_sources(self):
        self.assert_target_paths(
            RESOURCE_TARGET,
            "resource_source_layer_query",
            resource_source_paths(PACKAGE / "resources"),
        )

    def test_sustained_controller_host_filegroup_matches_freezer_sources(self):
        self.assert_target_paths(
            CONTROLLER_TARGET,
            "sustained_controller_host_query",
            CONTROLLER_REQUIRED,
        )

    def test_sustained_checkpoint_retention_host_filegroup_matches_freezer_sources(self):
        self.assert_target_paths(
            CHECKPOINT_RETENTION_TARGET,
            "sustained_checkpoint_retention_host_query",
            CHECKPOINT_RETENTION_REQUIRED,
        )

    def test_sustained_pilot_retention_host_filegroup_matches_freezer_sources(self):
        self.assert_target_paths(
            PILOT_RETENTION_TARGET,
            "sustained_pilot_retention_host_query",
            PILOT_RETENTION_REQUIRED,
        )

    def test_native_cache_retention_host_filegroup_matches_freezer_sources(self):
        self.assert_target_paths(
            NATIVE_CACHE_RETENTION_TARGET,
            "native_cache_retention_host_query",
            NATIVE_CACHE_RETENTION_REQUIRED,
        )


if __name__ == "__main__":
    unittest.main()
