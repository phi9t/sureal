import math
import unittest

import numpy as np

from geometry.oriented_box import (
    axis_aligned_bev_iou,
    bev_corners,
    count_points_in_box,
    enclosing_bev_rectangles,
    nearest_bev_rectangles,
    point_membership,
    point_membership_many,
    wrap_heading,
)


def _inverse_homogeneous_membership(points, box):
    c, s = math.cos(box[6]), math.sin(box[6])
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = np.array(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    transform[:3, 3] = box[:3]
    homogeneous = np.column_stack((points, np.ones(len(points), dtype=np.float64)))
    local = (np.linalg.inv(transform) @ homogeneous.T).T[:, :3]
    return np.all(np.abs(local) <= box[3:6] / 2, axis=1)


class OrientedBoxTests(unittest.TestCase):
    def test_membership_includes_faces_edges_and_corners_without_tolerance(self):
        box = np.array([1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 0.0])
        outside_x = np.nextafter(3.0, np.inf)
        points = np.array(
            [
                [1.0, 2.0, 3.0],
                [3.0, 2.0, 3.0],
                [3.0, 5.0, 3.0],
                [3.0, 5.0, 7.0],
                [outside_x, 2.0, 3.0],
            ],
            dtype=np.float64,
        )

        expected = np.array([True, True, True, True, False])
        np.testing.assert_array_equal(point_membership(points, box), expected)
        self.assertEqual(count_points_in_box(points, box), 4)

        shifted = box.copy()
        shifted[0] += 20.0
        many = point_membership_many(points, np.stack((box, shifted)))
        self.assertEqual(many.shape, (2, len(points)))
        np.testing.assert_array_equal(many[0], expected)
        np.testing.assert_array_equal(many[1], np.zeros(len(points), dtype=bool))
        self.assertEqual(point_membership_many(points, np.empty((0, 7))).shape, (0, len(points)))

    def test_membership_rejects_non_finite_values_and_non_positive_dimensions(self):
        box = np.array([0.0, 0.0, 0.0, 4.0, 2.0, 2.0, 0.0])
        points = np.zeros((2, 3), dtype=np.float64)

        bad_points = points.copy()
        bad_points[0, 0] = np.nan
        with self.assertRaises(ValueError):
            point_membership(bad_points, box)

        bad_box = box.copy()
        bad_box[6] = np.inf
        with self.assertRaises(ValueError):
            point_membership(points, bad_box)

        bad_box = box.copy()
        bad_box[3] = 0.0
        with self.assertRaises(ValueError):
            point_membership(points, bad_box)

    def test_membership_matches_inverse_homogeneous_reference_away_from_boundaries(self):
        rng = np.random.default_rng(20261008)
        for _ in range(32):
            box = np.array(
                [
                    rng.uniform(-20.0, 20.0),
                    rng.uniform(-20.0, 20.0),
                    rng.uniform(-2.0, 4.0),
                    rng.uniform(1.0, 8.0),
                    rng.uniform(1.0, 5.0),
                    rng.uniform(1.0, 3.0),
                    rng.uniform(-4.0 * np.pi, 4.0 * np.pi),
                ],
                dtype=np.float64,
            )
            points = rng.uniform(-25.0, 25.0, size=(128, 3))
            reference = _inverse_homogeneous_membership(points, box)
            np.testing.assert_array_equal(point_membership(points, box), reference)

    def test_wrap_heading_uses_half_open_range_and_producer_boundary_expression(self):
        angles = np.array(
            [
                -np.pi,
                np.pi,
                -3.0 * np.pi,
                3.0 * np.pi,
                0.0,
                np.pi / 2 + 1024.0 * 2.0 * np.pi,
                -np.pi / 2 - 2048.0 * 2.0 * np.pi,
            ],
            dtype=np.float64,
        )
        wrapped = wrap_heading(angles)

        self.assertEqual(wrapped[0], -np.pi)
        self.assertEqual(wrapped[1], -np.pi)
        self.assertEqual(wrapped[2], -np.pi)
        self.assertEqual(wrapped[3], -np.pi)
        self.assertEqual(wrap_heading(math.pi), -math.pi)
        np.testing.assert_array_equal(wrapped, (angles + np.pi) % (2 * np.pi) - np.pi)
        self.assertTrue(np.all(wrapped >= -np.pi))
        self.assertTrue(np.all(wrapped < np.pi))

    def test_bev_corners_are_ordered_by_local_negative_x_negative_y_first(self):
        box = np.array([10.0, 20.0, 0.0, 4.0, 2.0, 1.0, 0.0])
        np.testing.assert_allclose(
            bev_corners(box),
            np.array([[8.0, 19.0], [12.0, 19.0], [12.0, 21.0], [8.0, 21.0]]),
            atol=0.0,
        )

        rotated = box.copy()
        rotated[6] = np.pi / 2
        np.testing.assert_allclose(
            bev_corners(rotated),
            np.array([[11.0, 18.0], [11.0, 22.0], [9.0, 22.0], [9.0, 18.0]]),
            atol=1e-15,
        )

    def test_rectangles_and_iou_symmetry_identity_and_empty_union(self):
        boxes = np.array(
            [
                [0.0, 0.0, 0.0, 4.0, 2.0, 2.0, 0.0],
                [0.0, 0.0, 0.0, 4.0, 2.0, 2.0, np.pi / 2],
                [5.0, 0.0, 0.0, 4.0, 2.0, 2.0, 0.0],
            ],
            dtype=np.float64,
        )

        np.testing.assert_allclose(
            nearest_bev_rectangles(boxes[:2]),
            np.array([[-2.0, -1.0, 2.0, 1.0], [-1.0, -2.0, 1.0, 2.0]]),
            atol=1e-15,
        )
        np.testing.assert_allclose(
            enclosing_bev_rectangles(boxes[:2]),
            np.array([[-2.0, -1.0, 2.0, 1.0], [-1.0, -2.0, 1.0, 2.0]]),
            atol=1e-15,
        )

        rectangles = enclosing_bev_rectangles(boxes)
        iou = axis_aligned_bev_iou(rectangles, rectangles)
        np.testing.assert_allclose(iou, iou.T, atol=0.0)
        np.testing.assert_allclose(np.diag(iou), np.ones(len(rectangles)), atol=0.0)
        self.assertEqual(axis_aligned_bev_iou(rectangles, np.empty((0, 4))).shape, (3, 0))

        zero_area = np.array([[0.0, 0.0, 0.0, 0.0]])
        np.testing.assert_array_equal(axis_aligned_bev_iou(zero_area, zero_area), [[0.0]])


if __name__ == "__main__":
    unittest.main()
