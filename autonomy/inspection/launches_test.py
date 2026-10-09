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


class InspectionLaunchTests(unittest.TestCase):
    def test_inspection_plan_declares_geometry_as_named_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            rootfs = current_cpu_rootfs(cache)
            write_rootfs(rootfs)
            write_cpu_lock(rootfs.with_name(rootfs.name + ".lock.json"), rootfs)
            code = Path(temporary) / "code"
            source = Path(temporary) / "source"
            geometry = Path(temporary) / "geometry"
            output = Path(temporary) / "output"
            for path in (code, source, geometry, output):
                path.mkdir()

            runtime = load_default_runtime_lock(current_cpu_rootfs(cache))
            plan = build_plan(
                runtime,
                code=code,
                source=source,
                output=output,
                command=[
                    "python",
                    "-m",
                    "inspection.inspection_views",
                    "/source",
                    "/opt/reconstruction",
                    "/outputs/views",
                ],
                named_inputs={"/opt": geometry},
            )
            data = plan_data(plan)
            mounts = {mount["role"]: mount for mount in data["mounts"]}

            self.assertEqual(data["runtime"]["form"], "recipe-digest")
            self.assertEqual(mounts["input:/opt"]["inside_path"], "/opt")
            self.assertEqual(mounts["input:/opt"]["mode"], "read_only")
            self.assertIn(["--setenv", "PYTHONPATH", "/experiment"], data["environment"])
            self.assertNotIn(str(temporary), json.dumps(record_plan(plan), sort_keys=True))


if __name__ == "__main__":
    unittest.main()
