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


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
sys.path.insert(0, str(PIPELINE))


def run_cli(*args: str, cache: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if cache is not None:
        env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
    return subprocess.run(
        [str(ROOT / "run.sh"), *args],
        cwd=ROOT.parent.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class RegistryContractTest(unittest.TestCase):
    def test_curriculum_schema_declares_stable_module_contract(self) -> None:
        schema = json.loads((ROOT / "curriculum.schema.json").read_text())
        module = schema["$defs"]["module"]
        self.assertEqual(schema["properties"]["modules"]["minItems"], 15)
        self.assertEqual(schema["properties"]["modules"]["maxItems"], 15)
        self.assertLessEqual(
            {"id", "slug", "title", "evidence", "observable", "representation", "inference", "objectives", "metrics", "failure_sweep", "insula", "sources"},
            set(module["required"]),
        )

    def test_curriculum_has_fifteen_ordered_modules_with_stable_interfaces(self) -> None:
        curriculum = json.loads((ROOT / "curriculum.json").read_text())
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

    def test_source_registry_is_primary_unique_and_claim_bearing(self) -> None:
        sources = json.loads((ROOT / "sources.json").read_text())["sources"]
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
        curriculum = json.loads((ROOT / "curriculum.json").read_text())
        source_ids = {item["id"] for item in json.loads((ROOT / "sources.json").read_text())["sources"]}
        for module in curriculum["modules"]:
            self.assertLessEqual(set(module["sources"]), source_ids)

        assets = json.loads((ROOT / "assets.lock.json").read_text())["assets"]
        self.assertEqual(
            {item["id"] for item in assets},
            {
                "controlled-suite",
                "middlebury-mvs",
                "tum-rgbd",
                "depth-anything-v2-metric-hypersim-small",
                "nerf-synthetic",
                "surflo-paired-scenes",
            },
        )
        for asset in assets:
            self.assertIn(asset["mode"], {"generated", "download", "repository"})
            self.assertRegex(asset["sha256"], r"^[0-9a-f]{64}$")


class DispatcherContractTest(unittest.TestCase):
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
            self.assertIn("environment", payload["provenance"])
            self.assertIn("inputs_sha256", payload["provenance"])
            self.assertIn("config_sha256", payload["provenance"])
            self.assertIn("artifacts_sha256", payload["provenance"])

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


class InsulaContractTest(unittest.TestCase):
    def test_insulas_are_distinct_and_content_pinned(self) -> None:
        locks = json.loads((ROOT / "insulas" / "locks.json").read_text())["insulas"]
        self.assertEqual(set(locks), {"classical", "classical-mvs", "orb-slam", "neural-rendering"})
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
