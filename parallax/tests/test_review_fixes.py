from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
sys.path.insert(0, str(PIPELINE))


def run_cli(*args: str, cache: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
    return subprocess.run(
        [str(ROOT / "run.sh"), *args],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class ReviewHardeningTest(unittest.TestCase):
    def test_gpu_adapters_select_one_device_per_run(self) -> None:
        for name in (
            "neus_reference_runner.py",
            "nerfacto_reference_runner.py",
            "splatfacto_reference_runner.py",
            "foundation_geometry_reference_runner.py",
        ):
            tree = ast.parse((PIPELINE / name).read_text(encoding="utf-8"))
            calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "selected_gpu_device"
            ]
            self.assertEqual(len(calls), 1, name)

    def test_multistage_insula_locks_cover_the_runtime_image(self) -> None:
        from pipeline.audit import _image_lock_errors

        lock = {
            "base_image": "example/builder:1",
            "base_image_digest": "a" * 64,
            "runtime_image": "example/runtime:1",
            "runtime_image_digest": "b" * 64,
        }
        dockerfile = (
            f"FROM example/builder:1@sha256:{'a' * 64} AS builder\n"
            f"FROM example/runtime:1@sha256:{'b' * 64} AS runtime\n"
        )
        self.assertEqual(_image_lock_errors("fixture", lock, dockerfile), [])
        tampered = dockerfile.replace("b" * 64, "c" * 64)
        self.assertIn(
            "Insula runtime image lock mismatch: fixture",
            _image_lock_errors("fixture", lock, tampered),
        )
        source_lock = dict(lock, colmap_source_commit="d" * 40)
        self.assertIn(
            "Insula COLMAP source lock mismatch: fixture",
            _image_lock_errors("fixture", source_lock, dockerfile),
        )

    def test_reference_scope_and_container_locks_are_honest(self) -> None:
        curriculum = json.loads((ROOT / "curriculum.json").read_text())
        self.assertIn("repo-owned concept", curriculum["profiles"]["full"]["purpose"].lower())
        self.assertNotIn("adapter", curriculum["profiles"]["full"]["purpose"].lower())
        adapters = json.loads((ROOT / "reference-adapters.json").read_text())["adapters"]
        self.assertTrue(adapters)
        statuses = {item["id"]: item["status"] for item in adapters}
        self.assertEqual(statuses["colmap-sfm-reference"], "landed")
        self.assertEqual(statuses["colmap-mvs-reference"], "landed")
        self.assertEqual(statuses["orb-slam-reference"], "landed")
        self.assertEqual(statuses["depth-anything-v2-reference"], "landed")
        self.assertEqual(statuses["nerfstudio-neus-facto-reference"], "landed")
        self.assertEqual(statuses["nerfstudio-nerfacto-reference"], "landed")
        self.assertEqual(statuses["nerfstudio-splatfacto-reference"], "landed")
        self.assertEqual(statuses["foundation-geometry-reference"], "landed")
        landed = {
            "colmap-sfm-reference",
            "colmap-mvs-reference",
            "orb-slam-reference",
            "depth-anything-v2-reference",
            "nerfstudio-neus-facto-reference",
            "nerfstudio-nerfacto-reference",
            "nerfstudio-splatfacto-reference",
            "foundation-geometry-reference",
        }
        self.assertTrue(all(status == "not_landed" for adapter, status in statuses.items() if adapter not in landed))

        locks = json.loads((ROOT / "insulas" / "locks.json").read_text())["insulas"]
        from pipeline.audit import _image_lock_errors

        for name, lock in locks.items():
            dockerfile = ROOT / "insulas" / name / "Dockerfile"
            self.assertEqual(_image_lock_errors(name, lock, dockerfile.read_text()), [])
            self.assertEqual(lock["dockerfile_sha256"], hashlib.sha256(dockerfile.read_bytes()).hexdigest())

    def test_corrected_primary_source_metadata(self) -> None:
        sources = {item["id"]: item for item in json.loads((ROOT / "sources.json").read_text())["sources"]}
        self.assertEqual(sources["marr-poggio-1979"]["primary_url"], "https://doi.org/10.1098/rspb.1979.0029")
        self.assertEqual(sources["salvi-2010"]["primary_url"], "https://doi.org/10.1016/j.patcog.2010.03.004")
        self.assertEqual(sources["luiten-dynamic3dgs-2024"]["primary_url"], "https://doi.org/10.1109/3DV62453.2024.00044")
        self.assertIn("Feng Liu", sources["hong-lrm-2023"]["authors"])
        self.assertNotIn("Fangyun Wei", sources["hong-lrm-2023"]["authors"])

    def test_run_consumes_scene_profile_and_records_fixture_provenance(self) -> None:
        from pipeline.validator import validate_result

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            completed = run_cli("run", "--module", "01", "--profile", "smoke", "--run-id", "review-01", cache=cache)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "runs" / "review-01" / "01"
            result = validate_result(run_dir, "01")
            scene = json.loads((ROOT / "shared-scene.json").read_text())
            self.assertEqual(result["metrics"]["geometry"]["camera_fx_px"], scene["cameras"]["intrinsics"]["fx"])
            self.assertEqual(len(result["failure_sweep"]), 5)
            self.assertEqual(result["measurement_kind"], "controlled_fixture")
            self.assertTrue(result["metric_provenance"])
            self.assertEqual(
                result["provenance"]["inputs_sha256"]["shared-scene.json"],
                hashlib.sha256((ROOT / "shared-scene.json").read_bytes()).hexdigest(),
            )
            self.assertIn("pipeline/labs.py", result["provenance"]["implementation_sha256"])
            self.assertIn("report.md", result["provenance"]["reports_sha256"])

    def test_validator_rejects_tampering_and_report_validates_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            completed = run_cli("run", "--module", "01", "--profile", "smoke", "--run-id", "tamper", cache=cache)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = run_cli("report", "--run-id", "tamper", cache=cache)
            self.assertEqual(report.returncode, 0, report.stderr)
            manifest = json.loads((cache / "runs" / "tamper" / "report.json").read_text())
            self.assertFalse(manifest["complete_curriculum"])
            self.assertEqual(manifest["module_ids"], ["01"])

            result_path = cache / "runs" / "tamper" / "01" / "result.json"
            payload = json.loads(result_path.read_text())
            payload["provenance"]["config"]["seed"] += 1
            result_path.write_text(json.dumps(payload))
            validation = run_cli("validate", "--module", "01", "--run-id", "tamper", cache=cache)
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("config hash mismatch", validation.stderr)
            second_report = run_cli("report", "--run-id", "tamper", cache=cache)
            self.assertNotEqual(second_report.returncode, 0)

    def test_run_ids_are_confined_and_network_is_blocked_during_labs(self) -> None:
        from pipeline.runner import offline_network

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            escaped = run_cli("run", "--module", "01", "--run-id", "../escape", cache=cache)
            self.assertNotEqual(escaped.returncode, 0)
            self.assertFalse((cache / "escape").exists())

        with offline_network():
            with self.assertRaisesRegex(RuntimeError, "offline"):
                socket.create_connection(("example.com", 80))

    def test_validator_rejects_runtime_contract_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            for field, replacement in (
                ("network_isolation", "os_network_namespace"),
                ("cpu_memory_scope", "per_module_isolated_peak"),
            ):
                with self.subTest(field=field):
                    run_id = f"runtime-contract-{field}"
                    completed = run_cli(
                        "run",
                        "--module",
                        "01",
                        "--profile",
                        "smoke",
                        "--run-id",
                        run_id,
                        cache=cache,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    result_path = cache / "runs" / run_id / "01" / "result.json"
                    result = json.loads(result_path.read_text())
                    result["resources"][field] = replacement
                    result_path.write_text(json.dumps(result))
                    validation = run_cli(
                        "validate",
                        "--module",
                        "01",
                        "--run-id",
                        run_id,
                        cache=cache,
                    )
                    self.assertNotEqual(validation.returncode, 0)
                    self.assertIn("runtime contract mismatch", validation.stderr)

    def test_all_is_complete_and_module_15_is_reused_measurement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            completed = run_cli("all", "--profile", "smoke", "--run-id", "atomic-all", cache=cache)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            manifest = json.loads((cache / "runs" / "atomic-all" / "report.json").read_text())
            self.assertTrue(manifest["complete_curriculum"])
            self.assertEqual(len(manifest["module_ids"]), 15)
            endpoint = json.loads((cache / "runs" / "atomic-all" / "15" / "result.json").read_text())
            self.assertEqual(endpoint["measurement_kind"], "reused_measured_result")

    def test_fetch_manifest_has_correct_tum_url_and_selection_contract(self) -> None:
        assets = {item["id"]: item for item in json.loads((ROOT / "assets.lock.json").read_text())["assets"]}
        self.assertIn("/freiburg1/", assets["tum-rgbd"]["source"])
        self.assertEqual(assets["tum-rgbd"]["digest_status"], "verified_2026-09-26")
        self.assertEqual(assets["tum-rgbd"]["extraction"]["mode"], "tar")
        self.assertTrue(assets["middlebury-mvs"]["consumers"])
        self.assertEqual(assets["controlled-suite"]["episode_id"], "phase-a-v1")
        self.assertEqual(assets["controlled-suite"]["artifact_count"], 444)
        self.assertEqual(len(assets["controlled-suite"]["consumers"]), 15)
        with tempfile.TemporaryDirectory() as temporary:
            emitted = run_cli("--emit-plan", "fetch", "--asset", "tum-rgbd", cache=Path(temporary))
            self.assertEqual(emitted.returncode, 0, emitted.stderr)
            self.assertEqual(json.loads(emitted.stdout)["assets"], ["tum-rgbd"])
            controlled = run_cli(
                "--emit-plan",
                "fetch",
                "--asset",
                "controlled-suite",
                cache=Path(temporary),
            )
            self.assertEqual(controlled.returncode, 0, controlled.stderr)
            self.assertEqual(
                json.loads(controlled.stdout)["assets"], ["controlled-suite"]
            )


if __name__ == "__main__":
    unittest.main()
