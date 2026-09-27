from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _fixture(root: Path) -> dict[str, object]:
    view_root = root / "scene_a/context"
    for layer in ("depth", "ray_distance", "geometric_normal", "object_id", "validity"):
        (view_root / layer).mkdir(parents=True, exist_ok=True)
    depth = np.asarray([[2.0, 3.0], [4.0, 0.0]], dtype=np.float32)
    ray = depth.copy()
    normals = np.zeros((2, 2, 3), dtype=np.float32)
    normals[..., 2] = -1.0
    object_ids = np.asarray([[1, 1], [1, 0]], dtype=np.int32)
    validity = object_ids > 0
    arrays = {
        "depth": depth,
        "ray_distance": ray,
        "geometric_normal": normals,
        "object_id": object_ids,
        "validity": validity,
    }
    paths: dict[str, str] = {}
    for layer, array in arrays.items():
        path = view_root / layer / "0000.npy"
        np.save(path, array, allow_pickle=False)
        paths[layer] = path.relative_to(root).as_posix()
    camera = {
        "eye": [0.0, 0.0, 0.0],
        "intrinsics": [[2.0, 0.0, 0.5], [0.0, 2.0, 0.5], [0.0, 0.0, 1.0]],
        "world_to_camera": [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]],
    }
    manifest = {
        "schema_version": 2,
        "task": "paired_hidden-scene_ambiguity",
        "image_size": {"width": 2, "height": 2},
        "context_views": [camera],
        "target_views": [camera],
        "views": {"shared_context": [{"index": 0, **paths}], "scene_a_target": [], "scene_b_target": []},
        "paired_context": {"pixel_mismatches": 0},
        "renderer": {
            "blender_version": "4.5.14 LTS",
            "cycles_version": "4.5.14 LTS",
            "profile": "benchmark",
            "device": "OPTIX",
            "samples": 256,
            "resolution": [2, 2],
            "random_seeds": {"episode": 20260925, "cycles": 20260925, "surface_sampling": 20260926},
        },
        "scenes": {
            "scene_a": {"visibility": {"hidden_object_context_fraction": 0.0, "hidden_object_target_fraction": 0.7}},
            "scene_b": {"visibility": {"hidden_object_context_fraction": 0.0, "hidden_object_target_fraction": 0.6}},
        },
        "annotation_contract": {
            "coordinate_system": "opencv_world_to_camera",
            "world_units": "metres",
            "depth": "positive camera-axis z to first opaque surface",
            "ray_distance": "Euclidean camera-to-first-surface distance",
            "normals": "world-space unit vectors",
            "object_ids": "stable positive integers; 0 is invalid/background",
        },
    }
    _write_json(root / "manifest.json", manifest)
    artifact_hashes = {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    validation = {
        "schema_version": 1,
        "status": "pass",
        "episode_manifest_sha256": _sha256(root / "manifest.json"),
        "artifact_sha256": artifact_hashes,
        "camera_max_center_error_metres": 0.0,
        "counts": {"context_views": 1, "target_views_per_scene": 0, "surface_points_per_scene": 4},
        "visibility": {"scene_a": manifest["scenes"]["scene_a"]["visibility"], "scene_b": manifest["scenes"]["scene_b"]["visibility"]},
    }
    _write_json(root / "validation.json", validation)
    return {
        "id": "controlled-suite",
        "mode": "generated",
        "episode_id": "fixture",
        "episode_manifest_sha256": _sha256(root / "manifest.json"),
        "validation_sha256": _sha256(root / "validation.json"),
        "artifact_count": len(artifact_hashes),
        "context_views": 1,
        "target_views_per_hypothesis": 0,
        "surface_points_per_hypothesis": 4,
        "blender_version": "4.5.14 LTS",
        "profile": "benchmark",
        "samples": 256,
    }


class ControlledSuiteTest(unittest.TestCase):
    def test_lock_binds_the_existing_blender_episode_and_consumers(self) -> None:
        assets = {
            item["id"]: item
            for item in json.loads((ROOT / "assets.lock.json").read_text())["assets"]
        }
        record = assets["controlled-suite"]
        self.assertEqual(record["source"], "../photoreal-scenes/recipe.json")
        self.assertEqual(record["episode_id"], "phase-a-v1")
        self.assertEqual(record["episode_manifest_sha256"], "9df5874db09c15b08b708a7164531fea681a7897faf038944d359665067a92f8")
        self.assertEqual(record["validation_sha256"], "a62923fe8cdeb7f7217e114aa391d88acaabfb472573ba18fa451f794ca98351")
        self.assertEqual(record["artifact_count"], 444)
        self.assertEqual(record["blender_version"], "4.5.14 LTS")
        self.assertGreaterEqual(len(record["consumers"]), 8)

    def test_validation_consumes_blender_depth_normals_and_sensor_contract(self) -> None:
        import controlled_suite

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = _fixture(root)
            binding = controlled_suite.validate_controlled_suite(root, lock=lock)
            self.assertEqual(binding["episode_manifest_sha256"], lock["episode_manifest_sha256"])
            summary = controlled_suite.sensor_summary(root)
            self.assertEqual(summary["source_view"], "shared_context/0000")
            self.assertEqual(summary["valid_pixels"], 3)
            self.assertEqual(summary["depth_units"], "metres")
            self.assertGreater(summary["structured_light_missing_fraction"], 0.0)
            self.assertGreater(summary["tof_bias_mean_m"], 0.0)
            self.assertGreater(summary["lidar_return_count"], 0)

            artifact = root / "controlled-suite.json"
            controlled_suite.write_module_binding(root, artifact, "03", lock=lock)
            payload = json.loads(artifact.read_text())
            self.assertEqual(payload["module_id"], "03")
            self.assertEqual(payload["sensor_simulations"]["valid_pixels"], 3)

            depth_path = root / "scene_a/context/depth/0000.npy"
            depth_path.write_bytes(depth_path.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                controlled_suite.validate_controlled_suite(root, lock=lock)

    def test_cached_validation_rechecks_same_size_content_with_restored_mtime(self) -> None:
        import controlled_suite

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = _fixture(root)
            controlled_suite.validate_controlled_suite(root, lock=lock)
            depth_path = root / "scene_a/context/depth/0000.npy"
            metadata = depth_path.stat()
            content = bytearray(depth_path.read_bytes())
            content[-1] ^= 1
            depth_path.write_bytes(content)
            os.utime(
                depth_path,
                ns=(metadata.st_atime_ns, metadata.st_mtime_ns),
            )

            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                controlled_suite.validate_controlled_suite(root, lock=lock)


if __name__ == "__main__":
    unittest.main()
