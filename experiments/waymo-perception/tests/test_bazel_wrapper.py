import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from pipeline.runtime_identity import rootfs_identity


REPO = Path(__file__).resolve().parents[3]
WRAPPER = REPO / "bazelw"


def write_rootfs(root):
    for name in ("etc", "experiment", "outputs", "tmp", "usr/bin", "usr/local/bin"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "etc/resolv.conf").write_text("nameserver 127.0.0.1\n")
    (root / "usr/local/bin/python").write_text("#!/bin/sh\n")
    (root / "usr/local/bin/python").chmod(0o755)
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


class BazelWrapperTests(unittest.TestCase):
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

    def test_emit_plan_prints_sandbox_command_data_without_running_bwrap(self):
        self.assertTrue(WRAPPER.is_file(), "repository-level Bazel wrapper is missing")
        with tempfile.TemporaryDirectory() as temporary:
            result, marker, cache, rootfs, lock = self.run_wrapper(
                temporary,
                "--emit-plan",
                "test",
                "//experiments/waymo-perception:tools_test_suites",
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
            self.assertIn(["--ro-bind", str(REPO.resolve()), "/experiment"], plan["mounts"])
            self.assertIn(["--bind", str(cache.resolve()), "/outputs"], plan["mounts"])
            self.assertIn(["--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf"], plan["mounts"])
            self.assertIn(["--setenv", "HOME", "/outputs/home"], plan["environment"])
            self.assertIn("--output_base=/outputs/output-base", plan["bazel"])
            self.assertIn("--enable_workspace", plan["bazel"])
            self.assertIn("--noenable_bzlmod", plan["bazel"])
            self.assertIn("--repositories_without_autoloads=*", plan["bazel"])
            self.assertIn("--repository_cache=/outputs/repository-cache", plan["bazel"])
            self.assertIn("--disk_cache=/outputs/disk-cache", plan["bazel"])
            self.assertEqual(plan["lock"], str(lock.resolve()))
            self.assertFalse(marker.exists())

    def test_rootfs_identity_mismatch_is_rejected_before_bwrap_runs(self):
        self.assertTrue(WRAPPER.is_file(), "repository-level Bazel wrapper is missing")
        with tempfile.TemporaryDirectory() as temporary:
            result, marker, _, _, _ = self.run_wrapper(
                temporary,
                "test",
                "//experiments/waymo-perception:tools_test_suites",
                wrong_identity=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("rootfs content does not match rootfs lock", result.stderr)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
