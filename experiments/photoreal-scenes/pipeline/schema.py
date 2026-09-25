#!/usr/bin/env python3
"""Episode manifest schema v2 with compatibility fields for the v1 probe."""

from __future__ import annotations

from typing import Any, Sequence

from contracts import PROFILES, validate_device
from geometry import camera_center


PER_VIEW_ANNOTATIONS = {
    "srgb_png": "rgb/{index:04d}.png",
    "linear_multilayer_openexr": "exr/{index:04d}.exr",
    "camera_axis_depth": "depth/{index:04d}.npy",
    "ray_distance": "ray_distance/{index:04d}.npy",
    "world_geometric_normal": "geometric_normal/{index:04d}.npy",
    "world_shading_normal": "shading_normal/{index:04d}.npy",
    "object_id": "object_id/{index:04d}.npy",
    "diffuse_albedo": "albedo/{index:04d}.npy",
    "validity_mask": "validity/{index:04d}.npy",
}


def camera_payload(camera: Any) -> dict[str, object]:
    intrinsics, extrinsics = camera.matrices()
    return {
        "eye": list(camera.eye),
        "target": list(camera.target),
        "intrinsics": intrinsics.tolist(),
        "world_to_camera": extrinsics.tolist(),
        "opencv_axes": {"x": "right", "y": "down", "z": "forward"},
    }


def _scene_record(scene_name: str) -> dict[str, object]:
    from scene import object_specs, object_table

    objects = object_specs(scene_name)
    hidden = [item for item in objects if item.role == "hidden"]
    return {
        "hidden_object": hidden[0].name,
        "objects": object_table(scene_name),
        "visibility": {
            "hidden_object_context_fraction": None,
            "hidden_object_target_fraction": None,
            "target_new_surface_fraction": None,
            "target_only_surface_fraction": None,
        },
    }


def build_manifest_skeleton(
    *,
    profile: str,
    device: str,
    seed: int,
    asset_lock_sha256: str,
    context_cameras: Sequence[Any],
    target_cameras: Sequence[Any],
) -> dict[str, object]:
    if profile not in PROFILES:
        raise ValueError(f"unknown render profile: {profile}")
    device = validate_device(profile, device)
    settings = PROFILES[profile]
    context_payload = [camera_payload(camera) for camera in context_cameras]
    target_payload = [camera_payload(camera) for camera in target_cameras]
    center_errors = []
    for camera, payload in zip(
        [*context_cameras, *target_cameras],
        [*context_payload, *target_payload],
        strict=True,
    ):
        recovered = camera_center(payload["world_to_camera"])
        center_errors.append(
            float(sum((float(a) - float(b)) ** 2 for a, b in zip(recovered, camera.eye)) ** 0.5)
        )
    return {
        "schema_version": 2,
        "schema_compatibility": [1, 2],
        "task": "paired_hidden-scene_ambiguity",
        "prototype": False,
        "seed": int(seed),
        "image_size": {
            "width": int(settings["width"]),
            "height": int(settings["height"]),
        },
        "context_views": context_payload,
        "target_views": target_payload,
        "views": {"shared_context": [], "scene_a_target": [], "scene_b_target": []},
        "paired_context": {
            "pixel_mismatches": None,
            "sha256_a": None,
            "sha256_b": None,
            "storage": "rendered_once_then_hard_linked",
        },
        "paired_targets": {"sha256_a": None, "sha256_b": None},
        "camera_checks": {"max_center_error": max(center_errors, default=0.0)},
        "scenes": {
            "scene_a": _scene_record("scene_a"),
            "scene_b": _scene_record("scene_b"),
        },
        "annotation_contract": {
            "coordinate_system": "opencv_world_to_camera",
            "world_units": "metres",
            "depth": "positive camera-axis z to first opaque surface",
            "ray_distance": "Euclidean camera-to-first-surface distance",
            "normals": "world-space unit vectors",
            "object_ids": "stable positive integers; 0 is invalid/background",
            "surface_samples_per_scene": 250_000,
            "minimum_samples_per_object": 2_048,
            "visibility": "projection against rendered camera depth and object-ID buffers",
            "per_view": dict(PER_VIEW_ANNOTATIONS),
        },
        "renderer": {
            "blender_version": None,
            "cycles_version": None,
            "device": device,
            "gpu": None,
            "profile": profile,
            "resolution": [int(settings["width"]), int(settings["height"])],
            "samples": int(settings["samples"]),
            "random_seeds": {
                "episode": int(seed),
                "cycles": int(seed),
                "surface_sampling": int(seed) + 1,
            },
            "color_transform": "AgX",
            "beauty_denoiser": "OptiX" if device == "OPTIX" else "OpenImageDenoise",
            "denoised_passes": ["beauty"],
            "asset_lock_sha256": asset_lock_sha256,
            "runtime_seconds": None,
            "peak_memory_bytes": None,
        },
    }
