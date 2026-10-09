import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence.source_snapshot import file_sha256
from insula.launch_plan import (
    BAZEL_LINUX_X86_64_SHA256,
    BAZEL_VERSION,
    PlanError,
    RuntimeLockError,
    build_plan,
    load_runtime_lock,
    plan_data,
    record_plan,
    render_plan,
)
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import (
    CURRENT_CPU_ROOTFS_NAME,
    CURRENT_GPU_ROOTFS_NAME,
    CURRENT_MOTION_CLI_ROOTFS_NAME,
)


AUTONOMY = Path(__file__).resolve().parents[1]


def write_rootfs(root: Path):
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/python").write_text("#!/bin/sh\n")
    (root / "bin/python").chmod(0o755)
    (root / "etc").mkdir()
    (root / "etc/issue").write_text("fixture rootfs\n")


def write_cpu_recipe_lock(path: Path, rootfs: Path, **overrides):
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
    lock.update(overrides)
    path.write_text(json.dumps(lock, indent=2) + "\n")
    return lock


def write_gpu_recipe_lock(path: Path, rootfs: Path, **overrides):
    lock = {
        "schema_version": 1,
        "rootfs_sha256": rootfs_identity(rootfs),
        "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile.gpu-bazel-rootfs-v6"),
        "requirements_sha256": file_sha256(AUTONOMY / "insula/gpu-requirements.lock"),
        "bazel_version": BAZEL_VERSION,
        "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
    }
    lock.update(overrides)
    path.write_text(json.dumps(lock, indent=2) + "\n")
    return lock


def write_motion_cli_lock(path: Path, rootfs: Path, **overrides):
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
    lock.update(overrides)
    path.write_text(json.dumps(lock, indent=2) + "\n")
    return lock


class RuntimeLockTests(unittest.TestCase):
    def test_missing_runtime_lock_is_an_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            rootfs = Path(temporary) / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            with self.assertRaisesRegex(RuntimeLockError, "runtime lock"):
                load_runtime_lock(rootfs, Path(temporary) / "missing.lock.json")

    def test_recipe_digest_form_checks_every_declared_field(self):
        cases = {
            "schema_version": {"schema_version": 2},
            "rootfs_sha256": {"rootfs_sha256": "0" * 64},
            "dockerfile_sha256": {"dockerfile_sha256": "0" * 64},
            "requirements_sha256": {"requirements_sha256": "0" * 64},
            "test_tools_requirements_sha256": {"test_tools_requirements_sha256": "0" * 64},
            "bazel_version": {"bazel_version": "0.0.0"},
            "bazel_linux_x86_64_sha256": {"bazel_linux_x86_64_sha256": "0" * 64},
        }
        with tempfile.TemporaryDirectory() as temporary:
            rootfs = Path(temporary) / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock_path = rootfs.with_name(rootfs.name + ".lock.json")
            write_cpu_recipe_lock(lock_path, rootfs)

            runtime = load_runtime_lock(rootfs, lock_path)
            self.assertEqual(runtime.form, "recipe-digest")
            self.assertEqual(runtime.data["rootfs_sha256"], rootfs_identity(rootfs))

            for field, override in cases.items():
                with self.subTest(field=field):
                    write_cpu_recipe_lock(lock_path, rootfs, **override)
                    with self.assertRaisesRegex(RuntimeLockError, field):
                        load_runtime_lock(rootfs, lock_path)

    def test_image_form_checks_recipe_parent_image_and_content(self):
        cases = {
            "image_id": {"image_id": ""},
            "rootfs_sha256": {"rootfs_sha256": "0" * 64},
            "recipe_hashes": {"recipe_hashes": {"Dockerfile": "0" * 64}},
            "parent_image_id": {"parent_image_id": "sha256:" + "2" * 64},
        }
        with tempfile.TemporaryDirectory() as temporary:
            rootfs = Path(temporary) / CURRENT_MOTION_CLI_ROOTFS_NAME
            write_rootfs(rootfs)
            lock_path = rootfs.with_name(rootfs.name + ".lock.json")
            write_motion_cli_lock(lock_path, rootfs)

            runtime = load_runtime_lock(rootfs, lock_path)
            self.assertEqual(runtime.form, "image")

            for field, override in cases.items():
                with self.subTest(field=field):
                    write_motion_cli_lock(lock_path, rootfs, **override)
                    with self.assertRaisesRegex(RuntimeLockError, field):
                        load_runtime_lock(rootfs, lock_path)

    def test_content_digest_is_cached_per_rootfs_path_and_lock_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            rootfs = Path(temporary) / CURRENT_CPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock_path = rootfs.with_name(rootfs.name + ".lock.json")
            lock = write_cpu_recipe_lock(lock_path, rootfs)
            expected = lock["rootfs_sha256"]

            with patch("insula.launch_plan.rootfs_identity", return_value=expected) as identity:
                load_runtime_lock(rootfs, lock_path)
                load_runtime_lock(rootfs, lock_path)
                self.assertEqual(identity.call_count, 1)

                lock["note"] = "same rootfs, new lock digest"
                lock_path.write_text(json.dumps(lock, indent=2) + "\n")
                load_runtime_lock(rootfs, lock_path)
                self.assertEqual(identity.call_count, 2)


