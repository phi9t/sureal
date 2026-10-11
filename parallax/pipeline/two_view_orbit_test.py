"""Regression tests for the orbit two-view live runner."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pipeline.two_view_orbit import run_two_view_orbit


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


if __name__ == "__main__":
    unittest.main()
