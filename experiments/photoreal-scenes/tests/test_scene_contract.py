from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
sys.path.insert(0, str(PIPELINE))


def _import_required(name: str):
    path = PIPELINE / f"{name}.py"
    if not path.is_file():
        raise AssertionError(f"required module is missing: {path}")
    spec = importlib.util.spec_from_file_location(f"photoreal_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CameraContractTest(unittest.TestCase):
    def test_opencv_camera_center_recovers_below_one_micrometre(self) -> None:
        geometry = _import_required("geometry")
        eye = np.asarray([1.25, -3.5, 1.7], dtype=np.float64)
        intrinsics, extrinsics = geometry.look_at_opencv(
            eye=eye,
            target=np.asarray([0.1, 0.4, 1.0]),
            width=512,
            height=384,
            fov_degrees=58.0,
        )
        recovered = geometry.camera_center(extrinsics)
        self.assertLess(float(np.linalg.norm(recovered - eye)), 1e-6)
        self.assertEqual(intrinsics.shape, (3, 3))
        forward_point = np.asarray([[0.1, 0.4, 1.0]])
        camera_point = geometry.world_to_camera(forward_point, extrinsics)[0]
        self.assertGreater(camera_point[2], 0.0)

    def test_blender_matrix_conversion_uses_opencv_axis_convention(self) -> None:
        geometry = _import_required("geometry")
        # Blender camera at (0, 0, 2), identity orientation: right +x,
        # up +y, forward -z. OpenCV must be right +x, down +y, forward +z.
        matrix_world = np.eye(4, dtype=np.float64)
        matrix_world[:3, 3] = [0.0, 0.0, 2.0]
        extrinsics = geometry.opencv_extrinsics_from_blender(matrix_world)
        np.testing.assert_allclose(extrinsics[:, :3], np.diag([1.0, -1.0, -1.0]))
        np.testing.assert_allclose(geometry.camera_center(extrinsics), [0.0, 0.0, 2.0])


class SamplingAndVisibilityTest(unittest.TestCase):
    def test_surface_sampling_is_bit_exact_for_a_fixed_seed(self) -> None:
        geometry = _import_required("geometry")
        vertices = np.asarray(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 1.0, 0.0]]
        )
        triangles = np.asarray([[0, 1, 2], [1, 3, 2]])
        triangle_object_ids = np.asarray([1, 2], dtype=np.int32)
        first = geometry.sample_triangle_surface(
            vertices,
            triangles,
            triangle_object_ids,
            total=64,
            minimum=8,
            seed=20260926,
        )
        second = geometry.sample_triangle_surface(
            vertices,
            triangles,
            triangle_object_ids,
            total=64,
            minimum=8,
            seed=20260926,
        )
        for first_array, second_array in zip(first, second, strict=True):
            np.testing.assert_array_equal(first_array, second_array)

    def test_normal_supervision_is_unit_length_on_valid_pixels(self) -> None:
        scene = _import_required("scene")
        vectors = np.asarray(
            [[[0.0, 3.0, 4.0], [0.0, 0.0, 0.0]], [[2.0, 0.0, 0.0], [1.0, 2.0, 2.0]]],
            dtype=np.float32,
        )
        valid = np.asarray([[True, False], [True, True]])
        normalized = scene.normalize_valid_vectors(vectors, valid)
        np.testing.assert_allclose(np.linalg.norm(normalized[valid], axis=1), 1.0)
        np.testing.assert_array_equal(normalized[~valid], 0.0)

    def test_validity_is_derived_from_metric_depth_and_stable_object_id(self) -> None:
        scene = _import_required("scene")
        depth = np.asarray([[2.0, 0.0], [3.0, 4.0]], dtype=np.float32)
        object_ids = np.asarray([[7, 7], [0, 8]], dtype=np.int32)
        np.testing.assert_array_equal(
            scene.derive_validity(depth, object_ids),
            [[True, False], [False, True]],
        )

    def test_ray_distance_is_derived_at_nominal_pixel_centers(self) -> None:
        scene = _import_required("scene")
        depth = np.full((3, 3), 2.0, dtype=np.float32)
        intrinsics = np.asarray(
            [[2.0, 0.0, 1.0], [0.0, 2.0, 1.0], [0.0, 0.0, 1.0]]
        )
        ray = scene.camera_depth_to_ray_distance(depth, intrinsics)
        self.assertAlmostEqual(float(ray[1, 1]), 2.0)
        self.assertAlmostEqual(float(ray[0, 0]), float(2.0 * np.sqrt(1.5)), places=6)

    def test_allocation_guarantees_2048_per_object_and_exact_total(self) -> None:
        geometry = _import_required("geometry")
        allocation = geometry.allocate_surface_samples(
            np.asarray([1.0, 2.0, 7.0]), total=250_000, minimum=2_048
        )
        self.assertEqual(int(allocation.sum()), 250_000)
        self.assertTrue(np.all(allocation >= 2_048))
        self.assertGreater(allocation[2], allocation[1])
        self.assertGreater(allocation[1], allocation[0])
        np.testing.assert_array_equal(
            allocation,
            geometry.allocate_surface_samples(
                np.asarray([1.0, 2.0, 7.0]), total=250_000, minimum=2_048
            ),
        )

    def test_visibility_uses_projected_depth_id_and_scale_aware_tolerance(self) -> None:
        geometry = _import_required("geometry")
        intrinsics = np.asarray(
            [[100.0, 0.0, 1.0], [0.0, 100.0, 1.0], [0.0, 0.0, 1.0]]
        )
        extrinsics = np.concatenate([np.eye(3), np.zeros((3, 1))], axis=1)
        depth = np.zeros((3, 3), dtype=np.float32)
        object_ids = np.zeros((3, 3), dtype=np.int32)
        depth[1, 1] = 2.0
        object_ids[1, 1] = 7
        points = np.asarray(
            [
                [0.0, 0.0, 2.0],
                [0.0, 0.0, 2.015],
                [0.0, 0.0, 2.1],
                [0.0, 0.0, 3.0],
                [0.0, 0.0, 2.0],
                [10.0, 0.0, 2.0],
            ]
        )
        ids = np.asarray([7, 7, 7, 7, 8, 7], dtype=np.int32)
        visible = geometry.visibility_from_buffers(
            points,
            ids,
            intrinsics,
            extrinsics,
            depth,
            object_ids,
            scene_scale=10.0,
        )
        np.testing.assert_array_equal(visible, [True, True, False, False, False, False])


