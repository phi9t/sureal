import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from inspection.viewer.export.boxes import lidar_boxes_to_tracks, points_in_box
from inspection.viewer.export.manifest import canonical_json, inverse_rigid, mat4, sha256_file


class ManifestTest(unittest.TestCase):
    def test_canonical_json_sorted_and_finite(self):
        self.assertEqual(canonical_json({"b": [1, np.float64(2.5)], "a": np.int32(3)}), b'{"a":3,"b":[1,2.5]}\n')
        with self.assertRaises(ValueError):
            canonical_json({"x": float("nan")})

    def test_mat4_validation_and_inverse(self):
        m = np.eye(4)
        m[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
        m[:3, 3] = [1, 2, 3]
        v = mat4(list(m.reshape(16)))
        np.testing.assert_allclose(inverse_rigid(v) @ v, np.eye(4), atol=1e-12)
        bad = m.copy()
        bad[0, 0] = 2.0
        with self.assertRaises(ValueError):
            mat4(list(bad.reshape(16)))

    def test_file_digest_rejects_symlinked_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.bin"
            source.write_bytes(b"viewer")
            link = root / "link.bin"
            link.symlink_to(source)

            with self.assertRaisesRegex(ValueError, "regular non-symlinked file required"):
                sha256_file(link)


class BoxesTest(unittest.TestCase):
    def test_points_in_rotated_box(self):
        pts = np.array([[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 3.0]])
        # length 5 along heading (90 deg -> +y), width 1, height 2
        self.assertEqual(points_in_box(pts, [0, 0, 0], [5, 1, 2], math.pi / 2), 2)
        self.assertEqual(points_in_box(pts, [0, 0, 0], [5, 1, 2], 0.0), 2)

    def test_tracks_group_and_sort(self):
        def row(ts, oid, t=1):
            r = {"key.frame_timestamp_micros": ts, "key.laser_object_id": oid, "[LiDARBoxComponent].type": t}
            for k in ["box.center.x", "box.center.y", "box.center.z", "box.size.x", "box.size.y", "box.size.z", "box.heading",
                      "speed.x", "speed.y", "speed.z", "acceleration.x", "acceleration.y", "acceleration.z"]:
                r["[LiDARBoxComponent]." + k] = 1.0
            for k in ["num_lidar_points_in_box", "num_top_lidar_points_in_box", "difficulty_level.detection", "difficulty_level.tracking"]:
                r["[LiDARBoxComponent]." + k] = 2
            return r
        tracks = lidar_boxes_to_tracks([row(20, "b"), row(10, "a"), row(20, "a"), row(30, "zz")], {10: 0, 20: 1})
        self.assertEqual(list(tracks["tracks"]), ["a", "b"])
        self.assertEqual([r[0] for r in tracks["tracks"]["a"]["rows"]], [0, 1])
        with self.assertRaises(ValueError):
            lidar_boxes_to_tracks([row(10, "a"), row(10, "a")], {10: 0})


if __name__ == "__main__":
    unittest.main()
