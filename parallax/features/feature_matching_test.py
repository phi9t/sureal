"""Feature matching tests on the deterministic orbit scene."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from camera.pose import fundamental_from_poses, symmetric_epipolar_distance
from features.describe import describe_patches
from features.detect import detect_harris
from features.match import match_descriptors_locally
from scene.orbit import generate_orbit_scene


def _read_pgm(path: Path) -> np.ndarray:
    payload = path.read_bytes()
    header, width_height, max_value, data = payload.split(b"\n", 3)
    if header != b"P5" or max_value != b"255":
        raise ValueError(f"unsupported PGM fixture: {path}")
    width, height = (int(item) for item in width_height.split())
    return np.frombuffer(data, dtype=np.uint8).reshape(height, width)


class OrbitFeatureMatchingTest(unittest.TestCase):
    def test_orbit_scene_matches_are_ground_truth_epipolar_inliers(self) -> None:
        """Catches descriptors or ratio matching that accept repeated-texture mismatches."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = generate_orbit_scene(root, "smoke")
            first = manifest["frames"][0]
            second = manifest["frames"][1]
            image1 = _read_pgm(root / first["image_path"])
            image2 = _read_pgm(root / second["image_path"])

            keypoints1 = detect_harris(
                image1,
                max_keypoints=2200,
                quality=0.0,
                min_distance=1,
                border=3,
                window_radius=1,
                require_local_maximum=False,
            )
            keypoints2 = detect_harris(
                image2,
                max_keypoints=2200,
                quality=0.0,
                min_distance=1,
                border=3,
                window_radius=1,
                require_local_maximum=False,
            )
            described1 = describe_patches(image1, keypoints1, radius=3)
            described2 = describe_patches(image2, keypoints2, radius=3)
            matches = match_descriptors_locally(
                described1.keypoints,
                described1.descriptors,
                described2.keypoints,
                described2.descriptors,
                search_radius_x=5.0,
                search_radius_y=6.0,
                ratio=0.8,
            ).matches

            self.assertGreaterEqual(len(matches), 8)
            matched1 = described1.keypoints[matches[:, 0]]
            matched2 = described2.keypoints[matches[:, 1]]
            fundamental = fundamental_from_poses(
                np.asarray(first["K"], dtype=np.float64),
                np.asarray(first["R_world_to_camera"], dtype=np.float64),
                np.asarray(first["t_world_to_camera_m"], dtype=np.float64),
                np.asarray(second["K"], dtype=np.float64),
                np.asarray(second["R_world_to_camera"], dtype=np.float64),
                np.asarray(second["t_world_to_camera_m"], dtype=np.float64),
            )
            errors = np.array(
                [
                    symmetric_epipolar_distance(fundamental, left, right)
                    for left, right in zip(matched1, matched2)
                ],
                dtype=np.float64,
            )

            self.assertGreaterEqual(float(np.mean(errors < 0.75)), 0.9)


if __name__ == "__main__":
    unittest.main()
