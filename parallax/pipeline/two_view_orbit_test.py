"""Regression tests for the orbit two-view live runner."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from evaluation.pose_metrics import rotation_error_degrees
from pipeline.two_view_orbit import estimate_two_view_orbit_pair, run_two_view_orbit
from scene.orbit import generate_orbit_scene


def _without_score_only_fields(frame: dict) -> dict:
    stripped = dict(frame)
    for key in (
        "azimuth_degrees",
        "elevation_degrees",
        "R_world_to_camera",
        "t_world_to_camera_m",
        "camera_center_world_m",
        "depth_path",
        "normal_path",
        "surface_points_path",
        "surface_normals_path",
    ):
        stripped.pop(key, None)
    return stripped


class TwoViewOrbitTest(unittest.TestCase):
    def test_smoke_profile_reports_required_diagnostic_stages(self) -> None:
        """Catches match pipelines that hide where correspondence density is lost."""
        with tempfile.TemporaryDirectory() as temporary:
            record = run_two_view_orbit(Path(temporary) / "artifacts", "smoke")

        stages = record["match_stages"]
        self.assertGreater(stages["detected_view1"], 0)
        self.assertGreater(stages["detected_view2"], 0)
        self.assertGreater(stages["descriptors_view1"], 0)
        self.assertGreater(stages["descriptors_view2"], 0)
        self.assertGreater(stages["matches_before_ratio"], 0)
        self.assertGreater(stages["matches_after_ratio"], 0)
        self.assertGreater(stages["matches_after_mutual_check"], 0)
        self.assertGreater(stages["ransac_inliers"], 0)

    def test_smoke_profile_meets_two_view_density_and_accuracy_thresholds(self) -> None:
        """Catches sparse or unstable matches that cannot bootstrap incremental SfM."""
        with tempfile.TemporaryDirectory() as temporary:
            record = run_two_view_orbit(Path(temporary) / "artifacts", "smoke")

        self.assertGreaterEqual(record["ransac_inlier_count"], 200)
        self.assertGreaterEqual(record["ground_truth_f_inlier_ratio"], 0.95)
        self.assertLess(record["rotation_error_deg"], 1.0)
        self.assertLess(record["translation_direction_error_deg"], 2.0)

    def test_estimation_does_not_read_ground_truth_before_scoring(self) -> None:
        """Ground truth pose and azimuth are score-only inputs."""
        with tempfile.TemporaryDirectory() as temporary:
            scene_root = Path(temporary) / "scene"
            manifest = generate_orbit_scene(scene_root, "smoke")
            first = manifest["frames"][0]
            second = manifest["frames"][1]

            clean = estimate_two_view_orbit_pair(scene_root, first, second, "smoke")
            poisoned = estimate_two_view_orbit_pair(
                scene_root,
                _without_score_only_fields(first),
                _without_score_only_fields(second),
                "smoke",
            )

        self.assertEqual(clean.frame_pair, poisoned.frame_pair)
        self.assertEqual(clean.keypoints, poisoned.keypoints)
        self.assertEqual(clean.match_stages, poisoned.match_stages)
        np.testing.assert_array_equal(clean.ransac_inliers, poisoned.ransac_inliers)
        np.testing.assert_allclose(clean.points1, poisoned.points1)
        np.testing.assert_allclose(clean.points2, poisoned.points2)
        np.testing.assert_allclose(clean.pose.rotation, poisoned.pose.rotation)
        np.testing.assert_allclose(clean.pose.translation, poisoned.pose.translation)

    def test_full_profile_endpoint_pair_documents_fixed_window_alias(self) -> None:
        """Documents the fixed-window endpoint alias that ticket 06 works around."""
        with tempfile.TemporaryDirectory() as temporary:
            scene_root = Path(temporary) / "scene"
            manifest = generate_orbit_scene(scene_root, "full")
            first = manifest["frames"][5]
            second = manifest["frames"][6]

            estimate = estimate_two_view_orbit_pair(
                scene_root,
                first,
                second,
                "full",
            )

        truth_rotation = (
            np.asarray(second["R_world_to_camera"], dtype=np.float64)
            @ np.asarray(first["R_world_to_camera"], dtype=np.float64).T
        )
        rotation_error = rotation_error_degrees(estimate.pose.rotation, truth_rotation)
        print(f"full_endpoint_5_6_rotation_error_deg={rotation_error}")
        self.assertTrue(np.isfinite(rotation_error))
        self.assertGreater(rotation_error, 2.0)


if __name__ == "__main__":
    unittest.main()
