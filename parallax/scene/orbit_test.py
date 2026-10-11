"""Tests for the orbiting textured-planes scene."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from camera.pinhole import project
from pipeline.contracts import sha256_file
from scene.orbit import generate_orbit_scene


class OrbitSceneTest(unittest.TestCase):
    def test_surface_samples_project_to_the_rendered_depth(self) -> None:
        """Catches wrong camera-frame depth or stale poses in exported truth."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = generate_orbit_scene(root, "smoke")

            self.assertEqual(manifest["profile"], "smoke")
            self.assertEqual(len(manifest["frames"]), 3)
            rotations = [
                np.asarray(frame["R_world_to_camera"], dtype=np.float64)
                for frame in manifest["frames"]
            ]
            translations = [
                np.asarray(frame["t_world_to_camera_m"], dtype=np.float64)
                for frame in manifest["frames"]
            ]
            self.assertGreater(np.linalg.norm(rotations[0] - rotations[-1]), 0.1)
            self.assertGreater(
                np.linalg.norm(translations[0] - translations[-1]), 0.1
            )

            for frame in manifest["frames"]:
                image_path = root / frame["image_path"]
                depth_path = root / frame["depth_path"]
                points_path = root / frame["surface_points_path"]
                normals_path = root / frame["surface_normals_path"]
                self.assertEqual(frame["image_sha256"], sha256_file(image_path))
                self.assertEqual(frame["depth_sha256"], sha256_file(depth_path))
                self.assertEqual(frame["surface_points_sha256"], sha256_file(points_path))
                self.assertEqual(
                    frame["surface_normals_sha256"], sha256_file(normals_path)
                )

                points = np.load(points_path, allow_pickle=False)
                normals = np.load(normals_path, allow_pickle=False)
                depth = np.load(depth_path, allow_pickle=False)
                pixels, camera_depth = project(
                    points,
                    np.asarray(frame["K"], dtype=np.float64),
                    np.asarray(frame["R_world_to_camera"], dtype=np.float64),
                    np.asarray(frame["t_world_to_camera_m"], dtype=np.float64),
                )
                rounded = np.rint(pixels).astype(np.int64)
                self.assertTrue(np.all(np.abs(pixels - rounded) < 1e-8))
                sampled_depth = depth[rounded[:, 1], rounded[:, 0]].astype(np.float64)
                np.testing.assert_allclose(camera_depth, sampled_depth, atol=1e-6)
                np.testing.assert_allclose(
                    np.linalg.norm(normals, axis=1),
                    np.ones(len(normals)),
                    atol=1e-6,
                )

    def test_full_profile_exports_more_views_and_surface_samples(self) -> None:
        """Catches profile mix-ups that silently reuse the smoke fixture."""
        with tempfile.TemporaryDirectory() as temporary:
            manifest = generate_orbit_scene(Path(temporary), "full")

            self.assertEqual(manifest["profile"], "full")
            self.assertEqual(len(manifest["frames"]), 7)
            self.assertGreater(
                manifest["surface_truth"]["sample_count"],
                manifest["frames"][0]["surface_sample_count"],
            )
            self.assertEqual(
                manifest["surface_truth"]["points_sha256"],
                sha256_file(Path(temporary) / manifest["surface_truth"]["points_path"]),
            )

    def test_orbit_cameras_include_elevation_variation(self) -> None:
        """Catches scenes that test SfM with single-axis yaw motion only."""
        with tempfile.TemporaryDirectory() as temporary:
            manifest = generate_orbit_scene(Path(temporary), "full")

        centers = np.array(
            [frame["camera_center_world_m"] for frame in manifest["frames"]],
            dtype=np.float64,
        )
        self.assertGreater(float(np.ptp(centers[:, 1])), 0.08)
        self.assertIn("elevation", manifest["scene"]["camera_motion"])


if __name__ == "__main__":
    unittest.main()
