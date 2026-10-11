from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import numpy as np

import pipeline.classical_chain as classical_chain
from pipeline.classical_chain import run_classical_chain_profile
from pipeline.contracts import load_json
from pipeline.runner import run_module
import scene.orbit as orbit
from sfm.reconstruction import CameraPose, Reconstruction


def _toy_reconstruction(scale: float = 1.0) -> Reconstruction:
    intrinsic = np.array(
        [
            [100.0, 0.0, 32.0],
            [0.0, 100.0, 24.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    cameras = {
        "a": CameraPose(np.eye(3), scale * np.array([0.0, 0.0, 0.0])),
        "b": CameraPose(np.eye(3), scale * np.array([-0.5, 0.0, 0.0])),
        "c": CameraPose(np.eye(3), scale * np.array([0.5, 0.0, 0.0])),
    }
    points = {
        0: scale * np.array([-0.8, -0.2, 4.0], dtype=np.float64),
        1: scale * np.array([0.1, 0.3, 4.2], dtype=np.float64),
        2: scale * np.array([0.7, -0.1, 4.5], dtype=np.float64),
        3: scale * np.array([0.3, 0.4, 4.7], dtype=np.float64),
        4: scale * np.array([-0.4, 0.1, 4.9], dtype=np.float64),
        5: scale * np.array([0.0, -0.3, 5.1], dtype=np.float64),
        6: scale * np.array([0.5, 0.2, 5.4], dtype=np.float64),
        7: scale * np.array([-0.6, 0.4, 5.6], dtype=np.float64),
    }
    return Reconstruction(
        intrinsic,
        cameras,
        points,
        observations=[],
        registered_view_ids=["a", "b", "c"],
    )


class ClassicalChainTest(unittest.TestCase):
    def test_trimmed_icp_refinement_reports_small_similarity_correction(self) -> None:
        rng = np.random.default_rng(260925)
        truth = rng.normal(size=(80, 3))
        angle = np.deg2rad(1.0)
        rotation = np.array(
            [
                [np.cos(angle), -np.sin(angle), 0.0],
                [np.sin(angle), np.cos(angle), 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        translation = np.array([0.03, -0.02, 0.01], dtype=np.float64)
        source = 1.01 * (rotation @ truth.T).T + translation

        refined = classical_chain._refine_surface_alignment(
            source,
            truth,
            tau=0.05,
        )

        before = classical_chain.surface_metrics(source, truth, tau=0.05)
        self.assertLess(refined.metrics["chamfer_distance"], before["chamfer_distance"])
        self.assertGreater(refined.metrics["f_score"], before["f_score"])
        self.assertLess(refined.rotation_deg, 1.1)
        self.assertLess(refined.translation_m, 0.04)
        self.assertLess(abs(refined.scale - 1.0), 0.02)

    def test_gauge_parameters_scale_with_reconstruction_units(self) -> None:
        settings = classical_chain._profile_settings("full")
        base = classical_chain._derive_gauge_parameters(
            _toy_reconstruction(),
            ["a", "b", "c"],
            settings,
            profile="full",
        )
        scaled = classical_chain._derive_gauge_parameters(
            _toy_reconstruction(scale=1.7),
            ["a", "b", "c"],
            settings,
            profile="full",
        )

        self.assertAlmostEqual(base.voxel_size_m, settings.voxel_size_m)
        self.assertAlmostEqual(base.truncation_m, settings.truncation_m)
        self.assertAlmostEqual(base.padding_m, settings.padding_m)
        np.testing.assert_allclose(
            scaled.depth_hypotheses_m,
            1.7 * base.depth_hypotheses_m,
            rtol=1e-12,
            atol=1e-12,
        )
        self.assertAlmostEqual(scaled.voxel_size_m, 1.7 * base.voxel_size_m)
        self.assertAlmostEqual(scaled.truncation_m, 1.7 * base.truncation_m)
        self.assertAlmostEqual(scaled.padding_m, 1.7 * base.padding_m)

    def test_estimation_path_does_not_use_orbit_profile_ground_truth_scale(self) -> None:
        def rejected(*args: object, **kwargs: object) -> np.ndarray:
            raise AssertionError("ground-truth orbit camera centers are score-only")

        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    orbit,
                    "orbit_profile_camera_centers",
                    side_effect=rejected,
                    create=True,
                )
            )
            stack.enter_context(
                patch.object(
                    classical_chain,
                    "orbit_profile_camera_centers",
                    side_effect=rejected,
                    create=True,
                )
            )
            summary = run_classical_chain_profile(Path(temporary) / "chain", "smoke")

        self.assertGreater(summary["metrics"]["mesh_vertex_count"], 100)

    def test_chain_runs_sfm_depth_fusion_and_scores_sim3_aligned_mesh(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            summary = run_classical_chain_profile(
                Path(temporary) / "chain",
                "smoke",
                include_pose_attribution=True,
            )

        metrics = summary["metrics"]
        self.assertEqual(
            summary["mesh_alignment"],
            "sim3_to_ground_truth_then_score_only_icp",
        )
        self.assertEqual(metrics["registered_view_count"], metrics["evaluated_view_count"])
        self.assertGreaterEqual(metrics["registered_view_count"], 3)
        self.assertGreater(metrics["mesh_vertex_count"], 100)
        self.assertGreater(metrics["mesh_triangle_count"], 100)
        # Smoke is a plumbing tier only; full-profile tests own accuracy bounds.
        self.assertLess(metrics["surface_chamfer_m"], 0.35)
        self.assertGreater(metrics["surface_f_score_tau"], 0.40)
        self.assertIn("camera_aligned_surface_chamfer_m", metrics)
        self.assertIn("icp_refined_surface_chamfer_m", metrics)
        self.assertEqual(
            metrics["surface_chamfer_m"],
            metrics["icp_refined_surface_chamfer_m"],
        )
        attribution = summary["pose_attribution_diagnostic"]
        self.assertEqual(
            attribution["estimate_use"],
            "diagnostic_only_not_used_by_sfm_pose_chain",
        )
        self.assertIn("ground_truth_pose", attribution["metrics"])
        self.assertIn("sfm_pose", attribution["metrics"])

    def test_hiding_ground_truth_from_estimator_does_not_change_primary_mesh(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            visible = run_classical_chain_profile(Path(temporary) / "visible", "smoke")
            hidden = run_classical_chain_profile(
                Path(temporary) / "hidden",
                "smoke",
                hide_estimation_ground_truth=True,
            )

        self.assertEqual(
            visible["artifacts"]["depth_maps_sha256"],
            hidden["artifacts"]["depth_maps_sha256"],
        )
        self.assertEqual(
            visible["artifacts"]["mesh_sha256"],
            hidden["artifacts"]["mesh_sha256"],
        )
        self.assertEqual(
            visible["metrics"]["mesh_vertex_count"],
            hidden["metrics"]["mesh_vertex_count"],
        )
        self.assertEqual(
            visible["metrics"]["mesh_triangle_count"],
            hidden["metrics"]["mesh_triangle_count"],
        )

    def test_module06_reports_classical_chain_as_real_plus_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            run_dir = run_module(cache, "06", "smoke", "module06-chain")
            result = load_json(run_dir / "result.json")

        geometry = result["metrics"]["geometry"]
        self.assertEqual(result["module_implementation"], "real+baseline")
        for name in (
            "registered_view_count",
            "depth_absrel",
            "surface_chamfer_m",
            "surface_f_score_tau",
            "mesh_vertex_count",
            "mesh_triangle_count",
        ):
            self.assertIn(name, geometry)
            self.assertEqual(
                result["metric_provenance"]["geometry"][name],
                "computed_real",
            )

    def test_module04_registration_and_fusion_metrics_are_computed_real(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            run_dir = run_module(cache, "04", "smoke", "module04-real")
            result = load_json(run_dir / "result.json")

        geometry = result["metrics"]["geometry"]
        self.assertEqual(result["module_implementation"], "real")
        self.assertNotIn("mesh_completeness", geometry)
        for name in (
            "icp_initial_rmse_m",
            "icp_final_rmse_m",
            "surface_chamfer_m",
            "surface_f_score_tau",
        ):
            self.assertIn(name, geometry)
            self.assertEqual(
                result["metric_provenance"]["geometry"][name],
                "computed_real",
            )


if __name__ == "__main__":
    unittest.main()
