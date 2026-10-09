import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence.source_snapshot import file_sha256
from insula import verify_gpu_isolation, verify_gpu_live
from insula.launch_plan import (
    BAZEL_LINUX_X86_64_SHA256,
    BAZEL_VERSION,
    load_runtime_lock,
    plan_data,
)
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import CURRENT_GPU_ROOTFS_NAME, current_gpu_rootfs


AUTONOMY = Path(__file__).resolve().parents[1]


def write_rootfs(root: Path):
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/python").write_text("#!/bin/sh\n")
    (root / "bin/python").chmod(0o755)


def write_gpu_lock(rootfs: Path):
    lock_path = rootfs.with_name(rootfs.name + ".lock.json")
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rootfs_sha256": rootfs_identity(rootfs),
                "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile.gpu-bazel-rootfs-v6"),
                "requirements_sha256": file_sha256(AUTONOMY / "insula/gpu-requirements.lock"),
                "bazel_version": BAZEL_VERSION,
                "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
            },
            indent=2,
        )
        + "\n"
    )
    return lock_path


def fake_gpu_environment(root: Path):
    devices = root / "devices"
    devices.mkdir()
    pairs = []
    for guest in ("/dev/nvidia1", "/dev/nvidiactl", "/dev/nvidia-uvm"):
        host = devices / Path(guest).name
        host.write_text("")
        pairs.append(f"{host}={guest}")
    drivers = root / "driver-libs"
    drivers.mkdir()
    for name in (
        "libcuda.so",
        "libnvidia-ptxjitcompiler.so",
        "libnvidia-nvvm.so",
    ):
        (drivers / name).write_text(name)
    return {
        "SUREAL_BAZEL_GPU_DEVICES": ",".join(pairs),
        "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(drivers),
        "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
    }


class GPUVerifierPlanTests(unittest.TestCase):
    def test_live_verifier_loads_checked_runtime_and_builds_gpu_one_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            rootfs = current_gpu_rootfs(cache)
            write_rootfs(rootfs)
            lock = write_gpu_lock(rootfs)
            output = root / "output"
            output.mkdir()

            with patch.dict(os.environ, fake_gpu_environment(root), clear=False):
                runtime = verify_gpu_live.load_gpu_runtime(cache)
                plan = verify_gpu_live.gpu_probe_plan(runtime, output)

            self.assertEqual(runtime.lock_path, lock.resolve())
            data = plan_data(plan)
            self.assertEqual(data["gpu"], {"requested_index": 1, "device_uuid": "GPU-fixture-1"})
            self.assertEqual(
                [device["inside_path"] for device in data["devices"]],
                ["/dev/nvidia1", "/dev/nvidiactl", "/dev/nvidia-uvm"],
            )
            self.assertNotIn("/dev/nvidia0", json.dumps(data["devices"], sort_keys=True))
            self.assertEqual(
                data["command"],
                ["/opt/waymo/bin/python", "/experiment/insula/gpu_probe.py"],
            )

    def test_isolation_verifier_builds_fresh_gpu_plan_instead_of_replaying_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_GPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = write_gpu_lock(rootfs)
            runtime = load_runtime_lock(rootfs, lock)
            output = root / "output"
            source = root / "candidate"
            output.mkdir()
            source.mkdir()

            with patch.dict(os.environ, fake_gpu_environment(root), clear=False):
                plan = verify_gpu_isolation.gpu_isolation_plan(
                    runtime,
                    output=output,
                    source=source,
                    network_probe_port=31337,
                )

            data = plan_data(plan)
            self.assertEqual(data["gpu"], {"requested_index": 1, "device_uuid": "GPU-fixture-1"})
            self.assertEqual(
                [device["inside_path"] for device in data["devices"]],
                ["/dev/nvidia1", "/dev/nvidiactl", "/dev/nvidia-uvm"],
            )
            self.assertNotIn("/dev/nvidia0", json.dumps(data["devices"], sort_keys=True))
            self.assertEqual(data["command"][:2], ["/opt/waymo/bin/python", "-c"])
            self.assertIn("/experiment/insula/validate_gpu_probe.py", data["command"][2])

    def test_verifier_sources_do_not_copy_gpu_splicing_or_receipt_runtime_replay(self):
        live_source = Path(verify_gpu_live.__file__).read_text()
        isolation_source = Path(verify_gpu_isolation.__file__).read_text()

        self.assertNotIn("from insula.entry import launch_plan", live_source)
        self.assertNotIn("plan.index('--')", live_source)
        self.assertNotIn("receipt['command']", isolation_source)
        self.assertNotIn('receipt["command"]', isolation_source)
        self.assertNotIn("receipt['runtime_lock']", isolation_source)
        self.assertNotIn('receipt["runtime_lock"]', isolation_source)


if __name__ == "__main__":
    unittest.main()
