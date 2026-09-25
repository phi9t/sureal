#!/usr/bin/env python3
"""PROTOTYPE: generate a paired hidden-scene ambiguity episode.

The two scenes are constructed so every context render is bit-identical while
the target cameras reveal different hidden objects.  The analytic box renderer
also emits exact depth, normal, object-ID, camera, surface, and visibility data.
It is intentionally small: this probe tests the learning problem before a
production synthetic-data pipeline is chosen.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Box:
    name: str
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]
    color: tuple[float, float, float]
    object_id: int
    hidden_hypothesis: bool = False

    @property
    def lo(self) -> np.ndarray:
        return np.asarray(self.minimum, dtype=np.float64)

    @property
    def hi(self) -> np.ndarray:
        return np.asarray(self.maximum, dtype=np.float64)


@dataclass(frozen=True)
class Camera:
    eye: tuple[float, float, float]
    target: tuple[float, float, float]
    width: int
    height: int
    fov_degrees: float = 58.0

    def matrices(self) -> tuple[np.ndarray, np.ndarray]:
        eye = np.asarray(self.eye, dtype=np.float64)
        target = np.asarray(self.target, dtype=np.float64)
        forward = _normalize(target - eye)
        right = _normalize(np.cross(forward, np.asarray([0.0, 0.0, 1.0])))
        down = -_normalize(np.cross(right, forward))
        rotation = np.stack([right, down, forward], axis=0)
        translation = -(rotation @ eye)
        extrinsics = np.concatenate([rotation, translation[:, None]], axis=1)
        focal = 0.5 * self.width / np.tan(np.deg2rad(self.fov_degrees) / 2.0)
        intrinsics = np.asarray(
            [
                [focal, 0.0, (self.width - 1.0) / 2.0],
                [0.0, focal, (self.height - 1.0) / 2.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        return intrinsics, extrinsics

    def rays(self) -> tuple[np.ndarray, np.ndarray]:
        intrinsics, extrinsics = self.matrices()
        xs, ys = np.meshgrid(
            np.arange(self.width, dtype=np.float64),
            np.arange(self.height, dtype=np.float64),
        )
        camera_rays = np.stack(
            [
                (xs - intrinsics[0, 2]) / intrinsics[0, 0],
                (ys - intrinsics[1, 2]) / intrinsics[1, 1],
                np.ones_like(xs),
            ],
            axis=-1,
        ).reshape(-1, 3)
        directions = camera_rays @ extrinsics[:, :3]
        directions = directions / np.linalg.norm(directions, axis=1, keepdims=True)
        origins = np.broadcast_to(np.asarray(self.eye, dtype=np.float64), directions.shape)
        return origins, directions


def _normalize(value: np.ndarray) -> np.ndarray:
    return value / np.linalg.norm(value)


def _scene_boxes(scene_name: str) -> list[Box]:
    common = [
        Box("floor", (-4.0, -5.0, -0.12), (4.0, 4.0, 0.0), (0.62, 0.58, 0.48), 1),
        Box("back_wall", (-4.0, 3.9, 0.0), (4.0, 4.05, 3.1), (0.44, 0.57, 0.70), 2),
        Box("left_wall", (-4.05, -5.0, 0.0), (-3.9, 4.0, 3.1), (0.52, 0.62, 0.68), 3),
        Box("right_wall", (3.9, -5.0, 0.0), (4.05, 4.0, 3.1), (0.52, 0.62, 0.68), 4),
        Box("occluder", (-2.15, -0.12, 0.0), (2.15, 0.18, 2.75), (0.74, 0.69, 0.58), 5),
        Box("front_left", (-1.55, -1.25, 0.0), (-1.00, -0.70, 0.85), (0.31, 0.57, 0.39), 6),
        Box("front_right", (1.02, -1.45, 0.0), (1.62, -0.78, 1.25), (0.64, 0.34, 0.27), 7),
    ]
    if scene_name == "scene_a":
        hidden = Box(
            "hidden_sofa", (-1.45, 1.05, 0.0), (1.45, 2.05, 0.82),
            (0.73, 0.22, 0.18), 101, True,
        )
    elif scene_name == "scene_b":
        hidden = Box(
            "hidden_shelf", (-0.72, 1.18, 0.0), (0.72, 1.92, 2.28),
            (0.18, 0.34, 0.73), 102, True,
        )
    else:
        raise ValueError(f"unknown scene: {scene_name}")
    return [*common, hidden]


def _cameras(width: int, height: int, n_context: int, n_target: int) -> tuple[list[Camera], list[Camera]]:
    context = []
    for index, x in enumerate(np.linspace(-0.78, 0.78, n_context)):
        phase = 0.0 if n_context == 1 else index / (n_context - 1)
        context.append(
            Camera(
                eye=(float(x), -4.45, 1.18 + 0.12 * np.sin(np.pi * phase)),
                target=(0.0, 0.20, 1.12),
                width=width,
                height=height,
            )
        )
    target = []
    angles = np.linspace(-0.72, 0.72, n_target)
    for angle in angles:
        target.append(
            Camera(
                eye=(float(2.65 * np.sin(angle)), float(3.15 - 0.35 * np.cos(angle)), 1.28),
                target=(0.0, 1.48, 0.95),
                width=width,
                height=height,
            )
        )
    return context, target


def _box_intersections(
    origins: np.ndarray, directions: np.ndarray, box: Box,
) -> tuple[np.ndarray, np.ndarray]:
    inverse = np.full_like(directions, np.inf)
    np.divide(1.0, directions, out=inverse, where=np.abs(directions) > 1e-12)
    first = (box.lo - origins) * inverse
    second = (box.hi - origins) * inverse
    near = np.max(np.minimum(first, second), axis=1)
    far = np.min(np.maximum(first, second), axis=1)
    distance = np.where(near > 1e-7, near, far)
    valid = (far >= np.maximum(near, 0.0)) & (distance > 1e-7)
    return distance, valid


def _trace_first_hit(
    origins: np.ndarray, directions: np.ndarray, boxes: Sequence[Box],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    count = origins.shape[0]
    best_distance = np.full(count, np.inf, dtype=np.float64)
    best_id = np.full(count, -1, dtype=np.int32)
    best_normal = np.zeros((count, 3), dtype=np.float64)
    best_color = np.zeros((count, 3), dtype=np.float64)
    for box in boxes:
        distance, valid = _box_intersections(origins, directions, box)
        update = valid & (distance < best_distance)
        if not np.any(update):
            continue
        points = origins[update] + distance[update, None] * directions[update]
        face_distances = np.concatenate(
            [np.abs(points - box.lo), np.abs(points - box.hi)], axis=1,
        )
        faces = np.argmin(face_distances, axis=1)
        normals = np.zeros_like(points)
        rows = np.arange(points.shape[0])
        axes = faces % 3
        normals[rows, axes] = np.where(faces < 3, -1.0, 1.0)
        best_distance[update] = distance[update]
        best_id[update] = box.object_id
        best_normal[update] = normals
        best_color[update] = np.asarray(box.color, dtype=np.float64)
    return best_distance, best_id, best_normal, best_color


def _render(camera: Camera, boxes: Sequence[Box]) -> dict[str, np.ndarray]:
    origins, directions = camera.rays()
    distance, object_id, normal, color = _trace_first_hit(origins, directions, boxes)
    hit = np.isfinite(distance)
    points = origins + np.where(hit, distance, 0.0)[:, None] * directions
    light = _normalize(np.asarray([0.45, -0.55, 1.0], dtype=np.float64))
    diffuse = np.clip(normal @ light, 0.0, 1.0)
    checker = (
        np.floor(points[:, 0] * 2.0)
        + np.floor(points[:, 1] * 2.0)
        + np.floor(points[:, 2] * 2.0)
        + object_id
    ).astype(np.int64) & 1
    texture = np.where(checker[:, None] == 0, 0.82, 1.08)
    shaded = color * (0.38 + 0.62 * diffuse[:, None]) * texture
    background = np.stack(
        [
            np.full(camera.width * camera.height, 0.08),
            np.full(camera.width * camera.height, 0.10),
            0.14 + 0.10 * np.tile(np.linspace(0.0, 1.0, camera.height), camera.width),
        ],
        axis=1,
    )
    rgb = np.where(hit[:, None], shaded, background)
    _, extrinsics = camera.matrices()
    camera_depth = (points @ extrinsics[:, :3].T + extrinsics[:, 3])[:, 2]
    camera_depth = np.where(hit, camera_depth, 0.0)
    shape = (camera.height, camera.width)
    return {
        "rgb": (np.clip(rgb, 0.0, 1.0).reshape(*shape, 3) * 255.0 + 0.5).astype(np.uint8),
        "depth": camera_depth.reshape(shape).astype(np.float32),
        "ray_depth": np.where(hit, distance, 0.0).reshape(shape).astype(np.float32),
        "normal": normal.reshape(*shape, 3).astype(np.float32),
        "object_id": object_id.reshape(shape),
    }


def _sample_box_surface(box: Box, count: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed + 104729 * box.object_id)
    size = box.hi - box.lo
    face_areas = np.asarray(
        [size[1] * size[2], size[1] * size[2], size[0] * size[2],
         size[0] * size[2], size[0] * size[1], size[0] * size[1]],
        dtype=np.float64,
    )
    faces = rng.choice(6, size=count, p=face_areas / face_areas.sum())
    points = box.lo + rng.random((count, 3)) * size
    normals = np.zeros((count, 3), dtype=np.float64)
    rows = np.arange(count)
    axes = faces // 2
    use_max = (faces % 2) == 1
    points[rows, axes] = np.where(use_max, box.hi[axes], box.lo[axes])
    normals[rows, axes] = np.where(use_max, 1.0, -1.0)
    return points, normals


def _surface_cloud(
    boxes: Sequence[Box], points_per_box: int, seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    point_parts = []
    normal_parts = []
    id_parts = []
    hidden_parts = []
    for box in boxes:
        points, normals = _sample_box_surface(box, points_per_box, seed)
        point_parts.append(points)
        normal_parts.append(normals)
        id_parts.append(np.full(points_per_box, box.object_id, dtype=np.int32))
        hidden_parts.append(np.full(points_per_box, box.hidden_hypothesis, dtype=bool))
    return (
        np.concatenate(point_parts),
        np.concatenate(normal_parts),
        np.concatenate(id_parts),
        np.concatenate(hidden_parts),
    )


def _visible_from_any(
    points: np.ndarray, cameras: Sequence[Camera], boxes: Sequence[Box],
) -> np.ndarray:
    visible = np.zeros(points.shape[0], dtype=bool)
    for camera in cameras:
        intrinsics, extrinsics = camera.matrices()
        camera_points = points @ extrinsics[:, :3].T + extrinsics[:, 3]
        positive = camera_points[:, 2] > 1e-6
        projected_x = intrinsics[0, 0] * camera_points[:, 0] / np.maximum(camera_points[:, 2], 1e-6) + intrinsics[0, 2]
        projected_y = intrinsics[1, 1] * camera_points[:, 1] / np.maximum(camera_points[:, 2], 1e-6) + intrinsics[1, 2]
        in_frame = (
            positive
            & (projected_x >= 0.0) & (projected_x <= camera.width - 1.0)
            & (projected_y >= 0.0) & (projected_y <= camera.height - 1.0)
        )
        candidates = np.flatnonzero(in_frame & ~visible)
        if candidates.size == 0:
            continue
        eye = np.asarray(camera.eye, dtype=np.float64)
        vectors = points[candidates] - eye
        point_distance = np.linalg.norm(vectors, axis=1)
        directions = vectors / point_distance[:, None]
        origins = np.broadcast_to(eye, directions.shape)
        first_distance, _, _, _ = _trace_first_hit(origins, directions, boxes)
        visible[candidates] = np.abs(first_distance - point_distance) <= 2e-5
    return visible


def _write_render(root: Path, index: int, result: dict[str, np.ndarray]) -> Path:
    for layer in ("rgb", "depth", "ray_depth", "normal", "object_id"):
        (root / layer).mkdir(parents=True, exist_ok=True)
    rgb_path = root / "rgb" / f"{index:04d}.png"
    Image.fromarray(result["rgb"], mode="RGB").save(rgb_path)
    for layer in ("depth", "ray_depth", "normal", "object_id"):
        np.save(root / layer / f"{index:04d}.npy", result[layer])
    return rgb_path


def _hash_files(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _camera_payload(cameras: Sequence[Camera]) -> list[dict[str, object]]:
    payload = []
    for camera in cameras:
        intrinsics, extrinsics = camera.matrices()
        payload.append(
            {
                "eye": list(camera.eye),
                "target": list(camera.target),
                "intrinsics": intrinsics.tolist(),
                "world_to_camera": extrinsics.tolist(),
            }
        )
    return payload


def generate_episode(
    output_dir: Path,
    *,
    width: int = 512,
    height: int = 384,
    n_context: int = 16,
    n_target: int = 8,
    surface_points_per_box: int = 20_000,
    seed: int = 20260925,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    context_cameras, target_cameras = _cameras(width, height, n_context, n_target)

    scene_records: dict[str, dict[str, object]] = {}
    context_arrays: dict[str, list[np.ndarray]] = {}
    target_arrays: dict[str, list[np.ndarray]] = {}
    for scene_name in ("scene_a", "scene_b"):
        boxes = _scene_boxes(scene_name)
        context_arrays[scene_name] = []
        target_arrays[scene_name] = []
        for split, cameras, arrays in (
            ("context", context_cameras, context_arrays[scene_name]),
            ("target", target_cameras, target_arrays[scene_name]),
        ):
            for index, camera in enumerate(cameras):
                rendered = _render(camera, boxes)
                arrays.append(rendered["rgb"])
                _write_render(output_dir / scene_name / split, index, rendered)

        points, normals, object_ids, hidden = _surface_cloud(
            boxes, surface_points_per_box, seed,
        )
        context_visible = _visible_from_any(points, context_cameras, boxes)
        target_visible = _visible_from_any(points, target_cameras, boxes)
        new_in_target = target_visible & ~context_visible
        np.savez_compressed(
            output_dir / scene_name / "surface.npz",
            points=points.astype(np.float32),
            normals=normals.astype(np.float32),
            object_ids=object_ids,
            hidden_hypothesis=hidden,
            context_visible=context_visible,
            target_visible=target_visible,
            new_in_target=new_in_target,
        )
        hidden_count = max(int(hidden.sum()), 1)
        target_count = max(int(target_visible.sum()), 1)
        scene_records[scene_name] = {
            "hidden_object": next(box.name for box in boxes if box.hidden_hypothesis),
            "objects": [
                {
                    "name": box.name,
                    "object_id": box.object_id,
                    "minimum": list(box.minimum),
                    "maximum": list(box.maximum),
                    "hidden_hypothesis": box.hidden_hypothesis,
                }
                for box in boxes
            ],
            "visibility": {
                "hidden_object_context_fraction": float((context_visible & hidden).sum() / hidden_count),
                "hidden_object_target_fraction": float((target_visible & hidden).sum() / hidden_count),
                "target_new_surface_fraction": float(new_in_target.sum() / target_count),
            },
        }

    mismatch_count = sum(
        int(np.count_nonzero(a != b))
        for a, b in zip(context_arrays["scene_a"], context_arrays["scene_b"])
    )
    context_a_paths = list((output_dir / "scene_a" / "context" / "rgb").glob("*.png"))
    context_b_paths = list((output_dir / "scene_b" / "context" / "rgb").glob("*.png"))
    target_a_paths = list((output_dir / "scene_a" / "target" / "rgb").glob("*.png"))
    target_b_paths = list((output_dir / "scene_b" / "target" / "rgb").glob("*.png"))

    max_center_error = 0.0
    for camera in [*context_cameras, *target_cameras]:
        _, extrinsics = camera.matrices()
        recovered = -(extrinsics[:, :3].T @ extrinsics[:, 3])
        max_center_error = max(
            max_center_error,
            float(np.linalg.norm(recovered - np.asarray(camera.eye))),
        )

    context_intrinsics = np.stack([camera.matrices()[0] for camera in context_cameras])
    context_extrinsics = np.stack([camera.matrices()[1] for camera in context_cameras])
    target_intrinsics = np.stack([camera.matrices()[0] for camera in target_cameras])
    target_extrinsics = np.stack([camera.matrices()[1] for camera in target_cameras])
    np.savez_compressed(
        output_dir / "cameras.npz",
        context_intrinsics=context_intrinsics.astype(np.float32),
        context_extrinsics=context_extrinsics.astype(np.float32),
        target_intrinsics=target_intrinsics.astype(np.float32),
        target_extrinsics=target_extrinsics.astype(np.float32),
    )

    manifest = {
        "schema_version": 1,
        "task": "paired_hidden-scene_ambiguity",
        "prototype": True,
        "seed": seed,
        "image_size": {"width": width, "height": height},
        "context_views": _camera_payload(context_cameras),
        "target_views": _camera_payload(target_cameras),
        "paired_context": {
            "pixel_mismatches": mismatch_count,
            "sha256_a": _hash_files(context_a_paths),
            "sha256_b": _hash_files(context_b_paths),
        },
        "paired_targets": {
            "sha256_a": _hash_files(target_a_paths),
            "sha256_b": _hash_files(target_b_paths),
        },
        "camera_checks": {"max_center_error": max_center_error},
        "scenes": scene_records,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=384)
    parser.add_argument("--context-views", type=int, default=16)
    parser.add_argument("--target-views", type=int, default=8)
    parser.add_argument("--surface-points-per-box", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260925)
    args = parser.parse_args()
    manifest = generate_episode(
        args.output,
        width=args.width,
        height=args.height,
        n_context=args.context_views,
        n_target=args.target_views,
        surface_points_per_box=args.surface_points_per_box,
        seed=args.seed,
    )
    print(json.dumps({
        "output": str(args.output),
        "paired_context": manifest["paired_context"],
        "visibility": {
            name: record["visibility"] for name, record in manifest["scenes"].items()
        },
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
