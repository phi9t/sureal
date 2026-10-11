from __future__ import annotations

import unittest

import numpy as np

from stereo.depth_filter import consistent_depth_mask
from stereo.plane_sweep import StereoView


class DepthFilterTest(unittest.TestCase):
    def test_geometric_consistency_rejects_cross_view_depth_disagreement(self) -> None:
        height, width = 12, 14
        K = np.array(
            [
                [24.0, 0.0, (width - 1.0) / 2.0],
                [0.0, 24.0, (height - 1.0) / 2.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        reference = StereoView("reference", np.ones((height, width), dtype=np.uint8), K, np.eye(3), np.zeros(3))
        neighbour = StereoView(
            "neighbour",
            np.ones((height, width), dtype=np.uint8),
            K,
            np.eye(3),
            np.array([-0.25, 0.0, 0.0], dtype=np.float64),
        )
        reference_depth = np.full((height, width), 2.0, dtype=np.float64)
        neighbour_depth = np.full((height, width), 2.0, dtype=np.float64)
        neighbour_depth[:, 5:8] = 2.35

        mask = consistent_depth_mask(
            reference,
            neighbour,
            reference_depth,
            neighbour_depth,
            pixel_tolerance=0.75,
            relative_depth_tolerance=0.03,
        )

        columns = np.arange(width)[None, :]
        should_reject = (columns >= 8) & (columns <= 10)
        self.assertTrue(np.any(mask[:, 4:7]))
        self.assertFalse(np.any(mask[should_reject.repeat(height, axis=0)]))


if __name__ == "__main__":
    unittest.main()
