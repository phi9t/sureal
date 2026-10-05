from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "pipeline"))

from cli import dispatch_plan, parser, stage_reference_suite  # noqa: E402
from contracts import full_acceptance_status, load_json  # noqa: E402
from reporting import aggregate_report, module_report  # noqa: E402
from validator import validate_report  # noqa: E402


EXPECTED_REFERENCE_ADAPTERS = [
    "colmap-sfm",
    "colmap-mvs",
    "orb-slam",
    "depth-anything-v2",
    "neus-facto",
    "nerfacto",
    "splatfacto",
    "foundation-geometry",
]


class EndToEndCompletionContractTest(unittest.TestCase):
    def test_real_full_aggregate_is_an_opt_in_b200_gate(self) -> None:
        if os.environ.get("SURFLO_REQUIRE_PATHWAY_FULL") != "1":
            self.skipTest("set SURFLO_REQUIRE_PATHWAY_FULL=1 for the B200 all-full gate")
        cache = Path(
            os.environ.get(
                "SURFLO_PATHWAY_CACHE_ROOT",
                Path.home() / ".cache/surflo/3d-pathway",
            )
        ).expanduser()
        run_id = f"pathway-full-gate-{os.getpid()}-{time.time_ns()}"
        env = os.environ.copy()
        env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
        completed = subprocess.run(
            [str(ROOT / "run.sh"), "all", "--profile", "full", "--run-id", run_id],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        manifest = load_json(cache / "runs" / run_id / "report.json")
        self.assertTrue(manifest["full_acceptance"])
        self.assertEqual(manifest["profiles"], ["full"])
        self.assertEqual(manifest["reference_profiles"], ["full"])

    def test_full_acceptance_requires_full_modules_and_full_references(self) -> None:
        modules = [f"{index:02d}" for index in range(1, 16)]
        references = list(EXPECTED_REFERENCE_ADAPTERS)

        self.assertTrue(
            full_acceptance_status(
                modules,
                modules,
                ["full"],
                references,
                references,
                ["full"],
            )
        )
        self.assertFalse(
            full_acceptance_status(
                modules,
                modules,
                ["full"],
                references,
                references,
                ["smoke"],
            )
        )
        self.assertFalse(
            full_acceptance_status(
                modules,
                modules,
                ["full"],
                references,
                references,
                ["full", "smoke"],
            )
        )

    def test_reference_suite_is_moved_under_the_atomic_aggregate_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            cache.mkdir()
            aggregate = Path(temporary) / "aggregate"
            aggregate.mkdir()

            def external_reference_run(
                cache_root: Path,
                adapter: str,
                profile: str,
                child_run_id: str,
            ) -> Path:
                self.assertEqual(cache_root, cache)
                self.assertEqual(profile, "full")
                run_dir = cache_root / "reference-runs" / child_run_id / adapter
                run_dir.mkdir(parents=True)
                (run_dir / "witness.txt").write_text(adapter, encoding="utf-8")
                return run_dir

            with (
                patch(
                    "cli.landed_reference_adapter_names",
                    return_value=["adapter-a", "adapter-b"],
                ),
                patch("cli.run_reference", side_effect=external_reference_run),
                patch(
                    "cli.validate_landed_reference_result",
                    side_effect=lambda path, adapter: {
                        "adapter": adapter,
                        "path": str(path),
                    },
                ),
            ):
                staged = stage_reference_suite(cache, aggregate, "full")

            self.assertEqual(
                staged,
                [
                    aggregate / "references" / "adapter-a",
                    aggregate / "references" / "adapter-b",
                ],
            )
            self.assertEqual(
                (aggregate / "references" / "adapter-a" / "witness.txt").read_text(),
                "adapter-a",
            )
            self.assertEqual(
                (aggregate / "references" / "adapter-b" / "witness.txt").read_text(),
                "adapter-b",
            )
            self.assertEqual(list((cache / "reference-runs").iterdir()), [])

    def test_full_all_requires_every_landed_reference_while_smoke_stays_fixture_only(self) -> None:
        full = parser().parse_args(
            ["all", "--profile", "full", "--run-id", "full-e2e"]
        )
        smoke = parser().parse_args(
            ["all", "--profile", "smoke", "--run-id", "smoke-ci"]
        )
        fixture_only = parser().parse_args(
            [
                "all",
                "--profile",
                "full",
                "--run-id",
                "full-fixture",
                "--fixture-only",
            ]
        )

        full_plan = dispatch_plan(full)
        smoke_plan = dispatch_plan(smoke)
        fixture_plan = dispatch_plan(fixture_only)

        self.assertEqual(full_plan["reference_execution"], "required")
        self.assertEqual(full_plan["reference_adapters"], EXPECTED_REFERENCE_ADAPTERS)
        self.assertEqual(smoke_plan["reference_execution"], "not-requested")
        self.assertEqual(smoke_plan["reference_adapters"], [])
        self.assertEqual(fixture_plan["reference_execution"], "not-requested")
        self.assertEqual(fixture_plan["reference_adapters"], [])

    def test_cross_era_report_exposes_resources_assumptions_and_failure_boundaries(self) -> None:
        module = {
            "id": "05",
            "title": "Structure from motion and bundle adjustment",
        }
        module_result = {
            "measurement_kind": "controlled_fixture",
            "metrics": {
                "geometry": {"ba_final_reprojection_rmse_px": 0.125},
                "rendering": {},
                "generative": {},
            },
            "resources": {
                "runtime_seconds": 1.25,
                "peak_cpu_bytes": 4096,
                "peak_gpu_bytes": 0,
                "network_isolation": "python_socket_guard",
                "cpu_memory_scope": "process_lifetime_high_water_mark",
            },
            "observations": ["Monocular SfM retains a global similarity gauge."],
        }
        adapter = {
            "id": "colmap-sfm-reference",
            "modules": ["05"],
            "model_contract": {
                "inference": "per-scene-optimization",
                "completion_claim": False,
            },
            "measurement_note": "Sparse visible structure is not dense surface completion.",
        }
        reference_result = {
            "adapter": "colmap-sfm",
            "module_ids": ["05"],
            "profile": "full",
            "metrics": {
                "registered_images": 9,
                "sparse_points": 512,
                "mean_reprojection_error_px": 0.42,
            },
            "resources": {
                "runtime_seconds": 12.5,
                "peak_cpu_memory_bytes": 8192,
                "peak_gpu_compute_memory_bytes": 16384,
            },
        }

        report = aggregate_report(
            "full-e2e",
            [(module, module_result)],
            [(adapter, reference_result)],
        )

        self.assertIn("Maintained reference measurements", report)
        self.assertIn("colmap-sfm", report)
        self.assertIn("runtime_seconds=12.5", report)
        self.assertIn("peak_gpu_compute_memory_bytes=16384", report)
        self.assertIn("network_isolation=python_socket_guard", report)
        self.assertIn(
            "cpu_memory_scope=process_lifetime_high_water_mark", report
        )
        self.assertIn("per-scene-optimization", report)
        self.assertIn("Sparse visible structure is not dense surface completion.", report)
        self.assertIn("Monocular SfM retains a global similarity gauge.", report)

    def test_smoke_aggregate_binds_module_results_and_declares_reference_incompleteness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            completed = subprocess.run(
                [
                    str(ROOT / "run.sh"),
                    "all",
                    "--profile",
                    "smoke",
                    "--run-id",
                    "aggregate-contract",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_root = cache / "runs" / "aggregate-contract"
            manifest = load_json(run_root / "report.json")

            self.assertEqual(set(manifest["module_results_sha256"]), {
                f"{index:02d}/result.json" for index in range(1, 16)
            })
            self.assertEqual(manifest["reference_adapters"], [])
            self.assertFalse(manifest["complete_reference_suite"])
            self.assertFalse(manifest["full_acceptance"])
            self.assertEqual(manifest["reference_results_sha256"], {})

            # A coherently edited module result/report must still invalidate the
            # already-issued aggregate manifest through its bound result hash.
            result_path = run_root / "01" / "result.json"
            result = load_json(result_path)
            result["metrics"]["geometry"]["camera_fx_px"] = 521.0
            report_path = run_root / "01" / "report.md"
            report_path.write_text(
                module_report(load_json(ROOT / "curriculum.json")["modules"][0], result),
                encoding="utf-8",
            )
            import hashlib

            result["provenance"]["reports_sha256"]["report.md"] = hashlib.sha256(
                report_path.read_bytes()
            ).hexdigest()
            result_path.write_text(
                json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "aggregate module result hash mismatch"):
                validate_report(run_root)


if __name__ == "__main__":
    unittest.main()
