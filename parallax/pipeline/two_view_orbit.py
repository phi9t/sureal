#!/usr/bin/env python3
"""Run two-view feature matching and reconstruction on the orbit scene."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Any

import numpy as np

from camera.pose import fundamental_from_poses
from evaluation.pose_metrics import rotation_error_degrees, umeyama_sim3
from features.describe import describe_patches
from features.detect import detect_harris
from features.match import match_descriptors_locally
from geometry.epipolar import (
    RelativePose,
    estimate_relative_pose,
    essential_from_correspondences,
    refine_relative_pose,
    symmetric_epipolar_distances,
)
from geometry.ransac import ransac
from geometry.triangulate import triangulate_points
from scene.ground_truth import surface_samples_from_depth
from scene.orbit import generate_orbit_scene


EPIPOLAR_RANSAC_THRESHOLD_PX = 0.75
GROUND_TRUTH_F_THRESHOLD_PX = 0.75
DEFAULT_MIN_MATCH_DELTA_X_PX = -5.0
DEFAULT_MAX_MATCH_DELTA_X_PX = 5.0
DEFAULT_MAX_MATCH_DELTA_Y_PX = 6.0
DEFAULT_MATCH_RATIO = 0.8
DEFAULT_MAX_QUALITY_MATCHES = 700


@dataclass(frozen=True)
class TwoViewEstimate:
    frame_pair: tuple[str, str]
    image1: np.ndarray
    image2: np.ndarray
    points1: np.ndarray
    points2: np.ndarray
    ransac_inliers: np.ndarray
    pose: RelativePose
    match_stages: dict[str, int]
    keypoints: dict[str, int]
    ransac_iterations: int


def _read_pgm(path: Path) -> np.ndarray:
    payload = path.read_bytes()
    header, width_height, max_value, data = payload.split(b"\n", 3)
    if header != b"P5" or max_value != b"255":
        raise ValueError(f"unsupported PGM image: {path}")
    width, height = (int(item) for item in width_height.split())
    return np.frombuffer(data, dtype=np.uint8).reshape(height, width)


def _tree_digest(root: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    paths = sorted(path for path in root.rglob("*") if path.is_file())
    for path in paths:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return len(paths), digest.hexdigest()


def _translation_direction_error(estimated: np.ndarray, truth: np.ndarray) -> float:
    left = estimated / np.linalg.norm(estimated)
    right = truth / np.linalg.norm(truth)
    cosine = float(np.clip(np.dot(left, right), -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def _write_match_svg(
    path: Path,
    image1: np.ndarray,
    image2: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
    inliers: np.ndarray,
) -> None:
    height, width = image1.shape
    scale = 4
    svg_width = 2 * width * scale + 20
    svg_height = height * scale
    panel_width = width * scale
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{svg_width}" height="{svg_height}" '
        f'viewBox="0 0 {svg_width} {svg_height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<rect x="0" y="0" width="{panel_width}" height="{svg_height}" '
        'fill="#f7f7f7" stroke="#555"/>',
        f'<rect x="{panel_width + 20}" y="0" width="{panel_width}" '
        f'height="{svg_height}" fill="#f7f7f7" stroke="#555"/>',
    ]
    for source, target, ok in zip(left[:80], right[:80], inliers[:80]):
        color = "#287a3e" if bool(ok) else "#b43b34"
        x1 = source[0] * scale
        y1 = source[1] * scale
        x2 = width * scale + 20 + target[0] * scale
        y2 = target[1] * scale
        lines.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="1"/>'
        )
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_failure_sweep(path: Path, rows: list[dict[str, float | str]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        stream.write("parameter,value,metric,measurement\n")
        for row in rows:
            stream.write(
                f"{row['parameter']},{row['value']},{row['metric']},{row['measurement']}\n"
            )


def _normalized_patch_at(
    image: np.ndarray,
    point: np.ndarray,
    *,
    radius: int,
) -> np.ndarray | None:
    x, y = (float(point[0]), float(point[1]))
    height, width = image.shape
    if (
        x - radius < 0.0
        or x + radius > width - 1.0
        or y - radius < 0.0
        or y + radius > height - 1.0
    ):
        return None
    columns, rows = np.meshgrid(
        np.arange(-radius, radius + 1, dtype=np.float64) + x,
        np.arange(-radius, radius + 1, dtype=np.float64) + y,
    )
    left = np.floor(columns).astype(np.int64)
    top = np.floor(rows).astype(np.int64)
    right = np.minimum(left + 1, width - 1)
    bottom = np.minimum(top + 1, height - 1)
    wx = columns - left
    wy = rows - top
    patch = (
        (1.0 - wx) * (1.0 - wy) * image[top, left]
        + wx * (1.0 - wy) * image[top, right]
        + (1.0 - wx) * wy * image[bottom, left]
        + wx * wy * image[bottom, right]
    )
    vector = patch.reshape(-1).astype(np.float64)
    vector -= float(np.mean(vector))
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return None
    return vector / norm


def _refine_right_points_subpixel(
    image1: np.ndarray,
    image2: np.ndarray,
    points1: np.ndarray,
    points2: np.ndarray,
    *,
    radius: int,
) -> np.ndarray:
    refined = points2.astype(np.float64).copy()
    offsets = (
        np.array([-1.0, 0.0]),
        np.array([0.0, -1.0]),
        np.array([0.0, 0.0]),
        np.array([0.0, 1.0]),
        np.array([1.0, 0.0]),
    )
    for index, (left, right) in enumerate(zip(points1, points2)):
        reference = _normalized_patch_at(image1, left, radius=radius)
        if reference is None:
            continue
        costs: dict[tuple[float, float], float] = {}
        for offset in offsets:
            candidate = _normalized_patch_at(image2, right + offset, radius=radius)
            if candidate is None:
                break
            costs[(float(offset[0]), float(offset[1]))] = float(
                np.sum((reference - candidate) ** 2)
            )
        else:
            center = costs[(0.0, 0.0)]
            dx_denom = costs[(-1.0, 0.0)] - 2.0 * center + costs[(1.0, 0.0)]
            dy_denom = costs[(0.0, -1.0)] - 2.0 * center + costs[(0.0, 1.0)]
            dx = (
                0.5 * (costs[(-1.0, 0.0)] - costs[(1.0, 0.0)]) / dx_denom
                if abs(dx_denom) > 1e-12
                else 0.0
            )
            dy = (
                0.5 * (costs[(0.0, -1.0)] - costs[(0.0, 1.0)]) / dy_denom
                if abs(dy_denom) > 1e-12
                else 0.0
            )
            refined[index] = right + np.array(
                [
                    float(np.clip(dx, -0.75, 0.75)),
                    float(np.clip(dy, -0.75, 0.75)),
                ],
                dtype=np.float64,
            )
    return refined


def _feature_budget(profile: str) -> int:
    return 2200 if profile == "smoke" else 3500


def _match_bounds(
    image: np.ndarray,
    *,
    min_delta_x_px: float,
    max_delta_x_px: float,
    max_abs_delta_y_px: float,
) -> tuple[float, float, float, float]:
    """Return a generic fixed-pixel local search window.

    The bounds are deliberately independent of frame pose, azimuth or scene
    metadata; they are an estimator parameter for ordered nearby views.
    """
    height, width = image.shape
    if min_delta_x_px > max_delta_x_px:
        raise ValueError("min_delta_x_px must not exceed max_delta_x_px")
    if max_abs_delta_y_px < 0.0:
        raise ValueError("max_abs_delta_y_px must be non-negative")
    return (
        max(-float(width), float(min_delta_x_px)),
        min(float(width), float(max_delta_x_px)),
        -min(float(height), float(max_abs_delta_y_px)),
        min(float(height), float(max_abs_delta_y_px)),
    )


def _detect_describe(image: np.ndarray, profile: str):
    radius = 3
    keypoints = detect_harris(
        image,
        max_keypoints=_feature_budget(profile),
        quality=0.0,
        min_distance=1,
        border=radius,
        require_local_maximum=False,
    )
    return keypoints, describe_patches(image, keypoints, radius=radius), radius


def estimate_two_view_orbit_pair(
    scene_root: Path,
    first: dict[str, Any],
    second: dict[str, Any],
    profile: str,
    *,
    min_delta_x_px: float = DEFAULT_MIN_MATCH_DELTA_X_PX,
    max_delta_x_px: float = DEFAULT_MAX_MATCH_DELTA_X_PX,
    max_abs_delta_y_px: float = DEFAULT_MAX_MATCH_DELTA_Y_PX,
    match_ratio: float = DEFAULT_MATCH_RATIO,
    max_quality_matches: int = DEFAULT_MAX_QUALITY_MATCHES,
) -> TwoViewEstimate:
    """Estimate relative pose from only image pixels and calibration."""
    image1 = _read_pgm(scene_root / first["image_path"])
    image2 = _read_pgm(scene_root / second["image_path"])
    keypoints1, described1, descriptor_radius = _detect_describe(image1, profile)
    keypoints2, described2, _ = _detect_describe(image2, profile)
    min_delta_x, max_delta_x, min_delta_y, max_delta_y = _match_bounds(
        image1,
        min_delta_x_px=min_delta_x_px,
        max_delta_x_px=max_delta_x_px,
        max_abs_delta_y_px=max_abs_delta_y_px,
    )
    matched = match_descriptors_locally(
        described1.keypoints,
        described1.descriptors,
        described2.keypoints,
        described2.descriptors,
        search_radius_x=max(abs(min_delta_x), abs(max_delta_x)),
        search_radius_y=max(abs(min_delta_y), abs(max_delta_y)),
        min_delta_x=min_delta_x,
        max_delta_x=max_delta_x,
        min_delta_y=min_delta_y,
        max_delta_y=max_delta_y,
        ratio=match_ratio,
    )
    matches = matched.matches
    if len(matches) < 8:
        raise ValueError(
            f"two-view reconstruction needs at least 8 matches; found {len(matches)}"
        )
    descriptor_distances = np.linalg.norm(
        described1.descriptors[matches[:, 0]]
        - described2.descriptors[matches[:, 1]],
        axis=1,
    )
    matches = matches[np.argsort(descriptor_distances)[:max_quality_matches]]
    points1 = described1.keypoints[matches[:, 0]]
    points2 = _refine_right_points_subpixel(
        image1,
        image2,
        points1,
        described2.keypoints[matches[:, 1]],
        radius=descriptor_radius,
    )
    intrinsic1 = np.asarray(first["K"], dtype=np.float64)
    intrinsic2 = np.asarray(second["K"], dtype=np.float64)
    indices = np.arange(len(matches), dtype=np.int64)
    inverse1 = np.linalg.inv(intrinsic1)
    inverse2 = np.linalg.inv(intrinsic2)

    def fit(sample: np.ndarray) -> np.ndarray:
        return essential_from_correspondences(
            points1[sample],
            points2[sample],
            intrinsic1,
            intrinsic2,
        )

    def residuals(model: np.ndarray, sample: np.ndarray) -> np.ndarray:
        fundamental = inverse2.T @ model @ inverse1
        return symmetric_epipolar_distances(fundamental, points1[sample], points2[sample])

    result = ransac(
        indices,
        sample_size=8,
        fit_model=fit,
        residuals=residuals,
        threshold=EPIPOLAR_RANSAC_THRESHOLD_PX,
        max_trials=1600,
        seed=260925,
    )
    ransac_inliers = result.inlier_mask
    inlier_points1 = points1[ransac_inliers]
    inlier_points2 = points2[ransac_inliers]
    pose = estimate_relative_pose(
        inlier_points1,
        inlier_points2,
        intrinsic1,
        intrinsic2,
        essential=result.model,
    )
    pose = refine_relative_pose(
        pose,
        inlier_points1,
        inlier_points2,
        intrinsic1,
        intrinsic2,
    )
    match_stages = {
        "detected_view1": int(len(keypoints1)),
        "detected_view2": int(len(keypoints2)),
        "descriptors_view1": int(len(described1.keypoints)),
        "descriptors_view2": int(len(described2.keypoints)),
        "matches_before_ratio": matched.diagnostics.matches_before_ratio,
        "matches_after_ratio": matched.diagnostics.matches_after_ratio,
        "matches_after_mutual_check": matched.diagnostics.matches_after_mutual_check,
        "matches_after_quality_filter": int(len(matches)),
        "ransac_inliers": int(np.sum(ransac_inliers)),
    }
    return TwoViewEstimate(
        frame_pair=(str(first["id"]), str(second["id"])),
        image1=image1,
        image2=image2,
        points1=points1,
        points2=points2,
        ransac_inliers=ransac_inliers,
        pose=pose,
        match_stages=match_stages,
        keypoints={
            "view1": int(len(keypoints1)),
            "view2": int(len(keypoints2)),
            "described_view1": int(len(described1.keypoints)),
            "described_view2": int(len(described2.keypoints)),
        },
        ransac_iterations=result.iterations,
    )


def _score_two_view_estimate(
    artifacts: Path,
    scene_root: Path,
    first: dict[str, Any],
    second: dict[str, Any],
    estimate: TwoViewEstimate,
    *,
    artifact_suffix: str,
    runtime_seconds: float,
) -> dict[str, Any]:
    intrinsic1 = np.asarray(first["K"], dtype=np.float64)
    intrinsic2 = np.asarray(second["K"], dtype=np.float64)
    truth_rotation1 = np.asarray(first["R_world_to_camera"], dtype=np.float64)
    truth_translation1 = np.asarray(first["t_world_to_camera_m"], dtype=np.float64)
    truth_rotation2 = np.asarray(second["R_world_to_camera"], dtype=np.float64)
    truth_translation2 = np.asarray(second["t_world_to_camera_m"], dtype=np.float64)
    truth_fundamental = fundamental_from_poses(
        intrinsic1,
        truth_rotation1,
        truth_translation1,
        intrinsic2,
        truth_rotation2,
        truth_translation2,
    )
    truth_errors = symmetric_epipolar_distances(
        truth_fundamental,
        estimate.points1,
        estimate.points2,
    )
    candidate_truth_inliers = truth_errors < GROUND_TRUTH_F_THRESHOLD_PX
    ransac_inliers = estimate.ransac_inliers
    inlier_points1 = estimate.points1[ransac_inliers]
    inlier_points2 = estimate.points2[ransac_inliers]
    truth_relative_rotation = truth_rotation2 @ truth_rotation1.T
    truth_relative_translation = (
        truth_translation2 - truth_relative_rotation @ truth_translation1
    )
    reconstructed = triangulate_points(
        inlier_points1,
        inlier_points2,
        intrinsic1,
        np.eye(3),
        np.zeros(3),
        intrinsic2,
        estimate.pose.rotation,
        estimate.pose.translation,
    )
    depth1 = np.load(scene_root / first["depth_path"], allow_pickle=False)
    normals1 = np.load(scene_root / first["normal_path"], allow_pickle=False)
    rounded = np.rint(inlier_points1).astype(np.int64)
    truth_depth = depth1[rounded[:, 1], rounded[:, 0]].astype(np.float64)
    truth_camera1 = surface_samples_from_depth(
        depth1,
        normals1,
        intrinsic1,
        np.eye(3),
        np.zeros(3),
        stride=1,
    )[0]
    width = depth1.shape[1]
    truth_selected = truth_camera1[rounded[:, 1] * width + rounded[:, 0]]
    scale, rotation, translation = umeyama_sim3(reconstructed, truth_selected)
    aligned = (scale * (rotation @ reconstructed.T)).T + translation
    triangulation_rmse = float(
        np.sqrt(np.mean(np.sum((aligned - truth_selected) ** 2, axis=1)))
    )
    rotation_error = rotation_error_degrees(
        estimate.pose.rotation,
        truth_relative_rotation,
    )
    translation_error = _translation_direction_error(
        estimate.pose.translation,
        truth_relative_translation,
    )
    _write_match_svg(
        artifacts
        / (
            "two_view_matches.svg"
            if artifact_suffix == "adjacent"
            else f"two_view_matches_{artifact_suffix}.svg"
        ),
        estimate.image1,
        estimate.image2,
        estimate.points1,
        estimate.points2,
        candidate_truth_inliers,
    )
    _write_failure_sweep(
        artifacts
        / (
            "failure_sweep.csv"
            if artifact_suffix == "adjacent"
            else f"failure_sweep_{artifact_suffix}.csv"
        ),
        [
            {
                "parameter": "ground_truth_depth_min_m",
                "value": float(np.min(truth_depth)),
                "metric": "triangulated_point_rmse_m",
                "measurement": triangulation_rmse,
            },
            {
                "parameter": "ground_truth_depth_max_m",
                "value": float(np.max(truth_depth)),
                "metric": "inlier_ratio",
                "measurement": float(np.mean(ransac_inliers)),
            },
        ],
    )
    accepted_truth_inliers = candidate_truth_inliers[ransac_inliers]
    return {
        "frame_pair": list(estimate.frame_pair),
        "keypoints": estimate.keypoints,
        "match_stages": estimate.match_stages,
        "match_count": int(len(estimate.points1)),
        "accepted_match_count": int(np.sum(ransac_inliers)),
        "candidate_ground_truth_f_inlier_count": int(np.sum(candidate_truth_inliers)),
        "candidate_ground_truth_f_inlier_ratio": float(np.mean(candidate_truth_inliers)),
        "ground_truth_f_inlier_count": int(np.sum(accepted_truth_inliers)),
        "ground_truth_f_inlier_ratio": float(np.mean(accepted_truth_inliers)),
        "ransac_inlier_count": int(np.sum(ransac_inliers)),
        "ransac_inlier_ratio": float(np.mean(ransac_inliers)),
        "rotation_error_deg": float(rotation_error),
        "translation_direction_error_deg": float(translation_error),
        "triangulated_point_rmse_m_after_scale_alignment": triangulation_rmse,
        "relative_pose_refinement": "robust_epipolar_least_squares",
        "ransac_iterations": estimate.ransac_iterations,
        "runtime_seconds": runtime_seconds,
    }


def _run_frame_pair(
    artifacts: Path,
    scene_root: Path,
    manifest: dict[str, Any],
    profile: str,
    pair: tuple[int, int],
    *,
    artifact_suffix: str,
    min_delta_x_px: float,
    max_delta_x_px: float,
    max_abs_delta_y_px: float,
    match_ratio: float,
    max_quality_matches: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    first = manifest["frames"][pair[0]]
    second = manifest["frames"][pair[1]]
    estimate = estimate_two_view_orbit_pair(
        scene_root,
        first,
        second,
        profile,
        min_delta_x_px=min_delta_x_px,
        max_delta_x_px=max_delta_x_px,
        max_abs_delta_y_px=max_abs_delta_y_px,
        match_ratio=match_ratio,
        max_quality_matches=max_quality_matches,
    )
    scored = _score_two_view_estimate(
        artifacts,
        scene_root,
        first,
        second,
        estimate,
        artifact_suffix=artifact_suffix,
        runtime_seconds=time.perf_counter() - started,
    )
    scored["profile"] = profile
    return scored


def run_two_view_orbit(
    artifacts: Path,
    profile: str = "smoke",
    *,
    min_delta_x_px: float = DEFAULT_MIN_MATCH_DELTA_X_PX,
    max_delta_x_px: float = DEFAULT_MAX_MATCH_DELTA_X_PX,
    max_abs_delta_y_px: float = DEFAULT_MAX_MATCH_DELTA_Y_PX,
    match_ratio: float = DEFAULT_MATCH_RATIO,
    max_quality_matches: int = DEFAULT_MAX_QUALITY_MATCHES,
) -> dict[str, Any]:
    """Run the two-view feature/geometry chain and return measured metrics."""
    started = time.perf_counter()
    artifacts.mkdir(parents=True, exist_ok=True)
    scene_root = artifacts / "orbit-scene"
    manifest = generate_orbit_scene(scene_root, profile)
    record = _run_frame_pair(
        artifacts,
        scene_root,
        manifest,
        profile,
        (0, 1),
        artifact_suffix="adjacent",
        min_delta_x_px=min_delta_x_px,
        max_delta_x_px=max_delta_x_px,
        max_abs_delta_y_px=max_abs_delta_y_px,
        match_ratio=match_ratio,
        max_quality_matches=max_quality_matches,
    )
    if profile == "full":
        record["widest_baseline"] = _run_frame_pair(
            artifacts,
            scene_root,
            manifest,
            profile,
            (0, len(manifest["frames"]) - 1),
            artifact_suffix="widest_baseline",
            min_delta_x_px=min_delta_x_px,
            max_delta_x_px=max_delta_x_px,
            max_abs_delta_y_px=max_abs_delta_y_px,
            match_ratio=match_ratio,
            max_quality_matches=max_quality_matches,
        )
    artifact_count, artifact_tree_sha256 = _tree_digest(artifacts)
    record.update(
        {
            "total_runtime_seconds": time.perf_counter() - started,
            "artifact_count": artifact_count,
            "artifact_tree_sha256": artifact_tree_sha256,
            "manifest_sha256": hashlib.sha256(
                (scene_root / "manifest.json").read_bytes()
            ).hexdigest(),
            "generic_match_parameters": {
                "min_delta_x_px": min_delta_x_px,
                "max_delta_x_px": max_delta_x_px,
                "max_abs_delta_y_px": max_abs_delta_y_px,
                "match_ratio": match_ratio,
                "max_quality_matches": max_quality_matches,
                "epipolar_ransac_threshold_px": EPIPOLAR_RANSAC_THRESHOLD_PX,
            },
        }
    )
    return record


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    result.add_argument("--artifacts", type=Path, required=True)
    result.add_argument("--output", type=Path)
    result.add_argument(
        "--min-delta-x-px",
        type=float,
        default=DEFAULT_MIN_MATCH_DELTA_X_PX,
    )
    result.add_argument(
        "--max-delta-x-px",
        type=float,
        default=DEFAULT_MAX_MATCH_DELTA_X_PX,
    )
    result.add_argument(
        "--max-abs-delta-y-px",
        type=float,
        default=DEFAULT_MAX_MATCH_DELTA_Y_PX,
    )
    result.add_argument("--match-ratio", type=float, default=DEFAULT_MATCH_RATIO)
    result.add_argument(
        "--max-quality-matches",
        type=int,
        default=DEFAULT_MAX_QUALITY_MATCHES,
    )
    return result


def main() -> int:
    args = parser().parse_args()
    record = run_two_view_orbit(
        args.artifacts,
        args.profile,
        min_delta_x_px=args.min_delta_x_px,
        max_delta_x_px=args.max_delta_x_px,
        max_abs_delta_y_px=args.max_abs_delta_y_px,
        match_ratio=args.match_ratio,
        max_quality_matches=args.max_quality_matches,
    )
    payload = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
