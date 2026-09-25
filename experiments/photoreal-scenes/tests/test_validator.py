from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import OpenImageIO as oiio
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

try:
    from validator import ValidationError, validate_episode
except ModuleNotFoundError:  # Keep collection green enough to show a useful RED.
    ValidationError = AssertionError

    def validate_episode(*_args, **_kwargs):
        raise ValidationError("validator.py is missing")


WIDTH = 128
HEIGHT = 96
FX = 100.0
INTRINSICS = np.asarray(
    [[FX, 0.0, (WIDTH - 1.0) / 2.0], [0.0, FX, (HEIGHT - 1.0) / 2.0], [0.0, 0.0, 1.0]],
    dtype=np.float64,
)
EXTRINSICS = np.concatenate([np.eye(3), np.zeros((3, 1))], axis=1)
LAYERS = (
    "rgb",
    "exr",
    "depth",
    "ray_distance",
    "geometric_normal",
    "shading_normal",
    "object_id",
    "albedo",
    "validity",
)
EXR_CHANNELS = (
    "ViewLayer.Combined.R",
    "ViewLayer.Combined.G",
    "ViewLayer.Combined.B",
    "ViewLayer.Combined.A",
    "ViewLayer.CameraDepth.X",
    "ViewLayer.RayDistance.X",
    "ViewLayer.IndexOB.X",
    "ViewLayer.GeomNormal.R",
    "ViewLayer.GeomNormal.G",
    "ViewLayer.GeomNormal.B",
    "ViewLayer.ShadeNormal.R",
    "ViewLayer.ShadeNormal.G",
    "ViewLayer.ShadeNormal.B",
    "ViewLayer.DiffuseAlbedo.R",
    "ViewLayer.DiffuseAlbedo.G",
    "ViewLayer.DiffuseAlbedo.B",
)


def _hash_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _ray_distance(depth: float) -> np.ndarray:
    xs, ys = np.meshgrid(np.arange(WIDTH), np.arange(HEIGHT))
    return (
        depth
        * np.sqrt(
            1.0
            + ((xs - INTRINSICS[0, 2]) / INTRINSICS[0, 0]) ** 2
            + ((ys - INTRINSICS[1, 2]) / INTRINSICS[1, 1]) ** 2
        )
    ).astype(np.float32)


def _write_exr(path: Path) -> None:
    specification = oiio.ImageSpec(WIDTH, HEIGHT, len(EXR_CHANNELS), "float")
    specification.channelnames = list(EXR_CHANNELS)
    specification.attribute("oiio:ColorSpace", "Linear")
    output = oiio.ImageOutput.create(str(path))
    if output is None or not output.open(str(path), specification):
        raise RuntimeError(f"could not create test EXR: {oiio.geterror()}")
    try:
        pixels = np.zeros((HEIGHT, WIDTH, len(EXR_CHANNELS)), dtype=np.float32)
        if not output.write_image(pixels):
            raise RuntimeError(f"could not write test EXR: {output.geterror()}")
    finally:
        output.close()


def _write_view(root: Path, index: int, *, color: tuple[int, int, int], depth_value: float, object_id: int) -> None:
    for layer in LAYERS:
        (root / layer).mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (WIDTH, HEIGHT), color).save(root / "rgb" / f"{index:04d}.png")
    _write_exr(root / "exr" / f"{index:04d}.exr")
    depth = np.full((HEIGHT, WIDTH), depth_value, dtype=np.float32)
    normal = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
    normal[:, :, 2] = 1.0
    np.save(root / "depth" / f"{index:04d}.npy", depth)
    np.save(root / "ray_distance" / f"{index:04d}.npy", _ray_distance(depth_value))
    np.save(root / "geometric_normal" / f"{index:04d}.npy", normal)
    np.save(root / "shading_normal" / f"{index:04d}.npy", normal)
    np.save(root / "object_id" / f"{index:04d}.npy", np.full((HEIGHT, WIDTH), object_id, np.int32))
    np.save(root / "albedo" / f"{index:04d}.npy", np.full((HEIGHT, WIDTH, 3), 0.5, np.float32))
    np.save(root / "validity" / f"{index:04d}.npy", np.ones((HEIGHT, WIDTH), bool))


