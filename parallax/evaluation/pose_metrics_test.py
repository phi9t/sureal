"""Pose-metric tests against hand-derived camera geometry."""

from __future__ import annotations

import math
import unittest

import numpy as np

from evaluation.pose_metrics import (
    ate_sim3,
    reprojection_rmse,
    rotation_error_degrees,
    translation_error,
)


class PoseMetricsTest(unittest.TestCase):
    def test_pose_metrics_are_perfect_on_ground_truth_against_itself(self) -> None:
        """Catches non-zero identity errors in pose and reprojection metrics."""
        rotations = [np.eye(3), np.diag([1.0, -1.0, -1.0])]
        translations = [np.zeros(3), np.array([0.25, 0.0, 0.0])]
        centers = np.array(
            [
                [0.0, 0.0, 0.0],
                [0.25, 0.0, 0.0],
                [0.0, 0.25, 0.0],
                [0.0, 0.0, 0.25],
            ]
        )
        for rotation, translation in zip(rotations, translations):
            self.assertEqual(rotation_error_degrees(rotation, rotation), 0.0)
            self.assertEqual(translation_error(translation, translation), 0.0)
        self.assertAlmostEqual(ate_sim3(centers, centers), 0.0, places=12)

        point = np.array([[0.0, 0.0, 2.0]])
        cameras = [(np.eye(3), np.eye(3), np.zeros(3))]
        observations = np.array([[[0.0, 0.0]]])
        self.assertEqual(reprojection_rmse(point, observations, cameras), 0.0)

    def test_known_pose_perturbations_have_expected_values(self) -> None:
        """Catches radians/degrees and residual-axis averaging mistakes."""
        angle = math.radians(90.0)
        rotation_z = np.array(
            [
                [math.cos(angle), -math.sin(angle), 0.0],
                [math.sin(angle), math.cos(angle), 0.0],
                [0.0, 0.0, 1.0],
            ]
        )
        self.assertAlmostEqual(rotation_error_degrees(rotation_z, np.eye(3)), 90.0)
        self.assertEqual(
            translation_error(np.array([3.0, 4.0, 0.0]), np.zeros(3)),
            5.0,
        )

        truth = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [1.0, 1.0, 0.0],
            ]
        )
        estimated = 2.0 * truth + np.array([5.0, -3.0, 1.5])
        self.assertAlmostEqual(ate_sim3(estimated, truth), 0.0, places=12)

        point = np.array([[0.0, 0.0, 1.0]])
        cameras = [(np.eye(3), np.eye(3), np.zeros(3))]
        observations = np.array([[[3.0, 4.0]]])
        self.assertAlmostEqual(
            reprojection_rmse(point, observations, cameras),
            math.sqrt(12.5),
        )


if __name__ == "__main__":
    unittest.main()
