import json
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import file_sha256
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION, plan_data
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import current_cpu_rootfs

from geometry.launches import build_geometry_plan, load_current_cpu_runtime, plan_receipt


AUTONOMY = Path(__file__).resolve().parents[1]


def write_rootfs(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/python").write_text("#!/bin/sh\n")
    (root / "bin/python").chmod(0o755)
    (root / "etc").mkdir()
    (root / "etc/issue").write_text("fixture rootfs\n")


def write_cpu_lock(path: Path, rootfs: Path) -> None:
    path.write_text(
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


class GeometryLaunchTests(unittest.TestCase):
    def test_geometry_plans_declare_scene_and_reconstruction_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            rootfs = current_cpu_rootfs(cache)
            write_rootfs(rootfs)
            write_cpu_lock(rootfs.with_name(rootfs.name + ".lock.json"), rootfs)
            code = Path(temporary) / "code"
            source = Path(temporary) / "source"
            output = Path(temporary) / "output"
            prepared = Path(temporary) / "prepared-sidecars"
            points = Path(temporary) / "points"
            for path in (code, source, output, prepared, points):
                path.mkdir()

            runtime = load_current_cpu_runtime(cache)
            foundation = build_geometry_plan(
                runtime,
                code_root=code,
                source=source,
                output=output / "foundation",
                command=[
                    "python",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "/experiment/geometry",
                    "-p",
                    "geometry_foundation_test.py",
                    "-v",
                ],
            )
            scene = build_geometry_plan(
                runtime,
                code_root=code,
                source=source,
                output=output / "scene",
                command=["python", "-c", "validate"],
                named_inputs={"/opt": prepared, "/srv": points},
            )

            self.assertEqual(plan_data(foundation)["runtime"]["form"], "recipe-digest")
            scene_data = plan_data(scene)
            mounts = {mount["role"]: mount for mount in scene_data["mounts"]}
            self.assertEqual(mounts["input:/opt"]["inside_path"], "/opt")
            self.assertEqual(mounts["input:/srv"]["inside_path"], "/srv")
            self.assertEqual(mounts["input:/opt"]["mode"], "read_only")
            self.assertIn(["--setenv", "PYTHONPATH", "/experiment"], scene_data["environment"])
            receipt = plan_receipt(scene)
            self.assertEqual(receipt["command"], ["python", "-c", "validate"])
            self.assertNotIn(str(temporary), json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
