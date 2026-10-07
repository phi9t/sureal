import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from insula.runtime_identity import rootfs_identity


REPO = Path(__file__).resolve().parents[2]
AUTONOMY = REPO / "autonomy"
WRAPPER = REPO / "bazelw"


def write_rootfs(root):
    for name in (
        "bazel-cache",
        "etc",
        "experiment",
        "opt/waymo/bin",
        "outputs",
        "tmp",
        "usr/bin",
        "usr/local/bin",
    ):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "etc/resolv.conf").write_text("nameserver 127.0.0.1\n")
    (root / "usr/local/bin/python").write_text("#!/bin/sh\n")
    (root / "usr/local/bin/python").chmod(0o755)
    (root / "opt/waymo/bin/python").write_text("#!/bin/sh\n")
    (root / "opt/waymo/bin/python").chmod(0o755)
    (root / "usr/local/bin/bazel").write_text("#!/bin/sh\n")
    (root / "usr/local/bin/bazel").chmod(0o755)


def write_lock(lock, root, rootfs_sha256=None):
    lock.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rootfs_sha256": rootfs_sha256 or rootfs_identity(root),
                "bazel_version": "9.2.0",
            },
            indent=2,
        )
        + "\n"
    )


def write_fake_bwrap(fakebin, marker):
    fakebin.mkdir()
    script = f"""
        #!/usr/bin/env bash
        printf 'bwrap ran\\n' > {marker}
        exit 19
    """
    path = fakebin / "bwrap"
    path.write_text(textwrap.dedent(script).lstrip())
    path.chmod(0o755)


def has_mount_to(mounts, destination):
    return any(len(mount) == 3 and mount[0] == "--ro-bind" and mount[2] == destination for mount in mounts)


