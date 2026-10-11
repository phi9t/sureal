"""Two-view reconstruction contracts against synthetic ground truth."""

from __future__ import annotations

import math
import unittest

import numpy as np

from camera.pinhole import project
from evaluation.pose_metrics import rotation_error_degrees
from geometry.epipolar import (
    estimate_relative_pose,
    essential_from_correspondences,
    symmetric_epipolar_distances,
)
from geometry.pnp import solve_pnp
from geometry.ransac import ransac
from geometry.triangulate import triangulate_points


def _rotation_y(angle_radians: float) -> np.ndarray:
    cosine = math.cos(angle_radians)
    sine = math.sin(angle_radians)
    return np.array(
        [
            [cosine, 0.0, sine],
            [0.0, 1.0, 0.0],
            [-sine, 0.0, cosine],
        ],
        dtype=np.float64,
    )


def _synthetic_scene() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = np.linspace(-0.9, 0.9, 6)
    y = np.linspace(-0.55, 0.55, 5)
    xx, yy = np.meshgrid(x, y)
    ripple = ((np.arange(xx.size).reshape(xx.shape) % 4) - 1.5) * 0.11
    zz = 3.2 + 0.35 * np.sin(2.2 * xx) + 0.27 * np.cos(3.1 * yy) + ripple
    points = np.column_stack((xx.reshape(-1), yy.reshape(-1), zz.reshape(-1)))
    intrinsic = np.array(
        [[700.0, 0.0, 320.0], [0.0, 710.0, 240.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    rotation = _rotation_y(math.radians(7.0))
    translation = np.array([-0.38, 0.03, 0.02], dtype=np.float64)
    pixels1, _ = project(points, intrinsic, np.eye(3), np.zeros(3))
    pixels2, _ = project(points, intrinsic, rotation, translation)
    return points, intrinsic, rotation, translation, pixels1, pixels2


def _translation_direction_error(estimated: np.ndarray, truth: np.ndarray) -> float:
    left = estimated / np.linalg.norm(estimated)
    right = truth / np.linalg.norm(truth)
    cosine = float(np.clip(np.dot(left, right), -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


class TwoViewGeometryTest(unittest.TestCase):
    def test_noise_free_correspondences_recover_pose_to_one_e_minus_six(self) -> None:
        """Catches a wrong essential decomposition branch or pixel normalization."""
        points, intrinsic, truth_rotation, truth_translation, pixels1, pixels2 = (
            _synthetic_scene()
        )

        pose = estimate_relative_pose(pixels1, pixels2, intrinsic, intrinsic)

        self.assertLess(
            rotation_error_degrees(pose.rotation, truth_rotation),
            1e-6,
        )
        self.assertLess(
            _translation_direction_error(pose.translation, truth_translation),
            1e-6,
        )
        recovered = triangulate_points(
            pixels1,
            pixels2,
            intrinsic,
            np.eye(3),
            np.zeros(3),
            intrinsic,
            pose.rotation,
            pose.translation,
        )
        scale = np.linalg.norm(truth_translation) / np.linalg.norm(pose.translation)
        np.testing.assert_allclose(recovered * scale, points, atol=1e-6)

    def test_ransac_recovers_pose_with_thirty_percent_outliers(self) -> None:
        """Catches unseeded sampling and estimators that let outliers dominate."""
        _, intrinsic, truth_rotation, truth_translation, pixels1, pixels2 = (
            _synthetic_scene()
        )
        contaminated = pixels2.copy()
        contaminated[:9] = contaminated[::-1][:9] + np.array([37.0, -19.0])

        def fit(indices: np.ndarray) -> np.ndarray:
            return essential_from_correspondences(
                pixels1[indices],
                contaminated[indices],
                intrinsic,
                intrinsic,
            )

        def residuals(model: np.ndarray, indices: np.ndarray) -> np.ndarray:
            fundamental = np.linalg.inv(intrinsic).T @ model @ np.linalg.inv(intrinsic)
            return symmetric_epipolar_distances(
                fundamental,
                pixels1[indices],
                contaminated[indices],
            )

        result = ransac(
            np.arange(len(pixels1)),
            sample_size=8,
            fit_model=fit,
            residuals=residuals,
            threshold=1e-5,
            max_trials=600,
            seed=260925,
        )
        pose = estimate_relative_pose(
            pixels1[result.inlier_mask],
            contaminated[result.inlier_mask],
            intrinsic,
            intrinsic,
        )

        self.assertGreaterEqual(int(np.sum(result.inlier_mask)), 21)
        self.assertLess(rotation_error_degrees(pose.rotation, truth_rotation), 1e-6)
        self.assertLess(
            _translation_direction_error(pose.translation, truth_translation),
            1e-6,
        )

    def test_dlt_pnp_refinement_recovers_camera_pose(self) -> None:
        """Catches PnP solvers that return the inverse pose or skip refinement."""
        points, intrinsic, truth_rotation, truth_translation, _, pixels2 = (
            _synthetic_scene()
        )

        rotation, translation, error = solve_pnp(points, pixels2, intrinsic)

        self.assertLess(rotation_error_degrees(rotation, truth_rotation), 1e-6)
        np.testing.assert_allclose(translation, truth_translation, atol=1e-6)
        self.assertLess(error, 1e-6)


if __name__ == "__main__":
    unittest.main()
