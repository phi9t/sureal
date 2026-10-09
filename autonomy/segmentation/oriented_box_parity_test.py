import unittest

import numpy as np

from geometry.oriented_box_test_support import assert_membership_parity, assert_point_count_parity


def _old_foreground_support_mask(points, box):
    points = np.asarray(points, dtype=np.float64)
    box = np.asarray(box, dtype=np.float64)
    if (
        points.ndim != 2
        or points.shape[1] != 3
        or box.shape != (7,)
        or not np.isfinite(points).all()
        or not np.isfinite(box).all()
        or np.any(box[3:6] <= 0)
    ):
        raise ValueError("finite XYZ/native upright XYZLWHyaw boxes and native box classes1..4 required")
    delta = points - box[:3]
    c, s = np.cos(box[6]), np.sin(box[6])
    local_x = delta[:, 0] * c + delta[:, 1] * s
    local_y = -delta[:, 0] * s + delta[:, 1] * c
    return (
        (np.abs(local_x) <= box[3] / 2)
        & (np.abs(local_y) <= box[4] / 2)
        & (np.abs(delta[:, 2]) <= box[5] / 2)
    )


def _old_foreground_support_count(points, box):
    return int(np.count_nonzero(_old_foreground_support_mask(points, box)))


def _old_nlz_overlap_mask(points, box):
    points = np.asarray(points, dtype=np.float64)
    box = np.asarray(box, dtype=np.float64)
    if (
        points.ndim != 2
        or points.shape[1] != 3
        or box.shape != (7,)
        or not np.isfinite(points).all()
        or not np.isfinite(box).all()
        or np.any(box[3:6] <= 0)
    ):
        raise ValueError("upright box contract")
    delta = points - box[:3]
    c, s = np.cos(box[6]), np.sin(box[6])
    local_x = c * delta[:, 0] + s * delta[:, 1]
    local_y = -s * delta[:, 0] + c * delta[:, 1]
    return (
        (np.abs(local_x) <= box[3] / 2)
        & (np.abs(local_y) <= box[4] / 2)
        & (np.abs(delta[:, 2]) <= box[5] / 2)
    )


def _old_nlz_overlap_count(points, box):
    return int(np.count_nonzero(_old_nlz_overlap_mask(points, box)))


class OrientedBoxParityTest(unittest.TestCase):
    def test_foreground_support_copy_matches_shared_oriented_box_count(self):
        assert_point_count_parity(self, _old_foreground_support_count)

    def test_foreground_support_copy_matches_shared_oriented_box_mask(self):
        assert_membership_parity(self, _old_foreground_support_mask)

    def test_nlz_overlap_copy_matches_shared_oriented_box_count(self):
        assert_point_count_parity(self, _old_nlz_overlap_count)

    def test_nlz_overlap_copy_matches_shared_oriented_box_mask(self):
        assert_membership_parity(self, _old_nlz_overlap_mask)


if __name__ == "__main__":
    unittest.main()
