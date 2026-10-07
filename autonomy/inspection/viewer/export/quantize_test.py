import unittest

import numpy as np

from inspection.viewer.export.quantize import (decode_elongation, decode_intensity, dequantize_xyz, encode_elongation,
                                               encode_intensity, pack_flags, quantize_xyz, unpack_flags)


class QuantizeTest(unittest.TestCase):
    def test_xyz_round_trip_within_half_step(self):
        xyz = np.random.default_rng(0).uniform(-80, 80, (1000, 3))
        q = quantize_xyz(xyz)
        self.assertEqual(q.dtype, np.int16)
        self.assertLessEqual(np.abs(dequantize_xyz(q) - xyz).max(), 0.0025 + 1e-12)
        with self.assertRaises(ValueError):
            quantize_xyz(np.array([[200.0, 0, 0]]))

    def test_intensity_monotonic_and_saturating(self):
        v = np.array([0.0, 1.0, 10.0, 100.0, 40000.0])
        codes = encode_intensity(v, 32768.0)
        self.assertTrue((np.diff(codes.astype(int)) >= 0).all())
        self.assertEqual(codes[0], 0)
        self.assertEqual(codes[-1], 255)
        back = decode_intensity(codes, 32768.0)
        self.assertLess(abs(np.log1p(back[2]) - np.log1p(10.0)), np.log1p(32768.0) / 255)

    def test_elongation(self):
        codes = encode_elongation(np.array([0.0, 1.0, 5.0]), 2.0)
        self.assertEqual(list(codes), [0, 128, 255])
        self.assertAlmostEqual(decode_elongation(codes, 2.0)[2], 2.0)

    def test_flags_pack_unpack(self):
        flags = pack_flags([True, False], 2, 5, [False, True])
        f = unpack_flags(flags)
        self.assertEqual(list(f["nlz"]), [True, False])
        self.assertEqual(list(f["return_index"]), [2, 2])
        self.assertEqual(list(f["sensor"]), [5, 5])
        self.assertEqual(list(f["has_proj"]), [False, True])
        with self.assertRaises(ValueError):
            pack_flags([True], 3, 1, [True])


if __name__ == "__main__":
    unittest.main()
