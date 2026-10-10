"""Surface and depth metric tests with literal expected values."""

from __future__ import annotations

import unittest

import numpy as np

from evaluation.surface_metrics import (
    depth_absrel,
    depth_delta_less_than,
    surface_metrics,
)


class SurfaceMetricsTest(unittest.TestCase):
    def test_surface_metrics_are_perfect_on_ground_truth_against_itself(self) -> None:
        """Catches asymmetric nearest-neighbor or F-score identity errors."""
        points = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
            ]
        )
        metrics = surface_metrics(points, points, tau=0.01)

        self.assertEqual(metrics["accuracy"], 0.0)
        self.assertEqual(metrics["completeness"], 0.0)
        self.assertEqual(metrics["chamfer_distance"], 0.0)
        self.assertEqual(metrics["f_score"], 1.0)
        self.assertEqual(depth_absrel(np.ones((2, 2)), np.ones((2, 2))), 0.0)
        self.assertEqual(
            depth_delta_less_than(np.ones((2, 2)), np.ones((2, 2))),
            1.0,
        )

    def test_known_surface_and_depth_perturbations_have_expected_values(self) -> None:
        """Catches swapped accuracy/completeness and threshold comparison errors."""
        prediction = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
        truth = np.array([[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]])
        metrics = surface_metrics(prediction, truth, tau=1.0)

        self.assertEqual(metrics["accuracy"], 1.0)
        self.assertEqual(metrics["completeness"], 1.0)
        self.assertEqual(metrics["chamfer_distance"], 1.0)
        self.assertEqual(metrics["f_score"], 0.5)

        depth_prediction = np.array([[1.0, 2.0]])
        depth_truth = np.array([[1.0, 1.0]])
        self.assertEqual(depth_absrel(depth_prediction, depth_truth), 0.5)
        self.assertEqual(
            depth_delta_less_than(depth_prediction, depth_truth, threshold=1.25),
            0.5,
        )


if __name__ == "__main__":
    unittest.main()
