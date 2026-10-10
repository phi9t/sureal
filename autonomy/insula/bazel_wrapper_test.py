import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from evidence.source_snapshot import file_sha256
from insula import bazel_launcher
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION
from insula.bazel_launcher import LIVE_GATE_BWRAP, LIVE_GATE_CACHE_MOUNT
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import (
    CURRENT_GPU_ROOTFS_NAME,
    current_cpu_rootfs,
    current_curriculum_rootfs,
    current_gpu_rootfs,
)


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
    root = Path(root)
    if root.name == CURRENT_GPU_ROOTFS_NAME:
        recipe = {
            "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile.gpu-bazel-rootfs-v6"),
            "requirements_sha256": file_sha256(AUTONOMY / "insula/gpu-requirements.lock"),
        }
    elif root.name == "rootfs-v2" and "3d-pathway" in root.as_posix():
        recipe = {
            "dockerfile_sha256": file_sha256(REPO / "parallax/insulas/bazel-rootfs.Dockerfile"),
            "requirements_sha256": file_sha256(REPO / "parallax/insulas/bazel-requirements.lock"),
        }
    else:
        recipe = {
            "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile"),
            "requirements_sha256": file_sha256(AUTONOMY / "requirements-tracer.lock"),
            "test_tools_requirements_sha256": file_sha256(
                AUTONOMY / "insula/cpu-test-tools-requirements.lock"
            ),
        }
    lock.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rootfs_sha256": rootfs_sha256 or rootfs_identity(root),
                "bazel_version": BAZEL_VERSION,
                "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
                **recipe,
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


def has_mount(mounts, destination, *, host=None, mode=None, kind=None):
    for mount in mounts:
        if mount.get("inside_path") != destination:
            continue
        if host is not None and mount.get("host_path") != host:
            continue
        if mode is not None and mount.get("mode") != mode:
            continue
        if kind is not None and mount.get("kind") != kind:
            continue
        return True
    return False


LEGACY_AUTONOMY_ALIAS_DESTINATIONS = {
    "/experiment/association",
    "/experiment/camera",
    "/experiment/dataset",
    "/experiment/detection",
    "/experiment/evaluation",
    "/experiment/evidence",
    "/experiment/geometry",
    "/experiment/inspection",
    "/experiment/insula",
    "/experiment/motion",
    "/experiment/range_view",
    "/experiment/research",
    "/experiment/resources",
    "/experiment/retention",
    "/experiment/segmentation",
    "/experiment/studies",
    "/experiment/training_execution",
}


def mount_destinations(mounts):
    return {mount["inside_path"] for mount in mounts}


def repository_git_dir():
    path = REPO / ".git"
    if path.is_dir():
        return path.resolve()
    content = path.read_text(encoding="utf-8").strip()
    prefix = "gitdir: "
    if content.startswith(prefix):
        git_dir = Path(content[len(prefix):])
        if not git_dir.is_absolute():
            git_dir = path.parent / git_dir
        return git_dir.resolve()
    return path.resolve()


def launcher_git_dirs():
    git_dir = bazel_launcher._git_dir(bazel_launcher.REPO / ".git")
    if not git_dir.is_dir():
        return git_dir, git_dir, bazel_launcher.REPO_GATE_GIT_DIR
    common_dir = bazel_launcher._git_common_dir(git_dir)
    git_dir_inside = bazel_launcher._git_dir_inside_path(git_dir, common_dir)
    return git_dir, common_dir, git_dir_inside or bazel_launcher.REPO_GATE_GIT_DIR


