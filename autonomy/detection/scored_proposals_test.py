import unittest

import numpy as np

from detection.detector_decode import decode_proposals
from detection.scored_proposals_v2 import decode_scored_proposals as decode_v2
from detection.scored_proposals_v3 import canonical_direction_correct, decode_scored_proposals as decode_v3


class ScoredProposalTests(unittest.TestCase):
    def test_v2_preserves_reference_decoder_for_valid_selected_boxes(self):
        anchors = np.array(
            [[0, 0, 0, 2, 2, 2, 0], [10, 0, 0, 2, 2, 2, 0], [20, 0, 0, 2, 2, 2, 0]],
            dtype=float,
        )
        logits = np.array([[5, -5, -5, -5], [-100, -100, -100, -100], [4, -5, -5, -5]], dtype=float)
        residuals = np.zeros((3, 7), dtype=float)
        directions = np.array([[3, -3]] * 3, dtype=float)
        args = {"iou_threshold": 0.5, "score_floor": 0.05, "pre_limit": 4096, "post_limit": 500}

        reference = decode_proposals(logits, residuals, directions, anchors, **args)
        result = decode_v2(logits, residuals, directions, anchors, **args)

        for key in ["boxes", "classes", "scores", "anchor_indices"]:
            np.testing.assert_array_equal(result[key], reference[key])

    def test_v2_ignores_unselected_extreme_residuals_but_rejects_selected_ones(self):
        anchors = np.array(
            [[0, 0, 0, 2, 2, 2, 0], [10, 0, 0, 2, 2, 2, 0], [20, 0, 0, 2, 2, 2, 0]],
            dtype=float,
        )
        logits = np.array([[5, -5, -5, -5], [-100, -100, -100, -100], [4, -5, -5, -5]], dtype=float)
        residuals = np.zeros((3, 7), dtype=float)
        directions = np.array([[3, -3]] * 3, dtype=float)
        args = {"iou_threshold": 0.5, "score_floor": 0.05, "pre_limit": 4096, "post_limit": 500}

        residuals[1, 3:6] = 1000
        result = decode_v2(logits, residuals, directions, anchors, **args)
        self.assertEqual(result["anchor_indices"].tolist(), [0, 2])

        residuals[0, 3] = 1000
        with self.assertRaises(ValueError):
            decode_v2(logits, residuals, directions, anchors, **args)

    def test_v3_heading_correction_is_periodic_and_validates_binary_bins(self):
        yaw = np.array([-3.0, -1.0, 0.5, 2.7])
        bins = np.array([0, 0, 1, 1])
        for turns in [-4, -2, -1, 0, 1, 2, 4]:
            np.testing.assert_allclose(canonical_direction_correct(yaw + turns * 2 * np.pi, bins), yaw, atol=2e-14)
        with self.assertRaises(ValueError):
            canonical_direction_correct(np.array([0.5]), np.array([2]))

    def test_v3_returns_corrected_boxes_with_original_anchor_indices(self):
        anchors = np.array([[0, 0, 0, 2, 2, 2, 0], [20, 0, 0, 2, 2, 2, 0]], dtype=float)
        logits = np.array([[5, -5, -5, -5], [4, -5, -5, -5]], dtype=float)
        residuals = np.zeros((2, 7), dtype=float)
        directions = np.array([[3, -3], [-3, 3]], dtype=float)

        result = decode_v3(
            logits,
            residuals,
            directions,
            anchors,
            iou_threshold=0.5,
            score_floor=0.05,
            pre_limit=4096,
            post_limit=500,
        )

        self.assertEqual(result["anchor_indices"].tolist(), [0, 1])
        np.testing.assert_array_equal(result["classes"], np.array([1, 1]))


if __name__ == "__main__":
    unittest.main()
