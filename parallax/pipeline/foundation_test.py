from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"


def run_cli(*args: str, cache: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if cache is not None:
        env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
    return subprocess.run(
        [str(ROOT / "run.sh"), *args],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class RunnerBootstrapTest(unittest.TestCase):
    def test_parallax_concept_packages_own_moved_sources(self) -> None:
        expected = {
            "camera/pinhole.py",
            "camera/pose.py",
            "geometry/triangulate.py",
            "geometry/align.py",
            "fusion/tsdf.py",
            "scene/reference_scene.py",
            "scene/shared-scene.json",
            "baselines/reference_runner.py",
            "baselines/mvs_reference_runner.py",
            "baselines/slam_reference_runner.py",
            "baselines/depth_reference_runner.py",
            "baselines/neus_reference_runner.py",
            "baselines/nerfacto_reference_runner.py",
            "baselines/splatfacto_reference_runner.py",
            "baselines/foundation_geometry_reference_runner.py",
            "curriculum/labs.py",
            "curriculum/curriculum.json",
            "assets/assets.lock.json",
            "assets/foundation-models.lock.json",
            "assets/reference-adapters.json",
            "assets/sources.json",
            "assets/terminology.json",
            "schemas/curriculum.schema.json",
            "schemas/reference-result.schema.json",
            "schemas/report.schema.json",
            "schemas/result.schema.json",
        }
        missing = sorted(path for path in expected if not (ROOT / path).is_file())
        self.assertEqual(missing, [])

    def test_legacy_math3d_imports_reexport_concept_functions(self) -> None:
        from camera.pinhole import project, unproject
        from camera.pose import camera_center, fundamental_from_poses
        from fusion.tsdf import fuse_tsdf
        from geometry.align import apply_transform, icp, normalize_rows, opencv_opengl_camera_transform
        from geometry.triangulate import refine_point_gauss_newton, reprojection_rmse, triangulate_point
        from pipeline import math3d

        self.assertIs(math3d.project, project)
        self.assertIs(math3d.unproject, unproject)
        self.assertIs(math3d.camera_center, camera_center)
        self.assertIs(math3d.fundamental_from_poses, fundamental_from_poses)
        self.assertIs(math3d.triangulate_point, triangulate_point)
        self.assertIs(math3d.refine_point_gauss_newton, refine_point_gauss_newton)
        self.assertIs(math3d.reprojection_rmse, reprojection_rmse)
        self.assertIs(math3d.apply_transform, apply_transform)
        self.assertIs(math3d.icp, icp)
        self.assertIs(math3d.normalize_rows, normalize_rows)
        self.assertIs(math3d.opencv_opengl_camera_transform, opencv_opengl_camera_transform)
        self.assertIs(math3d.fuse_tsdf, fuse_tsdf)

    def test_run_script_launches_cli_with_parallax_on_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fakebin = Path(temporary) / "bin"
            fakebin.mkdir()
            capture = Path(temporary) / "capture.json"
            fake_python = fakebin / "python3"
            fake_python.write_text(
                "#!" + sys.executable + "\n"
                "import json\n"
                "import os\n"
                "import sys\n"
                "from pathlib import Path\n"
                "Path(os.environ['SURFLO_RUN_SH_CAPTURE']).write_text(\n"
                "    json.dumps({'argv': sys.argv, 'pythonpath': os.environ.get('PYTHONPATH', '')})\n"
                ")\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
            env["PYTHONPATH"] = "/existing"
            env["SURFLO_RUN_SH_CAPTURE"] = str(capture)

            result = subprocess.run(
                [str(ROOT / "run.sh"), "list", "--json"],
                cwd=ROOT.parent,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertTrue(capture.is_file(), result.stdout + result.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            invocation = json.loads(capture.read_text(encoding="utf-8"))
            self.assertEqual(invocation["argv"][1:], [str(PIPELINE / "cli.py"), "list", "--json"])
            self.assertEqual(
                invocation["pythonpath"],
                f"{ROOT}{os.pathsep}/existing",
            )


class RegistryContractTest(unittest.TestCase):
    def test_dependency_free_schema_validator_enforces_conditional_branches(self) -> None:
        from pipeline.contracts import validate_json_schema_instance

        schema = {
            "type": "object",
            "allOf": [
                {
                    "if": {"properties": {"adapter": {"const": "nerfacto"}}},
                    "then": {"required": ["support"]},
                }
            ],
        }
        validate_json_schema_instance(
            {"adapter": "other"}, schema, "conditional fixture"
        )
        with self.assertRaisesRegex(ValueError, "support"):
            validate_json_schema_instance(
                {"adapter": "nerfacto"}, schema, "conditional fixture"
            )

    def test_result_schema_pins_fixture_runtime_contract_values(self) -> None:
        from pipeline.contracts import validate_json_schema_instance

        schema = json.loads((ROOT / "schemas" / "result.schema.json").read_text())
        resources = schema["properties"]["resources"]
        expected = {
            "network_isolation": "python_socket_guard",
            "cpu_memory_scope": "process_lifetime_high_water_mark",
        }
        for field, value in expected.items():
            with self.subTest(field=field):
                self.assertEqual(resources["properties"][field]["const"], value)
                fixture = {
                    "schema_version": 1,
                    "module_id": "01",
                    "module_implementation": "synthetic",
                    "profile": "smoke",
                    "status": "complete",
                    "network_mode": "offline",
                    "measurement_kind": "controlled_fixture",
                    "metrics": {},
                    "metric_provenance": {},
                    "failure_sweep": [{}, {}],
                    "failure_sweep_provenance": "controlled_fixture",
                    "resources": {
                        "runtime_seconds": 0.1,
                        "peak_cpu_bytes": 1,
                        "peak_gpu_bytes": 0,
                        **expected,
                        field: "overstated_contract",
                    },
                    "provenance": {},
                }
                with self.assertRaisesRegex(
                    ValueError, f"result.resources.{field}"
                ):
                    validate_json_schema_instance(fixture, schema, "result")

    def test_curriculum_schema_declares_stable_module_contract(self) -> None:
        schema = json.loads((ROOT / "schemas" / "curriculum.schema.json").read_text())
        module = schema["$defs"]["module"]
        self.assertEqual(schema["properties"]["modules"]["minItems"], 15)
        self.assertEqual(schema["properties"]["modules"]["maxItems"], 15)
        self.assertLessEqual(
            {
                "id",
                "slug",
                "title",
                "implementation",
                "evidence",
                "observable",
                "representation",
                "inference",
                "objectives",
                "metrics",
                "failure_sweep",
                "insula",
                "sources",
            },
            set(module["required"]),
        )
        self.assertEqual(
            module["properties"]["implementation"]["enum"],
            ["synthetic", "real", "real+baseline"],
        )

    def test_curriculum_has_fifteen_ordered_modules_with_stable_interfaces(self) -> None:
        curriculum = json.loads((ROOT / "curriculum" / "curriculum.json").read_text())
        modules = curriculum["modules"]
        self.assertEqual([item["id"] for item in modules], [f"{i:02d}" for i in range(1, 16)])
        for module in modules:
            with self.subTest(module=module["id"]):
                self.assertRegex(module["slug"], r"^[a-z0-9-]+$")
                self.assertIn(module["inference"], {"analytic", "optimized", "amortized", "sampled", "hybrid"})
                self.assertTrue(module["evidence"])
                self.assertTrue(module["representation"])
                self.assertTrue(module["objectives"])
                self.assertTrue(module["metrics"])
                self.assertTrue(module["failure_sweep"])
                self.assertTrue(module["sources"])
                self.assertIn(module["insula"], curriculum["insulas"])
                expected_implementation = "real" if module["id"] == "06" else "synthetic"
                self.assertEqual(module["implementation"], expected_implementation)

    def test_metric_provenance_distinguishes_real_illustrative_and_synthetic_metrics(self) -> None:
        from pipeline.validator import validate_result

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            for module_id, expected in {
                "06": {
                    ("geometry", "depth_absrel"): "computed_real",
                    ("geometry", "depth_delta_lt_1_25"): "computed_real",
                    ("geometry", "valid_pixel_fraction"): "computed_real",
                },
                "07": {
                    ("geometry", "ate_before_loop_m"): "computed_synthetic",
                    ("geometry", "ate_after_loop_m"): "computed_synthetic",
                    ("geometry", "map_f_score"): "illustrative",
                },
            }.items():
                with self.subTest(module=module_id):
                    completed = run_cli(
                        "run",
                        "--module",
                        module_id,
                        "--profile",
                        "smoke",
                        "--run-id",
                        f"metric-labels-{module_id}",
                        cache=cache,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    result = validate_result(
                        cache / "runs" / f"metric-labels-{module_id}" / module_id,
                        module_id,
                    )
                    expected_implementation = "real" if module_id == "06" else "synthetic"
                    self.assertEqual(result["module_implementation"], expected_implementation)
                    for (family, metric), label in expected.items():
                        self.assertEqual(
                            result["metric_provenance"][family][metric],
                            label,
                        )

    def test_validator_rejects_real_modules_with_noncomputed_metric_labels(self) -> None:
        from pipeline.validator import validate_result

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            completed = run_cli(
                "run",
                "--module",
                "06",
                "--profile",
                "smoke",
                "--run-id",
                "real-provenance-check",
                cache=cache,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "runs" / "real-provenance-check" / "06"
            result_path = run_dir / "result.json"
            result = json.loads(result_path.read_text())
            result["metric_provenance"]["geometry"]["depth_absrel"] = "illustrative"
            result_path.write_text(json.dumps(result, sort_keys=True) + "\n")

            with self.assertRaisesRegex(
                ValueError,
                "real module metrics must be computed",
            ):
                validate_result(run_dir, "06")

    def test_source_registry_is_primary_unique_and_claim_bearing(self) -> None:
        sources = json.loads((ROOT / "assets" / "sources.json").read_text())["sources"]
        ids = [source["id"] for source in sources]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(sources), 45)
        for source in sources:
            with self.subTest(source=source["id"]):
                self.assertTrue(source["title"])
                self.assertTrue(source["authors"])
                self.assertIsInstance(source["year"], int)
                self.assertTrue(source["venue"])
                self.assertRegex(source["primary_url"], r"^https://")
                self.assertTrue(source["themes"])
                self.assertTrue(source["claims"])
        caveats = " ".join(source.get("credit_caveat", "") for source in sources).lower()
        self.assertIn("bundle adjustment", caveats)
        self.assertIn("splatting", caveats)

    def test_curriculum_references_registered_sources_and_locked_assets(self) -> None:
        curriculum = json.loads((ROOT / "curriculum" / "curriculum.json").read_text())
        source_ids = {item["id"] for item in json.loads((ROOT / "assets" / "sources.json").read_text())["sources"]}
        for module in curriculum["modules"]:
            self.assertLessEqual(set(module["sources"]), source_ids)

        assets = json.loads((ROOT / "assets" / "assets.lock.json").read_text())["assets"]
        self.assertEqual(
            {item["id"] for item in assets},
            {
                "controlled-suite",
                "middlebury-mvs",
                "tum-rgbd",
                "depth-anything-v2-metric-hypersim-small",
                "nerfstudio-lpips-alexnet",
                "foundation-geometry-models",
                "nerf-synthetic",
                "surflo-paired-scenes",
                "surflo-visible-scout",
            },
        )
        for asset in assets:
            self.assertIn(asset["mode"], {"generated", "download", "huggingface_snapshot", "repository"})
            self.assertRegex(asset["sha256"], r"^[0-9a-f]{64}$")


class DispatcherContractTest(unittest.TestCase):
    def test_gpu_selection_skips_reset_devices_and_validates_overrides(self) -> None:
        from pipeline.contracts import selected_gpu_device

        completed = subprocess.CompletedProcess(
            ["nvidia-smi"],
            0,
            stdout="0, Reset\n1, None\n2, None\n",
            stderr="",
        )
        with (
            patch.dict(os.environ, {}, clear=False),
            patch("contracts.shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("contracts.subprocess.run", return_value=completed),
        ):
            os.environ.pop("SURFLO_PATHWAY_GPU_DEVICE", None)
            self.assertEqual(selected_gpu_device(), "1")
        with (
            patch.dict(os.environ, {"SURFLO_PATHWAY_GPU_DEVICE": "1"}),
            patch("contracts.shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("contracts.subprocess.run", return_value=completed),
        ):
            self.assertEqual(selected_gpu_device(), "1")
        with (
            patch.dict(os.environ, {"SURFLO_PATHWAY_GPU_DEVICE": "0"}),
            patch("contracts.shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("contracts.subprocess.run", return_value=completed),
        ):
            with self.assertRaisesRegex(ValueError, "requires a reset"):
                selected_gpu_device()
        with (
            patch.dict(os.environ, {"SURFLO_PATHWAY_GPU_DEVICE": "6"}),
            patch("contracts.shutil.which", return_value="/usr/bin/nvidia-smi"),
            patch("contracts.subprocess.run", return_value=completed),
        ):
            with self.assertRaisesRegex(ValueError, "not reported"):
                selected_gpu_device()
        with patch.dict(os.environ, {"SURFLO_PATHWAY_GPU_DEVICE": "6"}):
            self.assertEqual(selected_gpu_device(require_health=False), "6")

    def test_list_returns_machine_readable_module_catalog(self) -> None:
        result = run_cli("list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        catalog = json.loads(result.stdout)
        self.assertEqual(len(catalog), 15)
        self.assertEqual(catalog[0]["id"], "01")
        self.assertEqual(catalog[-1]["id"], "15")

    def test_execution_plans_are_offline_and_build_fetch_are_explicitly_networked(self) -> None:
        run_plan = run_cli("--emit-plan", "run", "--module", "01", "--profile", "smoke")
        self.assertEqual(run_plan.returncode, 0, run_plan.stderr)
        self.assertEqual(json.loads(run_plan.stdout)["network_mode"], "offline")

        for command in ("build", "fetch"):
            with self.subTest(command=command):
                plan = run_cli("--emit-plan", command)
                self.assertEqual(plan.returncode, 0, plan.stderr)
                self.assertEqual(json.loads(plan.stdout)["network_mode"], "networked")

    def test_smoke_run_promotes_only_a_validated_complete_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            result = run_cli(
                "run", "--module", "01", "--profile", "smoke", "--run-id", "contract-01", cache=cache
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = cache / "runs" / "contract-01" / "01"
            self.assertTrue((run_dir / "result.json").is_file())
            self.assertTrue((run_dir / "report.md").is_file())
            self.assertTrue((run_dir / "artifacts" / "failure_sweep.csv").is_file())
            self.assertFalse(any((cache / "staging").glob("*")))

            payload = json.loads((run_dir / "result.json").read_text())
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["module_id"], "01")
            self.assertEqual(payload["profile"], "smoke")
            self.assertEqual(payload["status"], "complete")
            self.assertEqual(payload["network_mode"], "offline")
            self.assertTrue(payload["metrics"])
            self.assertTrue(payload["failure_sweep"])
            self.assertIn("runtime_seconds", payload["resources"])
            self.assertIn("peak_cpu_bytes", payload["resources"])
            self.assertEqual(
                payload["resources"]["network_isolation"],
                "python_socket_guard",
            )
            self.assertEqual(
                payload["resources"]["cpu_memory_scope"],
                "process_lifetime_high_water_mark",
            )
            self.assertIn("environment", payload["provenance"])
            self.assertIn("inputs_sha256", payload["provenance"])
            self.assertIn("config_sha256", payload["provenance"])
            self.assertIn("artifacts_sha256", payload["provenance"])
            module_text = (run_dir / "report.md").read_text()
            self.assertIn("network_isolation=python_socket_guard", module_text)
            self.assertIn(
                "cpu_memory_scope=process_lifetime_high_water_mark", module_text
            )

            validation = run_cli("validate", "--module", "01", "--run-id", "contract-01", cache=cache)
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertIn("valid", validation.stdout.lower())

    def test_report_aggregates_tasks_without_collapsing_metric_families(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            run_result = run_cli(
                "run", "--module", "01", "--profile", "smoke", "--run-id", "report-01", cache=cache
            )
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            report = run_cli("report", "--run-id", "report-01", cache=cache)
            self.assertEqual(report.returncode, 0, report.stderr)
            report_path = Path(report.stdout.strip())
            text = report_path.read_text()
            self.assertIn("Geometry metrics", text)
            self.assertIn("Rendering metrics", text)
            self.assertIn("Generative metrics", text)
            self.assertIn("network_isolation=python_socket_guard", text)
            self.assertIn(
                "cpu_memory_scope=process_lifetime_high_water_mark", text
            )


class InsulaContractTest(unittest.TestCase):
    def test_insulas_are_distinct_and_content_pinned(self) -> None:
        locks = json.loads((ROOT / "insulas" / "locks.json").read_text())["insulas"]
        self.assertEqual(
            set(locks),
            {
                "classical",
                "classical-mvs",
                "orb-slam",
                "neural-rendering",
                "implicit-surface",
                "radiance-field",
                "gaussian-splatting",
            },
        )
        self.assertNotEqual(locks["classical"]["base_image"], locks["neural-rendering"]["base_image"])
        for name, lock in locks.items():
            with self.subTest(name=name):
                dockerfile = ROOT / "insulas" / name / "Dockerfile"
                self.assertTrue(dockerfile.is_file())
                first_line = dockerfile.read_text().splitlines()[0]
                self.assertRegex(first_line, r"^FROM .+@sha256:[0-9a-f]{64}(?: AS builder)?$")
                digest = hashlib.sha256(dockerfile.read_bytes()).hexdigest()
                self.assertEqual(digest, lock["dockerfile_sha256"])
                self.assertRegex(lock["base_image_digest"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
