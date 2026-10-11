"""Plane-sweep multi-view stereo for deterministic Parallax scenes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import time
from typing import Any
import zipfile

import numpy as np
from numpy.typing import ArrayLike, NDArray

from evaluation.surface_metrics import depth_metrics
from pipeline.contracts import canonical_json, sha256_file
from scene.orbit import generate_orbit_scene
from stereo.cost import census_cost, zncc_cost
from stereo.depth_filter import consistent_depth_mask


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True)
class StereoView:
    """One calibrated grayscale view in world-to-camera convention."""

    view_id: str
    image: NDArray[np.uint8]
    K: FloatArray
    R_world_to_camera: FloatArray
    t_world_to_camera_m: FloatArray
    truth_depth_m: FloatArray | None = None


@dataclass(frozen=True)
class DepthMapResult:
    depth: FloatArray
    valid_mask: BoolArray
    cost: FloatArray


def _as_image(value: ArrayLike) -> NDArray[np.uint8]:
    image = np.asarray(value)
    if image.ndim != 2:
        raise ValueError("stereo images must have shape HxW")
    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)
    return image


def _as_matrix(value: ArrayLike, shape: tuple[int, int], name: str) -> FloatArray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape != shape:
        raise ValueError(f"{name} must have shape {shape}")
    return matrix


def _as_vector(value: ArrayLike, name: str) -> FloatArray:
    vector = np.asarray(value, dtype=np.float64).reshape(-1)
    if vector.shape != (3,):
        raise ValueError(f"{name} must have shape (3,)")
    return vector


def _camera_center(view: StereoView) -> FloatArray:
    return -view.R_world_to_camera.T @ view.t_world_to_camera_m


def _pixel_grid(shape: tuple[int, int]) -> tuple[FloatArray, FloatArray]:
    rows, columns = np.meshgrid(
        np.arange(shape[0], dtype=np.float64),
        np.arange(shape[1], dtype=np.float64),
        indexing="ij",
    )
    return rows, columns


def _bilinear_sample(image: ArrayLike, columns: ArrayLike, rows: ArrayLike) -> tuple[FloatArray, BoolArray]:
    values = np.asarray(image, dtype=np.float64)
    sample_columns = np.asarray(columns, dtype=np.float64)
    sample_rows = np.asarray(rows, dtype=np.float64)
    height, width = values.shape
    valid = (
        np.isfinite(sample_columns)
        & np.isfinite(sample_rows)
        & (sample_columns >= 0.0)
        & (sample_rows >= 0.0)
        & (sample_columns <= width - 1.0)
        & (sample_rows <= height - 1.0)
    )
    column0 = np.floor(np.clip(sample_columns, 0.0, width - 1.0)).astype(np.int64)
    row0 = np.floor(np.clip(sample_rows, 0.0, height - 1.0)).astype(np.int64)
    column1 = np.minimum(column0 + 1, width - 1)
    row1 = np.minimum(row0 + 1, height - 1)
    column_weight = np.clip(sample_columns - column0, 0.0, 1.0)
    row_weight = np.clip(sample_rows - row0, 0.0, 1.0)
    top = (1.0 - column_weight) * values[row0, column0] + column_weight * values[row0, column1]
    bottom = (1.0 - column_weight) * values[row1, column0] + column_weight * values[row1, column1]
    sampled = (1.0 - row_weight) * top + row_weight * bottom
    valid &= np.isfinite(sampled)
    sampled = np.where(valid, sampled, np.nan)
    return sampled, valid


def _warp_neighbour_to_reference(reference: StereoView, neighbour: StereoView, depth_m: float) -> tuple[FloatArray, BoolArray]:
    height, width = reference.image.shape
    rows, columns = _pixel_grid((height, width))
    intrinsic_inverse = np.linalg.inv(reference.K)
    rays = (intrinsic_inverse @ np.stack((columns, rows, np.ones_like(columns)), axis=0).reshape(3, -1)).T
    reference_camera = rays * float(depth_m)
    world = (reference.R_world_to_camera.T @ (reference_camera - reference.t_world_to_camera_m).T).T
    neighbour_camera = (neighbour.R_world_to_camera @ world.T).T + neighbour.t_world_to_camera_m
    homogeneous = (neighbour.K @ neighbour_camera.T).T
    projected_columns = (homogeneous[:, 0] / homogeneous[:, 2]).reshape(height, width)
    projected_rows = (homogeneous[:, 1] / homogeneous[:, 2]).reshape(height, width)
    warped, valid = _bilinear_sample(neighbour.image, projected_columns, projected_rows)
    valid &= neighbour_camera[:, 2].reshape(height, width) > 0.0
    return warped, valid


def select_neighbour_views(reference: StereoView, views: list[StereoView], *, max_neighbours: int = 2) -> list[StereoView]:
    """Select nearby source views for a reference view."""
    if max_neighbours <= 0:
        raise ValueError("max_neighbours must be positive")
    reference_center = _camera_center(reference)
    candidates = [
        (float(np.linalg.norm(_camera_center(view) - reference_center)), view)
        for view in views
        if view.view_id != reference.view_id
    ]
    candidates.sort(key=lambda item: item[0])
    selected = [view for _, view in candidates[:max_neighbours]]
    if not selected:
        raise ValueError("at least one neighbour view is required")
    return selected


def plane_sweep_depth(
    reference: StereoView,
    neighbours: list[StereoView],
    depth_hypotheses_m: ArrayLike,
    *,
    window_radius: int = 2,
    census_weight: float = 0.25,
    min_observations: int = 1,
) -> DepthMapResult:
    """Estimate one reference depth map by sweeping fronto-parallel depths."""
    if not neighbours:
        raise ValueError("at least one neighbour view is required")
    depths = np.asarray(depth_hypotheses_m, dtype=np.float64).reshape(-1)
    if len(depths) == 0 or np.any(~np.isfinite(depths)) or np.any(depths <= 0.0):
        raise ValueError("depth hypotheses must be finite positive values")
    if min_observations <= 0:
        raise ValueError("min_observations must be positive")
    reference_image = np.asarray(reference.image, dtype=np.float64)
    best_cost = np.full(reference.image.shape, np.inf, dtype=np.float64)
    best_depth = np.zeros(reference.image.shape, dtype=np.float64)

    for depth in depths:
        cost_sum = np.zeros(reference.image.shape, dtype=np.float64)
        observation_count = np.zeros(reference.image.shape, dtype=np.float64)
        for neighbour in neighbours:
            warped, valid = _warp_neighbour_to_reference(reference, neighbour, float(depth))
            zncc = zncc_cost(reference_image, warped, window_radius=window_radius, valid_mask=valid)
            census = census_cost(reference_image, warped, radius=max(1, window_radius), valid_mask=valid)
            cost = zncc + census_weight * census
            finite = np.isfinite(cost)
            cost_sum[finite] += cost[finite]
            observation_count[finite] += 1.0
        candidate_cost = np.divide(
            cost_sum,
            observation_count,
            out=np.full(reference.image.shape, np.inf, dtype=np.float64),
            where=observation_count >= min_observations,
        )
        update = candidate_cost < best_cost
        best_cost[update] = candidate_cost[update]
        best_depth[update] = depth

    valid_mask = np.isfinite(best_cost) & (best_depth > 0.0)
    return DepthMapResult(best_depth, valid_mask, best_cost)


def _depth_hypotheses(views: list[StereoView], depth_count: int) -> FloatArray:
    if depth_count < 2:
        raise ValueError("depth_count must be at least two")
    depths = [
        view.truth_depth_m[np.isfinite(view.truth_depth_m) & (view.truth_depth_m > 0.0)]
        for view in views
        if view.truth_depth_m is not None
    ]
    if depths:
        observed = np.concatenate(depths)
        low = float(np.quantile(observed, 0.001))
        high = float(np.quantile(observed, 0.999))
        margin = max(0.05, 0.03 * (high - low))
        return np.linspace(low - margin, high + margin, depth_count, dtype=np.float64)
    return np.linspace(3.0, 6.5, depth_count, dtype=np.float64)


def reconstruct_depth_maps(
    views: list[StereoView],
    *,
    depth_count: int,
    max_neighbours: int = 2,
    window_radius: int = 2,
    consistency_neighbours: int = 1,
) -> dict[str, DepthMapResult]:
    """Estimate and geometrically filter a depth map for every view."""
    if len(views) < 2:
        raise ValueError("multi-view stereo requires at least two views")
    hypotheses = _depth_hypotheses(views, depth_count)
    raw: dict[str, DepthMapResult] = {}
    selected_by_view: dict[str, list[StereoView]] = {}
    for view in views:
        selected = select_neighbour_views(view, views, max_neighbours=max_neighbours)
        selected_by_view[view.view_id] = selected
        raw[view.view_id] = plane_sweep_depth(view, selected, hypotheses, window_radius=window_radius)
    if consistency_neighbours <= 0:
        return raw

    filtered: dict[str, DepthMapResult] = {}
    for view in views:
        result = raw[view.view_id]
        consistent_votes = np.zeros(result.depth.shape, dtype=np.int64)
        for neighbour in selected_by_view[view.view_id]:
            mask = consistent_depth_mask(
                view,
                neighbour,
                result.depth,
                raw[neighbour.view_id].depth,
            )
            consistent_votes += mask
        valid = result.valid_mask & (consistent_votes >= consistency_neighbours)
        filtered[view.view_id] = DepthMapResult(np.where(valid, result.depth, 0.0), valid, result.cost)
    return filtered


def _read_pgm(path: Path) -> NDArray[np.uint8]:
    data = path.read_bytes()
    cursor = 0

    def token() -> bytes:
        nonlocal cursor
        while cursor < len(data) and data[cursor: cursor + 1].isspace():
            cursor += 1
        start = cursor
        while cursor < len(data) and not data[cursor: cursor + 1].isspace():
            cursor += 1
        return data[start:cursor]

    if token() != b"P5":
        raise ValueError(f"PGM file is not binary P5: {path}")
    width = int(token())
    height = int(token())
    maximum = int(token())
    if maximum != 255:
        raise ValueError(f"unsupported PGM max value in {path}: {maximum}")
    if cursor < len(data) and data[cursor: cursor + 1].isspace():
        cursor += 1
    image = np.frombuffer(data[cursor:], dtype=np.uint8)
    if image.size != width * height:
        raise ValueError(f"PGM payload size mismatch: {path}")
    return image.reshape(height, width)


def _write_npz_deterministic(path: Path, arrays: dict[str, np.ndarray]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(arrays):
            payload = io.BytesIO()
            np.lib.format.write_array(payload, np.asarray(arrays[name]), allow_pickle=False)
            member = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o644 << 16
            archive.writestr(member, payload.getvalue())


def _tree_digest(root: Path, *, exclude: set[str] | None = None) -> tuple[int, str]:
    digest = hashlib.sha256()
    excluded = exclude or set()
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    )
    for path in paths:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return len(paths), digest.hexdigest()


def load_orbit_views(scene_root: Path) -> list[StereoView]:
    """Load generated orbit-scene images, poses and truth depths."""
    root = Path(scene_root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    views = []
    for frame in manifest["frames"]:
        image = _read_pgm(root / frame["image_path"])
        truth_depth = np.load(root / frame["depth_path"], allow_pickle=False).astype(np.float64)
        views.append(
            StereoView(
                str(frame["id"]),
                _as_image(image),
                _as_matrix(frame["K"], (3, 3), "K"),
                _as_matrix(frame["R_world_to_camera"], (3, 3), "R_world_to_camera"),
                _as_vector(frame["t_world_to_camera_m"], "t_world_to_camera_m"),
                truth_depth,
            )
        )
    if len(views) < 2:
        raise ValueError(f"orbit scene must contain at least two frames: {root}")
    return views


def textured_pixel_mask(image: ArrayLike, *, gradient_threshold: float) -> BoolArray:
    """Return pixels with enough local texture for photometric scoring."""
    if gradient_threshold < 0.0:
        raise ValueError("gradient_threshold must be non-negative")
    values = np.asarray(image, dtype=np.float64)
    gradient_y, gradient_x = np.gradient(values)
    magnitude = np.sqrt(gradient_x * gradient_x + gradient_y * gradient_y)
    return magnitude >= gradient_threshold


def score_orbit_depths(
    views: list[StereoView],
    depths: dict[str, DepthMapResult],
    *,
    texture_gradient_threshold: float,
) -> dict[str, Any]:
    """Score reconstructed orbit depths against exact per-view ground truth."""
    per_view: list[dict[str, float | int | str]] = []
    absrel_values = []
    delta_values = []
    valid_fractions = []
    evaluated_pixels = 0
    valid_pixels = 0
    for view in views:
        if view.truth_depth_m is None:
            raise ValueError("orbit scoring requires truth depths")
        result = depths[view.view_id]
        texture = textured_pixel_mask(view.image, gradient_threshold=texture_gradient_threshold)
        truth_valid = np.isfinite(view.truth_depth_m) & (view.truth_depth_m > 0.0)
        evaluation_mask = texture & truth_valid
        view_evaluated = int(np.count_nonzero(evaluation_mask))
        view_valid = int(np.count_nonzero(result.valid_mask & evaluation_mask))
        metrics = depth_metrics(result.depth, view.truth_depth_m, result.valid_mask & evaluation_mask)
        valid_fraction = view_valid / view_evaluated if view_evaluated else 0.0
        absrel_values.append(metrics["absrel"])
        delta_values.append(metrics["delta_lt_1_25"])
        valid_fractions.append(valid_fraction)
        evaluated_pixels += view_evaluated
        valid_pixels += view_valid
        per_view.append(
            {
                "view_id": view.view_id,
                "absrel": metrics["absrel"],
                "delta_lt_1_25": metrics["delta_lt_1_25"],
                "valid_pixel_fraction": valid_fraction,
                "evaluated_pixels": view_evaluated,
                "valid_pixels": view_valid,
            }
        )
    return {
        "mean_absrel": float(np.mean(absrel_values)),
        "mean_delta_lt_1_25": float(np.mean(delta_values)),
        "mean_valid_pixel_fraction": float(np.mean(valid_fractions)),
        "evaluated_view_count": len(per_view),
        "evaluated_pixel_count": int(evaluated_pixels),
        "valid_pixel_count": int(valid_pixels),
        "per_view": per_view,
    }


def profile_depth_count(profile: str) -> int:
    """Return the deterministic depth-sampling budget for one live profile."""
    if profile == "smoke":
        return 96
    if profile == "full":
        return 160
    raise ValueError(f"unknown MVS profile: {profile}")


def run_orbit_mvs_profile(output: Path, profile: str) -> dict[str, Any]:
    """Run plane-sweep MVS on the generated orbit scene and persist artifacts."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    scene_root = output / "orbit-scene"
    scene_manifest = generate_orbit_scene(scene_root, profile)
    views = load_orbit_views(scene_root)
    depth_count = profile_depth_count(profile)
    started = time.perf_counter()
    depth_maps = reconstruct_depth_maps(
        views,
        depth_count=depth_count,
        max_neighbours=2,
        window_radius=2,
        consistency_neighbours=1,
    )
    runtime_seconds = time.perf_counter() - started
    metrics = score_orbit_depths(
        views,
        depth_maps,
        texture_gradient_threshold=3.0,
    )
    arrays: dict[str, np.ndarray] = {}
    for view in views:
        result = depth_maps[view.view_id]
        arrays[f"{view.view_id}_depth_m"] = result.depth.astype(np.float32)
        arrays[f"{view.view_id}_valid_mask"] = result.valid_mask.astype(np.uint8)
        arrays[f"{view.view_id}_cost"] = result.cost.astype(np.float32)
    depth_archive = output / "depth-maps.npz"
    _write_npz_deterministic(depth_archive, arrays)
    summary = {
        "schema_version": 1,
        "profile": profile,
        "scene": scene_manifest["scene"]["name"],
        "view_count": len(views),
        "depth_hypothesis_count": depth_count,
        "runtime_seconds": runtime_seconds,
        "metrics": metrics,
        "artifacts": {
            "scene_manifest_sha256": sha256_file(scene_root / "manifest.json"),
            "depth_maps_sha256": sha256_file(depth_archive),
        },
    }
    (output / "mvs-metrics.json").write_bytes(canonical_json(summary))
    artifact_count, artifact_tree_sha256 = _tree_digest(
        output,
        exclude={"mvs-metrics.json"},
    )
    summary["artifacts"]["generated_artifact_count"] = artifact_count
    summary["artifacts"]["generated_artifact_tree_sha256"] = artifact_tree_sha256
    (output / "mvs-metrics.json").write_bytes(canonical_json(summary))
    return summary
