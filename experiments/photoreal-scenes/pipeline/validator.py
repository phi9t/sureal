#!/usr/bin/env python3
"""Strict validator for schema-v2 photoreal paired-scene episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np
import OpenImageIO as oiio
from PIL import Image

from contracts import PROFILES, validate_device
from geometry import camera_center, visibility_from_views


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
REQUIRED_EXR_CHANNELS = {
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
}


class ValidationError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_files(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _view_paths(root: Path, count: int) -> dict[str, list[Path]]:
    result = {}
    extensions = {"rgb": "png", "exr": "exr"}
    for layer in LAYERS:
        extension = extensions.get(layer, "npy")
        directory = root / layer
        paths = [directory / f"{index:04d}.{extension}" for index in range(count)]
        extras = sorted(directory.glob(f"*.{extension}")) if directory.is_dir() else []
        _require(
            all(path.is_file() for path in paths) and len(extras) == count,
            f"wrong frame count or missing {layer} files under {root}",
        )
        result[layer] = paths
    return result


def _validate_exr(path: Path, *, width: int, height: int, label: str) -> None:
    source = oiio.ImageInput.open(str(path))
    _require(source is not None, f"{label} is not a decodable OpenEXR file")
    try:
        specification = source.spec()
        _require(
            (specification.width, specification.height) == (width, height),
            f"{label} OpenEXR has wrong dimensions",
        )
        _require(
            REQUIRED_EXR_CHANNELS.issubset(set(specification.channelnames)),
            f"{label} OpenEXR is missing required layers/channels",
        )
        _require(
            specification.get_string_attribute("oiio:ColorSpace", "") == "Linear",
            f"{label} OpenEXR must be linear",
        )
        _require(
            source.read_image(oiio.FLOAT) is not None,
            f"{label} OpenEXR pixel data cannot be decoded",
        )
    finally:
        source.close()


def _validate_view_records(
    manifest: dict[str, Any],
    *,
    context_intrinsics: Sequence[np.ndarray],
    context_extrinsics: Sequence[np.ndarray],
    target_intrinsics: Sequence[np.ndarray],
    target_extrinsics: Sequence[np.ndarray],
) -> None:
    views = manifest.get("views")
    _require(isinstance(views, dict), "manifest views must be an object")
    definitions = (
        ("shared_context", "scene_a/context", context_intrinsics, context_extrinsics),
        ("scene_a_target", "scene_a/target", target_intrinsics, target_extrinsics),
        ("scene_b_target", "scene_b/target", target_intrinsics, target_extrinsics),
    )
    expected_path_fields = {
        "rgb": "rgb/{index:04d}.png",
        "exr": "exr/{index:04d}.exr",
        "depth": "depth/{index:04d}.npy",
        "ray_distance": "ray_distance/{index:04d}.npy",
        "geometric_normal": "geometric_normal/{index:04d}.npy",
        "shading_normal": "shading_normal/{index:04d}.npy",
        "object_id": "object_id/{index:04d}.npy",
        "albedo": "albedo/{index:04d}.npy",
        "validity": "validity/{index:04d}.npy",
    }
    _require(set(views) == {item[0] for item in definitions}, "manifest view groups are wrong")
    for group, prefix, intrinsics, extrinsics in definitions:
        records = views[group]
        _require(
            isinstance(records, list) and len(records) == len(intrinsics),
            f"{group} view record count is wrong",
        )
        for index, record in enumerate(records):
            _require(
                isinstance(record, dict) and record.get("index") == index,
                f"{group} view record {index} has a wrong index",
            )
            for field, template in expected_path_fields.items():
                expected = f"{prefix}/{template.format(index=index)}"
                _require(
                    record.get(field) == expected,
                    f"{group} view record {index} {field} path is wrong",
                )
            try:
                record_intrinsics = np.asarray(record.get("intrinsics"), dtype=np.float64)
                record_extrinsics = np.asarray(record.get("world_to_camera"), dtype=np.float64)
            except (TypeError, ValueError) as error:
                raise ValidationError(f"{group} view record {index} camera is wrong") from error
            _require(
                record_intrinsics.shape == (3, 3)
                and record_extrinsics.shape == (3, 4)
                and np.allclose(record_intrinsics, intrinsics[index], atol=1e-9)
                and np.allclose(record_extrinsics, extrinsics[index], atol=1e-9),
                f"{group} view record {index} camera is wrong",
            )


def _validate_camera_payload(
    cameras: Sequence[dict[str, Any]], *, expected_count: int, label: str
) -> tuple[list[np.ndarray], list[np.ndarray], float]:
    _require(len(cameras) == expected_count, f"{label} must contain {expected_count} cameras")
    intrinsics_list = []
    extrinsics_list = []
    maximum_error = 0.0
    for index, camera in enumerate(cameras):
        intrinsics = np.asarray(camera.get("intrinsics"), dtype=np.float64)
        extrinsics = np.asarray(camera.get("world_to_camera"), dtype=np.float64)
        eye = np.asarray(camera.get("eye"), dtype=np.float64)
        _require(intrinsics.shape == (3, 3), f"{label} camera {index} intrinsics are not 3x3")
        _require(extrinsics.shape == (3, 4), f"{label} camera {index} extrinsics are not 3x4")
        _require(eye.shape == (3,), f"{label} camera {index} eye is not length 3")
        _require(
            np.all(np.isfinite(intrinsics)) and np.all(np.isfinite(extrinsics)),
            f"{label} camera {index} contains non-finite values",
        )
        rotation = extrinsics[:, :3]
        _require(
            np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-7)
            and abs(float(np.linalg.det(rotation)) - 1.0) < 1e-7,
            f"{label} camera {index} rotation is not orthonormal",
        )
        recovered = camera_center(extrinsics)
        error = float(np.linalg.norm(recovered - eye))
        maximum_error = max(maximum_error, error)
        _require(error < 1e-6, f"{label} camera {index} center recovery exceeds 1e-6 m")
        _require(
            intrinsics[0, 0] > 0.0 and intrinsics[1, 1] > 0.0 and intrinsics[2, 2] == 1.0,
            f"{label} camera {index} has invalid pinhole intrinsics",
        )
        intrinsics_list.append(intrinsics)
        extrinsics_list.append(extrinsics)
    return intrinsics_list, extrinsics_list, maximum_error


def _validate_view(
    paths: dict[str, list[Path]],
    index: int,
    *,
    width: int,
    height: int,
    intrinsics: np.ndarray,
    label: str,
    allowed_object_ids: set[int],
) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(paths["rgb"][index]) as image:
        _require(image.mode == "RGB", f"{label} RGB {index} is not three-channel sRGB")
        _require(image.size == (width, height), f"{label} RGB {index} has wrong shape")
        image.verify()
    _validate_exr(
        paths["exr"][index],
        width=width,
        height=height,
        label=f"{label} EXR {index}",
    )
    arrays = {layer: np.load(paths[layer][index]) for layer in LAYERS if layer not in {"rgb", "exr"}}
    for layer in ("depth", "ray_distance", "object_id", "validity"):
        _require(arrays[layer].shape == (height, width), f"{label} {layer} {index} has wrong shape")
    for layer in ("geometric_normal", "shading_normal", "albedo"):
        _require(arrays[layer].shape == (height, width, 3), f"{label} {layer} {index} has wrong shape")
    for layer, array in arrays.items():
        _require(np.all(np.isfinite(array)), f"{label} {layer} {index} must be finite")
    depth = arrays["depth"].astype(np.float64)
    ray_distance = arrays["ray_distance"].astype(np.float64)
    object_ids = arrays["object_id"]
    validity = arrays["validity"]
    _require(validity.dtype == np.bool_, f"{label} validity {index} must be boolean")
    _require(np.issubdtype(object_ids.dtype, np.integer), f"{label} object IDs {index} must be integers")
    _require(np.all(depth >= 0.0) and np.all(ray_distance >= 0.0), f"{label} depths {index} must be non-negative")
    _require(np.all(object_ids >= 0), f"{label} object IDs {index} must be non-negative")
    _require(
        set(map(int, np.unique(object_ids))).issubset({0, *allowed_object_ids}),
        f"{label} object IDs {index} contain values outside the object table",
    )
    _require(
        np.array_equal(validity, (depth > 0.0) & (object_ids > 0)),
        f"{label} validity {index} disagrees with depth/object ID",
    )
    xs, ys = np.meshgrid(np.arange(width), np.arange(height))
    expected_ray = depth * np.sqrt(
        1.0
        + ((xs - intrinsics[0, 2]) / intrinsics[0, 0]) ** 2
        + ((ys - intrinsics[1, 2]) / intrinsics[1, 1]) ** 2
    )
    _require(
        # Shader AOVs are integrated over subpixel Cycles samples while this
        # check uses the nominal pixel center.  Allow the resulting sub-mm
        # edge-of-frame discrepancy without masking metric-scale failures.
        np.allclose(ray_distance[validity], expected_ray[validity], rtol=3e-4, atol=3e-4),
        f"{label} camera-axis depth and ray distance {index} are inconsistent",
    )
    for layer in ("geometric_normal", "shading_normal"):
        lengths = np.linalg.norm(arrays[layer][validity], axis=1)
        _require(
            np.allclose(lengths, 1.0, rtol=2e-3, atol=2e-3),
            f"{label} {layer} {index} contains non-unit valid normals",
        )
    albedo = arrays["albedo"]
    _require(
        np.all((albedo[validity] >= 0.0) & (albedo[validity] <= 1.0)),
        f"{label} albedo {index} lies outside [0, 1]",
    )
    return depth.astype(np.float32), object_ids.astype(np.int32)


def _validate_geometry(scene_root: Path, valid_object_ids: set[int]) -> None:
    path = scene_root / "geometry.npz"
    _require(path.is_file(), f"evaluated geometry is missing: {path}")
    with np.load(path) as geometry:
        _require(
            {"vertices", "triangles", "triangle_object_ids"}.issubset(geometry.files),
            f"evaluated geometry fields are incomplete: {path}",
        )
        vertices = geometry["vertices"]
        triangles = geometry["triangles"]
        triangle_ids = geometry["triangle_object_ids"]
    _require(vertices.ndim == 2 and vertices.shape[1] == 3, f"geometry vertices have wrong shape: {path}")
    _require(triangles.ndim == 2 and triangles.shape[1] == 3, f"geometry is not triangulated: {path}")
    _require(len(triangles) == len(triangle_ids), f"geometry triangle IDs have wrong length: {path}")
    _require(np.all(np.isfinite(vertices)), f"geometry contains non-finite vertices: {path}")
    _require(
        np.issubdtype(triangles.dtype, np.integer)
        and triangles.min(initial=0) >= 0
        and triangles.max(initial=-1) < len(vertices),
        f"geometry triangle indices are invalid: {path}",
    )
    _require(set(map(int, np.unique(triangle_ids))) == valid_object_ids, f"geometry/object table IDs disagree: {path}")


def _validate_surface(
    root: Path,
    scene_name: str,
    scene_record: dict[str, Any],
    *,
    expected_count: int,
    minimum: int,
    context_views: Sequence[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    target_views: Sequence[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
) -> dict[str, float]:
    scene_root = root / scene_name
    surface_path = scene_root / "surface.npz"
    _require(surface_path.is_file(), f"surface sample is missing: {surface_path}")
    required = {
        "points", "normals", "object_ids", "roles", "hidden_hypothesis",
        "context_visible", "target_visible", "target_only_visible", "new_in_target",
    }
    with np.load(surface_path) as source:
        _require(required.issubset(source.files), f"surface fields are incomplete: {surface_path}")
        surface = {name: source[name] for name in required}
    points = surface["points"]
    normals = surface["normals"]
    ids = surface["object_ids"]
    hidden = surface["hidden_hypothesis"].astype(bool)
    context_visible = surface["context_visible"].astype(bool)
    target_visible = surface["target_visible"].astype(bool)
    target_only = surface["target_only_visible"].astype(bool)
    _require(points.shape == (expected_count, 3), f"{scene_name} surface must have {expected_count} points")
    _require(normals.shape == points.shape, f"{scene_name} surface normals have wrong shape")
    for name, values in surface.items():
        _require(len(values) == expected_count, f"{scene_name} surface {name} has wrong length")
    _require(np.all(np.isfinite(points)) and np.all(np.isfinite(normals)), f"{scene_name} surface must be finite")
    _require(np.allclose(np.linalg.norm(normals, axis=1), 1.0, rtol=2e-3, atol=2e-3), f"{scene_name} surface normals must be unit length")
    objects = scene_record.get("objects")
    _require(isinstance(objects, list) and objects, f"{scene_name} object table is missing")
    required_object_fields = {
        "name", "semantic_class", "object_id", "role", "asset_id",
        "material_asset_id", "geometry_kind", "transform", "asset_provenance", "relations",
    }
    _require(
        all(isinstance(item, dict) and required_object_fields.issubset(item) for item in objects),
        f"{scene_name} object table records are incomplete",
    )
    table_by_id = {int(item["object_id"]): item for item in objects}
    valid_ids = set(table_by_id)
    _require(len(table_by_id) == len(objects), f"{scene_name} object IDs are not unique")
    object_names = {str(item["name"]) for item in objects}
    _require(len(object_names) == len(objects), f"{scene_name} object names are not unique")
    for item in objects:
        relations = item["relations"]
        _require(
            isinstance(relations, dict)
            and set(relations) == {"supported_by", "supports", "occludes"}
            and all(isinstance(value, list) for value in relations.values()),
            f"{scene_name} {item['name']} relations are malformed",
        )
        for relation, targets in relations.items():
            _require(
                set(map(str, targets)).issubset(object_names),
                f"{scene_name} {item['name']} {relation} has a dangling reference",
            )
    by_name = {str(item["name"]): item for item in objects}
    for item in objects:
        for parent in item["relations"]["supported_by"]:
            _require(
                item["name"] in by_name[str(parent)]["relations"]["supports"],
                f"{scene_name} support relation is not reciprocal",
            )
    _require(set(map(int, np.unique(ids))) == valid_ids, f"{scene_name} surface/object table IDs disagree")
    for object_id in valid_ids:
        _require(int((ids == object_id).sum()) >= minimum, f"{scene_name} object {object_id} has fewer than {minimum} samples")
    expected_hidden = np.asarray([table_by_id[int(value)]["role"] == "hidden" for value in ids])
    _require(np.array_equal(hidden, expected_hidden), f"{scene_name} surface roles disagree with object table")
    _require(np.array_equal(surface["roles"].astype(bool), hidden), f"{scene_name} encoded roles disagree")
    _require(np.array_equal(surface["new_in_target"].astype(bool), target_only), f"{scene_name} v1 new_in_target alias disagrees")
    _require(np.array_equal(target_only, target_visible & ~context_visible), f"{scene_name} target-only mask is inconsistent")
    hidden_count = max(int(hidden.sum()), 1)
    target_count = max(int(target_visible.sum()), 1)
    metrics = {
        "hidden_object_context_fraction": float((hidden & context_visible).sum() / hidden_count),
        "hidden_object_target_fraction": float((hidden & target_visible).sum() / hidden_count),
        "target_new_surface_fraction": float(target_only.sum() / target_count),
        "target_only_surface_fraction": float((hidden & target_only).sum() / hidden_count),
    }
    _require(metrics["hidden_object_context_fraction"] == 0.0, f"{scene_name} hidden context visibility is nonzero")
    _require(metrics["hidden_object_target_fraction"] > 0.25, f"{scene_name} hidden target visibility must exceed 0.25")
    _require(metrics["target_only_surface_fraction"] > 0.25, f"{scene_name} hidden target-only fraction must exceed 0.25")
    recorded = scene_record.get("visibility", {})
    for name, value in metrics.items():
        _require(abs(float(recorded.get(name, -1.0)) - value) < 1e-8, f"{scene_name} recorded {name} is wrong")

    scene_scale = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))
    computed_context = visibility_from_views(points, ids, context_views, scene_scale=scene_scale)
    computed_target = visibility_from_views(points, ids, target_views, scene_scale=scene_scale)
    _require(np.array_equal(computed_context, context_visible), f"{scene_name} context reprojection disagrees with rendered pixels")
    _require(np.array_equal(computed_target, target_visible), f"{scene_name} target reprojection disagrees with rendered pixels")
    _validate_geometry(scene_root, valid_ids)
    object_path = scene_root / "objects.json"
    _require(object_path.is_file(), f"{scene_name} objects.json is missing")
    _require(json.loads(object_path.read_text()) == objects, f"{scene_name} objects.json disagrees with manifest")
    return metrics


def validate_episode(root: Path, *, asset_lock_path: Path | None = None) -> dict[str, object]:
    root = Path(root)
    manifest_path = root / "manifest.json"
    _require(manifest_path.is_file(), f"manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require(manifest.get("schema_version") == 2, "episode manifest must use schema version 2")
    _require(manifest.get("schema_compatibility") == [1, 2], "schema compatibility must be [1, 2]")
    _require(manifest.get("task") == "paired_hidden-scene_ambiguity", "unexpected episode task")

    renderer = manifest.get("renderer", {})
    profile = renderer.get("profile")
    _require(profile in PROFILES, f"unknown render profile: {profile}")
    try:
        device = validate_device(str(profile), str(renderer.get("device")))
    except ValueError as error:
        raise ValidationError(str(error)) from error
    settings = PROFILES[str(profile)]
    expected_resolution = [int(settings["width"]), int(settings["height"])]
    _require(renderer.get("resolution") == expected_resolution, "renderer resolution disagrees with profile")
    _require(renderer.get("samples") == settings["samples"], "renderer samples disagree with profile")
    _require(
        isinstance(renderer.get("blender_version"), str)
        and str(renderer["blender_version"]).startswith("4.5.14"),
        "renderer blender_version must record Blender 4.5.14",
    )
    _require(
        isinstance(renderer.get("cycles_version"), str)
        and str(renderer["cycles_version"]).startswith("4.5.14"),
        "renderer cycles_version must record Cycles 4.5.14",
    )
    gpu = renderer.get("gpu")
    _require(
        isinstance(gpu, list) and gpu and all(isinstance(name, str) and name for name in gpu),
        "renderer GPU/device list is missing",
    )
    if profile == "benchmark":
        _require(any("NVIDIA" in name for name in gpu), "benchmark renderer must record an NVIDIA GPU")
    _require(renderer.get("color_transform") == "AgX", "renderer color transform must be AgX")
    _require(renderer.get("denoised_passes") == ["beauty"], "only beauty may be denoised")
    expected_denoiser = "OptiX" if device == "OPTIX" else "OpenImageDenoise"
    _require(renderer.get("beauty_denoiser") == expected_denoiser, "renderer beauty denoiser is wrong")
    seed = manifest.get("seed")
    _require(isinstance(seed, int), "episode seed is missing")
    _require(
        renderer.get("random_seeds")
        == {"episode": seed, "cycles": seed, "surface_sampling": seed + 1},
        "renderer random seeds are wrong",
    )
    _require(float(renderer.get("runtime_seconds", 0.0)) > 0.0, "renderer runtime is missing")
    _require(int(renderer.get("peak_memory_bytes", 0)) > 0, "renderer peak memory is missing")
    width, height = expected_resolution
    _require(manifest.get("image_size") == {"width": width, "height": height}, "manifest image size disagrees with profile")
    if asset_lock_path is not None:
        asset_lock_path = Path(asset_lock_path)
        _require(asset_lock_path.is_file(), "asset lock is missing")
        _require(renderer.get("asset_lock_sha256") == _sha256(asset_lock_path), "asset-lock hash mismatch")

    context_intrinsics, context_extrinsics, context_center_error = _validate_camera_payload(
        manifest.get("context_views", []), expected_count=16, label="context"
    )
    target_intrinsics, target_extrinsics, target_center_error = _validate_camera_payload(
        manifest.get("target_views", []), expected_count=8, label="target"
    )
    maximum_center_error = max(context_center_error, target_center_error)
    _require(maximum_center_error < 1e-6, "camera center recovery exceeds 1e-6 m")
    _require(
        abs(float(manifest.get("camera_checks", {}).get("max_center_error", -1.0)) - maximum_center_error) < 1e-8,
        "recorded camera center error is wrong",
    )
    _validate_view_records(
        manifest,
        context_intrinsics=context_intrinsics,
        context_extrinsics=context_extrinsics,
        target_intrinsics=target_intrinsics,
        target_extrinsics=target_extrinsics,
    )

    scene_paths = {}
    for scene_name in ("scene_a", "scene_b"):
        scene_paths[scene_name] = {
            "context": _view_paths(root / scene_name / "context", 16),
            "target": _view_paths(root / scene_name / "target", 8),
        }
    for index in range(16):
        a = scene_paths["scene_a"]["context"]["rgb"][index]
        b = scene_paths["scene_b"]["context"]["rgb"][index]
        _require(a.read_bytes() == b.read_bytes(), f"context RGB {index} is not byte-identical")
        _require(os.path.samefile(a, b), f"context RGB {index} is not hard-linked")
    target_a_rgb = scene_paths["scene_a"]["target"]["rgb"]
    target_b_rgb = scene_paths["scene_b"]["target"]["rgb"]
    _require(
        any(a.read_bytes() != b.read_bytes() for a, b in zip(target_a_rgb, target_b_rgb, strict=True)),
        "target RGB is identical between hypotheses",
    )

    scene_records = manifest.get("scenes", {})
    _require(set(scene_records) == {"scene_a", "scene_b"}, "manifest must contain exactly two scenes")
    hidden_ids = {
        int(item["object_id"])
        for record in scene_records.values()
        for item in record.get("objects", [])
        if item.get("role") == "hidden"
    }
    scene_ids = {
        scene_name: {int(item["object_id"]) for item in record.get("objects", [])}
        for scene_name, record in scene_records.items()
    }
    common_ids = {
        scene_name: {
            int(item["object_id"])
            for item in record.get("objects", [])
            if item.get("role") == "common"
        }
        for scene_name, record in scene_records.items()
    }
    for scene_name in ("scene_a", "scene_b"):
        for index, path in enumerate(scene_paths[scene_name]["context"]["object_id"]):
            ids = np.load(path)
            _require(not np.isin(ids, list(hidden_ids)).any(), f"hidden object ID appears in context {scene_name}/{index}")

    context_buffers: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
    target_buffers: dict[str, list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]] = {
        "scene_a": [], "scene_b": []
    }
    for scene_name in ("scene_a", "scene_b"):
        for split, count, intrinsics_list, extrinsics_list in (
            ("context", 16, context_intrinsics, context_extrinsics),
            ("target", 8, target_intrinsics, target_extrinsics),
        ):
            for index in range(count):
                depth, ids = _validate_view(
                    scene_paths[scene_name][split],
                    index,
                    width=width,
                    height=height,
                    intrinsics=intrinsics_list[index],
                    label=f"{scene_name}/{split}",
                    allowed_object_ids=(
                        common_ids[scene_name] if split == "context" else scene_ids[scene_name]
                    ),
                )
                if scene_name == "scene_a" and split == "context":
                    context_buffers.append((intrinsics_list[index], extrinsics_list[index], depth, ids))
                elif split == "target":
                    target_buffers[scene_name].append((intrinsics_list[index], extrinsics_list[index], depth, ids))

    for layer in LAYERS:
        for a, b in zip(
            scene_paths["scene_a"]["context"][layer],
            scene_paths["scene_b"]["context"][layer],
            strict=True,
        ):
            _require(os.path.samefile(a, b), f"shared context {layer} is not hard-linked")

    paired_context = manifest.get("paired_context", {})
    context_hash_a = _hash_files(scene_paths["scene_a"]["context"]["rgb"])
    context_hash_b = _hash_files(scene_paths["scene_b"]["context"]["rgb"])
    _require(context_hash_a == context_hash_b, "context RGB hashes differ")
    _require(paired_context.get("pixel_mismatches") == 0, "paired context mismatch count is nonzero")
    _require(paired_context.get("sha256_a") == context_hash_a and paired_context.get("sha256_b") == context_hash_b, "recorded context RGB hash is wrong")
    target_hash_a = _hash_files(target_a_rgb)
    target_hash_b = _hash_files(target_b_rgb)
    _require(target_hash_a != target_hash_b, "target RGB hashes must differ")
    _require(
        manifest.get("paired_targets") == {"sha256_a": target_hash_a, "sha256_b": target_hash_b},
        "recorded target RGB hash is wrong",
    )

    camera_path = root / "cameras.npz"
    _require(camera_path.is_file(), "cameras.npz compatibility file is missing")
    with np.load(camera_path) as cameras:
        expected_camera_arrays = {
            "context_intrinsics": np.stack(context_intrinsics),
            "context_extrinsics": np.stack(context_extrinsics),
            "target_intrinsics": np.stack(target_intrinsics),
            "target_extrinsics": np.stack(target_extrinsics),
        }
        for name, expected in expected_camera_arrays.items():
            _require(name in cameras.files and np.allclose(cameras[name], expected, atol=1e-6), f"cameras.npz {name} disagrees with manifest")

    annotation = manifest.get("annotation_contract", {})
    _require(
        set(annotation.get("per_view", {}))
        == {
            "srgb_png", "linear_multilayer_openexr", "camera_axis_depth", "ray_distance",
            "world_geometric_normal", "world_shading_normal", "object_id", "diffuse_albedo",
            "validity_mask",
        },
        "per-view annotation contract is incomplete",
    )
    expected_surface_count = int(annotation.get("surface_samples_per_scene", 0))
    minimum = int(annotation.get("minimum_samples_per_object", 0))
    _require(expected_surface_count == 250_000, "surface contract must require 250,000 points")
    _require(minimum == 2_048, "surface contract must require 2,048 samples per object")
    visibility = {
        scene_name: _validate_surface(
            root,
            scene_name,
            scene_records[scene_name],
            expected_count=expected_surface_count,
            minimum=minimum,
            context_views=context_buffers,
            target_views=target_buffers[scene_name],
        )
        for scene_name in ("scene_a", "scene_b")
    }

    artifacts = {
        str(path.relative_to(root)): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "validation.json"
    }
    return {
        "schema_version": 1,
        "status": "pass",
        "episode_manifest_sha256": _sha256(manifest_path),
        "counts": {
            "context_views": 16,
            "target_views_per_scene": 8,
            "surface_points_per_scene": expected_surface_count,
        },
        "camera_max_center_error_metres": maximum_center_error,
        "visibility": visibility,
        "artifact_sha256": artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--asset-lock", type=Path)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    try:
        report = validate_episode(args.episode, asset_lock_path=args.asset_lock)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    if args.write_report:
        (args.episode / "validation.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
