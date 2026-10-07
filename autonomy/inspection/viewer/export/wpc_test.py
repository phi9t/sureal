import tempfile
import unittest
from pathlib import Path

import numpy as np

from export.constants import KIND_FLAGS, KIND_RGB, KIND_XYZ
from export.wpc import Section, read_wpc, write_wpc


class WpcTest(unittest.TestCase):
    def sections(self):
        return [
            Section(2, 1, KIND_RGB, np.arange(9, dtype=np.uint8).reshape(3, 3)),
            Section(1, 1, KIND_XYZ, np.array([[1, -2, 3], [4, 5, -6], [7, 8, 9]], dtype=np.int16)),
            Section(1, 1, KIND_FLAGS, np.array([1, 2, 3], dtype=np.uint8)),
        ]

    def test_round_trip_sorted_and_aligned(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f.wpc"
            n = write_wpc(p, 7, 123456789, 0.005, self.sections())
            self.assertEqual(n, p.stat().st_size)
            header, secs = read_wpc(p)
            self.assertEqual(header, {"frame_index": 7, "timestamp_micros": 123456789, "xyz_scale": np.float32(0.005)})
            self.assertEqual(list(secs), [(1, 1, KIND_XYZ), (1, 1, KIND_FLAGS), (2, 1, KIND_RGB)])
            np.testing.assert_array_equal(secs[(1, 1, KIND_XYZ)], [[1, -2, 3], [4, 5, -6], [7, 8, 9]])
            np.testing.assert_array_equal(secs[(2, 1, KIND_RGB)], np.arange(9).reshape(3, 3))
            self.assertEqual(n % 4, 0)

    def test_byte_identical_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a", Path(d) / "b"
            write_wpc(a, 0, 1, 0.005, self.sections())
            write_wpc(b, 0, 1, 0.005, list(reversed(self.sections())))
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with self.assertRaises(ValueError):
                write_wpc(a, 0, 1, 0.005, self.sections() + [Section(1, 1, KIND_XYZ, np.zeros((1, 3), np.int16))])


if __name__ == "__main__":
    unittest.main()