def has_symlink_mount(mounts, destination, *, target, mode=None):
    for mount in mounts:
        if mount.get("inside_path") != destination:
            continue
        if mount.get("kind") != "symlink":
            continue
        if mount.get("symlink_target") != target:
            continue
        if mode is not None and mount.get("mode") != mode:
            continue
        return True
    return False


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
                    self.assertTrue(
                        has_mount(
                            plan["mounts"],
                            "/experiment/autonomy",
                            host=str(AUTONOMY.resolve()),
                            mode="read_only",
                        )
                    )
                    self.assertFalse(
                        LEGACY_AUTONOMY_ALIAS_DESTINATIONS & mount_destinations(plan["mounts"]),
                        plan["mounts"],
                    )
                    git_dir, common_dir, git_dir_inside = launcher_git_dirs()
                    if git_dir_inside == bazel_launcher.REPO_GATE_GIT_DIR:
                        self.assertTrue(
                            has_mount(
                                plan["mounts"],
                                bazel_launcher.REPO_GATE_GIT_DIR,
                                host=str(repository_git_dir()),
                                mode="read_only",
                                kind="bind",
                            ),
                            plan["mounts"],
                        )
                    else:
                        self.assertTrue(
                            has_mount(
                                plan["mounts"],
                                bazel_launcher.REPO_GATE_GIT_COMMON_DIR,
                                host=str(common_dir),
                                mode="read_only",
                                kind="bind",
                            ),
                            plan["mounts"],
                        )
                        self.assertTrue(
                            has_symlink_mount(
                                plan["mounts"],
                                bazel_launcher.REPO_GATE_GIT_DIR,
                                target=git_dir_inside,
                                mode="read_only",
                            ),
                            plan["mounts"],
                        )
                        self.assertEqual(
                            Path(git_dir_inside).relative_to(bazel_launcher.REPO_GATE_GIT_COMMON_DIR),
                            git_dir.relative_to(common_dir),
                        )
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
        waymo_rootfs = current_cpu_rootfs(home / ".cache/waystone/waymo-perception")
        curriculum_rootfs = current_curriculum_rootfs(home / ".cache/waystone/3d-pathway")
        gpu_rootfs = current_gpu_rootfs(home / ".cache/waystone/waymo-perception")
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

    def run_git(self, cwd, *arguments):
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def write_git_fixture(self, root):
        root.mkdir(parents=True)
        self.run_git(root, "init")
        (root / "autonomy").mkdir()
        (root / "autonomy" / "sample_boundary_test.py").write_text("# boundary\n")
        (root / "BUILD.bazel").write_text(
            'REPO_GATE_TESTS = ["//autonomy:sample_boundary_test"]\n'
        )
        self.run_git(root, "add", ".")
        self.run_git(
            root,
            "-c",
            "user.name=Sureal Test",
            "-c",
            "user.email=sureal@example.invalid",
            "commit",
            "-m",
            "initial",
        )
        return root

    def materialize_mounts(self, mounts, sandbox):
        for mount in mounts:
            inside = sandbox / mount.inside_path.lstrip("/")
            if mount.kind == "tmpfs":
                inside.mkdir(parents=True, exist_ok=True)
                continue
            if mount.kind == "symlink":
                inside.parent.mkdir(parents=True, exist_ok=True)
                if inside.exists() or inside.is_symlink():
                    if inside.is_dir() and not inside.is_symlink():
                        shutil.rmtree(inside)
                    else:
                        inside.unlink()
                target = mount.symlink_target
                if target is not None and target.startswith("/"):
                    target = str((sandbox / target.lstrip("/")).resolve())
                inside.symlink_to(target)
                continue
            if mount.kind != "bind":
                continue
            inside.parent.mkdir(parents=True, exist_ok=True)
            if inside.exists() or inside.is_symlink():
                if inside.is_dir() and not inside.is_symlink():
                    shutil.rmtree(inside)
                else:
                    inside.unlink()
            host = Path(mount.host_path)
            if host.is_dir():
                shutil.copytree(host, inside, symlinks=True)
            else:
                shutil.copy2(host, inside)

    def translate_sandbox_path(self, sandbox, value):
        return str((sandbox / value.lstrip("/")).resolve())

    def repo_gate_git_environment(self, sandbox, wrapper_environment):
        env = os.environ.copy()
        env["GIT_OPTIONAL_LOCKS"] = "0"
        scalar_paths = {
            "SUREAL_REPO_GATE_GIT_DIR": "GIT_DIR",
            "SUREAL_REPO_GATE_GIT_WORK_TREE": "GIT_WORK_TREE",
            "SUREAL_REPO_GATE_GIT_COMMON_DIR": "GIT_COMMON_DIR",
            "SUREAL_REPO_GATE_GIT_OBJECT_DIRECTORY": "GIT_OBJECT_DIRECTORY",
        }
        for source, destination in scalar_paths.items():
            value = wrapper_environment.get(source)
            if value:
                env[destination] = self.translate_sandbox_path(sandbox, value)
        alternates = wrapper_environment.get("SUREAL_REPO_GATE_GIT_ALTERNATE_OBJECT_DIRECTORIES")
        if alternates:
            env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = os.pathsep.join(
                self.translate_sandbox_path(sandbox, path)
                for path in alternates.split(os.pathsep)
                if path
            )
        return env

    def assert_repo_gate_git_commands(self, sandbox, env):
        root = sandbox / "experiment"
        commands = [
            ["git", "-C", str(root), "ls-files", "--stage", "-z"],
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--",
                "autonomy/*_boundary_test.py",
                "autonomy/**/*_boundary_test.py",
            ],
            ["git", "-C", str(root), "diff", "--check", "HEAD", "--"],
        ]
        for command in commands:
            result = subprocess.run(
                command,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(
                result.returncode,
                0,
                result.stdout.decode("utf-8", "replace")
                + result.stderr.decode("utf-8", "replace"),
            )

    def test_repo_gate_git_metadata_supports_plain_alternate_and_linked_worktrees(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            plain = self.write_git_fixture(root / "plain")

            alternate_source = self.write_git_fixture(root / "alternate-source")
            alternate = root / "alternate"
            self.run_git(root, "clone", "--shared", str(alternate_source), str(alternate))

            linked_source = self.write_git_fixture(root / "linked-source")
            linked = root / "linked"
            self.run_git(
                linked_source,
                "worktree",
                "add",
                "-b",
                "repo-gate-linked-fixture",
                str(linked),
            )

            for name, repository in (
                ("plain", plain),
                ("alternate", alternate),
                ("linked", linked),
            ):
                with self.subTest(layout=name):
                    sandbox = root / f"sandbox-{name}"
                    with mock.patch.object(bazel_launcher, "REPO", repository):
                        mounts = bazel_launcher.repo_workspace_mounts()
                        wrapper_environment = bazel_launcher.git_test_environment()

                    self.assertTrue(
                        any(
                            mount.inside_path == "/experiment/.git"
                            and mount.mode == "read_only"
                            for mount in mounts
                        ),
                        mounts,
                    )
                    common_dir = wrapper_environment["SUREAL_REPO_GATE_GIT_COMMON_DIR"]
                    self.assertTrue(
                        any(
                            mount.inside_path == common_dir
                            and mount.mode == "read_only"
                            for mount in mounts
                        ),
                        mounts,
                    )

                    self.materialize_mounts(mounts, sandbox)
                    env = self.repo_gate_git_environment(sandbox, wrapper_environment)
                    self.assert_repo_gate_git_commands(sandbox, env)

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
            self.assertTrue(has_mount(plan["mounts"], "/experiment", kind="tmpfs"))
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/experiment/MODULE.bazel",
                    host=str((REPO / "MODULE.bazel").resolve()),
                    mode="read_only",
                )
            )
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/experiment/autonomy",
                    host=str(AUTONOMY.resolve()),
                    mode="read_only",
                )
            )
            self.assertFalse(
                LEGACY_AUTONOMY_ALIAS_DESTINATIONS & mount_destinations(plan["mounts"]),
                plan["mounts"],
            )
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/tmp/bazel-cache",
                    host=str(cache.resolve()),
                    mode="writable",
                )
            )
            self.assertTrue(has_mount(plan["mounts"], "/outputs", kind="tmpfs"))
            self.assertTrue(has_mount(plan["mounts"], "/tmp", kind="tmpfs"))
            self.assertFalse(has_mount(plan["mounts"], "/outputs", host=str(cache.resolve())))
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/etc/resolv.conf",
                    host="/etc/resolv.conf",
                    mode="read_only",
                )
            )
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

    def test_bazel_launcher_uses_public_launch_plan_api_and_renders_unique_mounts(self):
        source = (AUTONOMY / "insula/bazel_launcher.py").read_text()
        self.assertNotIn("_assemble_plan", source)
        self.assertNotIn("_gpu_mounts_environment_and_request", source)
        self.assertNotIn('("--setenv"', source)

        with tempfile.TemporaryDirectory() as temporary:
            result, _, _, _, _ = self.run_wrapper(
                temporary,
                "--emit-plan",
                "test",
                "//autonomy:source_snapshot_targets_test",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            argv = json.loads(result.stdout)["argv"]
            rendered = []
            index = 1
            while index < argv.index("--"):
                option = argv[index]
                if option in {"--ro-bind", "--bind", "--dev-bind", "--symlink"}:
                    rendered.append(argv[index + 2])
                    index += 3
                elif option in {"--proc", "--dev", "--tmpfs"}:
                    rendered.append(argv[index + 1])
                    index += 2
                elif option == "--chdir":
                    index += 2
                elif option == "--setenv":
                    index += 3
                else:
                    index += 1

            duplicates = sorted({inside for inside in rendered if rendered.count(inside) > 1})
            self.assertEqual(duplicates, [])

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
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/experiment/MODULE.bazel.lock",
                    host=str((REPO / "MODULE.bazel.lock").resolve()),
                    mode="writable",
                )
            )
            self.assertTrue(has_mount(plan["mounts"], "/experiment", kind="tmpfs"))
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/experiment/MODULE.bazel",
                    host=str((REPO / "MODULE.bazel").resolve()),
                    mode="read_only",
                )
            )
            self.assertFalse(marker.exists())

    def test_requires_live_gate_filter_projects_current_waymo_cache_to_tests(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, marker, _, waymo_rootfs, _, _ = self.run_wrapper_with_default_roots(
                temporary,
                "--emit-plan",
                "test",
                "--test_tag_filters=requires_live_gate,-requires_gpu,-known_failure",
                "//autonomy/insula:launch_plan_live_test",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = json.loads(result.stdout)
            waymo_cache = waymo_rootfs.parents[1]
            live_root = f"{LIVE_GATE_CACHE_MOUNT}/insula/{waymo_rootfs.name}"
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    LIVE_GATE_CACHE_MOUNT,
                    host=str(waymo_cache.resolve()),
                    mode="read_only",
                )
            )
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    LIVE_GATE_BWRAP,
                    host="/usr/bin/bwrap",
                    mode="read_only",
                )
            )
            self.assertIn(f"--test_env=SUREAL_LIVE_GATE_BWRAP={LIVE_GATE_BWRAP}", plan["bazel"])
            self.assertIn(f"--test_env=WAYMO_INSULA_ROOT={live_root}", plan["bazel"])
            self.assertIn(f"--test_env=WAYMO_INSULA_LOCK={live_root}.lock.json", plan["bazel"])
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
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/",
                    host=str(curriculum_rootfs.resolve()),
                    mode="read_only",
                )
            )
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/experiment/parallax",
                    host=str((REPO / "parallax").resolve()),
                    mode="read_only",
                )
            )
            self.assertFalse(has_mount(plan["mounts"], "/experiment/3d-pathway"), plan["mounts"])
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
            driver_aliases = {
                "libcuda.so": "libcuda.so.580.105.08",
                "libcuda.so.1": "libcuda.so.580.105.08",
                "libnvidia-ptxjitcompiler.so": "libnvidia-ptxjitcompiler.so.580.105.08",
                "libnvidia-ptxjitcompiler.so.1": "libnvidia-ptxjitcompiler.so.580.105.08",
                "libnvidia-nvvm.so": "libnvidia-nvvm.so.580.105.08",
                "libnvidia-nvvm.so.4": "libnvidia-nvvm.so.580.105.08",
            }
            for target in sorted(set(driver_aliases.values())):
                (driver_dir / target).write_text(target)
            for alias, target in driver_aliases.items():
                (driver_dir / alias).symlink_to(target)

            result, marker, _, waymo_rootfs, _, gpu_rootfs = self.run_wrapper_with_default_roots(
                temporary,
                "--emit-plan",
                "test",
                "--config=cuda",
                "//autonomy:advanced__test_models",
                extra_env={
                    "SUREAL_BAZEL_GPU_DEVICES": ",".join(device_pairs),
                    "SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS": str(driver_dir),
                    "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-fixture-1",
                },
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(gpu_rootfs.name, "gpu-rootfs-v7")
            plan = json.loads(result.stdout)
            self.assertEqual(plan["rootfs"], str(gpu_rootfs.resolve()))
            self.assertNotEqual(plan["rootfs"], str(waymo_rootfs.resolve()))
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/",
                    host=str(gpu_rootfs.resolve()),
                    mode="read_only",
                )
            )
            self.assertTrue(has_mount(plan["mounts"], "/experiment", kind="tmpfs"))
            self.assertFalse(
                LEGACY_AUTONOMY_ALIAS_DESTINATIONS & mount_destinations(plan["mounts"]),
                plan["mounts"],
            )
            self.assertIn("--output_base=/tmp/bazel-cache/output-base-gpu", plan["bazel"])
            self.assertIn("--config=cuda", plan["bazel"])
            self.assertIn(
                "--test_env=SUREAL_BAZEL_GPU_DEVICE_UUIDS=1=GPU-fixture-1",
                plan["bazel"],
            )
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    LIVE_GATE_CACHE_MOUNT,
                    host=str(waymo_rootfs.parents[1].resolve()),
                    mode="read_only",
                )
            )
            gpu_live_root = f"{LIVE_GATE_CACHE_MOUNT}/{gpu_rootfs.name}"
            self.assertIn(f"--test_env=WAYMO_GPU_INSULA_ROOT={gpu_live_root}", plan["bazel"])
            self.assertIn(f"--test_env=WAYMO_GPU_INSULA_LOCK={gpu_live_root}.lock.json", plan["bazel"])
            self.assertIn(f"--test_env=SUREAL_LIVE_GATE_BWRAP={LIVE_GATE_BWRAP}", plan["bazel"])
            self.assertTrue(has_mount(plan["mounts"], "/driver", kind="tmpfs"))
            for pair in device_pairs:
                host, guest = pair.split("=", 1)
                self.assertTrue(
                    has_mount(plan["mounts"], guest, host=host, kind="dev-bind"),
                    plan["mounts"],
                )
            self.assertNotIn("/dev/nvidia0", json.dumps(plan, sort_keys=True))
            self.assertEqual(
                plan["gpu"],
                {"requested_index": 1, "device_uuid": "GPU-fixture-1"},
            )
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/driver/libcuda.so",
                    host=str((driver_dir / "libcuda.so").resolve()),
                    mode="read_only",
                )
            )
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/driver/libcuda.so.1",
                    host=str((driver_dir / "libcuda.so.1").resolve()),
                    mode="read_only",
                )
            )
            self.assertTrue(
                has_mount(
                    plan["mounts"],
                    "/driver/libnvidia-ptxjitcompiler.so.580.105.08",
                    host=str((driver_dir / "libnvidia-ptxjitcompiler.so.580.105.08").resolve()),
                    mode="read_only",
                )
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
