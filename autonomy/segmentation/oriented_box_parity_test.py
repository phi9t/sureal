import unittest

import numpy as np

from geometry.oriented_box_test_support import assert_point_count_parity
from segmentation.foreground_support import foreground_support


def _foreground_support_count(points, box):
    result = foreground_support(
        points,
        np.asarray([box], dtype=np.float64),
        np.asarray([1], dtype=np.int64),
    )
    return int(len(result["object_point_indices"][0]))


class OrientedBoxParityTest(unittest.TestCase):
    def test_foreground_support_copy_matches_shared_oriented_box_count(self):
        assert_point_count_parity(self, _foreground_support_count)


if __name__ == "__main__":
    unittest.main()
