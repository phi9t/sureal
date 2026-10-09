"""Parity fixtures for inspection producers migrated to geometry.oriented_box."""
import unittest

import numpy as np

from geometry import oriented_box_test_support as support


def _old_viewer_point_count(points, box):
    points = np.asarray(points, dtype=np.float64)
    box = np.asarray(box, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError("finite viewer points required")
    if box.shape != (7,) or not np.isfinite(box).all() or np.any(box[3:6] <= 0):
        raise ValueError("finite positive viewer oriented box required")
    delta = points - box[:3]
    c, s = np.cos(box[6]), np.sin(box[6])
    local_x = delta[:, 0] * c + delta[:, 1] * s
    local_y = -delta[:, 0] * s + delta[:, 1] * c
    inside = (
        (np.abs(local_x) <= box[3] / 2)
        & (np.abs(local_y) <= box[4] / 2)
        & (np.abs(delta[:, 2]) <= box[5] / 2)
    )
    return int(inside.sum())


def _old_explorer_bev_corners(box):
    x, y, _z, length, width, _height, heading = np.asarray(box, dtype=np.float64)
    c, s = np.cos(heading), np.sin(heading)
    return np.asarray(
        [
            (x + c * u - s * v, y + s * u + c * v)
            for u, v in [
                (-length / 2, -width / 2),
                (length / 2, -width / 2),
                (length / 2, width / 2),
                (-length / 2, width / 2),
            ]
        ],
        dtype=np.float64,
    )


class InspectionBoxGeometryParityTests(unittest.TestCase):
    def test_viewer_point_count_matches_box_module(self):
        support.assert_point_count_parity(self, _old_viewer_point_count)

    def test_explorer_bev_corners_match_box_module(self):
        support.assert_bev_corners_parity(self, _old_explorer_bev_corners)


if __name__ == "__main__":
    unittest.main()
