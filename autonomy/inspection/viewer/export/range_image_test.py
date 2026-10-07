import math
import unittest

import numpy as np

from inspection.viewer.export.range_image import azimuths, inclinations, range_image_to_vehicle, rotation_rpy


def rz(t):
    c, s = math.cos(t), math.sin(t)
    m = np.eye(4)
    m[:2, :2] = [[c, -s], [s, c]]
    return m


class RangeImageTest(unittest.TestCase):
    def test_inclinations_are_reversed_and_half_pixel(self):
        inc = inclinations(4, -1.0, 1.0)
        self.assertEqual(inc.shape, (4,))
        self.assertAlmostEqual(inc[0], 0.75)   # row 0 = top beam
        self.assertAlmostEqual(inc[-1], -0.75)
        explicit = inclinations(3, 0, 0, [0.1, 0.2, 0.3])
        np.testing.assert_allclose(explicit, [0.3, 0.2, 0.1])
        with self.assertRaises(ValueError):
            inclinations(3, 0, 0, [0.1, 0.2])

    def test_azimuth_corrected_by_extrinsic_yaw(self):
        base = azimuths(8, np.eye(4))
        self.assertAlmostEqual(base[0], (7.5 / 8 * 2 - 1) * math.pi)
        turned = azimuths(8, rz(0.3))
        np.testing.assert_allclose(turned, base - 0.3)

    def test_single_pixel_maps_through_extrinsic(self):
        h, w = 4, 8
        ri = np.zeros((h, w, 4))
        ri[1, 2] = [10.0, 3.0, 0.5, 1.0]
        ext = rz(0.2)
        ext[:3, 3] = [1.0, 2.0, 3.0]
        inc = inclinations(h, -0.5, 0.5)
        az = azimuths(w, ext)
        out = range_image_to_vehicle(ri, ext, inc, az)
        self.assertEqual(out["xyz"].shape, (1, 3))
        e, a = inc[1], az[2]
        p = np.array([10 * math.cos(e) * math.cos(a), 10 * math.cos(e) * math.sin(a), 10 * math.sin(e), 1.0])
        np.testing.assert_allclose(out["xyz"][0], (ext @ p)[:3], atol=1e-12)
        self.assertEqual(list(out["rows"]), [1])
        self.assertEqual(list(out["cols"]), [2])
        self.assertEqual(out["intensity"][0], 3.0)
        self.assertTrue(out["nlz"][0])

    def test_point_order_is_row_major_over_valid_pixels(self):
        ri = np.zeros((3, 3, 4))
        for r, c in [(2, 0), (0, 1), (1, 2)]:
            ri[r, c, 0] = 1.0
        out = range_image_to_vehicle(ri, np.eye(4), inclinations(3, -0.1, 0.1), azimuths(3, np.eye(4)))
        self.assertEqual(list(zip(out["rows"], out["cols"])), [(0, 1), (1, 2), (2, 0)])

    def test_rotation_rpy_matches_composition(self):
        roll, pitch, yaw = 0.1, -0.2, 0.3
        rx = np.array([[1, 0, 0], [0, math.cos(roll), -math.sin(roll)], [0, math.sin(roll), math.cos(roll)]])
        ry = np.array([[math.cos(pitch), 0, math.sin(pitch)], [0, 1, 0], [-math.sin(pitch), 0, math.cos(pitch)]])
        rzm = np.array([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]])
        np.testing.assert_allclose(rotation_rpy(np.array([roll]), np.array([pitch]), np.array([yaw]))[0], rzm @ ry @ rx, atol=1e-12)

    def test_motion_compensation_composition(self):
        ri = np.zeros((2, 2, 4))
        ri[0, 0, 0] = 5.0
        inc = inclinations(2, 0.0, 0.0)
        az = azimuths(2, np.eye(4))
        raw = range_image_to_vehicle(ri, np.eye(4), inc, az)["xyz"][0]
        pixel_pose = np.zeros((2, 2, 6))
        pixel_pose[0, 0] = [0.0, 0.0, 0.5, 10.0, -3.0, 1.0]
        frame_pose = rz(0.2)
        frame_pose[:3, 3] = [9.0, -2.0, 1.5]
        out = range_image_to_vehicle(ri, np.eye(4), inc, az, pixel_pose=pixel_pose, world_from_vehicle=frame_pose)["xyz"][0]
        world = rz(0.5)[:3, :3] @ raw + [10.0, -3.0, 1.0]
        expected = np.linalg.inv(frame_pose) @ np.r_[world, 1.0]
        np.testing.assert_allclose(out, expected[:3], atol=1e-12)
        with self.assertRaises(ValueError):
            range_image_to_vehicle(ri, np.eye(4), inc, az, pixel_pose=pixel_pose)


if __name__ == "__main__":
    unittest.main()