class SceneFamilyContractTest(unittest.TestCase):
    def test_profiles_match_draft_and_benchmark_contracts(self) -> None:
        contracts = _import_required("contracts")
        self.assertIn(
            (contracts.PROFILES["draft"]["width"], contracts.PROFILES["draft"]["height"]),
            {(64, 48), (128, 96)},
        )
        self.assertEqual(contracts.PROFILES["draft"]["samples"], 32)
        self.assertEqual(
            (contracts.PROFILES["benchmark"]["width"], contracts.PROFILES["benchmark"]["height"]),
            (512, 384),
        )
        self.assertEqual(contracts.PROFILES["benchmark"]["samples"], 256)
        self.assertEqual(contracts.PROFILES["benchmark"]["required_device"], "OPTIX")

    def test_scene_family_has_stable_ids_assets_roles_and_camera_counts(self) -> None:
        scene = _import_required("scene")
        objects_a = scene.object_specs("scene_a")
        objects_b = scene.object_specs("scene_b")
        self.assertEqual(len({item.object_id for item in objects_a}), len(objects_a))
        self.assertEqual(len({item.object_id for item in objects_b}), len(objects_b))
        common_a = {(item.name, item.object_id) for item in objects_a if item.role == "common"}
        common_b = {(item.name, item.object_id) for item in objects_b if item.role == "common"}
        self.assertEqual(common_a, common_b)
        self.assertIn("WoodenChair_01", {item.asset_id for item in objects_a})
        self.assertIn("WoodenTable_01", {item.asset_id for item in objects_a})
        hidden_a = [item for item in objects_a if item.role == "hidden"]
        hidden_b = [item for item in objects_b if item.role == "hidden"]
        self.assertEqual([item.asset_id for item in hidden_a], ["Sofa_01"])
        self.assertEqual([item.asset_id for item in hidden_b], ["Shelf_01"])
        self.assertLess(abs(hidden_a[0].location[1] - hidden_b[0].location[1]), 0.75)
        context, target = scene.camera_specs(width=128, height=96)
        self.assertEqual(len(context), 16)
        self.assertEqual(len(target), 8)
        self.assertTrue(all(camera.target[1] <= -1.0 for camera in context))
        self.assertEqual(context, scene.camera_specs(width=128, height=96)[0])

    def test_object_relations_are_closed_over_each_scene_table(self) -> None:
        scene = _import_required("scene")
        for scene_name in ("scene_a", "scene_b"):
            table = scene.object_table(scene_name)
            names = {item["name"] for item in table}
            for item in table:
                for targets in item["relations"].values():
                    self.assertLessEqual(set(targets), names)

    def test_scene_module_imports_without_bpy(self) -> None:
        scene = _import_required("scene")
        self.assertTrue(hasattr(scene, "build_blender_scene"))


