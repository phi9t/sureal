import json
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import file_sha256
from insula.launch_plan import (
    BAZEL_LINUX_X86_64_SHA256,
    BAZEL_VERSION,
    build_plan,
    load_default_runtime_lock,
    plan_data,
    record_plan,
)
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import current_cpu_rootfs


AUTONOMY = Path(__file__).resolve().parents[1]


def write_rootfs(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/python").write_text("#!/bin/sh\n")
    (root / "bin/python").chmod(0o755)
    (root / "etc").mkdir()
    (root / "etc/issue").write_text("fixture rootfs\n")


def write_cpu_lock(path: Path, rootfs: Path) -> dict:
    lock = {
        "schema_version": 1,
        "rootfs_sha256": rootfs_identity(rootfs),
        "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile"),
        "requirements_sha256": file_sha256(AUTONOMY / "requirements-tracer.lock"),
        "test_tools_requirements_sha256": file_sha256(
            AUTONOMY / "insula/cpu-test-tools-requirements.lock"
        ),
        "bazel_version": BAZEL_VERSION,
        "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
    }
    path.write_text(json.dumps(lock, indent=2) + "\n")
    return lock


class CameraLaunchTests(unittest.TestCase):
    def test_camera_plans_declare_publication_and_replay_inputs_by_role(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            rootfs = current_cpu_rootfs(cache)
            write_rootfs(rootfs)
            write_cpu_lock(rootfs.with_name(rootfs.name + ".lock.json"), rootfs)
            code = Path(temporary) / "code"
            processing = Path(temporary) / "processing"
            publication = Path(temporary) / "publication"
            inputs = Path(temporary) / "inputs"
            sidecars = Path(temporary) / "sidecars"
            output = Path(temporary) / "output"
            for path in (code, processing, publication, inputs, sidecars, output):
                path.mkdir()

            runtime = load_default_runtime_lock(current_cpu_rootfs(cache))
            pack = build_plan(
                runtime,
                code=code,
                source=processing,
                output=output / "packed",
                command=["python", "-c", "pack"],
                named_inputs={"/mnt": inputs},
            )
            replay = build_plan(
                runtime,
                code=code,
                source=publication,
                output=output / "replay",
                command=["python", "-m", "camera.camera_replay_check"],
                named_inputs={"/opt": sidecars, "/mnt": inputs},
            )

            pack_data = plan_data(pack)
            replay_data = plan_data(replay)
            self.assertEqual(pack_data["runtime"]["form"], "recipe-digest")
            self.assertIn(["--setenv", "PYTHONPATH", "/experiment"], pack_data["environment"])
            self.assertEqual(pack_data["command"], ["python", "-c", "pack"])
            pack_mounts = {mount["role"]: mount for mount in pack_data["mounts"]}
            self.assertEqual(pack_mounts["input:/mnt"]["inside_path"], "/mnt")
            self.assertEqual(pack_mounts["input:/mnt"]["mode"], "read_only")
            replay_mounts = {mount["role"]: mount for mount in replay_data["mounts"]}
            self.assertEqual(replay_mounts["input:/opt"]["inside_path"], "/opt")
            self.assertEqual(replay_mounts["input:/mnt"]["inside_path"], "/mnt")

            receipt = record_plan(replay)
            self.assertEqual(receipt["runtime"]["form"], "recipe-digest")
            self.assertEqual(receipt["command"], ["python", "-m", "camera.camera_replay_check"])
            self.assertNotIn(str(temporary), json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