class LaunchPlanTests(unittest.TestCase):
    def load_fixture_runtime(self, root: Path):
        rootfs = root / CURRENT_CPU_ROOTFS_NAME
        write_rootfs(rootfs)
        lock = rootfs.with_name(rootfs.name + ".lock.json")
        write_cpu_recipe_lock(lock, rootfs)
        return load_runtime_lock(rootfs, lock)

    def test_plan_is_readable_as_data_and_rendered_only_at_the_edge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            source = root / "source"
            output = root / "output"
            extra = root / "extra"
            for path in (code, source, output, extra):
                path.mkdir()
            (code / "main.py").write_text("print('ok')\n")
            (source / "input.txt").write_text("input\n")
            (extra / "table.txt").write_text("table\n")

            plan = build_plan(
                runtime,
                code=code,
                source=source,
                output=output,
                named_inputs={"/tmp/tables": extra},
                extra_environment={"EXTRA_FLAG": "1"},
                command=["python", "main.py"],
            )
            data = plan_data(plan)

            self.assertEqual(data["runtime"]["form"], "recipe-digest")
            self.assertEqual(data["working_directory"], "/experiment")
            self.assertEqual(data["command"], ["python", "main.py"])
            self.assertIn(
                {
                    "role": "code",
                    "host_path": str(code.resolve()),
                    "inside_path": "/experiment",
                    "mode": "read_only",
                    "kind": "bind",
                },
                data["mounts"],
            )
            self.assertIn(["--setenv", "PYTHONPATH", "/experiment"], data["environment"])
            self.assertIn(["--setenv", "EXTRA_FLAG", "1"], data["environment"])

            argv = render_plan(plan)
            self.assertEqual(argv[0], "bwrap")
            self.assertIn("--clearenv", argv)
            self.assertIn("/tmp/tables", argv)
            self.assertEqual(argv[-2:], ["python", "main.py"])

    def test_receipt_record_has_digests_without_host_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            output = root / "output"
            fixture = root / "fixture"
            for path in (code, output, fixture):
                path.mkdir()
            (code / "main.py").write_text("print('ok')\n")
            (fixture / "data.txt").write_text("data\n")

            plan = build_plan(
                runtime,
                code=code,
                output=output,
                named_inputs={"/tmp/fixture": fixture},
                command=["python", "main.py"],
            )
            record = record_plan(plan)
            raw = json.dumps(record, sort_keys=True)

            self.assertEqual(record["runtime"]["lock_sha256"], runtime.lock_sha256)
            self.assertEqual(record["runtime"]["form"], "recipe-digest")
            self.assertNotIn(str(root), raw)
            mounts = {mount["role"]: mount for mount in record["mounts"]}
            self.assertRegex(mounts["code"]["digest"], r"^[0-9a-f]{64}$")
            self.assertRegex(mounts["input:/tmp/fixture"]["digest"], r"^[0-9a-f]{64}$")
            self.assertNotIn("digest", mounts["output"])
            self.assertEqual(record["command"], ["python", "main.py"])

    def test_mount_rules_name_the_colliding_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            source = root / "source"
            output = root / "output"
            writable = output / "scratch"
            for path in (code, source, output, writable):
                path.mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "code.*source|source.*code"):
                build_plan(runtime, code=code, source=code, output=output, command=["true"])

            with self.assertRaisesRegex(ValueError, "output.*input:/tmp/scratch|input:/tmp/scratch.*output"):
                build_plan(
                    runtime,
                    code=code,
                    source=source,
                    output=output,
                    writable_inputs={"/tmp/scratch": writable},
                    command=["true"],
                )

    def test_readonly_mounts_may_nest_and_named_inputs_are_restricted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            source = code / "source"
            output = root / "output"
            bad_input = root / "bad"
            for path in (source, output, bad_input):
                path.mkdir(parents=True)

            plan = build_plan(runtime, code=code, source=source, output=output, command=["true"])
            self.assertEqual(plan_data(plan)["command"], ["true"])

            with self.assertRaisesRegex(ValueError, "/home/input"):
                build_plan(
                    runtime,
                    code=code,
                    output=output,
                    named_inputs={"/home/input": bad_input},
                    command=["true"],
                )

    def test_extra_environment_cannot_replace_module_owned_variables(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.load_fixture_runtime(root)
            code = root / "code"
            output = root / "output"
            code.mkdir()
            output.mkdir()

            with self.assertRaisesRegex(ValueError, "PATH"):
                build_plan(
                    runtime,
                    code=code,
                    output=output,
                    extra_environment={"PATH": "/tmp/bin"},
                    command=["true"],
                )

    def test_gpu_plan_uses_requested_device_only_and_records_uuid_not_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_GPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_gpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)

            code = root / "code"
            output = root / "output"
            devices = root / "devices"
            driver_dir = root / "driver-libs"
            for path in (code, output, devices, driver_dir):
                path.mkdir()
            device_pairs = []
            for guest in ("/dev/nvidia1", "/dev/nvidiactl", "/dev/nvidia-uvm"):
                host = devices / Path(guest).name
                host.write_text("")
                device_pairs.append(f"{host}={guest}")
            for name in (
                "libcuda.so",
                "libnvidia-ptxjitcompiler.so",
                "libnvidia-nvvm.so",
            ):
                (driver_dir / name).write_text(name)

            environment = {
                "SUREAL_BAZEL_GPU_DEVICES": ",".join(device_pairs),
                "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(driver_dir),
                "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
            }
            with patch.dict(os.environ, environment, clear=False):
                plan = build_plan(
                    runtime,
                    code=code,
                    output=output,
                    gpu_index=1,
                    command=["python", "-c", "pass"],
                )

            data = plan_data(plan)
            self.assertEqual(
                data["devices"],
                [
                    {
                        "role": "gpu-device:/dev/nvidia1",
                        "host_path": str((devices / "nvidia1").resolve()),
                        "inside_path": "/dev/nvidia1",
                        "mode": "writable",
                        "kind": "dev-bind",
                    },
                    {
                        "role": "gpu-device:/dev/nvidiactl",
                        "host_path": str((devices / "nvidiactl").resolve()),
                        "inside_path": "/dev/nvidiactl",
                        "mode": "writable",
                        "kind": "dev-bind",
                    },
                    {
                        "role": "gpu-device:/dev/nvidia-uvm",
                        "host_path": str((devices / "nvidia-uvm").resolve()),
                        "inside_path": "/dev/nvidia-uvm",
                        "mode": "writable",
                        "kind": "dev-bind",
                    },
                ],
            )
            self.assertNotIn("/dev/nvidia0", json.dumps(data, sort_keys=True))
            self.assertIn(["--setenv", "CUDA_VISIBLE_DEVICES", "0"], data["environment"])
            self.assertEqual(
                data["gpu"],
                {"requested_index": 1, "device_uuid": "GPU-fixture-1"},
            )

            record = record_plan(plan)
            self.assertEqual(
                record["gpu"],
                {"requested_index": 1, "device_uuid": "GPU-fixture-1"},
            )
            raw_record = json.dumps(record, sort_keys=True)
            self.assertNotIn(str(devices), raw_record)
            self.assertNotIn("/dev/nvidia", raw_record)

    def test_gpu_device_override_rejects_different_gpu_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_GPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_gpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)

            code = root / "code"
            output = root / "output"
            devices = root / "devices"
            driver_dir = root / "driver-libs"
            for path in (code, output, devices, driver_dir):
                path.mkdir()
            for name in ("nvidia1", "nvidiactl", "nvidia-uvm"):
                (devices / name).write_text("")
            for name in (
                "libcuda.so",
                "libnvidia-ptxjitcompiler.so",
                "libnvidia-nvvm.so",
            ):
                (driver_dir / name).write_text(name)

            valid_control = [
                f"{devices / 'nvidiactl'}=/dev/nvidiactl",
                f"{devices / 'nvidia-uvm'}=/dev/nvidia-uvm",
            ]
            cases = {
                "guest": [
                    f"{devices / 'nvidia1'}=/dev/nvidia0",
                    *valid_control,
                ],
                "host": [
                    f"/dev/nvidia0=/dev/nvidia1",
                    *valid_control,
                ],
            }
            for side, device_pairs in cases.items():
                with self.subTest(side=side):
                    environment = {
                        "SUREAL_BAZEL_GPU_DEVICES": ",".join(device_pairs),
                        "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(driver_dir),
                        "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
                    }
                    with patch.dict(os.environ, environment, clear=False):
                        with self.assertRaisesRegex(PlanError, "/dev/nvidia0"):
                            build_plan(
                                runtime,
                                code=code,
                                output=output,
                                gpu_index=1,
                                command=["python", "-c", "pass"],
                            )

    def test_gpu_device_override_accepts_remapped_host_paths_for_requested_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rootfs = root / CURRENT_GPU_ROOTFS_NAME
            write_rootfs(rootfs)
            lock = rootfs.with_name(rootfs.name + ".lock.json")
            write_gpu_recipe_lock(lock, rootfs)
            runtime = load_runtime_lock(rootfs, lock)

            code = root / "code"
            output = root / "output"
            devices = root / "remapped-devices"
            driver_dir = root / "driver-libs"
            for path in (code, output, devices, driver_dir):
                path.mkdir()
            device_pairs = []
            remaps = {
                "/dev/nvidia1": "gpu-one",
                "/dev/nvidiactl": "ctl",
                "/dev/nvidia-uvm": "uvm",
                "/dev/nvidia-uvm-tools": "uvm-tools",
                "/dev/nvidia-modeset": "modeset",
            }
            for guest, host_name in remaps.items():
                host = devices / host_name
                host.write_text("")
                device_pairs.append(f"{host}={guest}")
            for name in (
                "libcuda.so",
                "libnvidia-ptxjitcompiler.so",
                "libnvidia-nvvm.so",
            ):
                (driver_dir / name).write_text(name)

            environment = {
                "SUREAL_BAZEL_GPU_DEVICES": ",".join(device_pairs),
                "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(driver_dir),
                "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
            }
            with patch.dict(os.environ, environment, clear=False):
                plan = build_plan(
                    runtime,
                    code=code,
                    output=output,
                    gpu_index=1,
                    command=["python", "-c", "pass"],
                )

            data = plan_data(plan)
            devices_by_inside = {
                device["inside_path"]: device["host_path"] for device in data["devices"]
            }
            self.assertEqual(
                devices_by_inside,
                {guest: str((devices / host_name).resolve()) for guest, host_name in remaps.items()},
            )
            self.assertEqual(data["gpu"], {"requested_index": 1, "device_uuid": "GPU-fixture-1"})


if __name__ == "__main__":
    unittest.main()