class ManifestV2ContractTest(unittest.TestCase):
    def test_manifest_v2_preserves_v1_probe_fields_and_records_supervision(self) -> None:
        schema = _import_required("schema")
        scene = _import_required("scene")
        context, target = scene.camera_specs(width=128, height=96)
        manifest = schema.build_manifest_skeleton(
            profile="draft",
            device="CPU",
            seed=20260925,
            asset_lock_sha256="a" * 64,
            context_cameras=context,
            target_cameras=target,
        )
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["task"], "paired_hidden-scene_ambiguity")
        # Existing stock-probe fields remain available at their v1 paths.
        for key in (
            "image_size",
            "context_views",
            "target_views",
            "paired_context",
            "paired_targets",
            "camera_checks",
            "scenes",
        ):
            self.assertIn(key, manifest)
        self.assertEqual(len(manifest["context_views"]), 16)
        self.assertEqual(len(manifest["target_views"]), 8)
        supervision = manifest["annotation_contract"]
        self.assertEqual(supervision["coordinate_system"], "opencv_world_to_camera")
        self.assertEqual(supervision["surface_samples_per_scene"], 250_000)
        self.assertEqual(supervision["minimum_samples_per_object"], 2_048)
        self.assertEqual(
            set(supervision["per_view"]),
            {
                "srgb_png",
                "linear_multilayer_openexr",
                "camera_axis_depth",
                "ray_distance",
                "world_geometric_normal",
                "world_shading_normal",
                "object_id",
                "diffuse_albedo",
                "validity_mask",
            },
        )
        renderer = manifest["renderer"]
        self.assertEqual(renderer["profile"], "draft")
        self.assertEqual(renderer["samples"], 32)
        self.assertEqual(renderer["device"], "CPU")
        self.assertEqual(renderer["color_transform"], "AgX")
        canonical = json.dumps(manifest, sort_keys=True)
        self.assertEqual(canonical, json.dumps(manifest, sort_keys=True))


class ContactSheetTest(unittest.TestCase):
    def test_contact_sheet_preserves_order_and_fixed_cell_geometry(self) -> None:
        contact_sheet = _import_required("contact_sheet")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = []
            for index, color in enumerate(((255, 0, 0), (0, 255, 0), (0, 0, 255))):
                path = root / f"{index:04d}.png"
                Image.new("RGB", (64, 48), color).save(path)
                paths.append(path)
            output = root / "sheet.png"
            contact_sheet.make_contact_sheet(
                paths, output, columns=2, cell_size=(64, 48), label_height=12
            )
            with Image.open(output) as sheet:
                self.assertEqual(sheet.size, (128, 120))
                self.assertEqual(sheet.getpixel((10, 10)), (255, 0, 0))
                self.assertEqual(sheet.getpixel((74, 10)), (0, 255, 0))
                self.assertEqual(sheet.getpixel((10, 70)), (0, 0, 255))


if __name__ == "__main__":
    unittest.main()
