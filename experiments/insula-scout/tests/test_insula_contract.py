from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCOUT_ROOT = Path(__file__).resolve().parents[1]


class InsulaContractTest(unittest.TestCase):
    def test_bundle_is_self_contained(self) -> None:
        required = [
            SCOUT_ROOT / "insula" / "Dockerfile",
            SCOUT_ROOT / "insula" / "build_rootfs.sh",
            SCOUT_ROOT / "insula" / "enter_rootfs.sh",
        ]
        for path in required:
            self.assertTrue(path.is_file(), path)

        forbidden = "torch" + "etta"
        candidates = [
            *SCOUT_ROOT.glob("*.sh"),
            *SCOUT_ROOT.glob("*.md"),
            *SCOUT_ROOT.glob("*.json"),
            *SCOUT_ROOT.glob("insula/*"),
        ]
        for path in candidates:
            if not path.is_file():
                continue
            self.assertNotIn(forbidden, path.read_text(encoding="utf-8").lower(), path)

    def test_entrypoint_emits_a_surflo_only_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            rootfs = Path(temp_dir) / "rootfs"
            env = {
                **os.environ,
                "SURFLO_INSULA_CACHE_ROOT": str(cache_root),
                "SURFLO_INSULA_ROOT": str(rootfs),
            }
            result = subprocess.run(
                [
                    str(SCOUT_ROOT / "enter.sh"),
                    "--emit-plan",
                    "--",
                    "/bin/true",
                ],
                check=False,
                capture_output=True,
                env=env,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["marker_env"], "SURFLO_IN_INSULA")
        self.assertEqual(plan["repo_mount"], "/workspace/surflo")
        self.assertEqual(plan["cache_mount"], "/cache/surflo")
        self.assertEqual(plan["command"], ["/bin/true"])
        self.assertNotIn("torch" + "etta", result.stdout.lower())

    def test_rootfs_builder_has_a_host_safe_help_path(self) -> None:
        result = subprocess.run(
            [str(SCOUT_ROOT / "insula" / "build_rootfs.sh"), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--dest", result.stdout)
        self.assertIn("--image", result.stdout)

    def test_rootfs_validation_resolves_absolute_symlinks_inside_rootfs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            rootfs = Path(temp_dir) / "rootfs"
            (rootfs / "bin").mkdir(parents=True)
            (rootfs / "etc").mkdir()
            (rootfs / "usr" / "local" / "bin").mkdir(parents=True)
            (rootfs / "usr" / "local" / "cuda-13.2" / "bin").mkdir(parents=True)
            for relative in ("bin/bash", "usr/local/bin/uv", "usr/local/cuda-13.2/bin/nvcc"):
                executable = rootfs / relative
                executable.write_text("#!/bin/sh\n", encoding="utf-8")
                executable.chmod(0o755)
            (rootfs / "usr" / "local" / "cuda").symlink_to("/usr/local/cuda-13.2")
            (rootfs / "etc" / "surflo-insula-contract").write_text(
                "schema_version=1\n", encoding="utf-8"
            )
            result = subprocess.run(
                [
                    str(SCOUT_ROOT / "insula" / "build_rootfs.sh"),
                    "--validate-rootfs",
                    str(rootfs),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_optional_nvdiffrast_build_does_not_target_the_checkout(self) -> None:
        installer = (SCOUT_ROOT / "install_env.sh").read_text(encoding="utf-8")
        self.assertIn("bash install/build_extensions.sh --with-da3", installer)
        self.assertNotIn("bash install/build_extensions.sh --all", installer)
        self.assertIn("mktemp -d", installer)
        self.assertIn('submodules/nvdiffrast/.', installer)
        self.assertIn('"${NVDIFFRAST_BUILD_SOURCE}"', installer)


if __name__ == "__main__":
    unittest.main()
