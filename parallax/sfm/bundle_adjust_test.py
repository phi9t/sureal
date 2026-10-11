"""Bundle-adjustment tests for incremental SfM."""

from __future__ import annotations

import unittest

import numpy as np

from camera.pinhole import project
from camera.pose import camera_center
from evaluation.pose_metrics import rotation_error_degrees, umeyama_sim3
from geometry.pnp import rotation_matrix_from_vector
from sfm.bundle_adjust import bundle_adjust
from sfm.reconstruction import CameraPose, Observation, Reconstruction


def _truth_fixture() -> tuple[Reconstruction, dict[str, CameraPose]]:
    intrinsic = np.array(
        [[180.0, 0.0, 63.5], [0.0, 180.0, 47.5], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    camera_ids = [f"view-{index}" for index in range(4)]
    centers = [
        np.array([0.0, 0.0, 0.0], dtype=np.float64),
        np.array([0.22, -0.03, 0.02], dtype=np.float64),
        np.array([0.44, 0.04, -0.01], dtype=np.float64),
        np.array([0.66, -0.02, 0.03], dtype=np.float64),
    ]
    rotations = [
        rotation_matrix_from_vector([0.0, 0.0, 0.0]),
        rotation_matrix_from_vector([0.018, -0.032, 0.006]),
        rotation_matrix_from_vector([-0.012, -0.064, 0.011]),
        rotation_matrix_from_vector([0.014, -0.092, -0.008]),
    ]
    cameras = {
        camera_id: CameraPose(rotation, -rotation @ center)
        for camera_id, rotation, center in zip(camera_ids, rotations, centers)
    }
    columns = np.linspace(-0.55, 0.55, 6)
    rows = np.linspace(-0.32, 0.34, 5)
    points = {
        index: np.array(
            [
                float(column),
                float(row),
                3.0 + 0.14 * ((index % 3) - 1),
            ],
            dtype=np.float64,
        )
        for index, (row, column) in enumerate((r, c) for r in rows for c in columns)
    }
    observations = []
    for camera_id, pose in cameras.items():
        for track_id, point in points.items():
            pixel = project(point.reshape(1, 3), intrinsic, pose.rotation, pose.translation)[0][0]
            observations.append(Observation(camera_id, track_id, pixel))
    return Reconstruction(intrinsic, cameras, points, observations), cameras


def _perturb(reconstruction: Reconstruction) -> Reconstruction:
    rng = np.random.default_rng(260925)
    cameras = {}
    for index, (camera_id, pose) in enumerate(reconstruction.cameras.items()):
        if index == 0:
            cameras[camera_id] = pose
            continue
        delta_rotation = rotation_matrix_from_vector(
            rng.normal(scale=0.012, size=3)
        )
        cameras[camera_id] = CameraPose(
            delta_rotation @ pose.rotation,
            pose.translation + rng.normal(scale=0.025, size=3),
        )
    points = {
        track_id: point + rng.normal(scale=0.035, size=3)
        for track_id, point in reconstruction.points.items()
    }
    return Reconstruction(
        reconstruction.intrinsic,
        cameras,
        points,
        list(reconstruction.observations),
    )


class BundleAdjustmentTest(unittest.TestCase):
    def test_bundle_adjustment_reduces_rmse_and_recovers_noise_free_poses(self) -> None:
        """Catches optimizers that move points only or skip camera refinement."""
        truth, truth_cameras = _truth_fixture()
        perturbed = _perturb(truth)

        result = bundle_adjust(
            perturbed,
            fixed_camera_ids=("view-0",),
            max_iterations=12,
        )

        self.assertTrue(result.used_schur_complement)
        self.assertLess(result.final_rmse_px, result.initial_rmse_px * 1e-3)
        truth_centers = np.array(
            [
                camera_center(pose.rotation, pose.translation)
                for pose in truth_cameras.values()
            ],
            dtype=np.float64,
        )
        estimated_centers = np.array(
            [
                camera_center(result.reconstruction.cameras[camera_id].rotation, result.reconstruction.cameras[camera_id].translation)
                for camera_id in truth_cameras
            ],
            dtype=np.float64,
        )
        scale, align_rotation, align_translation = umeyama_sim3(
            estimated_centers,
            truth_centers,
        )
        aligned_centers = (
            scale * (align_rotation @ estimated_centers.T)
        ).T + align_translation
        center_errors = np.linalg.norm(aligned_centers - truth_centers, axis=1)
        rotation_errors = [
            rotation_error_degrees(
                result.reconstruction.cameras[camera_id].rotation
                @ align_rotation.T,
                truth_cameras[camera_id].rotation,
            )
            for camera_id in truth_cameras
        ]
        self.assertLess(float(np.max(center_errors)), 2e-3)
        self.assertLess(float(np.max(rotation_errors)), 0.05)


if __name__ == "__main__":
    unittest.main()