def _hardlink_tree(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(path, target)


def _camera_payload(count: int) -> list[dict[str, object]]:
    return [
        {
            "eye": [0.0, 0.0, 0.0],
            "target": [0.0, 0.0, 1.0],
            "intrinsics": INTRINSICS.tolist(),
            "world_to_camera": EXTRINSICS.tolist(),
            "opencv_axes": {"x": "right", "y": "down", "z": "forward"},
        }
        for _ in range(count)
    ]


def _view_record(scene_name: str, split: str, index: int) -> dict[str, object]:
    prefix = f"{scene_name}/{split}"
    return {
        "index": index,
        "rgb": f"{prefix}/rgb/{index:04d}.png",
        "exr": f"{prefix}/exr/{index:04d}.exr",
        "depth": f"{prefix}/depth/{index:04d}.npy",
        "ray_distance": f"{prefix}/ray_distance/{index:04d}.npy",
        "geometric_normal": f"{prefix}/geometric_normal/{index:04d}.npy",
        "shading_normal": f"{prefix}/shading_normal/{index:04d}.npy",
        "object_id": f"{prefix}/object_id/{index:04d}.npy",
        "albedo": f"{prefix}/albedo/{index:04d}.npy",
        "validity": f"{prefix}/validity/{index:04d}.npy",
        "intrinsics": INTRINSICS.tolist(),
        "world_to_camera": EXTRINSICS.tolist(),
    }


def _surface(scene_root: Path, hidden_id: int) -> None:
    common_count = 2_048
    hidden_count = 250_000 - common_count
    points = np.concatenate(
        [
            np.tile(np.asarray([[0.0, 0.0, 2.0]], np.float32), (common_count, 1)),
            np.tile(np.asarray([[0.0, 0.0, 3.0]], np.float32), (hidden_count, 1)),
        ]
    )
    normals = np.tile(np.asarray([[0.0, 0.0, 1.0]], np.float32), (250_000, 1))
    ids = np.concatenate(
        [np.full(common_count, 1, np.int32), np.full(hidden_count, hidden_id, np.int32)]
    )
    hidden = ids == hidden_id
    context = ids == 1
    target = hidden.copy()
    np.savez_compressed(
        scene_root / "surface.npz",
        points=points,
        normals=normals,
        object_ids=ids,
        roles=hidden.astype(np.uint8),
        hidden_hypothesis=hidden,
        context_visible=context,
        target_visible=target,
        target_only_visible=target,
        new_in_target=target,
    )
    vertices = np.asarray(
        [[-0.1, -0.1, 2.0], [0.1, -0.1, 2.0], [0.0, 0.1, 2.0],
         [-0.1, -0.1, 3.0], [0.1, -0.1, 3.0], [0.0, 0.1, 3.0]],
        np.float32,
    )
    np.savez_compressed(
        scene_root / "geometry.npz",
        vertices=vertices,
        triangles=np.asarray([[0, 1, 2], [3, 4, 5]], np.int32),
        triangle_object_ids=np.asarray([1, hidden_id], np.int32),
    )


def create_valid_episode(root: Path) -> None:
    for index in range(16):
        _write_view(root / "scene_a" / "context", index, color=(80, 90, 100), depth_value=2.0, object_id=1)
    _hardlink_tree(root / "scene_a" / "context", root / "scene_b" / "context")
    for index in range(8):
        _write_view(root / "scene_a" / "target", index, color=(150, 50, 40), depth_value=3.0, object_id=101)
        _write_view(root / "scene_b" / "target", index, color=(40, 70, 160), depth_value=3.0, object_id=102)
    _surface(root / "scene_a", 101)
    _surface(root / "scene_b", 102)
    common_object = {
        "name": "common_plane",
        "semantic_class": "wall",
        "object_id": 1,
        "role": "common",
        "asset_id": "procedural",
        "material_asset_id": "white_plaster_02",
        "geometry_kind": "box",
        "transform": {},
        "asset_provenance": {},
        "relations": {"supported_by": [], "supports": [], "occludes": []},
    }
    scene_records = {}
    for scene_name, hidden_id, hidden_name in (
        ("scene_a", 101, "hidden_sofa"),
        ("scene_b", 102, "hidden_shelf"),
    ):
        objects = [
            common_object,
            {
                "name": hidden_name,
                "semantic_class": "sofa" if hidden_id == 101 else "shelf",
                "object_id": hidden_id,
                "role": "hidden",
                "asset_id": "Sofa_01" if hidden_id == 101 else "Shelf_01",
                "material_asset_id": None,
                "geometry_kind": "asset",
                "transform": {},
                "asset_provenance": {},
                "relations": {"supported_by": [], "supports": [], "occludes": []},
            },
        ]
        (root / scene_name / "objects.json").write_text(
            json.dumps(objects), encoding="utf-8"
        )
        scene_records[scene_name] = {
            "hidden_object": hidden_name,
            "objects": objects,
            "visibility": {
                "hidden_object_context_fraction": 0.0,
                "hidden_object_target_fraction": 1.0,
                "target_new_surface_fraction": 1.0,
                "target_only_surface_fraction": 1.0,
            },
        }
    context_paths = list((root / "scene_a" / "context" / "rgb").glob("*.png"))
    target_a_paths = list((root / "scene_a" / "target" / "rgb").glob("*.png"))
    target_b_paths = list((root / "scene_b" / "target" / "rgb").glob("*.png"))
    lock_sha = hashlib.sha256((ROOT / "assets.lock.json").read_bytes()).hexdigest()
    manifest = {
        "schema_version": 2,
        "schema_compatibility": [1, 2],
        "task": "paired_hidden-scene_ambiguity",
        "prototype": False,
        "seed": 20260925,
        "image_size": {"width": WIDTH, "height": HEIGHT},
        "context_views": _camera_payload(16),
        "target_views": _camera_payload(8),
        "views": {
            "shared_context": [_view_record("scene_a", "context", i) for i in range(16)],
            "scene_a_target": [_view_record("scene_a", "target", i) for i in range(8)],
            "scene_b_target": [_view_record("scene_b", "target", i) for i in range(8)],
        },
        "paired_context": {
            "pixel_mismatches": 0,
            "sha256_a": _hash_files(context_paths),
            "sha256_b": _hash_files(list((root / "scene_b" / "context" / "rgb").glob("*.png"))),
            "storage": "rendered_once_then_hard_linked",
        },
        "paired_targets": {
            "sha256_a": _hash_files(target_a_paths),
            "sha256_b": _hash_files(target_b_paths),
        },
        "camera_checks": {"max_center_error": 0.0},
        "scenes": scene_records,
        "annotation_contract": {
            "coordinate_system": "opencv_world_to_camera",
            "surface_samples_per_scene": 250_000,
            "minimum_samples_per_object": 2_048,
            "per_view": {
                "srgb_png": "rgb/{index:04d}.png",
                "linear_multilayer_openexr": "exr/{index:04d}.exr",
                "camera_axis_depth": "depth/{index:04d}.npy",
                "ray_distance": "ray_distance/{index:04d}.npy",
                "world_geometric_normal": "geometric_normal/{index:04d}.npy",
                "world_shading_normal": "shading_normal/{index:04d}.npy",
                "object_id": "object_id/{index:04d}.npy",
                "diffuse_albedo": "albedo/{index:04d}.npy",
                "validity_mask": "validity/{index:04d}.npy",
            },
        },
        "renderer": {
            "blender_version": "4.5.14 LTS",
            "cycles_version": "4.5.14",
            "device": "CPU",
            "gpu": ["CPU"],
            "profile": "draft",
            "resolution": [WIDTH, HEIGHT],
            "samples": 32,
            "random_seeds": {"episode": 20260925, "cycles": 20260925, "surface_sampling": 20260926},
            "color_transform": "AgX",
            "beauty_denoiser": "OpenImageDenoise",
            "denoised_passes": ["beauty"],
            "asset_lock_sha256": lock_sha,
            "runtime_seconds": 1.0,
            "peak_memory_bytes": 1,
        },
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    np.savez_compressed(
        root / "cameras.npz",
        context_intrinsics=np.stack([INTRINSICS] * 16).astype(np.float32),
        context_extrinsics=np.stack([EXTRINSICS] * 16).astype(np.float32),
        target_intrinsics=np.stack([INTRINSICS] * 8).astype(np.float32),
        target_extrinsics=np.stack([EXTRINSICS] * 8).astype(np.float32),
    )


def _replace_npy(path: Path, value: np.ndarray) -> None:
    path.unlink()
    np.save(path, value)


class EpisodeValidatorTest(unittest.TestCase):
    def _episode(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / "episode"
        root.mkdir()
        create_valid_episode(root)
        return temporary, root

    def test_valid_full_contract_fixture_passes(self) -> None:
        temporary, root = self._episode()
        try:
            report = validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
        finally:
            temporary.cleanup()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["counts"]["context_views"], 16)
        self.assertEqual(report["counts"]["target_views_per_scene"], 8)
        self.assertEqual(report["counts"]["surface_points_per_scene"], 250_000)
        self.assertGreater(len(report["artifact_sha256"]), 100)

    def test_rejects_context_cue_leak_or_non_hardlinked_context(self) -> None:
        temporary, root = self._episode()
        try:
            path = root / "scene_b" / "context" / "rgb" / "0000.png"
            path.unlink()
            Image.new("RGB", (WIDTH, HEIGHT), (1, 2, 3)).save(path)
            with self.assertRaisesRegex(ValidationError, "context RGB"):
                validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
        finally:
            temporary.cleanup()

    def test_rejects_hidden_id_in_context(self) -> None:
        temporary, root = self._episode()
        try:
            path = root / "scene_a" / "context" / "object_id" / "0000.npy"
            values = np.load(path).copy()
            values[0, 0] = 101
            _replace_npy(path, values)
            with self.assertRaisesRegex(ValidationError, "hidden object ID"):
                validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
        finally:
            temporary.cleanup()

    def test_rejects_object_id_not_present_in_scene_table(self) -> None:
        temporary, root = self._episode()
        try:
            path = root / "scene_a" / "context" / "object_id" / "0000.npy"
            ids = np.load(path)
            ids[0, 0] = 19
            _replace_npy(path, ids)
            validity_path = root / "scene_a" / "context" / "validity" / "0000.npy"
            _replace_npy(validity_path, np.ones((HEIGHT, WIDTH), bool))
            with self.assertRaisesRegex(ValidationError, "outside the object table"):
                validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
        finally:
            temporary.cleanup()

    def test_rejects_malformed_exr_missing_required_channels(self) -> None:
        temporary, root = self._episode()
        try:
            path = root / "scene_a" / "target" / "exr" / "0000.exr"
            path.write_bytes(b"\x76\x2f\x31\x01not-an-exr")
            with self.assertRaisesRegex(ValidationError, "OpenEXR"):
                validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
        finally:
            temporary.cleanup()

    def test_rejects_incomplete_renderer_or_mismatched_view_record(self) -> None:
        for mutation, message in (("renderer", "blender_version"), ("view", "view record")):
            with self.subTest(mutation=mutation):
                temporary, root = self._episode()
                try:
                    manifest_path = root / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if mutation == "renderer":
                        del manifest["renderer"]["blender_version"]
                    else:
                        manifest["views"]["scene_a_target"][0]["rgb"] = "wrong.png"
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    with self.assertRaisesRegex(ValidationError, message):
                        validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
                finally:
                    temporary.cleanup()

    def test_rejects_identical_target_rgb(self) -> None:
        temporary, root = self._episode()
        try:
            for index in range(8):
                destination = root / "scene_b" / "target" / "rgb" / f"{index:04d}.png"
                destination.write_bytes(
                    (root / "scene_a" / "target" / "rgb" / f"{index:04d}.png").read_bytes()
                )
            with self.assertRaisesRegex(ValidationError, "target RGB"):
                validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
        finally:
            temporary.cleanup()

    def test_rejects_nan_and_depth_ray_inconsistency(self) -> None:
        temporary, root = self._episode()
        try:
            path = root / "scene_a" / "target" / "depth" / "0000.npy"
            values = np.load(path).copy()
            values[0, 0] = np.nan
            _replace_npy(path, values)
            with self.assertRaisesRegex(ValidationError, "finite"):
                validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
        finally:
            temporary.cleanup()

        temporary, root = self._episode()
        try:
            path = root / "scene_a" / "target" / "ray_distance" / "0000.npy"
            values = np.load(path).copy()
            values[10, 10] += 1.0
            _replace_npy(path, values)
            with self.assertRaisesRegex(ValidationError, "ray distance"):
                validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
        finally:
            temporary.cleanup()

    def test_rejects_hidden_target_visibility_below_threshold(self) -> None:
        temporary, root = self._episode()
        try:
            path = root / "scene_a" / "surface.npz"
            with np.load(path) as source:
                payload = {key: source[key] for key in source.files}
            payload["target_visible"] = np.zeros(250_000, bool)
            payload["target_only_visible"] = np.zeros(250_000, bool)
            payload["new_in_target"] = np.zeros(250_000, bool)
            np.savez_compressed(path, **payload)
            with self.assertRaisesRegex(ValidationError, "hidden target visibility"):
                validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
        finally:
            temporary.cleanup()

    def test_rejects_cpu_benchmark_metadata(self) -> None:
        temporary, root = self._episode()
        try:
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["renderer"].update(
                {"profile": "benchmark", "resolution": [512, 384], "samples": 256}
            )
            manifest["image_size"] = {"width": 512, "height": 384}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "OptiX"):
                validate_episode(root, asset_lock_path=ROOT / "assets.lock.json")
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
