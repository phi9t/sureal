import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from insula.launch_plan import (
    GPURequest,
    Mount,
    RuntimeLock,
    build_plan,
    record_plan as record_launch_plan,
    render_plan,
    with_mounts,
)
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME, CURRENT_GPU_ROOTFS_NAME
from resources.command import wrap_rendered_plan_command, wrap_resource_plan
from training_execution.sustained_controller_backend import (
    build_sustained_stage_plan,
    record_plan as record_sustained_plan,
)


GOLDEN_BASE_COMMIT = "6e4eda1540c07acee26a5133802850f748ddbe38"

GOLDEN_CASES = {
    "cpu": {
        "argv": [
            "bwrap",
            "--unshare-all",
            "--die-with-parent",
            "--ro-bind",
            "$ROOT/rootfs-v5-t29-20261008T230657Z",
            "/",
            "--ro-bind",
            "$ROOT/code",
            "/experiment",
            "--ro-bind",
            "$ROOT/source",
            "/source",
            "--bind",
            "$ROOT/output",
            "/outputs",
            "--ro-bind",
            "$ROOT/srv-input",
            "/srv/data",
            "--tmpfs",
            "/tmp",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp/private-home",
            "--setenv",
            "PATH",
            "/usr/local/bin:/usr/bin:/bin",
            "--setenv",
            "PYTHONNOUSERSITE",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "PYTHONPATH",
            "/experiment",
            "--setenv",
            "EXTRA_FLAG",
            "1",
            "--chdir",
            "/experiment",
            "--",
            "python",
            "/experiment/train.py",
            "--epochs",
            "1",
        ]
    },
    "gpu_with_driver_pins": {
        "argv": [
            "bwrap",
            "--unshare-all",
            "--die-with-parent",
            "--ro-bind",
            "$ROOT/gpu-rootfs-v7",
            "/",
            "--ro-bind",
            "$ROOT/code",
            "/experiment",
            "--bind",
            "$ROOT/output",
            "/outputs",
            "--tmpfs",
            "/driver",
            "--ro-bind",
            "$ROOT/drivers/libcuda.so.fixture",
            "/driver/libcuda.so.fixture",
            "--ro-bind",
            "$ROOT/drivers/libnvidia-ptxjitcompiler.so.fixture",
            "/driver/libnvidia-ptxjitcompiler.so.fixture",
            "--ro-bind",
            "$ROOT/drivers/libnvidia-nvvm.so.fixture",
            "/driver/libnvidia-nvvm.so.fixture",
            "--tmpfs",
            "/tmp",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--dev-bind",
            "$ROOT/devices/nvidia1",
            "/dev/nvidia1",
            "--dev-bind",
            "$ROOT/devices/nvidiactl",
            "/dev/nvidiactl",
            "--dev-bind",
            "$ROOT/devices/nvidia-uvm",
            "/dev/nvidia-uvm",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp/private-home",
            "--setenv",
            "PYTHONNOUSERSITE",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "PYTHONPATH",
            "/experiment",
            "--setenv",
            "PATH",
            "/opt/waymo/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin",
            "--setenv",
            "LD_LIBRARY_PATH",
            "/driver:/usr/local/cuda/lib64",
            "--setenv",
            "CUDA_VISIBLE_DEVICES",
            "0",
            "--chdir",
            "/experiment",
            "--",
            "python",
            "/experiment/gpu_worker.py",
        ],
        "driver_mount_digests": {
            "gpu-driver:libcuda.so.fixture": "327ca648a891f005cf8d0d3dd3242afa82666f60a236bb2d950a719da8f2e376",
            "gpu-driver:libnvidia-nvvm.so.fixture": "53a80e4a77edd0d7ce3a98a465613168782790a930aca3c21b766112feffc7cd",
            "gpu-driver:libnvidia-ptxjitcompiler.so.fixture": "dd15c2d64d7f2cb8c03e7684d80c09e5322ff08a04700445eee57b498e49adee",
        },
        "gpu": {
            "device_minor": 1,
            "device_uuid": "GPU-fixture-1",
            "requested_index": 1,
        },
    },
    "resource_with_mounts": {
        "argv": [
            "bwrap",
            "--unshare-all",
            "--die-with-parent",
            "--ro-bind",
            "$ROOT/rootfs-v5-t29-20261008T230657Z",
            "/",
            "--ro-bind",
            "$ROOT/code",
            "/experiment",
            "--bind",
            "$ROOT/output",
            "/outputs",
            "--ro-bind",
            "$ROOT/resource-code/resources",
            "/experiment/resources",
            "--ro-bind",
            "$ROOT/resource-code/evidence",
            "/experiment/evidence",
            "--tmpfs",
            "/tmp",
            "--ro-bind",
            "$ROOT/resource-code",
            "/tmp/resource-layer",
            "--bind",
            "$ROOT/resource-output",
            "/tmp/resource-output",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp/private-home",
            "--setenv",
            "PATH",
            "/usr/local/bin:/usr/bin:/bin",
            "--setenv",
            "PYTHONNOUSERSITE",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "PYTHONPATH",
            "/experiment",
            "--chdir",
            "/experiment",
            "--",
            "python",
            "/tmp/resource-layer/resources/execute_worker.py",
            "/tmp/resource-output",
            "/experiment/worker.py",
        ]
    },
    "resource_wrap_rendered_plan_command": {
        "argv": [
            "bwrap",
            "--unshare-all",
            "--die-with-parent",
            "--ro-bind",
            "$ROOT/rootfs-v5-t29-20261008T230657Z",
            "/",
            "--ro-bind",
            "$ROOT/code",
            "/experiment",
            "--bind",
            "$ROOT/output",
            "/outputs",
            "--ro-bind",
            "$ROOT/resource-code/resources",
            "/experiment/resources",
            "--ro-bind",
            "$ROOT/resource-code/evidence",
            "/experiment/evidence",
            "--tmpfs",
            "/tmp",
            "--ro-bind",
            "$ROOT/resource-code",
            "/tmp/resource-layer",
            "--bind",
            "$ROOT/resource-output",
            "/tmp/resource-output",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp/private-home",
            "--setenv",
            "PATH",
            "/usr/local/bin:/usr/bin:/bin",
            "--setenv",
            "PYTHONNOUSERSITE",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "PYTHONPATH",
            "/experiment",
            "--chdir",
            "/experiment",
            "--",
            "python",
            "/tmp/resource-layer/resources/execute_worker.py",
            "/tmp/resource-output",
            "/experiment/worker.py",
        ],
        "worker_argv": ["/experiment/worker.py"],
    },
    "resource_wrap_resource_plan": {
        "argv": [
            "bwrap",
            "--unshare-all",
            "--die-with-parent",
            "--ro-bind",
            "$ROOT/rootfs-v5-t29-20261008T230657Z",
            "/",
            "--ro-bind",
            "$ROOT/code",
            "/experiment",
            "--bind",
            "$ROOT/output",
            "/outputs",
            "--ro-bind",
            "$ROOT/resource-code/resources",
            "/experiment/resources",
            "--ro-bind",
            "$ROOT/resource-code/evidence",
            "/experiment/evidence",
            "--tmpfs",
            "/tmp",
            "--ro-bind",
            "$ROOT/resource-code",
            "/tmp/resource-layer",
            "--bind",
            "$ROOT/resource-output",
            "/tmp/resource-output",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp/private-home",
            "--setenv",
            "PATH",
            "/usr/local/bin:/usr/bin:/bin",
            "--setenv",
            "PYTHONNOUSERSITE",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "PYTHONPATH",
            "/experiment",
            "--chdir",
            "/experiment",
            "--",
            "python",
            "/tmp/resource-layer/resources/execute_worker.py",
            "/tmp/resource-output",
            "/experiment/worker.py",
        ],
        "worker_argv": ["/experiment/worker.py"],
    },
    "split_runtime_symlink_rootfs": {
        "argv": [
            "bwrap",
            "--unshare-all",
            "--die-with-parent",
            "--symlink",
            "usr/bin",
            "/bin",
            "--ro-bind",
            "$ROOT/split-rootfs/etc",
            "/etc",
            "--symlink",
            "usr/lib",
            "/lib",
            "--ro-bind",
            "$ROOT/split-rootfs/usr",
            "/usr",
            "--ro-bind",
            "$ROOT/code",
            "/experiment",
            "--bind",
            "$ROOT/output",
            "/outputs",
            "--tmpfs",
            "/tmp",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp/private-home",
            "--setenv",
            "PATH",
            "/usr/local/bin:/usr/bin:/bin",
            "--setenv",
            "PYTHONNOUSERSITE",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "PYTHONPATH",
            "/experiment",
            "--chdir",
            "/experiment",
            "--",
            "python",
            "/experiment/split_worker.py",
        ]
    },
    "sustained_stage": {
        "argv": [
            "bwrap",
            "--unshare-all",
            "--die-with-parent",
            "--ro-bind",
            "$ROOT/gpu-rootfs-v7",
            "/",
            "--ro-bind",
            "$ROOT/code",
            "/experiment",
            "--bind",
            "$ROOT/output",
            "/outputs",
            "--tmpfs",
            "/driver",
            "--ro-bind",
            "$ROOT/drivers/libcuda.so.fixture",
            "/driver/libcuda.so.fixture",
            "--ro-bind",
            "$ROOT/drivers/libnvidia-ptxjitcompiler.so.fixture",
            "/driver/libnvidia-ptxjitcompiler.so.fixture",
            "--ro-bind",
            "$ROOT/drivers/libnvidia-nvvm.so.fixture",
            "/driver/libnvidia-nvvm.so.fixture",
            "--tmpfs",
            "/tmp",
            "--ro-bind",
            "$ROOT/stage-input",
            "/tmp/inputs",
            "--ro-bind",
            "$ROOT/native",
            "/tmp/native",
            "--ro-bind",
            "$ROOT/physical",
            "/tmp/physical",
            "--ro-bind",
            "$ROOT/boxes",
            "/tmp/boxes",
            "--ro-bind",
            "$ROOT/runtime-lock.json",
            "/tmp/runtime-lock.json",
            "--ro-bind",
            "$ROOT/scientific",
            "/tmp/scientific",
            "--ro-bind",
            "$ROOT/source-snapshots",
            "/tmp/source-snapshots",
            "--ro-bind",
            "$ROOT/verifier",
            "/tmp/verifier",
            "--ro-bind",
            "$ROOT/retained",
            "/tmp/retained",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--dev-bind",
            "$ROOT/devices/nvidia1",
            "/dev/nvidia1",
            "--dev-bind",
            "$ROOT/devices/nvidiactl",
            "/dev/nvidiactl",
            "--dev-bind",
            "$ROOT/devices/nvidia-uvm",
            "/dev/nvidia-uvm",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp/private-home",
            "--setenv",
            "PYTHONNOUSERSITE",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "PYTHONPATH",
            "/experiment",
            "--setenv",
            "PATH",
            "/opt/waymo/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin",
            "--setenv",
            "LD_LIBRARY_PATH",
            "/driver:/usr/local/cuda/lib64",
            "--setenv",
            "CUDA_VISIBLE_DEVICES",
            "0",
            "--setenv",
            "CUBLAS_WORKSPACE_CONFIG",
            ":4096:8",
            "--setenv",
            "SUREAL_SOURCE_SNAPSHOT_STORE",
            "/tmp/source-snapshots",
            "--chdir",
            "/experiment",
            "--",
            "python",
            "/tmp/verifier/audit_sustained_transition.py",
        ],
        "gpu": {
            "device_minor": 1,
            "device_uuid": "GPU-fixture-1",
            "requested_index": 1,
        },
        "scientific_digest": "5555555555555555555555555555555555555555555555555555555555555555",
    },
    "tmpfs_with_tmp_children": {
        "argv": [
            "bwrap",
            "--unshare-all",
            "--die-with-parent",
            "--ro-bind",
            "$ROOT/rootfs-v5-t29-20261008T230657Z",
            "/",
            "--ro-bind",
            "$ROOT/code",
            "/experiment",
            "--bind",
            "$ROOT/output",
            "/outputs",
            "--tmpfs",
            "/tmp",
            "--ro-bind",
            "$ROOT/tmp-input",
            "/tmp/read-only",
            "--bind",
            "$ROOT/tmp-writable",
            "/tmp/scratch",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp/private-home",
            "--setenv",
            "PATH",
            "/usr/local/bin:/usr/bin:/bin",
            "--setenv",
            "PYTHONNOUSERSITE",
            "1",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "PYTHONPATH",
            "/experiment",
            "--chdir",
            "/experiment",
            "--",
            "python",
            "/experiment/tmp_worker.py",
        ]
    },
}


