from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))


class AmbiguousSceneContractTest(unittest.TestCase):
    def test_shared_scene_latent_is_coherent_while_independent_points_hybridize(self) -> None:
        from generative import compare_ambiguous_samplers

        comparison = compare_ambiguous_samplers(samples=128, points_per_sample=257, seed=13)
        independent = comparison["independent_points"]
        shared = comparison["shared_scene_latent"]
        self.assertLess(independent["within_sample_coherence"], 0.65)
        self.assertEqual(shared["within_sample_coherence"], 1.0)
        self.assertGreater(independent["hypothesis_coverage"], 0.9)
        self.assertGreater(shared["hypothesis_coverage"], 0.9)
        self.assertEqual(independent["evidence_consistency"], 1.0)
        self.assertEqual(shared["evidence_consistency"], 1.0)


class FrontierLabContractTest(unittest.TestCase):
    def test_modules_12_through_15_emit_foundation_generation_dynamic_and_surflo_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            results: dict[str, dict] = {}
            for module_id in ("12", "13", "14", "15"):
                completed = subprocess.run(
                    [str(ROOT / "run.sh"), "run", "--module", module_id, "--profile", "smoke", "--run-id", "frontier"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, f"module {module_id}: {completed.stderr}")
                run_dir = cache / "runs" / "frontier" / module_id
                results[module_id] = json.loads((run_dir / "result.json").read_text())
                self.assertTrue(any((run_dir / "artifacts").glob("*.svg")))

            foundation = results["12"]["metrics"]["geometry"]
            self.assertLess(foundation["aligned_point_rmse_m"], foundation["raw_point_rmse_m"])
            self.assertEqual(foundation["hidden_surface_recall"], 0.0)

            generation = results["13"]["metrics"]["generative"]
            self.assertGreater(generation["shared_latent_coherence"], generation["independent_point_coherence"])
            self.assertGreater(generation["shared_latent_hypothesis_coverage"], 0.9)

            dynamics = results["14"]["metrics"]["geometry"]
            self.assertGreater(dynamics["moving_camera_object_post_occlusion_error_m"], dynamics["static_camera_post_occlusion_error_m"])

            surflo = results["15"]
            photoreal = REPO_ROOT / "experiments" / "photoreal-scenes" / "results.json"
            expected_hash = hashlib.sha256(photoreal.read_bytes()).hexdigest()
            self.assertEqual(surflo["source_results_sha256"], expected_hash)
            self.assertEqual(surflo["metrics"]["generative"]["hidden_hypothesis_support"], 0.0)
            self.assertEqual(surflo["observations"][0], "Tracked paired-scene outcome: unsupported for all four seeds.")

    def test_all_smoke_runs_every_module_and_builds_cross_era_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            completed = subprocess.run(
                [str(ROOT / "run.sh"), "all", "--profile", "smoke", "--run-id", "all-smoke"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_root = cache / "runs" / "all-smoke"
            self.assertEqual(len(list(run_root.glob("[0-9][0-9]/result.json"))), 15)
            report = (run_root / "report.md").read_text()
            self.assertIn("01 Image formation and observability", report)
            self.assertIn("15 Surflo as the current case study", report)
            self.assertIn("Metrics from different task families", report)


if __name__ == "__main__":
    unittest.main()
