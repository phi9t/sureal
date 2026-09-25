from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _load_module(relative: str, name: str):
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"required module is missing: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BlenderInsulaContractTest(unittest.TestCase):
    def test_bundle_is_self_contained(self) -> None:
        required = [
            ROOT / "run.sh",
            ROOT / "build.sh",
            ROOT / "assets.lock.json",
            ROOT / "model.lock.json",
            ROOT / "insula" / "Dockerfile",
            ROOT / "insula" / "build_rootfs.sh",
            ROOT / "insula" / "enter_rootfs.sh",
        ]
        for path in required:
            self.assertTrue(path.is_file(), path)

    def test_entrypoint_plan_has_separate_cache_exchange_and_network_mode(self) -> None:
        entrypoint = ROOT / "enter.sh"
        self.assertTrue(entrypoint.is_file(), entrypoint)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env = {
                **os.environ,
                "PHOTOREAL_CACHE_ROOT": str(root / "blender-cache"),
                "PHOTOREAL_INSULA_ROOT": str(root / "rootfs"),
                "SURFLO_SCOUT_CACHE_ROOT": str(root / "surflo-cache"),
            }
            result = subprocess.run(
                [str(entrypoint), "--offline", "--emit-plan", "--", "/bin/true"],
                check=False,
                capture_output=True,
                env=env,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["network_mode"], "offline")
        self.assertEqual(plan["repo_mount"], "/workspace/surflo")
        self.assertEqual(plan["cache_mount"], "/cache/blender")
        self.assertEqual(plan["exchange_mount"], "/exchange")
        self.assertNotEqual(plan["host_cache_root"], plan["host_exchange_root"])
        self.assertEqual(plan["command"], ["/bin/true"])

    def test_nvidia_smi_binds_into_the_precreated_driver_mount(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rootfs = root / "rootfs"
            for directory in (
                "bin", "etc", "opt/blender", "workspace/surflo", "cache/blender",
                "exchange", "run/photoreal-nvidia-driver",
            ):
                (rootfs / directory).mkdir(parents=True, exist_ok=True)
            for path in (rootfs / "bin" / "bash", rootfs / "opt" / "blender" / "blender"):
                path.write_text("#!/bin/sh\n", encoding="utf-8")
                path.chmod(0o755)
            (rootfs / "etc" / "photoreal-blender-insula-contract").write_text(
                "schema_version=1\n"
                "blender_version=4.5.14\n"
                "blender_archive_sha256="
                "9ba871ff2ecd36526b77432745980b7e6664ecd0c7ca11c48849073dcfe06da3\n",
                encoding="utf-8",
            )
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            fake_bwrap = fake_bin / "bwrap"
            fake_bwrap.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
            fake_bwrap.chmod(0o755)
            result = subprocess.run(
                [
                    str(ROOT / "insula" / "enter_rootfs.sh"),
                    "--rootfs", str(rootfs),
                    "--cache-root", str(root / "cache"),
                    "--exchange-root", str(root / "exchange-host"),
                    "--repo", str(ROOT.parents[1]),
                    "--offline", "--", "/bin/true",
                ],
                check=False,
                capture_output=True,
                env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = result.stdout.splitlines()
        if "/usr/bin/nvidia-smi" in arguments:
            source_index = arguments.index("/usr/bin/nvidia-smi")
            self.assertEqual(
                arguments[source_index + 1],
                "/run/photoreal-nvidia-driver/nvidia-smi",
            )
        self.assertNotIn("/nix/store", arguments)

    def test_dispatcher_exposes_only_the_documented_commands(self) -> None:
        dispatcher = ROOT / "run.sh"
        self.assertTrue(dispatcher.is_file(), dispatcher)
        result = subprocess.run(
            [str(dispatcher), "--help"], check=False, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in (
            "build",
            "fetch",
            "render-draft",
            "render",
            "validate",
            "probe",
            "all",
        ):
            self.assertIn(command, result.stdout)

    def test_dispatcher_plans_fetch_online_and_render_offline(self) -> None:
        dispatcher = ROOT / "run.sh"
        self.assertTrue(dispatcher.is_file(), dispatcher)
        fetch = subprocess.run(
            [str(dispatcher), "--emit-plan", "fetch"],
            check=False,
            capture_output=True,
            text=True,
        )
        render = subprocess.run(
            [str(dispatcher), "--emit-plan", "render", "--run-id", "episode-1"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(fetch.returncode, 0, fetch.stderr)
        self.assertEqual(render.returncode, 0, render.stderr)
        self.assertEqual(json.loads(fetch.stdout)["network_mode"], "networked")
        render_plan = json.loads(render.stdout)
        self.assertEqual(render_plan["network_mode"], "offline")
        self.assertEqual(render_plan["command"], "render")
        self.assertEqual(render_plan["profile"], "benchmark")
        self.assertEqual(render_plan["device"], "OPTIX")

    def test_rootfs_validator_checks_pinned_blender(self) -> None:
        builder = ROOT / "insula" / "build_rootfs.sh"
        self.assertTrue(builder.is_file(), builder)
        with tempfile.TemporaryDirectory() as temp_dir:
            rootfs = Path(temp_dir) / "rootfs"
            (rootfs / "bin").mkdir(parents=True)
            (rootfs / "etc").mkdir()
            (rootfs / "opt" / "blender").mkdir(parents=True)
            (rootfs / "workspace" / "surflo").mkdir(parents=True)
            (rootfs / "cache" / "blender").mkdir(parents=True)
            (rootfs / "exchange").mkdir()
            (rootfs / "run" / "photoreal-nvidia-driver").mkdir(parents=True)
            bash = rootfs / "bin" / "bash"
            bash.write_text("#!/bin/sh\n", encoding="utf-8")
            bash.chmod(0o755)
            blender = rootfs / "opt" / "blender" / "blender"
            blender.write_text("#!/bin/sh\n", encoding="utf-8")
            blender.chmod(0o755)
            (rootfs / "etc" / "photoreal-blender-insula-contract").write_text(
                "schema_version=1\n"
                "blender_version=4.5.14\n"
                "blender_archive_sha256="
                "9ba871ff2ecd36526b77432745980b7e6664ecd0c7ca11c48849073dcfe06da3\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(builder), "--validate-rootfs", str(rootfs)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rootfs_validator_rejects_missing_bubblewrap_mountpoints(self) -> None:
        builder = ROOT / "insula" / "build_rootfs.sh"
        with tempfile.TemporaryDirectory() as temp_dir:
            rootfs = Path(temp_dir) / "rootfs"
            (rootfs / "bin").mkdir(parents=True)
            (rootfs / "etc").mkdir()
            (rootfs / "opt" / "blender").mkdir(parents=True)
            for path in (rootfs / "bin" / "bash", rootfs / "opt" / "blender" / "blender"):
                path.write_text("#!/bin/sh\n", encoding="utf-8")
                path.chmod(0o755)
            (rootfs / "etc" / "photoreal-blender-insula-contract").write_text(
                "schema_version=1\n"
                "blender_version=4.5.14\n"
                "blender_archive_sha256="
                "9ba871ff2ecd36526b77432745980b7e6664ecd0c7ca11c48849073dcfe06da3\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(builder), "--validate-rootfs", str(rootfs)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mountpoint", result.stderr)


class AssetLockTest(unittest.TestCase):
    def test_lock_covers_required_cc0_assets_with_sha256(self) -> None:
        lock_path = ROOT / "assets.lock.json"
        self.assertTrue(lock_path.is_file(), lock_path)
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(lock["schema_version"], 1)
        by_id: dict[str, list[dict[str, object]]] = {}
        for item in lock["files"]:
            by_id.setdefault(str(item["asset_id"]), []).append(item)
            self.assertEqual(item["license"], "CC0-1.0")
            self.assertEqual(item["resolution"], "2k")
            self.assertGreater(item["size_bytes"], 0)
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(str(item["source_url"]).startswith("https://dl.polyhaven.org/"))
        self.assertEqual(
            set(by_id),
            {
                "Sofa_01",
                "Shelf_01",
                "WoodenChair_01",
                "WoodenTable_01",
                "wood_floor",
                "white_plaster_02",
                "kloofendal_overcast_puresky",
            },
        )

    def test_verifier_accepts_exact_file_and_rejects_missing_or_corrupt(self) -> None:
        fetcher = ROOT / "pipeline" / "assets.py"
        self.assertTrue(fetcher.is_file(), fetcher)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            asset_root = root / "assets"
            asset_root.mkdir()
            payload = b"locked asset bytes\n"
            locked_file = asset_root / "fixture.bin"
            locked_file.write_bytes(payload)
            lock_path = root / "lock.json"
            lock_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "files": [
                            {
                                "asset_id": "fixture",
                                "local_path": "fixture.bin",
                                "source_url": "https://example.invalid/fixture.bin",
                                "resolution": "test",
                                "license": "CC0-1.0",
                                "size_bytes": len(payload),
                                "sha256": hashlib.sha256(payload).hexdigest(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            good = subprocess.run(
                [
                    os.environ.get("PYTHON", "python3"),
                    str(fetcher),
                    "verify",
                    "--lock",
                    str(lock_path),
                    "--asset-root",
                    str(asset_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            locked_file.write_bytes(b"x" * len(payload))
            corrupt = subprocess.run(
                [
                    os.environ.get("PYTHON", "python3"),
                    str(fetcher),
                    "verify",
                    "--lock",
                    str(lock_path),
                    "--asset-root",
                    str(asset_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            locked_file.unlink()
            missing = subprocess.run(
                [
                    os.environ.get("PYTHON", "python3"),
                    str(fetcher),
                    "verify",
                    "--lock",
                    str(lock_path),
                    "--asset-root",
                    str(asset_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertNotEqual(corrupt.returncode, 0)
        self.assertIn("sha256 mismatch", corrupt.stderr)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("missing", missing.stderr)


class RunStoreAndDeviceTest(unittest.TestCase):
    def test_benchmark_requires_optix_and_draft_cpu_is_explicit(self) -> None:
        contract = _load_module("pipeline/contracts.py", "photoreal_contracts")
        self.assertEqual(contract.validate_device("benchmark", "OPTIX"), "OPTIX")
        with self.assertRaisesRegex(ValueError, "OptiX"):
            contract.validate_device("benchmark", "CPU")
        self.assertEqual(contract.validate_device("draft", "CPU"), "CPU")
        with self.assertRaisesRegex(ValueError, "explicit"):
            contract.validate_device("draft", "AUTO")

    def test_run_is_validated_before_atomic_promotion_and_overwrite_is_explicit(self) -> None:
        store = _load_module("pipeline/run_store.py", "photoreal_run_store")
        with tempfile.TemporaryDirectory() as temp_dir:
            runs = Path(temp_dir) / "runs"
            temporary, final = store.begin_run(runs, "episode-1", overwrite=False)
            self.assertFalse(final.exists())
            (temporary / "validated.json").write_text("{}\n", encoding="utf-8")
            store.promote_run(temporary, final, validated=True, overwrite=False)
            self.assertTrue((final / "validated.json").is_file())
            with self.assertRaises(FileExistsError):
                store.begin_run(runs, "episode-1", overwrite=False)
            replacement, replacement_final = store.begin_run(
                runs, "episode-1", overwrite=True
            )
            (replacement / "validated.json").write_text("{\"new\": true}\n")
            with self.assertRaisesRegex(RuntimeError, "validation"):
                store.promote_run(
                    replacement, replacement_final, validated=False, overwrite=True
                )
            store.promote_run(
                replacement, replacement_final, validated=True, overwrite=True
            )
            self.assertIn("new", (replacement_final / "validated.json").read_text())


if __name__ == "__main__":
    unittest.main()
