#!/usr/bin/env python3
"""Run two-view feature matching and reconstruction on the orbit scene."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from camera.pose import fundamental_from_poses
from evaluation.pose_metrics import rotation_error_degrees, umeyama_sim3
from features.describe import describe_patches
from features.detect import detect_harris
from features.match import match_descriptors
from geometry.epipolar import (
    estimate_relative_pose,
    fundamental_from_correspondences,
    symmetric_epipolar_distances,
)
from geometry.ransac import ransac
from geometry.triangulate import triangulate_points
from scene.ground_truth import surface_samples_from_depth
from scene.orbit import generate_orbit_scene


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


def run_two_view_orbit(artifacts: Path, profile: str = "smoke") -> dict[str, Any]:
    """Run the two-view feature/geometry chain and return measured metrics."""
    artifacts.mkdir(parents=True, exist_ok=True)
    scene_root = artifacts / "orbit-scene"
    manifest = generate_orbit_scene(scene_root, profile)
    first = manifest["frames"][0]
    second = manifest["frames"][1]
    image1 = _read_pgm(scene_root / first["image_path"])
    image2 = _read_pgm(scene_root / second["image_path"])
    keypoints1 = detect_harris(image1, max_keypoints=500, min_distance=2)
    keypoints2 = detect_harris(image2, max_keypoints=500, min_distance=2)
    described1 = describe_patches(image1, keypoints1, radius=4)
    described2 = describe_patches(image2, keypoints2, radius=4)
    matches = match_descriptors(described1.descriptors, described2.descriptors, ratio=0.7)
    if len(matches) < 8:
        raise ValueError(
            f"two-view reconstruction needs at least 8 matches; found {len(matches)}"
        )
    points1 = described1.keypoints[matches[:, 0]]
    points2 = described2.keypoints[matches[:, 1]]
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
    truth_errors = symmetric_epipolar_distances(truth_fundamental, points1, points2)
    truth_inliers = truth_errors < 0.75

    indices = np.arange(len(matches), dtype=np.int64)

    def fit(sample: np.ndarray) -> np.ndarray:
        return fundamental_from_correspondences(points1[sample], points2[sample])

    def residuals(model: np.ndarray, sample: np.ndarray) -> np.ndarray:
        return symmetric_epipolar_distances(model, points1[sample], points2[sample])

    result = ransac(
        indices,
        sample_size=8,
        fit_model=fit,
        residuals=residuals,
        threshold=0.25,
        max_trials=800,
        seed=260925,
    )
    ransac_inliers = result.inlier_mask
    inlier_points1 = points1[ransac_inliers]
    inlier_points2 = points2[ransac_inliers]
    pose = estimate_relative_pose(inlier_points1, inlier_points2, intrinsic1, intrinsic2)
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
        pose.rotation,
        pose.translation,
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
    rotation_error = rotation_error_degrees(pose.rotation, truth_relative_rotation)
    translation_error = _translation_direction_error(
        pose.translation,
        truth_relative_translation,
    )
    _write_match_svg(
        artifacts / "two_view_matches.svg",
        image1,
        image2,
        points1,
        points2,
        truth_inliers,
    )
    _write_failure_sweep(
        artifacts / "failure_sweep.csv",
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
    artifact_count, artifact_tree_sha256 = _tree_digest(artifacts)
    return {
        "profile": profile,
        "frame_pair": [first["id"], second["id"]],
        "keypoints": {
            "view1": int(len(keypoints1)),
            "view2": int(len(keypoints2)),
            "described_view1": int(len(described1.keypoints)),
            "described_view2": int(len(described2.keypoints)),
        },
        "match_count": int(len(matches)),
        "ground_truth_f_inlier_count": int(np.sum(truth_inliers)),
        "ground_truth_f_inlier_ratio": float(np.mean(truth_inliers)),
        "ransac_inlier_count": int(np.sum(ransac_inliers)),
        "ransac_inlier_ratio": float(np.mean(ransac_inliers)),
        "rotation_error_deg": float(rotation_error),
        "translation_direction_error_deg": float(translation_error),
        "triangulated_point_rmse_m_after_scale_alignment": triangulation_rmse,
        "artifact_count": artifact_count,
        "artifact_tree_sha256": artifact_tree_sha256,
        "manifest_sha256": hashlib.sha256(
            (scene_root / "manifest.json").read_bytes()
        ).hexdigest(),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    result.add_argument("--artifacts", type=Path, required=True)
    result.add_argument("--output", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    record = run_two_view_orbit(args.artifacts, args.profile)
    payload = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
