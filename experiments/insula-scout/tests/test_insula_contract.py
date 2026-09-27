from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCOUT_ROOT = Path(__file__).resolve().parents[1]


class InsulaContractTest(unittest.TestCase):
    def test_foundation_environment_plan_is_fully_content_addressed(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCOUT_ROOT / "verify_environment_lock.py"),
                "--emit-plan",
            ],
            cwd=SCOUT_ROOT.parent.parent,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(
            plan["cuda_base_image"],
            "nvidia/cuda@sha256:6435dc5a825b0095648d87a3c91240fd7788a85fafaf215739544d389ab74366",
        )
        self.assertEqual(plan["ubuntu_snapshot"], "20260925T000000Z")
        self.assertGreaterEqual(len(plan["apt_packages"]), 19)
        self.assertTrue(all("=" in package for package in plan["apt_packages"]))
        self.assertEqual(plan["python_lock"]["format"], "pylock.toml")
        self.assertGreaterEqual(plan["python_lock"]["package_count"], 200)
        self.assertRegex(plan["python_lock"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(plan["python_lock"]["all_artifacts_hashed"])
        self.assertGreaterEqual(plan["build_scripts"]["file_count"], 9)
        self.assertTrue(plan["build_scripts"]["all_hashes_match"])
        self.assertEqual(plan["local_install_dependency_mode"], "no-deps")
        self.assertEqual(plan["post_build_verification"], "byte-for-byte environment tree")

    def test_build_exposes_the_same_locked_plan_without_building(self) -> None:
        result = subprocess.run(
            [str(SCOUT_ROOT / "build.sh"), "--emit-plan"],
            cwd=SCOUT_ROOT.parent.parent,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(
            plan["cuda_base_image"],
            "nvidia/cuda@sha256:6435dc5a825b0095648d87a3c91240fd7788a85fafaf215739544d389ab74366",
        )
        self.assertEqual(plan["ubuntu_snapshot"], "20260925T000000Z")
        self.assertEqual(plan["python_lock"]["format"], "pylock.toml")
        self.assertEqual(plan["local_install_dependency_mode"], "no-deps")

    def test_build_initializes_required_gitlink_sources(self) -> None:
        build = (SCOUT_ROOT / "build.sh").read_text(encoding="utf-8")
        self.assertIn(
            'git -C "${REPO_ROOT}" submodule update --init --recursive -- '
            'submodules/nvdiffrast',
            build,
        )

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
        self.assertEqual(plan["git_common_mount"], "/run/surflo-git-common")
        self.assertTrue(plan["git_dir"].startswith("/run/surflo-git-common"))
        self.assertEqual(plan["git_work_tree"], "/workspace/surflo")
        self.assertEqual(plan["command"], ["/bin/true"])
        self.assertNotIn("torch" + "etta", result.stdout.lower())

    def test_entrypoint_scopes_git_metadata_to_the_provenance_verifier(self) -> None:
        entrypoint = (SCOUT_ROOT / "insula" / "enter_rootfs.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('--setenv SURFLO_GIT_DIR "${INSULA_GIT_DIR}"', entrypoint)
        self.assertIn('--setenv SURFLO_GIT_WORK_TREE "${REPO_MOUNT}"', entrypoint)
        self.assertNotIn('--setenv GIT_DIR ', entrypoint)
        self.assertNotIn('--setenv GIT_WORK_TREE ', entrypoint)

    def test_entrypoint_pins_compiler_environment(self) -> None:
        entrypoint = (SCOUT_ROOT / "insula" / "enter_rootfs.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('--setenv CC /usr/bin/gcc', entrypoint)
        self.assertIn('--setenv CXX /usr/bin/g++', entrypoint)
        self.assertIn('--setenv CUDAHOSTCXX /usr/bin/g++', entrypoint)

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
        extension_builder = (
            SCOUT_ROOT.parent.parent / "install" / "build_extensions.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("bash install/build_extensions.sh --with-da3", installer)
        self.assertNotIn("bash install/build_extensions.sh --all", installer)
        self.assertIn("mktemp -d", installer)
        self.assertIn('submodules/nvdiffrast/.', installer)
        self.assertIn('"${NVDIFFRAST_BUILD_SOURCE}"', installer)
        self.assertIn("RASTERIZER_DIR_OVERRIDE", installer)
        self.assertIn("RASTERIZER_DIR_OVERRIDE", extension_builder)
        self.assertIn('RASTERIZER_INSTALL="${RASTERIZER}"', extension_builder)
        self.assertIn('pip install "${BUILD_FLAGS[@]}" -c "$PIN_FILE" "$RASTERIZER_INSTALL"', extension_builder)

    def test_installer_uses_rootfs_python_for_lock_verification(self) -> None:
        installer = (SCOUT_ROOT / "install_env.sh").read_text(encoding="utf-8")
        self.assertIn('/usr/bin/python3 "${VERIFY_SCRIPT}" --emit-plan', installer)
        self.assertIn('/usr/bin/python3 "${VERIFY_SCRIPT}" --verify-environment', installer)
        self.assertIn('/usr/bin/python3 "${VERIFY_SCRIPT}" --write-manifest', installer)
        self.assertNotIn('python3 "${VERIFY_SCRIPT}"', installer.replace("/usr/bin/python3", ""))

    def test_locked_git_fetch_recovers_from_an_incomplete_cache(self) -> None:
        installer = (SCOUT_ROOT / "install_env.sh").read_text(encoding="utf-8")
        self.assertIn('rm -rf -- "${destination}"', installer)
        self.assertIn(
            'git -C "${stage}" fetch -q --depth 1 origin "${commit}" || return 1',
            installer,
        )

    def test_interrupted_environment_backup_uses_a_unique_path(self) -> None:
        installer = (SCOUT_ROOT / "install_env.sh").read_text(encoding="utf-8")
        self.assertIn('BACKUP="$(mktemp -d "${CACHE}/venv.previous.XXXXXX")"', installer)
        self.assertNotIn('BACKUP="${VENV}.previous.$$"', installer)

    def test_environment_normalization_is_deterministic_and_idempotent(self) -> None:
        installer = (SCOUT_ROOT / "install_env.sh").read_text(encoding="utf-8")
        self.assertIn(
            '/usr/bin/python3 experiments/insula-scout/normalize_environment.py "${VENV}"',
            installer,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "venv"
            site = root / "lib" / "python3.10" / "site-packages"
            dist_info = site / "demo-1.0.dist-info"
            gradio = site / "gradio"
            dist_info.mkdir(parents=True)
            gradio.mkdir()
            (root / "lib64").symlink_to("lib")
            native = site / "native.so"
            native.write_bytes(b"prefix tmpxft_12ab34cd_00000000-6_unit.cu suffix")
            cache_metadata = dist_info / "uv_cache.json"
            cache_metadata.write_text(
                '{"timestamp":{"secs_since_epoch":123,"nanos_since_epoch":456}}',
                encoding="utf-8",
            )
            seed = gradio / "hash_seed.txt"
            seed.write_text("random-seed", encoding="utf-8")
            record = dist_info / "RECORD"
            record.write_text(
                "native.so,,\n"
                "demo-1.0.dist-info/uv_cache.json,,\n"
                "demo-1.0.dist-info/RECORD,,\n",
                encoding="utf-8",
            )

            command = [
                sys.executable,
                str(SCOUT_ROOT / "normalize_environment.py"),
                str(root),
            ]
            first = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_hash = hashlib.sha256(
                b"".join(path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file())
            ).hexdigest()
            second = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            second_hash = hashlib.sha256(
                b"".join(path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file())
            ).hexdigest()
            self.assertEqual(first_hash, second_hash)
            self.assertIn("tmpxft_00000000_", native.read_bytes().decode())
            self.assertEqual(seed.read_text(encoding="utf-8"), "0" * 64)
            self.assertEqual(
                json.loads(cache_metadata.read_text(encoding="utf-8"))["timestamp"],
                {"secs_since_epoch": 0, "nanos_since_epoch": 0},
            )
            self.assertIn("sha256=", record.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
