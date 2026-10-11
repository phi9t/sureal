from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.classical_chain import run_classical_chain_profile


class ClassicalChainFullProfileTest(unittest.TestCase):
    def test_full_profile_chain_meets_surface_accuracy_with_sfm_poses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            summary = run_classical_chain_profile(
                Path(temporary) / "chain",
                "full",
                include_pose_attribution=True,
            )

        metrics = summary["metrics"]
        self.assertEqual(summary["view_count"], 7)
        self.assertEqual(metrics["registered_view_count"], 7)
        self.assertEqual(summary["settings"]["surface_tau_m"], 0.12)
        attribution = summary["pose_attribution_diagnostic"]["metrics"]
        print(
            "FULL_PROFILE_CHAIN_METRICS "
            + json.dumps(
                {
                    "sfm_pose": attribution["sfm_pose"],
                    "ground_truth_pose": attribution["ground_truth_pose"],
                    "artifacts": summary["artifacts"],
                },
                sort_keys=True,
            )
        )
        attribution_detail = json.dumps(attribution, sort_keys=True)
        self.assertLessEqual(metrics["surface_chamfer_m"], 0.08, attribution_detail)
        self.assertGreaterEqual(
            metrics["surface_f_score_tau"],
            0.85,
            attribution_detail,
        )
        self.assertEqual(
            metrics["surface_chamfer_m"],
            metrics["icp_refined_surface_chamfer_m"],
        )
        self.assertEqual(
            metrics["surface_f_score_tau"],
            metrics["icp_refined_surface_f_score_tau"],
        )
        self.assertIn("camera_aligned_surface_chamfer_m", metrics)
        self.assertIn("camera_aligned_surface_f_score_tau", metrics)
        self.assertLess(metrics["icp_refinement_rotation_deg"], 2.0, attribution_detail)
        self.assertLess(metrics["icp_refinement_translation_m"], 0.15, attribution_detail)
        self.assertLess(abs(metrics["icp_refinement_scale"] - 1.0), 0.03)

        self.assertEqual(
            attribution["sfm_pose"]["surface_chamfer_m"],
            metrics["surface_chamfer_m"],
        )
        self.assertEqual(
            attribution["sfm_pose"]["surface_f_score_tau"],
            metrics["surface_f_score_tau"],
        )
        self.assertEqual(
            attribution["sfm_pose"]["camera_aligned_surface_chamfer_m"],
            metrics["camera_aligned_surface_chamfer_m"],
        )
        self.assertLessEqual(
            attribution["ground_truth_pose"]["surface_chamfer_m"],
            0.08,
            attribution_detail,
        )
        self.assertGreaterEqual(
            attribution["ground_truth_pose"]["surface_f_score_tau"],
            0.85,
            attribution_detail,
        )
        for pose_metrics in attribution.values():
            self.assertIn("camera_aligned_surface_chamfer_m", pose_metrics)
            self.assertIn("icp_refined_surface_chamfer_m", pose_metrics)
            self.assertLess(
                pose_metrics["icp_refinement_rotation_deg"],
                2.0,
                attribution_detail,
            )
            self.assertLess(
                pose_metrics["icp_refinement_translation_m"],
                0.15,
                attribution_detail,
            )
            self.assertLess(
                abs(pose_metrics["icp_refinement_scale"] - 1.0),
                0.03,
                attribution_detail,
            )


if __name__ == "__main__":
    unittest.main()
