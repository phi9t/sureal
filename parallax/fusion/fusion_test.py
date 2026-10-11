from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from evaluation.surface_metrics import surface_metrics
from fusion.marching_tetrahedra import marching_tetrahedra
from fusion.tsdf import fuse_depth_maps
from scene.orbit import generate_orbit_scene
from stereo.plane_sweep import load_orbit_views


class FusionTest(unittest.TestCase):
    def test_sphere_sdf_meshes_to_analytic_radius_within_voxel_tolerance(self) -> None:
        """Catches missing edge interpolation or incorrect grid-coordinate scaling."""
        voxel_size_m = 0.08
        radius_m = 0.62
        coordinates = np.arange(-0.88, 0.88 + voxel_size_m, voxel_size_m)
        x, y, z = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
        sdf = np.sqrt(x * x + y * y + z * z) - radius_m

        mesh = marching_tetrahedra(
            sdf,
            origin_m=(coordinates[0], coordinates[0], coordinates[0]),
            voxel_size_m=voxel_size_m,
        )

        radii = np.linalg.norm(mesh.vertices, axis=1)
        self.assertGreater(mesh.triangles.shape[0], 1000)
        self.assertLess(float(abs(np.mean(radii) - radius_m)), voxel_size_m)
        self.assertLess(float(np.percentile(np.abs(radii - radius_m), 95)), voxel_size_m)

    def test_sphere_sdf_mesh_is_welded_and_indexed(self) -> None:
        """Catches triangle soup exports that duplicate every generated vertex."""
        voxel_size_m = 0.10
        coordinates = np.arange(-0.8, 0.8 + voxel_size_m, voxel_size_m)
        x, y, z = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
        sdf = np.sqrt(x * x + y * y + z * z) - 0.52

        mesh = marching_tetrahedra(
            sdf,
            origin_m=(coordinates[0], coordinates[0], coordinates[0]),
            voxel_size_m=voxel_size_m,
        )

        unique_vertices = np.unique(np.round(mesh.vertices, decimals=12), axis=0)
        self.assertEqual(unique_vertices.shape[0], mesh.vertices.shape[0])
        self.assertLess(mesh.vertices.shape[0], mesh.triangles.shape[0])
        self.assertLessEqual(int(mesh.triangles.max()), mesh.vertices.shape[0] - 1)

    def test_truth_depth_fusion_mesh_beats_orbit_surface_thresholds(self) -> None:
        """Catches TSDF projection sign errors and missing per-view weight fusion."""
        with tempfile.TemporaryDirectory() as temporary:
            scene_root = Path(temporary) / "orbit"
            manifest = generate_orbit_scene(scene_root, "smoke")
            views = load_orbit_views(scene_root)
            truth_points = np.load(
                scene_root / manifest["surface_truth"]["points_path"],
                allow_pickle=False,
            )
            volume = fuse_depth_maps(
                views,
                {view.view_id: view.truth_depth_m for view in views},
                voxel_size_m=0.12,
                truncation_m=0.24,
                padding_m=0.24,
            )
            mesh = marching_tetrahedra(
                volume.values,
                origin_m=volume.origin_m,
                voxel_size_m=volume.voxel_size_m,
                valid_mask=volume.weights > 0.0,
            )
            metrics = surface_metrics(mesh.vertices, truth_points, tau=0.18)

        self.assertGreater(mesh.vertices.shape[0], 250)
        self.assertLess(metrics["chamfer_distance"], 0.16)
        self.assertGreater(metrics["f_score"], 0.80)


if __name__ == "__main__":
    unittest.main()
