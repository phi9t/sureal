import json
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import file_sha256
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION, plan_data, render_plan
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME
from insula.verify_m0 import build_m0_plan


AUTONOMY = Path(__file__).resolve().parents[1]


def write_runtime_lock(lock_path: Path, rootfs: Path) -> None:
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rootfs_sha256": rootfs_identity(rootfs),
                "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile"),
                "requirements_sha256": file_sha256(AUTONOMY / "requirements-tracer.lock"),
                "test_tools_requirements_sha256": file_sha256(
                    AUTONOMY / "insula/cpu-test-tools-requirements.lock"
                ),
                "bazel_version": BAZEL_VERSION,
                "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
            },
            indent=2,
        )
        + "\n"
    )


class VerifyM0PlanTests(unittest.TestCase):
    def test_m0_execution_builds_a_checked_launch_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_CPU_ROOTFS_NAME
            rootfs.mkdir()
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_runtime_lock(lock, rootfs)
            source = root / "source"
            output = root / "output"
            experiment = root / "experiment"
            for path in (source, output, experiment):
                path.mkdir()

            plan = build_m0_plan(
                rootfs,
                source,
                output,
                ["python", "-m", "insula.m0_validate"],
                lock=lock,
                experiment=experiment,
            )
            data = plan_data(plan)

            self.assertEqual(data["runtime"]["lock"], str(lock.resolve()))
            self.assertEqual(data["runtime"]["form"], "recipe-digest")
            self.assertEqual(data["command"], ["python", "-m", "insula.m0_validate"])
            mounts = {mount["role"]: mount for mount in data["mounts"]}
            self.assertEqual(mounts["code"]["inside_path"], "/experiment")
            self.assertEqual(mounts["code"]["host_path"], str(experiment.resolve()))
            self.assertEqual(mounts["source"]["inside_path"], "/source")
            self.assertEqual(mounts["output"]["inside_path"], "/outputs")
            self.assertNotIn("enter.sh", render_plan(plan))


if __name__ == "__main__":
    unittest.main()