class BazelWrapperTests(unittest.TestCase):
    def test_external_cwd_and_symlink_preserve_relative_options_and_environment(self):
        for options in ("arguments", "environment"):
            for symlink in (False, True):
                with self.subTest(options=options, symlink=symlink), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary).resolve()
                    rootfs = root / "root fs"
                    write_rootfs(rootfs)
                    lock = root / "rootfs lock.json"
                    write_lock(lock, rootfs)
                    cache = root / "cache directory"
                    marker = root / "bwrap-ran"
                    fakebin = root / "fakebin"
                    write_fake_bwrap(fakebin, marker)
                    env = os.environ.copy()
                    env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
                    env["PYTHONSAFEPATH"] = "1"
                    settings = {
                        "SUREAL_BAZEL_ROOTFS": rootfs.name,
                        "SUREAL_BAZEL_ROOTFS_LOCK": lock.name,
                        "SUREAL_BAZEL_CACHE": cache.name,
                    }
                    for name in settings:
                        env.pop(name, None)
                    arguments = []
                    if options == "environment":
                        env.update(settings)
                    else:
                        arguments = ["--rootfs", rootfs.name, "--lock", lock.name, "--cache", cache.name]
                    entry = WRAPPER
                    if symlink:
                        entry = root / "linked-bazelw"
                        entry.symlink_to(WRAPPER)
                    result = subprocess.run(
                        [str(entry), "--emit-plan", *arguments, "test", "//autonomy/..."],
                        cwd=root, env=env, text=True, capture_output=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    plan = json.loads(result.stdout)
                    self.assertEqual(plan["rootfs"], str(rootfs))
                    self.assertEqual(plan["lock"], str(lock))
                    self.assertEqual(plan["cache"], str(cache))
                    self.assertIn(["--ro-bind", str(AUTONOMY.resolve()), "/experiment/autonomy"], plan["mounts"])
                    self.assertFalse(marker.exists())
                    result = subprocess.run(
                        [str(entry), *arguments, "test", "//autonomy/..."],
                        cwd=root, env=env, text=True, capture_output=True,
                    )
                    self.assertEqual(result.returncode, 19, result.stdout + result.stderr)
                    self.assertEqual(marker.read_text(), "bwrap ran\n")
                    self.assertTrue((cache / "output-base").is_dir())

    def test_implementation_import_does_not_change_cwd_or_launch_processes(self):
        code = """
from unittest.mock import patch
with patch('os.chdir', side_effect=AssertionError('import changed cwd')):
    with patch('os.execvp', side_effect=AssertionError('import launched a process')):
        import insula.bazel_launcher
"""
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=AUTONOMY,
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def run_wrapper(self, temporary, *arguments, wrong_identity=False):
        root = Path(temporary)
        rootfs = root / "rootfs"
        rootfs.mkdir()
        write_rootfs(rootfs)
        lock = root / "rootfs.lock.json"
        write_lock(lock, rootfs, "0" * 64 if wrong_identity else None)
        cache = root / "cache"
        fakebin = root / "fakebin"
        marker = root / "bwrap-ran"
        write_fake_bwrap(fakebin, marker)
        env = os.environ.copy()
        env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
        env["SUREAL_BAZEL_ROOTFS"] = str(rootfs)
        env["SUREAL_BAZEL_ROOTFS_LOCK"] = str(lock)
        env["SUREAL_BAZEL_CACHE"] = str(cache)
        result = subprocess.run(
            [str(WRAPPER), *arguments],
            cwd=REPO,
            env=env,
            text=True,
            capture_output=True,
        )
        return result, marker, cache, rootfs, lock

    def run_wrapper_with_default_roots(self, temporary, *arguments, extra_env=None):
        root = Path(temporary)
        home = root / "home"
        waymo_rootfs = home / ".cache/waystone/waymo-perception/insula/rootfs-v4"
        curriculum_rootfs = home / ".cache/waystone/3d-pathway/insula/rootfs-v2"
        gpu_rootfs = home / ".cache/waystone/waymo-perception/gpu-rootfs-v6"
        for rootfs in (waymo_rootfs, curriculum_rootfs, gpu_rootfs):
            rootfs.mkdir(parents=True)
            write_rootfs(rootfs)
            write_lock(rootfs.with_name(rootfs.name + ".lock.json"), rootfs)
        cache = root / "cache"
        fakebin = root / "fakebin"
        marker = root / "bwrap-ran"
        write_fake_bwrap(fakebin, marker)
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
        env["SUREAL_BAZEL_CACHE"] = str(cache)
        if extra_env:
            env.update(extra_env)
        env.pop("SUREAL_BAZEL_ROOTFS", None)
        env.pop("SUREAL_BAZEL_ROOTFS_LOCK", None)
        result = subprocess.run(
            [str(WRAPPER), *arguments],
            cwd=REPO,
            env=env,
            text=True,
            capture_output=True,
        )
        return result, marker, cache, waymo_rootfs, curriculum_rootfs, gpu_rootfs

    def test_emit_plan_prints_sandbox_command_data_without_running_bwrap(self):
        self.assertTrue(WRAPPER.is_file(), "repository-level Bazel wrapper is missing")
        with tempfile.TemporaryDirectory() as temporary:
            result, marker, cache, rootfs, lock = self.run_wrapper(
                temporary,
                "--emit-plan",
                "test",
                "//autonomy:source_snapshot_targets_test",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = json.loads(result.stdout)
            argv = plan["argv"]
            self.assertEqual(argv[0], "bwrap")
            self.assertIn("--clearenv", argv)
            self.assertIn("--die-with-parent", argv)
            self.assertNotIn("--unshare-net", argv)
            self.assertEqual(
                argv[argv.index("--ro-bind") + 1 : argv.index("--ro-bind") + 3],
                [str(rootfs.resolve()), "/"],
            )
            self.assertIn(["--tmpfs", "/experiment"], plan["mounts"])
            self.assertIn(["--ro-bind", str((REPO / "MODULE.bazel").resolve()), "/experiment/MODULE.bazel"], plan["mounts"])
            self.assertIn(["--ro-bind", str(AUTONOMY.resolve()), "/experiment/autonomy"], plan["mounts"])
            self.assertTrue(has_mount_to(plan["mounts"], "/experiment/training_execution"), plan["mounts"])
            self.assertTrue(has_mount_to(plan["mounts"], "/experiment/evaluation"), plan["mounts"])
            self.assertTrue(has_mount_to(plan["mounts"], "/experiment/retention"), plan["mounts"])
            self.assertIn(["--bind", str(cache.resolve()), "/tmp/bazel-cache"], plan["mounts"])
            self.assertIn(["--tmpfs", "/outputs"], plan["mounts"])
            self.assertIn(["--tmpfs", "/tmp"], plan["mounts"])
            self.assertNotIn(["--bind", str(cache.resolve()), "/outputs"], plan["mounts"])
            self.assertIn(["--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf"], plan["mounts"])
            self.assertIn(["--setenv", "HOME", "/tmp/bazel-cache/home"], plan["environment"])
            self.assertNotIn(
                ["--setenv", "PYTHONPATH", "/experiment/autonomy"],
                plan["environment"],
            )
            self.assertIn("--output_base=/tmp/bazel-cache/output-base", plan["bazel"])
            self.assertNotIn("--enable_workspace", plan["bazel"])
            self.assertNotIn("--noenable_bzlmod", plan["bazel"])
            self.assertNotIn("--repositories_without_autoloads=*", plan["bazel"])
            self.assertIn("--ignore_dev_dependency", plan["bazel"])
            self.assertIn("--lockfile_mode=error", plan["bazel"])
            self.assertIn("--repository_cache=/tmp/bazel-cache/repository-cache", plan["bazel"])
            self.assertIn("--disk_cache=/tmp/bazel-cache/disk-cache", plan["bazel"])
            self.assertEqual(plan["lock"], str(lock.resolve()))
            self.assertFalse(marker.exists())

    def test_update_lock_plan_makes_only_the_module_lock_writable(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, marker, _, _, _ = self.run_wrapper(
                temporary,
                "--emit-plan",
                "--update-lock",
                "test",
                "//autonomy:source_snapshot_targets_test",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = json.loads(result.stdout)
            self.assertIn("--ignore_dev_dependency", plan["bazel"])
            self.assertIn("--lockfile_mode=update", plan["bazel"])
            self.assertNotIn("--lockfile_mode=error", plan["bazel"])
            self.assertIn(
                ["--bind", str((REPO / "MODULE.bazel.lock").resolve()), "/experiment/MODULE.bazel.lock"],
                plan["mounts"],
            )
            self.assertIn(["--tmpfs", "/experiment"], plan["mounts"])
            self.assertIn(["--ro-bind", str((REPO / "MODULE.bazel").resolve()), "/experiment/MODULE.bazel"], plan["mounts"])
            self.assertFalse(marker.exists())

    def test_rootfs_identity_mismatch_is_rejected_before_bwrap_runs(self):
        self.assertTrue(WRAPPER.is_file(), "repository-level Bazel wrapper is missing")
        with tempfile.TemporaryDirectory() as temporary:
            result, marker, _, _, _ = self.run_wrapper(
                temporary,
                "test",
                "//autonomy:source_snapshot_targets_test",
                wrong_identity=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("rootfs content does not match rootfs lock", result.stderr)
            self.assertFalse(marker.exists())

    def test_parallax_targets_select_the_curriculum_rootfs(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, marker, _, waymo_rootfs, curriculum_rootfs, _ = self.run_wrapper_with_default_roots(
                temporary,
                "--emit-plan",
                "test",
                "//parallax:test_classical",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["rootfs"], str(curriculum_rootfs.resolve()))
            self.assertNotEqual(plan["rootfs"], str(waymo_rootfs.resolve()))
            self.assertIn(
                ["--ro-bind", str(curriculum_rootfs.resolve()), "/"],
                plan["mounts"],
            )
            self.assertIn(["--ro-bind", str((REPO / "parallax").resolve()), "/experiment/parallax"], plan["mounts"])
            self.assertFalse(has_mount_to(plan["mounts"], "/experiment/3d-pathway"), plan["mounts"])
            self.assertIn("--output_base=/tmp/bazel-cache/output-base-3d-pathway", plan["bazel"])
            self.assertNotIn("--output_base=/tmp/bazel-cache/output-base", plan["bazel"])
            self.assertFalse(marker.exists())

    def test_cuda_config_selects_gpu_rootfs_and_projects_driver_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            devices = root / "devices"
            devices.mkdir()
            device_pairs = []
            for guest in ("/dev/nvidia1", "/dev/nvidiactl", "/dev/nvidia-uvm"):
                host = devices / Path(guest).name
                host.write_text("")
                device_pairs.append(f"{host}={guest}")
            driver_dir = root / "driver-libs"
            driver_dir.mkdir()
            for name in (
                "libcuda.so",
                "libcuda.so.1",
                "libcuda.so.580.105.08",
                "libnvidia-ptxjitcompiler.so",
                "libnvidia-ptxjitcompiler.so.1",
                "libnvidia-ptxjitcompiler.so.580.105.08",
                "libnvidia-nvvm.so",
                "libnvidia-nvvm.so.4",
                "libnvidia-nvvm.so.580.105.08",
            ):
                (driver_dir / name).write_text(name)

            result, marker, _, waymo_rootfs, _, gpu_rootfs = self.run_wrapper_with_default_roots(
                temporary,
                "--emit-plan",
                "test",
                "--config=cuda",
                "//autonomy:advanced__test_models",
                extra_env={
                    "SUREAL_BAZEL_GPU_DEVICES": ",".join(device_pairs),
                    "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(driver_dir),
                },
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["rootfs"], str(gpu_rootfs.resolve()))
            self.assertNotEqual(plan["rootfs"], str(waymo_rootfs.resolve()))
            self.assertIn(["--ro-bind", str(gpu_rootfs.resolve()), "/"], plan["mounts"])
            self.assertIn(["--tmpfs", "/experiment"], plan["mounts"])
            self.assertTrue(has_mount_to(plan["mounts"], "/experiment/training_execution"), plan["mounts"])
            self.assertTrue(has_mount_to(plan["mounts"], "/experiment/evaluation"), plan["mounts"])
            self.assertTrue(has_mount_to(plan["mounts"], "/experiment/retention"), plan["mounts"])
            self.assertIn("--output_base=/tmp/bazel-cache/output-base-gpu", plan["bazel"])
            self.assertIn("--config=cuda", plan["bazel"])
            self.assertIn(["--tmpfs", "/driver"], plan["mounts"])
            for pair in device_pairs:
                host, guest = pair.split("=", 1)
                self.assertIn(["--dev-bind", host, guest], plan["mounts"])
            self.assertIn(
                ["--ro-bind", str((driver_dir / "libcuda.so").resolve()), "/driver/libcuda.so"],
                plan["mounts"],
            )
            self.assertIn(
                [
                    "--ro-bind",
                    str((driver_dir / "libnvidia-ptxjitcompiler.so.580.105.08").resolve()),
                    "/driver/libnvidia-ptxjitcompiler.so.580.105.08",
                ],
                plan["mounts"],
            )
            self.assertIn(
                ["--setenv", "PATH", "/opt/waymo/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"],
                plan["environment"],
            )
            self.assertIn(
                ["--setenv", "LD_LIBRARY_PATH", "/driver:/usr/local/cuda/lib64"],
                plan["environment"],
            )
            self.assertIn(["--setenv", "CUDA_VISIBLE_DEVICES", "0"], plan["environment"])

    def test_broad_target_pattern_is_rejected_before_selecting_one_rootfs(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, marker, _, _, _, _ = self.run_wrapper_with_default_roots(
                temporary,
                "--emit-plan",
                "test",
                "//...",
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(
                "target pattern spans autonomy and parallax",
                result.stderr,
            )
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
