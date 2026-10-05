from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))


class CameraGeometryContractTest(unittest.TestCase):
    def test_projection_round_trip_and_camera_center_recovery(self) -> None:
        from math3d import camera_center, project, unproject

        K = np.array([[500.0, 0.0, 320.0], [0.0, 510.0, 240.0], [0.0, 0.0, 1.0]])
        R = np.eye(3)
        t = np.array([-0.25, 0.1, 0.0])
        points = np.array([[0.2, -0.1, 2.0], [0.8, 0.3, 4.0], [-0.5, 0.2, 3.0]])
        pixels, depth = project(points, K, R, t)
        recovered = unproject(pixels, depth, K, R, t)
        np.testing.assert_allclose(recovered, points, atol=1e-10)
        np.testing.assert_allclose(camera_center(R, t), np.array([0.25, -0.1, 0.0]), atol=1e-12)

    def test_epipolar_residual_and_triangulation_are_numerically_consistent(self) -> None:
        from math3d import fundamental_from_poses, project, symmetric_epipolar_distance, triangulate_point

        K = np.array([[600.0, 0.0, 320.0], [0.0, 600.0, 240.0], [0.0, 0.0, 1.0]])
        R1 = np.eye(3)
        t1 = np.zeros(3)
        R2 = np.eye(3)
        t2 = np.array([-0.2, 0.0, 0.0])
        point = np.array([[0.15, -0.05, 2.5]])
        x1, _ = project(point, K, R1, t1)
        x2, _ = project(point, K, R2, t2)
        F = fundamental_from_poses(K, R1, t1, K, R2, t2)
        self.assertLess(symmetric_epipolar_distance(F, x1[0], x2[0]), 1e-10)
        recovered = triangulate_point(x1[0], x2[0], K, R1, t1, K, R2, t2)
        np.testing.assert_allclose(recovered, point[0], atol=1e-9)

    def test_point_bundle_refinement_reduces_reprojection_error(self) -> None:
        from math3d import project, refine_point_gauss_newton, reprojection_rmse

        K = np.array([[550.0, 0.0, 320.0], [0.0, 550.0, 240.0], [0.0, 0.0, 1.0]])
        cameras = [
            (K, np.eye(3), np.array([0.0, 0.0, 0.0])),
            (K, np.eye(3), np.array([-0.25, 0.0, 0.0])),
            (K, np.eye(3), np.array([0.0, -0.2, 0.0])),
        ]
        truth = np.array([[0.1, -0.15, 2.8]])
        observations = np.array([project(truth, *camera)[0][0] for camera in cameras])
        initial = np.array([0.35, 0.15, 2.1])
        before = reprojection_rmse(initial, observations, cameras)
        refined, history = refine_point_gauss_newton(initial, observations, cameras, iterations=12)
        after = reprojection_rmse(refined, observations, cameras)
        self.assertLess(after, before * 1e-4)
        self.assertLessEqual(history[-1], history[0])

    def test_coordinate_conversion_is_an_involution(self) -> None:
        from math3d import opencv_opengl_camera_transform

        matrix = np.array(
            [[1.0, 0.0, 0.0, 0.2], [0.0, 1.0, 0.0, -0.4], [0.0, 0.0, 1.0, 1.5], [0.0, 0.0, 0.0, 1.0]]
        )
        np.testing.assert_allclose(opencv_opengl_camera_transform(opencv_opengl_camera_transform(matrix)), matrix)


class FusionContractTest(unittest.TestCase):
    def test_icp_converges_from_a_nearby_initialization(self) -> None:
        from math3d import apply_transform, icp

        rng = np.random.default_rng(9)
        source = rng.normal(size=(40, 3))
        angle = 0.08
        rotation = np.array([[np.cos(angle), -np.sin(angle), 0.0], [np.sin(angle), np.cos(angle), 0.0], [0.0, 0.0, 1.0]])
        target = apply_transform(source, rotation, np.array([0.12, -0.08, 0.04]))
        estimated_rotation, estimated_translation, history = icp(source, target, iterations=30)
        self.assertLess(history[-1], history[0] * 0.05)
        np.testing.assert_allclose(estimated_rotation, rotation, atol=2e-3)
        np.testing.assert_allclose(estimated_translation, np.array([0.12, -0.08, 0.04]), atol=2e-3)

    def test_tsdf_weighted_fusion_and_unit_normals(self) -> None:
        from math3d import fuse_tsdf, normalize_rows

        fused, weight = fuse_tsdf(0.1, 2.0, -0.2, 1.0)
        self.assertAlmostEqual(fused, 0.0)
        self.assertEqual(weight, 3.0)
        normals = normalize_rows(np.array([[3.0, 0.0, 4.0], [0.0, -2.0, 0.0]]))
        np.testing.assert_allclose(np.linalg.norm(normals, axis=1), np.ones(2), atol=1e-12)


class ClassicalLabContractTest(unittest.TestCase):
    def test_modules_01_through_07_emit_valid_characteristic_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            results: dict[str, dict] = {}
            for module_id in (f"{index:02d}" for index in range(1, 8)):
                completed = subprocess.run(
                    [str(ROOT / "run.sh"), "run", "--module", module_id, "--profile", "smoke", "--run-id", "classical"],
                    cwd=ROOT.parent.parent,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, f"module {module_id}: {completed.stderr}")
                validation = subprocess.run(
                    [str(ROOT / "run.sh"), "validate", "--module", module_id, "--run-id", "classical"],
                    cwd=ROOT.parent.parent,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(validation.returncode, 0, f"module {module_id}: {validation.stderr}")
                run_dir = cache / "runs" / "classical" / module_id
                results[module_id] = json.loads((run_dir / "result.json").read_text())
                self.assertTrue((run_dir / "artifacts" / "failure_sweep.csv").is_file())
                self.assertTrue(any((run_dir / "artifacts").glob("*.svg")))

            self.assertLess(results["02"]["metrics"]["geometry"]["concavity_recall"], 1.0)
            self.assertGreater(results["03"]["metrics"]["geometry"]["far_depth_std_m"], results["03"]["metrics"]["geometry"]["near_depth_std_m"])
            self.assertLess(results["04"]["metrics"]["geometry"]["icp_final_rmse_m"], results["04"]["metrics"]["geometry"]["icp_initial_rmse_m"])
            self.assertLess(results["05"]["metrics"]["geometry"]["ba_final_reprojection_rmse_px"], results["05"]["metrics"]["geometry"]["ba_initial_reprojection_rmse_px"])
            sweep_06 = results["06"]["failure_sweep"]
            view_rows = [row for row in sweep_06 if row["parameter"] == "view_count"]
            self.assertGreater(view_rows[-1]["measurement"], view_rows[0]["measurement"])
            self.assertLess(results["07"]["metrics"]["geometry"]["ate_after_loop_m"], results["07"]["metrics"]["geometry"]["ate_before_loop_m"])


if __name__ == "__main__":
    unittest.main()
