from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from scene.orbit import generate_orbit_scene
from stereo.plane_sweep import (
    StereoView,
    load_orbit_views,
    plane_sweep_depth,
    reconstruct_depth_maps,
    score_orbit_depths,
)


def _shift_left(image: np.ndarray, pixels: int) -> np.ndarray:
    shifted = np.zeros_like(image)
    shifted[:, :-pixels] = image[:, pixels:]
    shifted[:, -pixels:] = image[:, -1:]
    return shifted


class PlaneSweepDepthTest(unittest.TestCase):
    def test_fronto_parallel_plane_recovers_exact_sampled_depth(self) -> None:
        height, width = 32, 48
        depth_m = 2.0
        focal_px = 32.0
        baseline_m = 0.25
        disparity_px = int(round(focal_px * baseline_m / depth_m))
        rng = np.random.default_rng(260925)
        reference_image = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
        neighbour_image = _shift_left(reference_image, disparity_px)
        K = np.array(
            [
                [focal_px, 0.0, (width - 1.0) / 2.0],
                [0.0, focal_px, (height - 1.0) / 2.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        reference = StereoView("reference", reference_image, K, np.eye(3), np.zeros(3))
        neighbour = StereoView(
            "neighbour",
            neighbour_image,
            K,
            np.eye(3),
            np.array([-baseline_m, 0.0, 0.0], dtype=np.float64),
        )

        result = plane_sweep_depth(
            reference,
            [neighbour],
            np.array([1.5, 1.75, depth_m, 2.25, 2.5], dtype=np.float64),
            window_radius=2,
        )

        rows, columns = np.indices((height, width))
        interior = (
            result.valid_mask
            & (columns >= disparity_px + 4)
            & (columns < width - 4)
            & (rows >= 4)
            & (rows < height - 4)
        )
        self.assertGreater(float(np.mean(interior)), 0.45)
        np.testing.assert_array_equal(result.depth[interior], depth_m)

    def test_orbit_scene_depth_beats_absrel_threshold_on_textured_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            scene_root = Path(temporary) / "orbit"
            generate_orbit_scene(scene_root, "smoke")
            views = load_orbit_views(scene_root)
            depths = reconstruct_depth_maps(
                views,
                depth_count=96,
                max_neighbours=2,
                window_radius=2,
                consistency_neighbours=1,
            )
            metrics = score_orbit_depths(views, depths, texture_gradient_threshold=3.0)

        self.assertLess(metrics["mean_absrel"], 0.08)
        self.assertGreater(metrics["mean_delta_lt_1_25"], 0.94)
        self.assertGreater(metrics["mean_valid_pixel_fraction"], 0.65)


if __name__ == "__main__":
    unittest.main()
