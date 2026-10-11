from __future__ import annotations

import unittest

import numpy as np

from stereo.cost import census_cost, zncc_cost


class StereoCostTest(unittest.TestCase):
    def test_zncc_and_census_prefer_matching_texture(self) -> None:
        image = np.array(
            [
                [11, 17, 29, 43, 61],
                [13, 23, 37, 53, 71],
                [19, 31, 47, 67, 89],
                [23, 41, 59, 83, 97],
                [29, 43, 73, 101, 113],
            ],
            dtype=np.float64,
        )
        mismatch = np.fliplr(image)

        matching_zncc = zncc_cost(image, image, window_radius=1)
        mismatched_zncc = zncc_cost(image, mismatch, window_radius=1)
        matching_census = census_cost(image, image, radius=1)
        mismatched_census = census_cost(image, mismatch, radius=1)

        center = (slice(1, -1), slice(1, -1))
        self.assertLess(float(np.nanmean(matching_zncc[center])), 1e-12)
        self.assertGreater(float(np.nanmean(mismatched_zncc[center])), 0.5)
        self.assertEqual(float(np.nanmean(matching_census[center])), 0.0)
        self.assertGreater(float(np.nanmean(mismatched_census[center])), 0.2)


if __name__ == "__main__":
    unittest.main()
