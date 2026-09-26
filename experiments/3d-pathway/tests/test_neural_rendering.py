from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LearnedAndRenderableLabContractTest(unittest.TestCase):
    def test_modules_08_through_11_keep_geometry_and_rendering_claims_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            results: dict[str, dict] = {}
            for module_id in ("08", "09", "10", "11"):
                completed = subprocess.run(
                    [str(ROOT / "run.sh"), "run", "--module", module_id, "--profile", "smoke", "--run-id", "neural"],
                    cwd=ROOT.parent.parent,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, f"module {module_id}: {completed.stderr}")
                run_dir = cache / "runs" / "neural" / module_id
                results[module_id] = json.loads((run_dir / "result.json").read_text())
                self.assertTrue(any((run_dir / "artifacts").glob("*.svg")))

            learned = results["08"]["metrics"]["geometry"]
            self.assertLess(learned["scale_aligned_rmse_m"], learned["metric_rmse_m"])
            self.assertGreater(learned["unsupported_completion_fraction"], 0.0)

            implicit = results["09"]["metrics"]["geometry"]
            self.assertGreater(implicit["voxel_memory_at_512_mib"], implicit["implicit_model_mib"])
            self.assertGreater(implicit["marching_cubes_evaluations"], 0)
            self.assertEqual(implicit["representations_compared"], 3)
            self.assertGreater(implicit["voxel_surface_rmse_m"], implicit["sdf_surface_rmse_m"])
            self.assertGreaterEqual(
                implicit["occupancy_surface_rmse_m"], implicit["sdf_surface_rmse_m"]
            )
            self.assertGreater(implicit["unsupported_surface_fraction"], 0.0)
            self.assertGreater(implicit["hidden_counterfactual_disagreement_fraction"], 0.0)
            self.assertTrue(
                (cache / "runs/neural/09/artifacts/representation_comparison.csv").is_file()
            )
            with (
                cache / "runs/neural/09/artifacts/representation_comparison.csv"
            ).open(newline="") as stream:
                storage = {
                    float(row["sampled_grid_storage_mib"])
                    for row in csv.DictReader(stream)
                }
            self.assertEqual(len(storage), 1, "all dense grids use the declared float32 encoding")
            self.assertGreaterEqual(
                len({
                    row["parameter"]
                    for row in results["09"]["failure_sweep"]
                }),
                2,
            )

            radiance = results["10"]["metrics"]
            self.assertGreater(radiance["rendering"]["radiance_field_psnr_db"], radiance["rendering"]["surface_model_psnr_db"])
            self.assertGreater(radiance["geometry"]["radiance_field_surface_rmse_m"], radiance["geometry"]["surface_model_rmse_m"])

            splats = results["11"]["metrics"]
            self.assertGreater(splats["rendering"]["splat_psnr_db"], splats["rendering"]["extracted_mesh_psnr_db"])
            self.assertGreater(splats["geometry"]["unregularized_surface_rmse_m"], splats["geometry"]["regularized_surface_rmse_m"])

    def test_report_explicitly_marks_non_applicable_metric_families(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            completed = subprocess.run(
                [str(ROOT / "run.sh"), "run", "--module", "08", "--profile", "smoke", "--run-id", "depth"],
                cwd=ROOT.parent.parent,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = (cache / "runs" / "depth" / "08" / "report.md").read_text()
            self.assertIn("Rendering metrics", report)
            self.assertIn("Generative metrics", report)
            self.assertGreaterEqual(report.count("Not applicable for this module."), 2)


if __name__ == "__main__":
    unittest.main()