def _runtime(root, name, digest, *, form="recipe-digest"):
    rootfs = root / name
    rootfs.mkdir(parents=True)
    return RuntimeLock(
        rootfs=rootfs,
        lock_path=root / (name + ".lock.json"),
        data={"schema_version": 1, "rootfs_sha256": digest},
        form=form,
        lock_sha256=digest,
    )


def _write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def _mkdir(root, name):
    path = root / name
    path.mkdir(parents=True)
    _write(path / "file.txt", name + "\n")
    return path


def _gpu_environment(root):
    devices = root / "devices"
    drivers = root / "drivers"
    devices.mkdir()
    drivers.mkdir()
    for name in ("nvidia1", "nvidiactl", "nvidia-uvm"):
        _write(devices / name, name + "\n")
    for name in (
        "libcuda.so.fixture",
        "libnvidia-ptxjitcompiler.so.fixture",
        "libnvidia-nvvm.so.fixture",
    ):
        _write(drivers / name, name + "\n")
    return {
        "SUREAL_BAZEL_GPU_DEVICES": ",".join(
            [
                f"{devices / 'nvidia1'}=/dev/nvidia1",
                f"{devices / 'nvidiactl'}=/dev/nvidiactl",
                f"{devices / 'nvidia-uvm'}=/dev/nvidia-uvm",
            ]
        ),
        "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(drivers),
        "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
    }


