import json
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import file_sha256
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION, plan_data
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME, current_cpu_rootfs

from dataset.launches import (
    build_dataset_plan,
    load_dataset_runtime,
    load_pinned_dataset_runtime,
    plan_receipt,
)


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


class DatasetLaunchTests(unittest.TestCase):
    def test_dataset_plan_declares_named_inputs_with_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            rootfs = current_cpu_rootfs(cache)
            write_rootfs(rootfs)
            write_cpu_lock(rootfs.with_name(rootfs.name + ".lock.json"), rootfs)
            code = Path(tmp) / "code"
            source = Path(tmp) / "source"
            output = Path(tmp) / "output"
            opt = Path(tmp) / "prepared"
            mnt = Path(tmp) / "manifest"
            srv = Path(tmp) / "reference"
            job = Path(tmp) / "job"
            scratch = Path(tmp) / "scratch"
            for path in (code, source, output, opt, mnt, srv, job, scratch):
                path.mkdir()
            (mnt / "trusted.json").write_text("{}\n")

            runtime = load_dataset_runtime(cache)
            plan = build_dataset_plan(
                runtime,
                code_root=code,
                source=source,
                output=output,
                command=["python", "-c", "pass"],
                named_inputs={
                    "/opt": opt,
                    "/mnt/trusted": mnt,
                    "/srv/reference": srv,
                    "/tmp/job": job,
                },
                writable_inputs={"/tmp/scratch": scratch},
            )
            data = plan_data(plan)

            self.assertEqual(data["runtime"]["form"], "recipe-digest")
            self.assertEqual(data["runtime"]["rootfs"], str(rootfs.resolve()))
            self.assertIn(["--setenv", "PYTHONPATH", "/experiment"], data["environment"])
            mounts = {mount["role"]: mount for mount in data["mounts"]}
            self.assertEqual(mounts["source"]["inside_path"], "/source")
            self.assertEqual(mounts["output"]["mode"], "writable")
            for inside in ("/opt", "/mnt/trusted", "/srv/reference", "/tmp/job"):
                self.assertEqual(mounts[f"input:{inside}"]["inside_path"], inside)
                self.assertEqual(mounts[f"input:{inside}"]["mode"], "read_only")
            self.assertEqual(mounts["input:/tmp/scratch"]["mode"], "writable")

            receipt = plan_receipt(plan)
            self.assertEqual(receipt["runtime"]["form"], "recipe-digest")
            self.assertEqual(receipt["command"], ["python", "-c", "pass"])
            self.assertNotIn(str(tmp), json.dumps(receipt, sort_keys=True))

    def test_whole_lock_comparison_happens_on_loaded_runtime_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            rootfs = Path(tmp) / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = write_cpu_lock(rootfs.with_name(rootfs.name + ".lock.json"), rootfs)

            runtime = load_pinned_dataset_runtime(rootfs, lock)
            self.assertEqual(runtime.data, lock)

            changed = dict(lock)
            changed["dockerfile_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "runtime lock differs"):
                load_pinned_dataset_runtime(rootfs, changed)


if __name__ == "__main__":
    unittest.main()
