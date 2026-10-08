import math
import unittest

import numpy as np

from geometry import oriented_box_test_support as support
from geometry.oriented_box import count_points_in_box, point_membership


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


if __name__ == "__main__":
    unittest.main()