def _resource_code(root):
    code = _mkdir(root, "resource-code")
    _write(code / "resources" / "execute_worker.py", "print('resource worker')\n")
    _write(code / "evidence" / "source_snapshot.py", "def file_sha256(path): return 'fixture'\n")
    return code


def _normalizer(root):
    prefix = str(root.resolve())

    def normalize(value):
        if isinstance(value, str):
            return value.replace(prefix, "$ROOT")
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize(child) for key, child in value.items()}
        return value

    return normalize


def rendered_golden_cases(root):
    normalize = _normalizer(root)
    cpu = _runtime(root, CURRENT_CPU_ROOTFS_NAME, "1" * 64)
    gpu = _runtime(root, CURRENT_GPU_ROOTFS_NAME, "2" * 64)
    metrics = _runtime(root, "metrics-rootfs-v2", "3" * 64, form="image")

    paths = {
        name: _mkdir(root, name)
        for name in (
            "code",
            "source",
            "output",
            "tmp-input",
            "tmp-writable",
            "srv-input",
            "resource-output",
            "stage-input",
            "native",
            "physical",
            "boxes",
            "scientific",
            "source-snapshots",
            "retained",
            "verifier",
        )
    }
    runtime_lock_path = _write(root / "runtime-lock.json", "{}\n")
    score_receipt = _write(root / "score-receipt.json", "{}\n")
    expected = _write(root / "expected.json", "{}\n")
    resource_code = _resource_code(root)

    cpu_plan = build_plan(
        cpu,
        code=paths["code"],
        source=paths["source"],
        output=paths["output"],
        named_inputs={"/srv/data": paths["srv-input"]},
        extra_environment={"EXTRA_FLAG": "1"},
        command=["python", "/experiment/train.py", "--epochs", "1"],
    )
    tmp_plan = build_plan(
        cpu,
        code=paths["code"],
        output=paths["output"],
        named_inputs={"/tmp/read-only": paths["tmp-input"]},
        writable_inputs={"/tmp/scratch": paths["tmp-writable"]},
        command=["python", "/experiment/tmp_worker.py"],
    )

    with patch.dict(os.environ, _gpu_environment(root), clear=False):
        gpu_plan = build_plan(
            gpu,
            code=paths["code"],
            output=paths["output"],
            gpu_index=1,
            command=["python", "/experiment/gpu_worker.py"],
        )
        sustained_plan = build_sustained_stage_plan(
            gpu,
            package=paths["code"],
            stage_source=paths["stage-input"],
            output=paths["output"],
            worker="audit_sustained_transition.py",
            native=paths["native"],
            physical=paths["physical"],
            boxes=paths["boxes"],
            runtime_lock_path=runtime_lock_path,
            scientific_root=paths["scientific"],
            source_snapshot_store=paths["source-snapshots"],
            extra={
                "/tmp/verifier": paths["verifier"],
                "/tmp/retained": paths["retained"],
            },
            gpu_index=1,
            source_snapshot_digest="4" * 64,
            scientific_root_digest="5" * 64,
        )

    split_rootfs = root / "split-rootfs"
    _write(split_rootfs / "usr" / "bin" / "python", "#!/bin/sh\n")
    _write(split_rootfs / "usr" / "lib" / "libfixture.so", "lib\n")
    _write(split_rootfs / "etc" / "issue", "split\n")
    os.symlink("usr/bin", split_rootfs / "bin")
    os.symlink("usr/lib", split_rootfs / "lib")
    for masked in ("dev", "proc", "tmp", "experiment", "outputs", "source"):
        (split_rootfs / masked).mkdir()
    split_runtime = RuntimeLock(
        rootfs=split_rootfs,
        lock_path=root / "split-rootfs.lock.json",
        data={"schema_version": 1, "rootfs_sha256": "6" * 64},
        form="recipe-digest",
        lock_sha256="6" * 64,
    )
    split_plan = build_plan(
        split_runtime,
        code=paths["code"],
        output=paths["output"],
        command=["python", "/experiment/split_worker.py"],
        split_runtime_root=True,
    )

    base_worker_plan = build_plan(
        cpu,
        code=paths["code"],
        output=paths["output"],
        command=["python", "/experiment/worker.py"],
    )
    wrapped_plan, worker_argv = wrap_resource_plan(
        base_worker_plan,
        resource_code,
        paths["resource-output"],
    )
    with_mounts_plan = with_mounts(
        base_worker_plan,
        before_devices=[
            Mount("resource-layer", "bind", "/tmp/resource-layer", "read_only", resource_code),
            Mount(
                "resource-experiment-resources",
                "bind",
                "/experiment/resources",
                "read_only",
                resource_code / "resources",
            ),
            Mount(
                "resource-experiment-evidence",
                "bind",
                "/experiment/evidence",
                "read_only",
                resource_code / "evidence",
            ),
            Mount("resource-output", "bind", "/tmp/resource-output", "writable", paths["resource-output"]),
        ],
        command=[
            "python",
            "/tmp/resource-layer/resources/execute_worker.py",
            "/tmp/resource-output",
            "/experiment/worker.py",
        ],
    )
    wrapped_rendered, wrapped_rendered_worker = wrap_rendered_plan_command(
        render_plan(base_worker_plan),
        resource_code,
        paths["resource-output"],
    )

    gpu_record = record_launch_plan(gpu_plan)
    driver_mounts = {
        mount["role"]: mount["digest"]
        for mount in gpu_record["mounts"]
        if mount["role"].startswith("gpu-driver:")
    }
    sustained_record = record_sustained_plan(sustained_plan)
    sustained_scientific = next(
        mount for mount in sustained_record["mounts"] if mount["inside_path"] == "/tmp/scientific"
    )

    cases = {
        "cpu": {"argv": render_plan(cpu_plan)},
        "gpu_with_driver_pins": {
            "argv": render_plan(gpu_plan),
            "driver_mount_digests": driver_mounts,
            "gpu": gpu_record["gpu"],
        },
        "split_runtime_symlink_rootfs": {"argv": render_plan(split_plan)},
        "tmpfs_with_tmp_children": {"argv": render_plan(tmp_plan)},
        "resource_wrap_resource_plan": {
            "argv": render_plan(wrapped_plan),
            "worker_argv": worker_argv,
        },
        "resource_with_mounts": {"argv": render_plan(with_mounts_plan)},
        "resource_wrap_rendered_plan_command": {
            "argv": wrapped_rendered,
            "worker_argv": wrapped_rendered_worker,
        },
        "sustained_stage": {
            "argv": render_plan(sustained_plan),
            "gpu": sustained_record["gpu"],
            "scientific_digest": sustained_scientific["digest"],
        },
    }
    return normalize(cases)


class LaunchPlanGoldenTests(unittest.TestCase):
    def test_rendered_argv_matches_base_commit_goldens(self):
        with tempfile.TemporaryDirectory() as temporary:
            actual = rendered_golden_cases(Path(temporary))

        self.assertEqual(set(actual), set(GOLDEN_CASES))
        for name in GOLDEN_CASES:
            with self.subTest(name=name):
                self.assertEqual(actual[name], GOLDEN_CASES[name])


if __name__ == "__main__":
    unittest.main()
