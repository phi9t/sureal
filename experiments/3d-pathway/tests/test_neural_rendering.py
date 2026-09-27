from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


class LearnedAndRenderableLabContractTest(unittest.TestCase):
    def test_module_11_metrics_are_recomputed_from_persisted_gaussian_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            completed = subprocess.run(
                [
                    str(ROOT / "run.sh"),
                    "run",
                    "--module",
                    "11",
                    "--profile",
                    "smoke",
                    "--run-id",
                    "splats",
                ],
                cwd=ROOT.parent.parent,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

            run_dir = cache / "runs" / "splats" / "11"
            result = json.loads((run_dir / "result.json").read_text())
            comparison = json.loads(
                (run_dir / "artifacts" / "gaussian_comparison.json").read_text()
            )
            self.assertEqual(comparison["schema_version"], 1)
            self.assertEqual(comparison["evidence"], "calibrated synthetic RGB")
            self.assertEqual(
                comparison["representation"],
                "simplified isotropic screen-space Gaussian samples",
            )
            self.assertEqual(comparison["inference"], "analytic controlled construction")
            self.assertFalse(comparison["mesh_extraction_supported"])
            self.assertFalse(comparison["completion_claim"])

            with np.load(run_dir / "artifacts" / "gaussian_comparison.npz") as arrays:
                truth = arrays["truth_rgb"].astype(np.float64)
                predicted = arrays["splat_rgb"].astype(np.float64)
                unregularized = arrays["unregularized_means_m"].astype(np.float64)
                regularized = arrays["regularized_means_m"].astype(np.float64)
                radius = float(arrays["truth_radius_m"])
                mse = float(np.mean((predicted - truth) ** 2))
                psnr = float(-10.0 * np.log10(mse))
                unregularized_rmse = float(
                    np.sqrt(np.mean((np.linalg.norm(unregularized, axis=1) - radius) ** 2))
                )
                regularized_rmse = float(
                    np.sqrt(np.mean((np.linalg.norm(regularized, axis=1) - radius) ** 2))
                )

            self.assertAlmostEqual(
                result["metrics"]["rendering"]["splat_psnr_db"], psnr, places=10
            )
            self.assertAlmostEqual(
                result["metrics"]["geometry"]["unregularized_surface_rmse_m"],
                unregularized_rmse,
                places=10,
            )
            self.assertAlmostEqual(
                result["metrics"]["geometry"]["regularized_surface_rmse_m"],
                regularized_rmse,
                places=10,
            )
            self.assertGreater(unregularized_rmse, regularized_rmse)
            self.assertEqual(
                {row["parameter"] for row in result["failure_sweep"]},
                {"primitive_count", "depth_jitter_amplitude_m"},
            )

    def test_module_10_metrics_are_recomputed_from_persisted_field_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            completed = subprocess.run(
                [str(ROOT / "run.sh"), "run", "--module", "10", "--profile", "smoke", "--run-id", "fields"],
                cwd=ROOT.parent.parent,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

            run_dir = cache / "runs" / "fields" / "10"
            result = json.loads((run_dir / "result.json").read_text())
            comparison = json.loads((run_dir / "artifacts" / "comparison.json").read_text())
            self.assertEqual(comparison["schema_version"], 1)
            self.assertEqual(comparison["evidence"], "posed RGB only")
            self.assertEqual(comparison["radiance_field"]["representation"], "volume density and radiance")
            self.assertEqual(comparison["surface_model"]["representation"], "signed-distance level set")
            self.assertEqual(
                comparison["radiance_field"]["rendering_operator"],
                "alpha compositing",
            )
            self.assertEqual(
                comparison["surface_model"]["rendering_operator"],
                "zero-level ray intersection",
            )
            self.assertFalse(comparison["radiance_field"]["completion_claim"])
            self.assertFalse(comparison["surface_model"]["completion_claim"])

            with np.load(run_dir / "artifacts" / "field_comparison.npz") as arrays:
                truth_rgb = arrays["truth_rgb"]
                evaluation_mask = arrays["evaluation_mask"].astype(bool)
                truth_depth = arrays["truth_depth_m"]
                sample_depths = arrays["sample_depths_m"]
                surface_sdf = arrays["surface_model_sdf_samples"]
                self.assertEqual(surface_sdf.shape, (*truth_depth.shape, len(sample_depths)))
                crossing = (surface_sdf[..., :-1] <= 0.0) & (surface_sdf[..., 1:] >= 0.0)
                self.assertTrue(np.all(np.any(crossing[evaluation_mask], axis=-1)))
                recomputed = {}
                for name in ("radiance_field", "surface_model"):
                    predicted_rgb = arrays[f"{name}_rgb"]
                    predicted_depth = arrays[f"{name}_depth_m"]
                    mse = float(np.mean((predicted_rgb - truth_rgb) ** 2))
                    recomputed[f"{name}_psnr_db"] = float(-10.0 * np.log10(mse))
                    residual = predicted_depth[evaluation_mask] - truth_depth[evaluation_mask]
                    recomputed[f"{name}_rmse_m"] = float(np.sqrt(np.mean(residual * residual)))

                crossing_index = np.argmax(crossing, axis=-1)
                low = np.take(sample_depths, crossing_index)
                high = np.take(sample_depths, crossing_index + 1)
                low_sdf = np.take_along_axis(
                    surface_sdf, crossing_index[..., None], axis=-1
                )[..., 0]
                high_sdf = np.take_along_axis(
                    surface_sdf, (crossing_index + 1)[..., None], axis=-1
                )[..., 0]
                offset = np.zeros_like(low)
                np.divide(
                    low_sdf * (high - low),
                    high_sdf - low_sdf,
                    out=offset,
                    where=(high_sdf - low_sdf) != 0.0,
                )
                root = low - offset
                self.assertTrue(
                    np.allclose(
                        arrays["surface_model_depth_m"][evaluation_mask],
                        root[evaluation_mask],
                        atol=1e-12,
                        rtol=0.0,
                    )
                )

            rendering = result["metrics"]["rendering"]
            geometry = result["metrics"]["geometry"]
            self.assertAlmostEqual(
                rendering["radiance_field_psnr_db"],
                recomputed["radiance_field_psnr_db"],
                places=10,
            )
            self.assertAlmostEqual(
                rendering["surface_model_psnr_db"],
                recomputed["surface_model_psnr_db"],
                places=10,
            )
            self.assertAlmostEqual(
                geometry["radiance_field_rendered_depth_rmse_m"],
                recomputed["radiance_field_rmse_m"],
                places=10,
            )
            self.assertAlmostEqual(
                geometry["surface_model_rmse_m"],
                recomputed["surface_model_rmse_m"],
                places=10,
            )
            self.assertEqual(
                {row["value"] for row in result["failure_sweep"]},
                {3, 5, 9},
            )

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
            self.assertGreater(radiance["geometry"]["radiance_field_rendered_depth_rmse_m"], radiance["geometry"]["surface_model_rmse_m"])

            splats = results["11"]["metrics"]
            self.assertGreater(splats["rendering"]["splat_psnr_db"], 0.0)
            self.assertGreater(
                splats["geometry"]["unregularized_surface_rmse_m"],
                splats["geometry"]["regularized_surface_rmse_m"],
            )
            self.assertFalse(splats["geometry"]["mesh_extraction_supported"])

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
