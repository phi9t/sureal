import math
import unittest

import numpy as np

from geometry import oriented_box_test_support as support
from geometry.oriented_box import (
    axis_aligned_bev_iou,
    bev_corners,
    count_points_in_box,
    enclosing_bev_rectangles,
    nearest_bev_rectangles,
    point_membership,
    wrap_heading,
)


def _wrong_count_on_pi_boundary(points, box):
    count = count_points_in_box(points, box)
    if box[6] == math.pi and _has_boundary_point(points, box):
        return count + 1
    return count


def _wrong_mask_on_pi_boundary(points, box):
    mask = point_membership(points, box).copy()
    if box[6] == math.pi and _has_boundary_point(points, box):
        mask[0] = ~mask[0]
    return mask


def _wrong_wrap_at_positive_pi(angles):
    wrapped = np.asarray(wrap_heading(angles)).copy()
    return np.where(np.asarray(angles) == math.pi, math.pi, wrapped)


def _wrong_nearest_rectangles_at_pi_quarter(boxes):
    rectangles = nearest_bev_rectangles(boxes).copy()
    boxes = np.asarray(boxes, dtype=np.float64)
    if np.any(boxes[:, 6] == math.pi / 4):
        rectangles[:, 0] = np.nextafter(rectangles[:, 0], -math.inf)
    return rectangles


def _wrong_enclosing_rectangles_at_pi_quarter(boxes):
    rectangles = enclosing_bev_rectangles(boxes).copy()
    boxes = np.asarray(boxes, dtype=np.float64)
    if np.any(boxes[:, 6] == math.pi / 4):
        rectangles[:, 1] = np.nextafter(rectangles[:, 1], -math.inf)
    return rectangles


def _wrong_iou(first, second):
    iou = axis_aligned_bev_iou(first, second).copy()
    if iou.size:
        iou[0, 0] = np.nextafter(iou[0, 0], math.inf)
    return iou


def _wrong_bev_corners_at_pi_half(box):
    corners = bev_corners(box).copy()
    box = np.asarray(box, dtype=np.float64)
    if box[6] == math.pi / 2:
        corners[0, 0] = np.nextafter(corners[0, 0], math.inf)
    return corners


def _has_boundary_point(points, box):
    delta = points - box[:3]
    c, s = math.cos(box[6]), math.sin(box[6])
    local = np.column_stack((
        delta[:, 0] * c + delta[:, 1] * s,
        -delta[:, 0] * s + delta[:, 1] * c,
        delta[:, 2],
    ))
    return bool(np.any(np.isclose(np.abs(local), box[3:6] / 2, rtol=0.0, atol=1e-12)))


class OrientedBoxParityHarnessTests(unittest.TestCase):
    def test_point_count_parity_stresses_pi_boundary_surfaces(self):
        with self.assertRaises(AssertionError):
            support.assert_point_count_parity(self, _wrong_count_on_pi_boundary)

    def test_membership_parity_helper_uses_boundary_surface_cases(self):
        helper = getattr(support, "assert_membership_parity", None)
        if helper is None:
            self.fail("assert_membership_parity missing")

        with self.assertRaises(AssertionError):
            helper(self, _wrong_mask_on_pi_boundary)

    def test_heading_wrap_parity_helper_uses_pi_boundaries(self):
        helper = getattr(support, "assert_heading_wrap_parity", None)
        if helper is None:
            self.fail("assert_heading_wrap_parity missing")

        with self.assertRaises(AssertionError):
            helper(self, _wrong_wrap_at_positive_pi)

    def test_bev_rectangle_parity_helper_uses_boundary_headings_and_iou(self):
        helper = getattr(support, "assert_bev_rectangle_parity", None)
        if helper is None:
            self.fail("assert_bev_rectangle_parity missing")

        with self.assertRaises(AssertionError):
            helper(self, _wrong_nearest_rectangles_at_pi_quarter, enclosing_bev_rectangles, axis_aligned_bev_iou)
        with self.assertRaises(AssertionError):
            helper(self, nearest_bev_rectangles, _wrong_enclosing_rectangles_at_pi_quarter, axis_aligned_bev_iou)
        with self.assertRaises(AssertionError):
            helper(self, nearest_bev_rectangles, enclosing_bev_rectangles, _wrong_iou)

    def test_bev_corners_parity_helper_uses_boundary_headings(self):
        helper = getattr(support, "assert_bev_corners_parity", None)
        if helper is None:
            self.fail("assert_bev_corners_parity missing")

        with self.assertRaises(AssertionError):
            helper(self, _wrong_bev_corners_at_pi_half)


if __name__ == "__main__":
    unittest.main()
