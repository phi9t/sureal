import json
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence.source_snapshot import file_sha256
from insula.launch_plan import RuntimeLockError, load_runtime_lock, plan_data
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import (
    CURRENT_MOTION_CLI_ROOTFS_NAME,
    CURRENT_MOTION_METRICS_ROOTFS_NAME,
)
from motion import (
    verify_motion_cli,
    verify_motion_cli_expanded,
    verify_motion_native,
)


AUTONOMY = Path(__file__).resolve().parents[1]


def write_rootfs(root: Path):
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/sh").write_text("#!/bin/sh\n")
    (root / "bin/sh").chmod(0o755)
    (root / "etc").mkdir()
    (root / "etc/issue").write_text("motion fixture\n")


def write_motion_cli_lock(rootfs: Path):
    lock = {
        "schema_version": 1,
        "rootfs_sha256": rootfs_identity(rootfs),
        "image_id": "sha256:" + "1" * 64,
        "parent_image_id": "sha256:84fb83dd874d0cfff8e9ee3df0759d89f9ad85e9538c0071c9eb606a13d8c233",
        "recipe_hashes": {
            "Dockerfile": file_sha256(AUTONOMY / "motion/cli/motion_cli.Dockerfile"),
            "CMakeLists.txt": file_sha256(AUTONOMY / "motion/cli/CMakeLists.txt"),
            "motion_metrics_main.cc": file_sha256(
                AUTONOMY / "motion/cli/motion_metrics_main.cc"
            ),
        },
    }
    rootfs.with_name(rootfs.name + ".lock.json").write_text(json.dumps(lock, indent=2) + "\n")


def write_motion_metrics_lock(rootfs: Path):
    lock = {
        "schema_version": 1,
        "rootfs_sha256": rootfs_identity(rootfs),
        "image_id": "sha256:" + "2" * 64,
        "parent_image_id": "sha256:c0018cf57e482c6a9e6623ea32f29c6039f22f5dafb0f3311bad6d411a7bb135",
        "recipe_hashes": {
            "Dockerfile": file_sha256(AUTONOMY / "motion/ingestion/native_metric.Dockerfile"),
            "CMakeLists.txt": file_sha256(AUTONOMY / "motion/CMakeLists.txt"),
        },
    }
    rootfs.with_name(rootfs.name + ".lock.json").write_text(json.dumps(lock, indent=2) + "\n")


class MotionVerifierLaunchPlanTests(unittest.TestCase):
    def test_motion_verifiers_load_image_locks_and_mount_code_without_source(self):
        cases = [
            (verify_motion_cli, CURRENT_MOTION_CLI_ROOTFS_NAME, write_motion_cli_lock),
            (verify_motion_cli_expanded, CURRENT_MOTION_CLI_ROOTFS_NAME, write_motion_cli_lock),
            (verify_motion_native, CURRENT_MOTION_METRICS_ROOTFS_NAME, write_motion_metrics_lock),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out"
            output.mkdir()
            for module, name, write_lock in cases:
                with self.subTest(module=module.__name__):
                    rootfs = root / module.__name__.replace(".", "_") / name
                    write_rootfs(rootfs)
                    write_lock(rootfs)

                    runtime = module.load_motion_runtime(rootfs)
                    plan = module.build_motion_plan(runtime, output, ["true"])
                    data = plan_data(plan)

                    self.assertEqual(runtime.form, "image")
                    self.assertEqual(data["runtime"]["form"], "image")
                    self.assertEqual(data["command"], ["true"])
                    roles = {mount["role"]: mount for mount in data["mounts"]}
                    self.assertEqual(roles["code"]["inside_path"], "/experiment")
                    self.assertNotIn("source", roles)

                    rootfs.with_name(rootfs.name + ".lock.json").unlink()
                    with self.assertRaises(RuntimeLockError):
                        module.load_motion_runtime(rootfs)

    def test_motion_foundation_replay_builds_checked_plan_for_code_and_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(sys, "argv", ["replay_motion_foundation.py"]):
                replay_motion_foundation = importlib.import_module(
                    "motion.replay_motion_foundation"
                )
            root = Path(temporary)
            rootfs = root / CURRENT_MOTION_CLI_ROOTFS_NAME
            code = root / "code"
            inputs = root / "inputs"
            output = root / "output"
            for path in (code, inputs, output):
                path.mkdir()
            write_rootfs(rootfs)
            write_motion_cli_lock(rootfs)

            runtime = replay_motion_foundation.load_motion_runtime(rootfs)
            plan = replay_motion_foundation.build_foundation_plan(
                runtime,
                code,
                inputs,
                output,
                "python /experiment/check_tensorflow.py",
            )
            data = plan_data(plan)
            roles = {mount["role"]: mount for mount in data["mounts"]}

            self.assertEqual(data["runtime"]["form"], "image")
            self.assertEqual(roles["code"]["host_path"], str(code.resolve()))
            self.assertEqual(roles["source"]["host_path"], str(inputs.resolve()))
            self.assertNotEqual(roles["code"]["host_path"], roles["source"]["host_path"])
            self.assertEqual(data["command"], ["/bin/sh", "-c", "python /experiment/check_tensorflow.py"])


if __name__ == "__main__":
    unittest.main()
