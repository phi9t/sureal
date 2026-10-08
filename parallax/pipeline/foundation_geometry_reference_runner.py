"""Offline VGGT and Depth Anything 3 maintained-reference execution for module 12."""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import time
from typing import Any
import uuid

import numpy as np

from contracts import (
    ROOT,
    canonical_json,
    ensure_finite,
    load_json,
    selected_gpu_device,
    sha256_file,
    validate_json_schema_instance,
    validate_run_id,
    write_json,
)
from environment_manifest import environment_tree_manifest
from mvs_reference_runner import _gpu_hardware, _peak_cpu_memory_bytes, _run_monitored
from reference_runner import _hash_tree, _inspect_image, _require_regular_file, _secure_directory
from reference_scene import _render_implicit_sphere, generate_implicit_surface_scene


ADAPTER = "foundation-geometry"
IMAGE = "surflo-insula:cuda13.2.1"
VGGT_METHOD = "vggt/direct"
DA3_METHOD = "da3-base/camera-head"
VGGT_SOURCE_COMMIT = "a288dd0f14786c93483e45524328726ab7b1b4ce"
DA3_SOURCE_COMMIT = "3d835ec1a5802d64a8b8b15f817a1ab54809bfe4"
METHODS = (VGGT_METHOD, DA3_METHOD)
IMAGE_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
SUPPORT_CONTRACT = {
    "prediction_domain": "input-visible-pixels",
    "model_output": "deterministic-feed-forward-cameras-depth-and-pointmaps",
    "hidden_scene_prediction_count": 0,
    "complete_scene_samples": 0,
    "completion_claim": "none",
    "posterior_sampling_claim": "none",
}
REFERENCE_IMPLEMENTATION = (
    "pipeline/cli.py",
    "pipeline/contracts.py",
    "pipeline/environment_manifest.py",
    "pipeline/reference_runner.py",
    "pipeline/foundation_geometry_reference_runner.py",
    "pipeline/reference_scene.py",
    "insulas/surflo-foundation/run-foundation-models.py",
    "foundation-models.lock.json",
    "reference-result.schema.json",
    "shared-scene.json",
    "reference-adapters.json",
)


def _prepare_reference_scene(
    root: Path, scene: dict[str, Any], profile: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create evaluator truth and a physically separate RGB-only model input."""
    evaluation_root = root / "evaluation"
    evidence_root = root / "evidence"
    full_angles = [float(value) for value in range(-80, 81, 10)] + [180.0]
    evaluation = generate_implicit_surface_scene(
        evaluation_root,
        scene,
        profile,
        context_angles_override=full_angles if profile == "full" else None,
    )
    (evidence_root / "images").mkdir(parents=True)

    frames = evaluation["context_frames"]
    for frame in frames:
        source = evaluation_root / frame["image_path"]
        destination = evidence_root / "images" / f"{frame['id']}.png"
        shutil.copyfile(source, destination)

    if profile == "smoke":
        primary_case_id = "views-5"
        case_indices = [
            ("views-1-monocular", [2], "view-count", "not-applicable", "canonical"),
            ("views-2-high-overlap", [1, 2], "overlap", "high", "canonical"),
            ("views-2-low-overlap", [0, 4], "overlap", "low", "canonical"),
            ("views-3", [0, 2, 4], "view-count", "mixed", "canonical"),
            ("views-5", [0, 1, 2, 3, 4], "view-count", "mixed", "canonical"),
            ("views-5-permuted", [2, 0, 4, 1, 3], "order", "mixed", "permuted"),
        ]
    elif profile == "full":
        primary_case_id = "views-16"
        nested = [8, 9, 7, 10, 6, 11, 5, 12, 4, 13, 3, 14, 2, 15, 1, 16]
        case_indices = [
            ("views-1-monocular", nested[:1], "view-count", "not-applicable", "canonical"),
            ("views-2", nested[:2], "view-count", "high", "canonical"),
            ("views-4", nested[:4], "view-count", "mixed", "canonical"),
            ("views-8", nested[:8], "view-count", "mixed", "canonical"),
            ("views-16", nested[:16], "view-count", "mixed", "canonical"),
            ("views-2-high-overlap", [8, 9], "overlap", "high", "canonical"),
            ("views-2-medium-overlap", [6, 10], "overlap", "medium", "canonical"),
            ("views-2-low-overlap", [2, 14], "overlap", "low", "canonical"),
            ("views-2-disconnected", [8, 17], "overlap", "disconnected", "canonical"),
            ("views-8-permuted", list(reversed(nested[:8])), "order", "mixed", "permuted"),
        ]
    else:
        raise ValueError(f"unknown foundation-geometry profile: {profile}")

    cases = []
    for case_id, indices, family, overlap, order in case_indices:
        selected = [frames[index] for index in indices]
        image_paths = [f"images/{frame['id']}.png" for frame in selected]
        cases.append(
            {
                "id": case_id,
                "frame_ids": [frame["id"] for frame in selected],
                "image_paths": image_paths,
                "image_sha256": [
                    sha256_file(evidence_root / image_path) for image_path in image_paths
                ],
                "sweep": {
                    "family": family,
                    "view_count": len(indices),
                    "overlap": overlap,
                    "order": order,
                    "surface_slices": ["observed", "unseen"],
                },
            }
        )
    evidence = {
        "schema_version": 2,
        "profile": profile,
        "prediction_input": "ordered unposed RGB only",
        "reference_view_index": 0,
        "primary_case_id": primary_case_id,
        "original_size_hw": [
            int(evaluation["intrinsics"]["height"]),
            int(evaluation["intrinsics"]["width"]),
        ],
        "cases": cases,
    }
    (evidence_root / "manifest.json").write_bytes(canonical_json(evidence))
    return evaluation, evidence


def _fit_similarity(source: np.ndarray, target: np.ndarray) -> dict[str, Any]:
    """Fit ``target = scale * rotation @ source + translation`` by Umeyama."""
    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3:
        raise ValueError("similarity alignment requires matching Nx3 point arrays")
    if len(source) < 2 or not np.isfinite(source).all() or not np.isfinite(target).all():
        raise ValueError("similarity alignment requires at least two finite correspondences")
    source_center = np.mean(source, axis=0)
    target_center = np.mean(target, axis=0)
    source_zero = source - source_center
    target_zero = target - target_center
    variance = float(np.mean(np.sum(source_zero * source_zero, axis=1)))
    if variance <= np.finfo(np.float64).eps:
        raise ValueError("similarity alignment source is degenerate")
    covariance = target_zero.T @ source_zero / len(source)
    left, singular_values, right_transpose = np.linalg.svd(covariance)
    signs = np.ones(3)
    signs[-1] = 1.0 if np.linalg.det(left @ right_transpose) >= 0.0 else -1.0
    rotation = left @ np.diag(signs) @ right_transpose
    scale = float(np.sum(singular_values * signs) / variance)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("similarity alignment produced a non-positive scale")
    translation = target_center - scale * (rotation @ source_center)
    aligned = scale * (source @ rotation.T) + translation
    rmse = float(np.sqrt(np.mean(np.sum((aligned - target) ** 2, axis=1))))
    return {
        "aligned": aligned,
        "scale": scale,
        "rotation": rotation,
        "translation": translation,
        "rmse": rmse,
    }


def _fit_rigid(source: np.ndarray, target: np.ndarray) -> dict[str, Any]:
    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3:
        raise ValueError("rigid alignment requires matching Nx3 point arrays")
    source_center = np.mean(source, axis=0)
    target_center = np.mean(target, axis=0)
    covariance = (target - target_center).T @ (source - source_center)
    left, _, right_transpose = np.linalg.svd(covariance)
    signs = np.ones(3)
    signs[-1] = 1.0 if np.linalg.det(left @ right_transpose) >= 0.0 else -1.0
    rotation = left @ np.diag(signs) @ right_transpose
    translation = target_center - rotation @ source_center
    aligned = source @ rotation.T + translation
    return {
        "aligned": aligned,
        "rotation": rotation,
        "translation": translation,
        "rmse": float(np.sqrt(np.mean(np.sum((aligned - target) ** 2, axis=1)))),
    }


def _fit_pose_alignment(
    predicted_centers: np.ndarray,
    predicted_rotations: np.ndarray,
    truth_centers: np.ndarray,
    truth_rotations: np.ndarray,
    *,
    allow_scale: bool,
    predicted_points: np.ndarray | None = None,
    truth_points: np.ndarray | None = None,
) -> dict[str, Any]:
    """Fit a world-frame transform while using camera orientation to fix rotation.

    Camera centers alone leave rotation about a two-view baseline undefined.  The
    predicted and truth camera orientations determine the global rotation; center
    spread determines scale when possible.  A monocular condition uses declared
    evaluator point correspondences only to determine scale.
    """
    predicted_centers = np.asarray(predicted_centers, dtype=np.float64)
    predicted_rotations = np.asarray(predicted_rotations, dtype=np.float64)
    truth_centers = np.asarray(truth_centers, dtype=np.float64)
    truth_rotations = np.asarray(truth_rotations, dtype=np.float64)
    if (
        predicted_centers.shape != truth_centers.shape
        or predicted_centers.ndim != 2
        or predicted_centers.shape[1] != 3
        or predicted_rotations.shape != truth_rotations.shape
        or predicted_rotations.shape != (len(predicted_centers), 3, 3)
        or not np.isfinite(predicted_centers).all()
        or not np.isfinite(truth_centers).all()
        or not np.isfinite(predicted_rotations).all()
        or not np.isfinite(truth_rotations).all()
    ):
        raise ValueError("pose alignment requires matching finite centers and rotations")
    if not len(predicted_centers):
        raise ValueError("pose alignment requires at least one camera")

    desired_rotations = np.einsum(
        "nij,nkj->nik", truth_rotations, predicted_rotations
    )
    left, _, right_transpose = np.linalg.svd(np.sum(desired_rotations, axis=0))
    signs = np.ones(3)
    signs[-1] = 1.0 if np.linalg.det(left @ right_transpose) >= 0.0 else -1.0
    rotation = left @ np.diag(signs) @ right_transpose
    rotated_centers = predicted_centers @ rotation.T
    scale = 1.0
    scale_source = "fixed-unit-scale"
    if allow_scale:
        source_zero = rotated_centers - np.mean(rotated_centers, axis=0)
        target_zero = truth_centers - np.mean(truth_centers, axis=0)
        denominator = float(np.sum(source_zero * source_zero))
        if denominator > np.finfo(np.float64).eps:
            scale = float(np.sum(source_zero * target_zero) / denominator)
            scale_source = "camera-center-spread"
        else:
            if predicted_points is None or truth_points is None:
                raise ValueError(
                    "monocular similarity alignment requires evaluator point correspondences"
                )
            source_points, target_points = _sample_correspondences(
                predicted_points, truth_points
            )
            rotated_points = source_points @ rotation.T
            source_zero = rotated_points - np.mean(rotated_points, axis=0)
            target_zero = target_points - np.mean(target_points, axis=0)
            denominator = float(np.sum(source_zero * source_zero))
            if denominator <= np.finfo(np.float64).eps:
                raise ValueError("monocular similarity scale correspondences are degenerate")
            scale = float(np.sum(source_zero * target_zero) / denominator)
            scale_source = "evaluator-visible-point-correspondences"
        if not math.isfinite(scale) or scale <= 0.0:
            raise ValueError("pose alignment produced a non-positive scale")
    translation = np.mean(truth_centers - scale * rotated_centers, axis=0)
    aligned = scale * rotated_centers + translation
    return {
        "aligned": aligned,
        "scale": scale,
        "scale_source": scale_source,
        "rotation": rotation,
        "translation": translation,
        "rmse": float(np.sqrt(np.mean(np.sum((aligned - truth_centers) ** 2, axis=1)))),
    }


def _score_aligned_geometry(
    predicted_centers: np.ndarray,
    predicted_points: np.ndarray,
    truth_centers: np.ndarray,
    truth_points: np.ndarray,
) -> dict[str, dict[str, float]]:
    """Score corresponding cameras/points without silently choosing a gauge."""
    predicted_centers = np.asarray(predicted_centers, dtype=np.float64)
    predicted_points = np.asarray(predicted_points, dtype=np.float64)
    truth_centers = np.asarray(truth_centers, dtype=np.float64)
    truth_points = np.asarray(truth_points, dtype=np.float64)
    rigid = _fit_rigid(predicted_centers, truth_centers)
    similarity = _fit_similarity(predicted_centers, truth_centers)

    raw_point_rmse = float(
        np.sqrt(np.mean(np.sum((predicted_points - truth_points) ** 2, axis=1)))
    )
    rigid_points = predicted_points @ rigid["rotation"].T + rigid["translation"]
    rigid_point_rmse = float(
        np.sqrt(np.mean(np.sum((rigid_points - truth_points) ** 2, axis=1)))
    )
    similarity_points = (
        similarity["scale"] * (predicted_points @ similarity["rotation"].T)
        + similarity["translation"]
    )
    similarity_point_rmse = float(
        np.sqrt(np.mean(np.sum((similarity_points - truth_points) ** 2, axis=1)))
    )
    return {
        "raw": {
            "camera_center_rmse_m": float(
                np.sqrt(
                    np.mean(np.sum((predicted_centers - truth_centers) ** 2, axis=1))
                )
            ),
            "point_rmse_m": raw_point_rmse,
            "scale": 1.0,
        },
        "se3": {
            "camera_center_rmse_m": rigid["rmse"],
            "point_rmse_m": rigid_point_rmse,
            "scale": 1.0,
        },
        "sim3": {
            "camera_center_rmse_m": similarity["rmse"],
            "point_rmse_m": similarity_point_rmse,
            "scale": similarity["scale"],
        },
    }


def _camera_centers_and_rotations(extrinsics: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    extrinsics = np.asarray(extrinsics, dtype=np.float64)
    if extrinsics.ndim != 3 or extrinsics.shape[1:] != (4, 4):
        raise ValueError("camera extrinsics must be Nx4x4")
    rotations_w2c = extrinsics[:, :3, :3]
    centers = -np.einsum(
        "nij,nj->ni", rotations_w2c.transpose(0, 2, 1), extrinsics[:, :3, 3]
    )
    return centers, rotations_w2c.transpose(0, 2, 1)


def _rotation_errors_degrees(predicted: np.ndarray, target: np.ndarray) -> np.ndarray:
    relative = np.einsum("nij,nkj->nik", predicted, target)
    cosine = np.clip((np.trace(relative, axis1=1, axis2=2) - 1.0) / 2.0, -1.0, 1.0)
    return np.rad2deg(np.arccos(cosine))


def _pair_pose_auc(
    predicted_centers: np.ndarray,
    predicted_rotations: np.ndarray,
    truth_centers: np.ndarray,
    truth_rotations: np.ndarray,
    threshold_degrees: float = 30.0,
) -> float:
    errors = []
    for first in range(len(predicted_centers)):
        for second in range(first + 1, len(predicted_centers)):
            predicted_direction = predicted_rotations[first].T @ (
                predicted_centers[second] - predicted_centers[first]
            )
            truth_direction = truth_rotations[first].T @ (
                truth_centers[second] - truth_centers[first]
            )
            denominator = np.linalg.norm(predicted_direction) * np.linalg.norm(truth_direction)
            if denominator <= np.finfo(np.float64).eps:
                continue
            translation_error = float(
                np.rad2deg(
                    np.arccos(
                        np.clip(
                            np.dot(predicted_direction, truth_direction) / denominator,
                            -1.0,
                            1.0,
                        )
                    )
                )
            )
            predicted_relative = predicted_rotations[first].T @ predicted_rotations[second]
            truth_relative = truth_rotations[first].T @ truth_rotations[second]
            rotation_error = float(
                _rotation_errors_degrees(
                    predicted_relative[None], truth_relative[None]
                )[0]
            )
            errors.append(max(rotation_error, translation_error))
    if not errors:
        raise ValueError("relative-pose AUC requires at least one non-degenerate pair")
    values = np.asarray(errors)
    return float(np.mean(np.maximum(0.0, threshold_degrees - values)) / threshold_degrees)


def _sample_correspondences(
    predicted: np.ndarray, truth: np.ndarray, maximum: int = 8192
) -> tuple[np.ndarray, np.ndarray]:
    predicted = np.asarray(predicted, dtype=np.float64).reshape(-1, 3)
    truth = np.asarray(truth, dtype=np.float64).reshape(-1, 3)
    valid = np.isfinite(predicted).all(axis=1) & np.isfinite(truth).all(axis=1)
    predicted = predicted[valid]
    truth = truth[valid]
    if len(predicted) < 3:
        raise ValueError("geometry evaluation requires at least three finite points")
    if len(predicted) > maximum:
        indices = np.linspace(0, len(predicted) - 1, maximum, dtype=np.int64)
        predicted = predicted[indices]
        truth = truth[indices]
    return predicted, truth


def _sample_cloud(points: np.ndarray, maximum: int = 1024) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1)]
    points = np.unique(points, axis=0)
    if not len(points):
        raise ValueError("point-cloud metrics require at least one finite point")
    if len(points) > maximum:
        points = points[np.linspace(0, len(points) - 1, maximum, dtype=np.int64)]
    return points


def _nearest_distances(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    distances = []
    for start in range(0, len(source), 128):
        chunk = source[start : start + 128]
        squared = np.sum((chunk[:, None, :] - target[None, :, :]) ** 2, axis=-1)
        distances.append(np.sqrt(np.min(squared, axis=1)))
    return np.concatenate(distances)


def _bidirectional_cloud_metrics(
    predicted: np.ndarray, truth: np.ndarray, threshold_m: float
) -> dict[str, float | int]:
    """Compute point-cloud accuracy/completeness and their real harmonic F-score."""
    if not math.isfinite(threshold_m) or threshold_m <= 0.0:
        raise ValueError("point-cloud threshold must be finite and positive")
    predicted_cloud = _sample_cloud(predicted)
    truth_cloud = _sample_cloud(truth)
    accuracy_distances = _nearest_distances(predicted_cloud, truth_cloud)
    completeness_distances = _nearest_distances(truth_cloud, predicted_cloud)
    precision = float(np.mean(accuracy_distances <= threshold_m))
    recall = float(np.mean(completeness_distances <= threshold_m))
    fscore = (
        float(2.0 * precision * recall / (precision + recall))
        if precision + recall > 0.0
        else 0.0
    )
    accuracy_mean = float(np.mean(accuracy_distances))
    completeness_mean = float(np.mean(completeness_distances))
    return {
        "accuracy_mean_m": accuracy_mean,
        "completeness_mean_m": completeness_mean,
        "chamfer_l1_m": 0.5 * (accuracy_mean + completeness_mean),
        "precision": precision,
        "recall": recall,
        "fscore": fscore,
        "threshold_m": threshold_m,
        "predicted_points": int(len(predicted_cloud)),
        "truth_points": int(len(truth_cloud)),
    }


def _pointmap_metrics(
    predicted: np.ndarray,
    truth: np.ndarray,
    rigid: dict[str, Any],
    similarity: dict[str, Any],
    threshold_m: float,
) -> dict[str, float]:
    predicted, truth = _sample_correspondences(predicted, truth)
    raw = np.linalg.norm(predicted - truth, axis=1)
    rigid_points = predicted @ rigid["rotation"].T + rigid["translation"]
    rigid_error = np.linalg.norm(rigid_points - truth, axis=1)
    similarity_points = (
        similarity["scale"] * (predicted @ similarity["rotation"].T)
        + similarity["translation"]
    )
    similarity_error = np.linalg.norm(similarity_points - truth, axis=1)
    return {
        "raw_point_rmse_m": float(np.sqrt(np.mean(raw * raw))),
        "se3_point_rmse_m": float(np.sqrt(np.mean(rigid_error * rigid_error))),
        "sim3_point_rmse_m": float(
            np.sqrt(np.mean(similarity_error * similarity_error))
        ),
        "sim3_correspondence_error_mean_m": float(np.mean(similarity_error)),
        "sim3_correspondence_within_threshold": float(
            np.mean(similarity_error <= threshold_m)
        ),
        "correspondence_threshold_m": threshold_m,
        "evaluated_points": int(len(similarity_error)),
    }


def _apply_alignment(points: np.ndarray, alignment: dict[str, Any]) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    return (
        alignment["scale"] * (points @ alignment["rotation"].T)
        + alignment["translation"]
    )


def _confidence_coverage_curve(
    errors: np.ndarray, confidence: np.ndarray
) -> list[dict[str, float | int]]:
    errors = np.asarray(errors, dtype=np.float64).reshape(-1)
    confidence = np.asarray(confidence, dtype=np.float64).reshape(-1)
    valid = np.isfinite(errors) & np.isfinite(confidence)
    errors = errors[valid]
    confidence = confidence[valid]
    if not len(errors):
        raise ValueError("confidence coverage requires finite evaluated points")
    order = np.argsort(-confidence, kind="stable")
    curve = []
    for coverage in (0.25, 0.5, 0.75, 1.0):
        count = max(1, int(math.ceil(coverage * len(order))))
        selected = order[:count]
        curve.append(
            {
                "coverage": coverage,
                "selected_points": count,
                "confidence_threshold": float(confidence[selected[-1]]),
                "sim3_correspondence_error_mean_m": float(np.mean(errors[selected])),
            }
        )
    return curve


def _surface_truth_slices(
    evaluation_root: Path,
    evaluation: dict[str, Any],
    truth_centers: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    surface = evaluation["surface_truth"]
    points_path = evaluation_root / surface["points_path"]
    normals_path = evaluation_root / surface["normals_path"]
    if (
        sha256_file(points_path) != surface["points_sha256"]
        or sha256_file(normals_path) != surface["normals_sha256"]
    ):
        raise ValueError("surface truth hash mismatch")
    points = np.load(points_path, allow_pickle=False).astype(np.float64)
    normals = np.load(normals_path, allow_pickle=False).astype(np.float64)
    sight = truth_centers[:, None, :] - points[None, :, :]
    observed = np.any(np.sum(normals[None, :, :] * sight, axis=-1) > 0.0, axis=0)
    if not np.any(observed) or not np.any(~observed):
        raise ValueError("surface slices require both observed and unseen truth")
    return points[observed], points[~observed]


def _unseen_surface_metrics(
    predicted: np.ndarray, unseen_truth: np.ndarray, threshold_m: float
) -> dict[str, float | int]:
    predicted_cloud = _sample_cloud(predicted)
    truth_cloud = _sample_cloud(unseen_truth)
    distances = _nearest_distances(truth_cloud, predicted_cloud)
    return {
        "completeness_mean_m": float(np.mean(distances)),
        "recall": float(np.mean(distances <= threshold_m)),
        "threshold_m": threshold_m,
        "truth_points": int(len(truth_cloud)),
    }


def _direct_point_reprojection(
    points: np.ndarray, extrinsics: np.ndarray, intrinsics: np.ndarray
) -> dict[str, float | int]:
    points = np.asarray(points, dtype=np.float64)
    height, width = points.shape[1:3]
    rows, columns = np.meshgrid(
        np.arange(height, dtype=np.float64),
        np.arange(width, dtype=np.float64),
        indexing="ij",
    )
    errors = []
    positive_count = 0
    for index in range(len(points)):
        camera = (
            points[index] @ extrinsics[index, :3, :3].astype(np.float64).T
            + extrinsics[index, :3, 3]
        )
        valid = np.isfinite(camera).all(axis=-1) & (camera[..., 2] > 0.0)
        positive_count += int(np.count_nonzero(valid))
        if np.any(valid):
            projected_x = (
                intrinsics[index, 0, 0] * camera[..., 0] / camera[..., 2]
                + intrinsics[index, 0, 2]
            )
            projected_y = (
                intrinsics[index, 1, 1] * camera[..., 1] / camera[..., 2]
                + intrinsics[index, 1, 2]
            )
            errors.append(
                np.sqrt(
                    (projected_x[valid] - columns[valid]) ** 2
                    + (projected_y[valid] - rows[valid]) ** 2
                )
            )
    if not errors:
        return {
            "positive_depth_points": 0,
            "positive_depth_fraction": 0.0,
            "reprojection_mean_px": math.inf,
            "reprojection_max_px": math.inf,
        }
    values = np.concatenate(errors)
    return {
        "positive_depth_points": positive_count,
        "positive_depth_fraction": float(positive_count / np.prod(points.shape[:3])),
        "reprojection_mean_px": float(np.mean(values)),
        "reprojection_max_px": float(np.max(values)),
    }


def _truth_for_case(
    evaluation_root: Path,
    evaluation: dict[str, Any],
    frame_ids: list[str],
    height: int,
    width: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    frames = {frame["id"]: frame for frame in evaluation["context_frames"]}
    base = evaluation["intrinsics"]
    intrinsics = np.array(
        [
            [float(base["fx"]) * width / int(base["width"]), 0.0, (width - 1) / 2.0],
            [0.0, float(base["fy"]) * height / int(base["height"]), (height - 1) / 2.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    render_intrinsics = {
        "width": width,
        "height": height,
        "fx": intrinsics[0, 0],
        "fy": intrinsics[1, 1],
        "cx": intrinsics[0, 2],
        "cy": intrinsics[1, 2],
    }
    depths = []
    masks = []
    points = []
    centers = []
    rotations = []
    for frame_id in frame_ids:
        if frame_id not in frames:
            raise ValueError(f"unknown evaluation frame: {frame_id}")
        camera_to_world = np.asarray(frames[frame_id]["camera_to_world_model"], dtype=np.float64)
        _, mask, depth, normals = _render_implicit_sphere(
            render_intrinsics, camera_to_world, float(evaluation["sphere_radius_m"])
        )
        foreground = mask > 0
        depths.append(depth)
        masks.append(foreground)
        points.append(normals.astype(np.float64) * float(evaluation["sphere_radius_m"]))
        centers.append(camera_to_world[:3, 3])
        rotations.append(camera_to_world[:3, :3])
    return (
        np.asarray(depths),
        np.asarray(masks),
        np.asarray(points),
        np.asarray(centers),
        np.asarray(rotations),
    )


def _tree_manifest(root: Path, *, environment: bool = False) -> dict[str, Any]:
    if environment:
        return environment_tree_manifest(root)
    records: list[dict[str, Any]] = []
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            records.append({"path": relative, "symlink": os.readlink(path)})
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        record = {"path": relative, "size": size, "sha256": sha256_file(path)}
        records.append(record)
        total_bytes += size
    digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "root_kind": "source-tree",
        "tree_sha256": digest,
        "file_count": len(records),
        "byte_size": total_bytes,
        "files": records,
    }
    return manifest


def _tracked_source_manifest(checkout: Path) -> dict[str, Any]:
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    if status.returncode != 0 or status.stdout:
        raise ValueError("Depth Anything 3 source checkout is dirty")
    listed = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=checkout,
        capture_output=True,
        check=False,
    )
    if listed.returncode != 0:
        raise ValueError("cannot inventory Depth Anything 3 source checkout")
    records = []
    gitlinks = []
    for raw in listed.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            staged, raw_relative = raw.split(b"\t", 1)
            mode, object_id, stage = staged.decode("ascii").split(" ")
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError("malformed Depth Anything 3 tracked source entry") from error
        if stage != "0":
            raise ValueError("Depth Anything 3 source checkout has unresolved index stages")
        relative = raw_relative.decode("utf-8")
        if mode == "160000":
            record = {"path": relative, "mode": mode, "commit": object_id}
            records.append(record)
            gitlinks.append(record)
            continue
        path = checkout / relative
        if path.is_file():
            records.append(
                {
                    "path": relative,
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    records.sort(key=lambda item: item["path"])
    return {
        "schema_version": 1,
        "root_kind": "tracked-source-tree",
        "tree_sha256": hashlib.sha256(
            json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "file_count": len(records),
        "byte_size": sum(item.get("size", 0) for item in records),
        "files": records,
        "gitlinks": gitlinks,
    }


def _verify_model_cache(pathway_cache_root: Path) -> dict[str, Any]:
    lock = load_json(ROOT / "foundation-models.lock.json")
    if lock.get("schema_version") != 2 or set(lock.get("models", {})) != {
        "vggt",
        "depth-anything-3",
    }:
        raise ValueError("foundation model lock is malformed")
    repository = ROOT.parent
    build_lock = lock["environment"].get("build_lock", {})
    build_lock_path = repository / str(build_lock.get("path", ""))
    if (
        not build_lock_path.is_file()
        or sha256_file(build_lock_path) != build_lock.get("sha256")
    ):
        raise ValueError("Surflo foundation environment build lock mismatch")
    source_checkout = repository / "submodules/Depth-Anything-3"
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    if (
        completed.returncode != 0
        or completed.stdout.strip()
        != lock["models"]["depth-anything-3"]["source_commit"]
    ):
        raise ValueError("Depth Anything 3 source checkout does not match its lock")
    da3_source_manifest = _tracked_source_manifest(source_checkout)
    da3_lock = lock["models"]["depth-anything-3"]
    if (
        da3_source_manifest["tree_sha256"] != da3_lock["source_tree_sha256"]
        or da3_source_manifest["file_count"] != da3_lock["source_tree_file_count"]
        or da3_source_manifest["byte_size"] != da3_lock["source_tree_byte_size"]
        or da3_source_manifest["gitlinks"] != da3_lock["nested_gitlinks"]
    ):
        raise ValueError("Depth Anything 3 tracked source tree does not match its lock")
    cache_root = Path(
        os.environ.get(
            "SURFLO_INSULA_CACHE_ROOT",
            Path.home() / ".cache" / "surflo" / "insula-scout",
        )
    ).expanduser().resolve()
    paths: dict[str, Path] = {}
    for model_id, record in lock["models"].items():
        snapshot = cache_root / record["cache_path"] / "snapshots" / record["revision"]
        try:
            snapshot.resolve(strict=True).relative_to(cache_root)
        except (FileNotFoundError, ValueError) as error:
            raise ValueError(
                f"locked {model_id} snapshot is missing; run the explicit model fetch first"
            ) from error
        for filename, expected in record["files"].items():
            path = snapshot / filename
            if not path.is_file():
                raise ValueError(f"locked {model_id} file is missing: {filename}")
            if path.stat().st_size != expected["byte_size"]:
                raise ValueError(f"locked {model_id} file byte-size mismatch: {filename}")
            if sha256_file(path) != expected["sha256"]:
                raise ValueError(f"locked {model_id} file hash mismatch: {filename}")
        paths[model_id] = snapshot
    source_lock = lock["models"]["vggt"]["source_archive"]
    source_root = pathway_cache_root / "assets" / source_lock["id"]
    source_manifest_path = pathway_cache_root / "assets" / f"{source_lock['id']}.extraction.json"
    if not source_root.is_dir() or not source_manifest_path.is_file():
        raise ValueError("locked VGGT source is missing; run the explicit model fetch first")
    source_manifest = load_json(source_manifest_path)
    actual_vggt_source = _tree_manifest(source_root)
    if (
        actual_vggt_source["tree_sha256"] != source_lock["tree_sha256"]
        or actual_vggt_source["file_count"] != source_lock["tree_file_count"]
        or actual_vggt_source["byte_size"] != source_lock["tree_byte_size"]
        or source_manifest.get("tree_sha256") != source_lock["tree_sha256"]
    ):
        raise ValueError("VGGT source tree does not match its lock")
    environment_lock = lock["environment"]
    environment_root = cache_root / environment_lock["cache_path"]
    if not environment_root.is_dir():
        raise ValueError("Surflo foundation environment is missing; run `run.sh build` first")
    environment_manifest = _tree_manifest(environment_root, environment=True)
    if (
        environment_manifest["tree_sha256"] != environment_lock["tree_sha256"]
        or environment_manifest["file_count"] != environment_lock["file_count"]
        or environment_manifest["byte_size"] != environment_lock["byte_size"]
    ):
        raise ValueError("Surflo foundation environment does not match its byte lock")
    return {
        "models": paths,
        "sources": {
            "vggt": source_root,
            "depth-anything-3": source_checkout,
        },
        "source_manifests": {
            "vggt": actual_vggt_source,
            "depth-anything-3": da3_source_manifest,
        },
        "environment": {
            "root": environment_root,
            "manifest": environment_manifest,
        },
    }


def _container_path(host_path: Path, cache_root: Path) -> str:
    try:
        relative = host_path.resolve(strict=True).relative_to(cache_root.resolve(strict=True))
    except ValueError as error:
        raise ValueError(f"model snapshot escapes Surflo cache: {host_path}") from error
    return f"/cache/surflo/{relative.as_posix()}"


def _container_command(
    engine: str,
    image_id: str,
    staging: Path,
    cuda_cache: Path,
    execution_inputs: dict[str, Any],
    gpu_device: str,
) -> list[str]:
    repository = ROOT.parent.resolve()
    cache_root = Path(
        os.environ.get(
            "SURFLO_INSULA_CACHE_ROOT",
            Path.home() / ".cache" / "surflo" / "insula-scout",
        )
    ).expanduser().resolve()
    script = "/workspace/surflo/parallax/insulas/surflo-foundation/run-foundation-models.py"
    model_paths = execution_inputs["models"]
    source_paths = execution_inputs["sources"]
    command = [
        engine,
        "run",
        "--rm",
        "--network",
        "none",
        "--pull=never",
        "--gpus",
        f"device={gpu_device}",
        "--cidfile",
        str(staging / "container.cid"),
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        "HOME=/tmp",
        "-e",
        "HF_HUB_OFFLINE=1",
        "-e",
        "TRANSFORMERS_OFFLINE=1",
        "-e",
        "HF_HOME=/cache/surflo/huggingface",
        "-e",
        "CUDA_VISIBLE_DEVICES=0",
        "-e",
        "CUDA_CACHE_PATH=/cuda-cache",
        "-v",
        f"{repository}:/workspace/surflo:ro",
        "-v",
        f"{cache_root}:/cache/surflo:ro",
        "-v",
        f"{source_paths['vggt'].resolve()}:/opt/vggt:ro",
        "-v",
        f"{cuda_cache.resolve()}:/cuda-cache",
        "-v",
        f"{(staging / 'config').resolve()}:/config:ro",
        "-v",
        f"{(staging / 'evidence').resolve()}:/input:ro",
        "-v",
        f"{(staging / 'output').resolve()}:/output",
        image_id,
        "bash",
        "-lc",
        f"/cache/surflo/venv/bin/python {script} "
        "--input /input --output /output "
        "--vggt-source /opt/vggt "
        "--da3-source /workspace/surflo/submodules/Depth-Anything-3 "
        "--model-lock /workspace/surflo/parallax/foundation-models.lock.json "
        "--environment-manifest /config/environment-manifest.json "
        f"--vggt-model {_container_path(model_paths['vggt'], cache_root)} "
        f"--da3-model {_container_path(model_paths['depth-anything-3'], cache_root)}",
    ]
    return command


def _validate_archive(
    archive_path: Path, method_id: str, view_count: int, height: int, width: int
) -> dict[str, np.ndarray]:
    if stat.S_ISLNK(archive_path.lstat().st_mode) or not stat.S_ISREG(
        archive_path.lstat().st_mode
    ):
        raise ValueError(f"model archive is not a regular file: {archive_path.name}")
    required = {
        "confidence",
        "depth",
        "extrinsics_w2c",
        "intrinsics_px",
        "pointmap_depth",
    }
    if method_id == VGGT_METHOD:
        required |= {
            "pointmap_direct",
            "track_confidence",
            "track_queries",
            "track_visibility",
            "tracks",
        }
    with np.load(archive_path, allow_pickle=False) as archive:
        if set(archive.files) != required:
            raise ValueError(f"unexpected {method_id} archive members: {archive.files}")
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    expected_depth = (view_count, height, width)
    expected_points = (*expected_depth, 3)
    if arrays["depth"].shape != expected_depth or arrays["confidence"].shape != expected_depth:
        raise ValueError(f"{method_id} depth/confidence shape mismatch")
    if arrays["pointmap_depth"].shape != expected_points:
        raise ValueError(f"{method_id} pointmap shape mismatch")
    if arrays["extrinsics_w2c"].shape != (view_count, 4, 4):
        raise ValueError(f"{method_id} camera shape mismatch")
    if arrays["intrinsics_px"].shape != (view_count, 3, 3):
        raise ValueError(f"{method_id} intrinsics shape mismatch")
    if method_id == VGGT_METHOD:
        if arrays["pointmap_direct"].shape != expected_points:
            raise ValueError("VGGT direct pointmap shape mismatch")
        query_count = arrays["track_queries"].shape[0]
        if (
            arrays["track_queries"].shape != (query_count, 2)
            or arrays["tracks"].shape != (view_count, query_count, 2)
            or arrays["track_visibility"].shape != (view_count, query_count)
            or arrays["track_confidence"].shape != (view_count, query_count)
        ):
            raise ValueError("VGGT track output shape mismatch")
    for name, array in arrays.items():
        if array.dtype.kind in "fc" and not np.isfinite(array).all():
            raise ValueError(f"non-finite {method_id} archive member: {name}")
    if np.any(arrays["depth"] <= 0.0):
        raise ValueError(f"{method_id} depth must be finite and positive")
    rotations = arrays["extrinsics_w2c"][:, :3, :3].astype(np.float64)
    orthogonality = np.max(np.abs(rotations @ rotations.transpose(0, 2, 1) - np.eye(3)))
    determinants = np.linalg.det(rotations)
    if orthogonality > 5e-3 or np.max(np.abs(determinants - 1.0)) > 5e-3:
        raise ValueError(f"{method_id} camera rotations are invalid")
    if np.any(arrays["intrinsics_px"][:, (0, 1), (0, 1)] <= 0.0):
        raise ValueError(f"{method_id} focal lengths must be positive")
    return arrays


def _validated_track_record(
    method_id: str,
    case_id: str,
    case_record: dict[str, Any],
    arrays: dict[str, np.ndarray],
    frame_ids: list[str],
    height: int,
    width: int,
) -> dict[str, Any]:
    record = case_record.get("tracks")
    if method_id != VGGT_METHOD:
        if record != {"status": "unsupported"}:
            raise ValueError(f"unsupported track record mismatch: {method_id}/{case_id}")
        return {"status": "unsupported", "query_count": 0}
    if not isinstance(record, dict) or record.get("status") != "measured":
        raise ValueError(f"missing measured track record: {method_id}/{case_id}")
    expected_convention = {
        "order": "xy",
        "space": "processed input image pixels",
        "origin": "(0,0) is the center of the upper-left pixel",
        "pixel_center_lattice": "integer centers 0..W-1 and 0..H-1",
    }
    if (
        record.get("query_frame") != {"index": 0, "frame_id": frame_ids[0]}
        or record.get("coordinate_convention") != expected_convention
        or record.get("resolution_hw") != [height, width]
    ):
        raise ValueError(f"track coordinate record mismatch: {method_id}/{case_id}")
    semantics = {
        "track_queries": "reference-frame query xy coordinates",
        "tracks": "predicted xy coordinates for every frame and query",
        "track_visibility": "per-frame visibility scores",
        "track_confidence": "per-frame track confidence scores",
    }
    array_records = record.get("arrays")
    if not isinstance(array_records, dict) or set(array_records) != set(semantics):
        raise ValueError(f"track array record mismatch: {method_id}/{case_id}")
    for name, expected_semantics in semantics.items():
        expected = {
            "archive_member": name,
            "shape": list(arrays[name].shape),
            "dtype": str(arrays[name].dtype),
            "semantics": expected_semantics,
        }
        if array_records.get(name) != expected:
            raise ValueError(f"track array metadata mismatch: {method_id}/{case_id}/{name}")
    expected_scores = {
        "visibility": {
            "domain": "sigmoid score in [0,1]",
            "threshold": None,
            "semantics": "model estimate that the query is visible in each frame",
        },
        "confidence": {
            "domain": "sigmoid score in [0,1]",
            "threshold": None,
            "semantics": "model confidence in each predicted track coordinate",
        },
    }
    if any(record.get(name) != expected for name, expected in expected_scores.items()):
        raise ValueError(f"track score semantics mismatch: {method_id}/{case_id}")
    for name in ("track_visibility", "track_confidence"):
        if np.min(arrays[name]) < 0.0 or np.max(arrays[name]) > 1.0:
            raise ValueError(f"track score outside [0,1]: {method_id}/{case_id}/{name}")
    result = dict(record)
    result.update(
        {
            "query_count": int(arrays["track_queries"].shape[0]),
            "observed_score_ranges": {
                "visibility": [
                    float(np.min(arrays["track_visibility"])),
                    float(np.max(arrays["track_visibility"])),
                ],
                "confidence": [
                    float(np.min(arrays["track_confidence"])),
                    float(np.max(arrays["track_confidence"])),
                ],
            },
        }
    )
    return result


def _evaluate_case(
    staging: Path,
    evaluation: dict[str, Any],
    method_id: str,
    case_id: str,
    case_record: dict[str, Any],
    threshold_m: float,
) -> dict[str, Any]:
    frame_ids = case_record.get("frame_ids")
    processed_size = case_record.get("processed_size_hw")
    if (
        not isinstance(frame_ids, list)
        or not frame_ids
        or not isinstance(processed_size, list)
        or len(processed_size) != 2
    ):
        raise ValueError(f"malformed inference case metadata: {method_id}/{case_id}")
    height, width = (int(processed_size[0]), int(processed_size[1]))
    if height <= 0 or width <= 0:
        raise ValueError("processed image dimensions must be positive")
    archive_name = case_record.get("archive")
    if not isinstance(archive_name, str) or Path(archive_name).name != archive_name:
        raise ValueError("model archive name must be one safe path component")
    archive_path = _require_regular_file(staging, f"output/{archive_name}")
    arrays = _validate_archive(
        archive_path, method_id, len(frame_ids), height, width
    )
    tracks = _validated_track_record(
        method_id, case_id, case_record, arrays, frame_ids, height, width
    )
    truth_depth, foreground, truth_points, truth_centers, truth_rotations = _truth_for_case(
        staging / "evaluation", evaluation, frame_ids, height, width
    )
    predicted_centers, predicted_rotations = _camera_centers_and_rotations(
        arrays["extrinsics_w2c"]
    )
    correspondence_predicted = arrays["pointmap_depth"][foreground]
    correspondence_truth = truth_points[foreground]
    rigid = _fit_pose_alignment(
        predicted_centers,
        predicted_rotations,
        truth_centers,
        truth_rotations,
        allow_scale=False,
        predicted_points=correspondence_predicted,
        truth_points=correspondence_truth,
    )
    similarity = _fit_pose_alignment(
        predicted_centers,
        predicted_rotations,
        truth_centers,
        truth_rotations,
        allow_scale=True,
        predicted_points=correspondence_predicted,
        truth_points=correspondence_truth,
    )
    raw_center_error = np.linalg.norm(predicted_centers - truth_centers, axis=1)
    rigid_center_error = np.linalg.norm(rigid["aligned"] - truth_centers, axis=1)
    sim_center_error = np.linalg.norm(similarity["aligned"] - truth_centers, axis=1)
    raw_rotation = _rotation_errors_degrees(predicted_rotations, truth_rotations)
    rigid_rotation = _rotation_errors_degrees(
        np.einsum("ij,njk->nik", rigid["rotation"], predicted_rotations),
        truth_rotations,
    )
    sim_rotation = _rotation_errors_degrees(
        np.einsum("ij,njk->nik", similarity["rotation"], predicted_rotations),
        truth_rotations,
    )
    relative_pose_auc = (
        _pair_pose_auc(
            predicted_centers,
            predicted_rotations,
            truth_centers,
            truth_rotations,
            30.0,
        )
        if len(frame_ids) > 1
        else None
    )
    camera = {
        "raw_center_rmse_m": float(np.sqrt(np.mean(raw_center_error**2))),
        "se3_center_rmse_m": float(np.sqrt(np.mean(rigid_center_error**2))),
        "sim3_center_rmse_m": float(np.sqrt(np.mean(sim_center_error**2))),
        "sim3_scale": similarity["scale"],
        "raw_rotation_mean_deg": float(np.mean(raw_rotation)),
        "se3_rotation_mean_deg": float(np.mean(rigid_rotation)),
        "sim3_rotation_mean_deg": float(np.mean(sim_rotation)),
        "relative_pose_auc_30": relative_pose_auc,
        "relative_pose_auc_30_status": (
            "measured" if relative_pose_auc is not None else "unsupported-single-view"
        ),
    }
    first_extrinsic = arrays["extrinsics_w2c"][0].astype(np.float64)
    camera["first_camera_translation_residual"] = float(
        np.linalg.norm(first_extrinsic[:3, 3])
    )
    camera["first_camera_rotation_residual_deg"] = float(
        _rotation_errors_degrees(first_extrinsic[None, :3, :3], np.eye(3)[None])[0]
    )
    base_intrinsics = evaluation["intrinsics"]
    expected_focal = np.array(
        [
            float(base_intrinsics["fx"]) * width / int(base_intrinsics["width"]),
            float(base_intrinsics["fy"]) * height / int(base_intrinsics["height"]),
        ]
    )
    predicted_focal = arrays["intrinsics_px"][:, (0, 1), (0, 1)].astype(np.float64)
    camera["focal_relative_error_mean"] = float(
        np.mean(np.abs(predicted_focal - expected_focal) / expected_focal)
    )
    predicted_principal = arrays["intrinsics_px"][:, (0, 1), (2, 2)].astype(np.float64)
    expected_principal = np.array([(width - 1) / 2.0, (height - 1) / 2.0])
    camera["principal_point_error_px_mean"] = float(
        np.mean(np.linalg.norm(predicted_principal - expected_principal, axis=1))
    )
    predicted_depth = arrays["depth"].astype(np.float64)
    depth_valid = foreground & np.isfinite(predicted_depth) & (predicted_depth > 0.0)
    if np.count_nonzero(depth_valid) < 3:
        raise ValueError(f"{method_id}/{case_id} has insufficient valid foreground depth")
    truth_values = truth_depth[depth_valid].astype(np.float64)
    predicted_values = predicted_depth[depth_valid]
    raw_depth_error = predicted_values - truth_values
    sim_depth_error = similarity["scale"] * predicted_values - truth_values
    raw_ratio = np.maximum(
        predicted_values / truth_values, truth_values / predicted_values
    )
    scaled_values = similarity["scale"] * predicted_values
    sim_ratio = np.maximum(scaled_values / truth_values, truth_values / scaled_values)
    depth = {
        "foreground_valid_fraction": float(
            np.count_nonzero(depth_valid) / np.count_nonzero(foreground)
        ),
        "raw_rmse_m": float(np.sqrt(np.mean(raw_depth_error**2))),
        "raw_abs_rel": float(np.mean(np.abs(raw_depth_error) / truth_values)),
        "raw_delta_1_25": float(np.mean(raw_ratio < 1.25)),
        "sim3_scaled_rmse_m": float(np.sqrt(np.mean(sim_depth_error**2))),
        "sim3_scaled_abs_rel": float(
            np.mean(np.abs(sim_depth_error) / truth_values)
        ),
        "sim3_scaled_delta_1_25": float(np.mean(sim_ratio < 1.25)),
    }
    pointmap_depth = _pointmap_metrics(
        correspondence_predicted,
        correspondence_truth,
        rigid,
        similarity,
        threshold_m,
    )
    aligned_depth_points = _apply_alignment(correspondence_predicted, similarity)
    observed_truth, unseen_truth = _surface_truth_slices(
        staging / "evaluation", evaluation, truth_centers
    )
    scene_threshold_m = float(evaluation["sphere_radius_m"]) * 0.05
    pointmap_depth["surface_observed_metric"] = _bidirectional_cloud_metrics(
        aligned_depth_points, observed_truth, threshold_m
    )
    pointmap_depth["surface_observed_scene_normalized"] = (
        _bidirectional_cloud_metrics(
            aligned_depth_points, observed_truth, scene_threshold_m
        )
    )
    pointmap_depth["surface_unseen_metric"] = _unseen_surface_metrics(
        aligned_depth_points, unseen_truth, threshold_m
    )
    depth_correspondence_error = np.linalg.norm(
        aligned_depth_points - correspondence_truth, axis=1
    )
    pointmap_depth["confidence_coverage"] = _confidence_coverage_curve(
        depth_correspondence_error, arrays["confidence"][foreground]
    )
    pointmap_direct: dict[str, Any]
    if method_id == VGGT_METHOD:
        pointmap_direct = _pointmap_metrics(
            arrays["pointmap_direct"][foreground],
            truth_points[foreground],
            rigid,
            similarity,
            threshold_m,
        )
        disagreement = np.linalg.norm(
            arrays["pointmap_direct"].astype(np.float64)
            - arrays["pointmap_depth"].astype(np.float64),
            axis=-1,
        )
        pointmap_direct["depth_unprojection_disagreement_rmse"] = float(
            np.sqrt(np.mean(disagreement[foreground] ** 2))
        )
        aligned_direct_points = _apply_alignment(
            arrays["pointmap_direct"][foreground], similarity
        )
        pointmap_direct["surface_observed_metric"] = _bidirectional_cloud_metrics(
            aligned_direct_points, observed_truth, threshold_m
        )
        pointmap_direct["surface_observed_scene_normalized"] = (
            _bidirectional_cloud_metrics(
                aligned_direct_points, observed_truth, scene_threshold_m
            )
        )
        pointmap_direct["surface_unseen_metric"] = _unseen_surface_metrics(
            aligned_direct_points, unseen_truth, threshold_m
        )
        pointmap_direct["reprojection_diagnostic"] = _direct_point_reprojection(
            arrays["pointmap_direct"],
            arrays["extrinsics_w2c"],
            arrays["intrinsics_px"],
        )
    else:
        pointmap_direct = {"status": "unsupported"}
    checks = case_record.get("checks")
    if not isinstance(checks, dict):
        raise ValueError(f"missing geometry checks: {method_id}/{case_id}")
    if (
        float(checks.get("depth_point_z_max_error", math.inf)) > 1e-2
        or float(checks.get("depth_point_reprojection_max_px", math.inf)) > 1e-2
    ):
        raise ValueError(f"geometry round-trip failed: {method_id}/{case_id}")
    expected_tracks = method_id == VGGT_METHOD
    if bool(case_record.get("tracks_present")) != expected_tracks:
        raise ValueError(f"track capability mismatch: {method_id}/{case_id}")
    return {
        "view_count": len(frame_ids),
        "camera": camera,
        "depth": depth,
        "validity": {
            "evaluation_total_pixels": int(foreground.size),
            "evaluation_foreground_pixels": int(np.count_nonzero(foreground)),
            "evaluation_background_pixels": int(np.count_nonzero(~foreground)),
            "valid_foreground_depth_pixels": int(np.count_nonzero(depth_valid)),
            "finite_foreground_confidence_pixels": int(
                np.count_nonzero(np.isfinite(arrays["confidence"][foreground]))
            ),
            "sky_mask_status": "unsupported",
        },
        "pointmap_depth": pointmap_depth,
        "pointmap_direct": pointmap_direct,
        "tracks": tracks,
        "gauge": {
            "raw": "unaligned learned gauge",
            "se3": "camera-orientation-constrained rigid evaluation alignment",
            "sim3": "camera-orientation-constrained similarity evaluation alignment",
            "sim3_scale_source": similarity["scale_source"],
            "evaluator_only": True,
            "optimization": case_record.get("optimization"),
        },
        "roundtrip": {
            "depth_point_z_max_error": float(checks["depth_point_z_max_error"]),
            "depth_point_reprojection_max_px": float(
                checks["depth_point_reprojection_max_px"]
            ),
        },
    }


def _validate_inference_manifest(staging: Path) -> dict[str, Any]:
    manifest = load_json(_require_regular_file(staging, "output/inference-manifest.json"))
    if manifest.get("schema_version") != 2 or manifest.get("network_mode") != "offline":
        raise ValueError("foundation inference manifest identity mismatch")
    if set(manifest.get("methods", {})) != set(METHODS):
        raise ValueError("foundation inference method set mismatch")
    expected_sources = {
        VGGT_METHOD: VGGT_SOURCE_COMMIT,
        DA3_METHOD: DA3_SOURCE_COMMIT,
    }
    lock = load_json(ROOT / "foundation-models.lock.json")
    model_locks = {
        VGGT_METHOD: lock["models"]["vggt"],
        DA3_METHOD: lock["models"]["depth-anything-3"],
    }
    source_tree_hashes = {
        VGGT_METHOD: lock["models"]["vggt"]["source_archive"]["tree_sha256"],
        DA3_METHOD: lock["models"]["depth-anything-3"]["source_tree_sha256"],
    }
    evidence = load_json(staging / "evidence/manifest.json")
    expected_cases = {case["id"]: case for case in evidence["cases"]}
    for method_id, method in manifest["methods"].items():
        if method.get("source_commit") != expected_sources[method_id]:
            raise ValueError(f"foundation source commit mismatch: {method_id}")
        model_lock = model_locks[method_id]
        if method.get("source") != {
            "repository": model_lock["source_repository"],
            "commit": model_lock["source_commit"],
            "license": model_lock["source_license"],
            "tree_sha256": source_tree_hashes[method_id],
            "nested_gitlinks": model_lock["nested_gitlinks"],
        }:
            raise ValueError(f"foundation source record mismatch: {method_id}")
        if method.get("checkpoint") != {
            "repository": model_lock["repository"],
            "revision": model_lock["revision"],
            "license": model_lock["license"],
            "files": model_lock["files"],
        }:
            raise ValueError(f"foundation checkpoint record mismatch: {method_id}")
        parity = method.get("upstream_unprojection_parity", {})
        expected_helper = (
            "vggt.utils.geometry.unproject_depth_map_to_point_map"
            if method_id == VGGT_METHOD
            else "depth_anything_3.utils.geometry.unproject_depth"
        )
        if (
            parity.get("helper") != expected_helper
            or parity.get("pixel_coordinate_origin")
            != "integer pixel centers (0,0) through (W-1,H-1)"
            or float(parity.get("max_abs_error", math.inf)) > 1e-6
        ):
            raise ValueError(f"upstream unprojection parity failed: {method_id}")
        if set(method.get("cases", {})) != set(expected_cases):
            raise ValueError(f"foundation case set mismatch: {method_id}")
        for case_id, case in method["cases"].items():
            if case.get("frame_ids") != expected_cases[case_id]["frame_ids"]:
                raise ValueError(f"foundation frame order mismatch: {method_id}/{case_id}")
            if case.get("optimization") != "none":
                raise ValueError(f"direct method contains optimization: {method_id}/{case_id}")
            inputs = case.get("inputs", {})
            if (
                inputs.get("ordered_frame_ids") != expected_cases[case_id]["frame_ids"]
                or inputs.get("ordered_image_sha256")
                != expected_cases[case_id]["image_sha256"]
                or inputs.get("reference_view_index_before_reorder") != 0
                or inputs.get("reference_view_index_after_reorder") != 0
                or not isinstance(inputs.get("geometric_transform"), str)
                or not isinstance(inputs.get("normalization"), str)
            ):
                raise ValueError(f"foundation input record mismatch: {method_id}/{case_id}")
            if case.get("gauge", {}).get("alignment_applied") != "none":
                raise ValueError(f"model record contains evaluator alignment: {method_id}/{case_id}")
            if set(case.get("runtime_seconds", {})) != {
                "preprocessing",
                "network",
                "decoding_unprojection",
                "export",
                "total",
            }:
                raise ValueError(f"foundation runtime decomposition mismatch: {method_id}/{case_id}")
            if not isinstance(case.get("confidence", {}).get("raw_head"), str):
                raise ValueError(f"foundation confidence record mismatch: {method_id}/{case_id}")
            if int(case.get("validity", {}).get("finite_points", 0)) <= 0:
                raise ValueError(f"foundation validity record mismatch: {method_id}/{case_id}")
            validity = case["validity"]
            if (
                validity.get("sky_mask_status") != "unsupported"
                or validity.get("background_mask_status") != "unsupported-model-side"
                or validity.get("evaluation_mask_status")
                != "evaluator-only; not mounted into inference container"
            ):
                raise ValueError(f"foundation mask validity mismatch: {method_id}/{case_id}")
            if method_id == VGGT_METHOD and not {
                "direct_point_positive_depth_count",
                "direct_point_reprojection_mean_px",
                "direct_point_reprojection_max_px",
            }.issubset(case.get("checks", {})):
                raise ValueError(f"VGGT direct-point diagnostic is missing: {case_id}")
    runtime = manifest.get("runtime", {})
    if runtime.get("deterministic_seed") != 260925 or runtime.get("cudnn_benchmark") is not False:
        raise ValueError("foundation runtime determinism mismatch")
    environment = manifest.get("environment", {})
    archived_environment = load_json(
        _require_regular_file(staging, "config/environment-manifest.json")
    )
    if (
        environment.get("tree_sha256") != lock["environment"]["tree_sha256"]
        or environment.get("build_lock") != lock["environment"]["build_lock"]
        or environment.get("file_count") != lock["environment"]["file_count"]
        or environment.get("byte_size") != lock["environment"]["byte_size"]
        or environment.get("manifest_sha256")
        != sha256_file(staging / "config/environment-manifest.json")
        or environment.get("distributions") != archived_environment["distributions"]
        or environment.get("native_binaries") != archived_environment["native_binaries"]
        or not environment.get("loaded_module_files")
    ):
        raise ValueError("foundation environment record mismatch")
    ensure_finite(manifest, "inference-manifest")
    return manifest


def _evaluate_outputs(staging: Path, profile: str) -> dict[str, Any]:
    inference = _validate_inference_manifest(staging)
    evaluation = load_json(staging / "evaluation/manifest.json")
    evidence = load_json(staging / "evidence/manifest.json")
    threshold_m = 0.10 if profile == "smoke" else 0.05
    methods: dict[str, Any] = {}
    failure_sweep: dict[str, Any] = {}
    primary_case_id = evidence["primary_case_id"]
    expected_cases = {case["id"]: case for case in evidence["cases"]}
    for method_id in METHODS:
        cases = {}
        for case_id, case_record in inference["methods"][method_id]["cases"].items():
            case_metrics = _evaluate_case(
                staging,
                evaluation,
                method_id,
                case_id,
                case_record,
                threshold_m,
            )
            case_metrics["runtime_seconds"] = case_record["runtime_seconds"]
            cases[case_id] = case_metrics
            failure_sweep.setdefault(case_id, {})[method_id] = {
                "view_count": case_metrics["view_count"],
                "sim3_center_rmse_m": case_metrics["camera"]["sim3_center_rmse_m"],
                "sim3_point_rmse_m": case_metrics["pointmap_depth"]["sim3_point_rmse_m"],
                "sim3_depth_abs_rel": case_metrics["depth"]["sim3_scaled_abs_rel"],
                "runtime_seconds": case_record["runtime_seconds"].get(
                    "total", sum(case_record["runtime_seconds"].values())
                ),
            }
            failure_sweep[case_id]["sweep"] = expected_cases[case_id]["sweep"]
        primary_runtime = cases[primary_case_id]["runtime_seconds"]
        methods[method_id] = {
            "primary_case_id": primary_case_id,
            "primary_case": cases[primary_case_id],
            "cases": cases,
            "runtime": {
                "load_seconds": inference["methods"][method_id]["load_seconds"],
                "preprocessing_seconds": primary_runtime.get("preprocessing", 0.0),
                "network_seconds": primary_runtime.get(
                    "network", primary_runtime.get("preprocessing_and_network", 0.0)
                ),
                "decoding_unprojection_seconds": primary_runtime.get(
                    "decoding_unprojection",
                    primary_runtime.get("decoding_export", 0.0),
                ),
                "export_seconds": primary_runtime.get("export", 0.0),
                "case_total_seconds": primary_runtime.get(
                    "total", sum(primary_runtime.values())
                ),
                "sweep_case_total_seconds": float(
                    sum(
                        case["runtime_seconds"].get(
                            "total", sum(case["runtime_seconds"].values())
                        )
                        for case in cases.values()
                    )
                ),
                "peak_gpu_memory_bytes": inference["methods"][method_id][
                    "peak_gpu_memory_bytes"
                ],
            },
        }
    result = {
        "methods": methods,
        "failure_sweep": failure_sweep,
        "unsupported": {
            "hidden_surface_completion": "unsupported",
            "watertight_surface": "unsupported",
            "metric_scale": "unsupported",
            "posterior_scene_sampling": "unsupported",
            "bundle_adjustment": "not-run",
        },
    }
    ensure_finite(result, "foundation metrics")
    return result


def _adapter_record() -> dict[str, Any]:
    matches = [
        item
        for item in load_json(ROOT / "reference-adapters.json")["adapters"]
        if item.get("id") == "foundation-geometry-reference"
    ]
    if len(matches) != 1:
        raise ValueError("foundation geometry adapter registry mismatch")
    return matches[0]


def _acceptance_failures(metrics: dict[str, Any], acceptance: dict[str, Any]) -> list[str]:
    failures = []
    methods = metrics["methods"]
    if len(metrics["failure_sweep"]) < acceptance["evaluated_cases_min"]:
        failures.append("evaluated_cases_min")
    for method_id, method in methods.items():
        primary = method["primary_case"]
        if (
            primary["depth"]["foreground_valid_fraction"]
            < acceptance["foreground_valid_fraction_min"]
        ):
            failures.append(f"{method_id}:foreground_valid_fraction_min")
        if (
            primary["camera"]["sim3_center_rmse_m"]
            > acceptance["sim3_center_rmse_m_max"]
        ):
            failures.append(f"{method_id}:sim3_center_rmse_m_max")
        if (
            primary["camera"]["relative_pose_auc_30"]
            < acceptance["relative_pose_auc_30_min"]
        ):
            failures.append(f"{method_id}:relative_pose_auc_30_min")
        if (
            primary["depth"]["sim3_scaled_abs_rel"]
            > acceptance["sim3_depth_abs_rel_max"]
        ):
            failures.append(f"{method_id}:sim3_depth_abs_rel_max")
        if (
            primary["pointmap_depth"]["sim3_point_rmse_m"]
            > acceptance["sim3_point_rmse_m_max"]
        ):
            failures.append(f"{method_id}:sim3_point_rmse_m_max")
        if (
            primary["pointmap_depth"]["surface_observed_metric"]["fscore"]
            < acceptance["observed_surface_fscore_min"]
        ):
            failures.append(f"{method_id}:observed_surface_fscore_min")
        if (
            primary["pointmap_depth"]["surface_unseen_metric"]["recall"]
            > acceptance["unseen_surface_recall_max"]
        ):
            failures.append(f"{method_id}:unseen_surface_recall_max")
        if (
            primary["roundtrip"]["depth_point_reprojection_max_px"]
            > acceptance["roundtrip_max_px"]
        ):
            failures.append(f"{method_id}:roundtrip_max_px")
    return failures


def _report(profile: str, metrics: dict[str, Any], inference: dict[str, Any]) -> str:
    lines = [
        "# Module 12 maintained foundation-geometry reference",
        "",
        f"Profile: `{profile}`. Both methods ran offline from byte-locked local checkpoints.",
        "",
        "| Method | Views | Pose AUC@30 | Sim(3) camera RMSE | Sim(3) depth AbsRel | Sim(3) point RMSE | Observed F1 | Unseen recall | Primary total |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id in METHODS:
        primary = metrics["methods"][method_id]["primary_case"]
        case_id = metrics["methods"][method_id]["primary_case_id"]
        lines.append(
            f"| `{method_id}` | {primary['view_count']} | "
            f"{primary['camera']['relative_pose_auc_30']:.4f} | "
            f"{primary['camera']['sim3_center_rmse_m']:.6f} m | "
            f"{primary['depth']['sim3_scaled_abs_rel']:.4f} | "
            f"{primary['pointmap_depth']['sim3_point_rmse_m']:.6f} m | "
            f"{primary['pointmap_depth']['surface_observed_metric']['fscore']:.4f} | "
            f"{primary['pointmap_depth']['surface_unseen_metric']['recall']:.4f} | "
            f"{metrics['methods'][method_id]['runtime']['case_total_seconds']:.3f} s (`{case_id}`) |"
        )
    lines.extend(
        [
            "",
            "Raw, SE(3), and Sim(3) metrics are retained separately. Sim(3) is an evaluator diagnostic and is not part of either feed-forward method.",
            "",
            "Point correspondence threshold accuracy, bidirectional point-cloud precision/recall/F1, and unseen-surface recall are separate metrics. F1 is the harmonic mean of nearest-neighbor precision and recall; it is not a corresponding-pixel hit rate.",
            "",
            "VGGT's canonical pointmap is its predicted depth unprojected through its predicted cameras; the native direct point head is preserved and scored separately. DA3-BASE has no direct point or track head.",
            "",
            "The factorial view-count/overlap/order sweep evaluates both observed and unseen ground-truth surface slices. Model outputs remain input-visible pointmaps; hidden-surface completion, watertight reconstruction, metric scale, bundle adjustment, and posterior scene sampling are unsupported.",
            "",
            f"Runtime: `{inference['runtime']['device']}`, Torch `{inference['runtime']['torch']}`, CUDA `{inference['runtime']['cuda_runtime']}`.",
            "",
        ]
    )
    return "\n".join(lines)


def _visualization_svg(metrics: dict[str, Any]) -> str:
    cases = list(metrics["failure_sweep"])
    values = {
        method: [
            float(metrics["failure_sweep"][case][method]["sim3_point_rmse_m"])
            for case in cases
        ]
        for method in METHODS
    }
    maximum = max(max(series) for series in values.values())
    width, height = 720, 320
    left, top, plot_width, plot_height = 70, 45, 600, 190
    colors = {VGGT_METHOD: "#266c8e", DA3_METHOD: "#b05252"}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="70" y="25" font-family="sans-serif" font-size="16">Module 12 visible-point error by evidence condition</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#555"/>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#555"/>',
    ]
    for method in METHODS:
        points = []
        for index, value in enumerate(values[method]):
            x = left + plot_width * index / max(1, len(cases) - 1)
            y = top + plot_height * (1.0 - value / maximum)
            points.append(f"{x:.2f},{y:.2f}")
        lines.append(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{colors[method]}" stroke-width="3"/>'
        )
    for index, case in enumerate(cases):
        x = left + plot_width * index / max(1, len(cases) - 1)
        lines.append(
            f'<text x="{x:.2f}" y="258" text-anchor="middle" font-family="sans-serif" font-size="10">{html.escape(case)}</text>'
        )
    lines.extend(
        [
            f'<text x="70" y="290" font-family="sans-serif" font-size="11" fill="{colors[VGGT_METHOD]}">VGGT direct</text>',
            f'<text x="220" y="290" font-family="sans-serif" font-size="11" fill="{colors[DA3_METHOD]}">DA3-BASE camera head</text>',
            f'<text x="510" y="290" font-family="sans-serif" font-size="11">max {maximum:.4f} m</text>',
            "</svg>",
            "",
        ]
    )
    return "\n".join(lines)


def _expected_config(
    profile: str,
    image_id: str,
    acceptance: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "profile": profile,
        "container_image": IMAGE,
        "container_image_id": image_id,
        "network_mode": "offline",
        "gpu_selection": "CUDA device 0",
        "methods": list(METHODS),
        "primary_case_id": evidence["primary_case_id"],
        "cases": [
            {
                "id": case["id"],
                "frame_ids": case["frame_ids"],
                "sweep": case["sweep"],
            }
            for case in evidence["cases"]
        ],
        "model_lock_sha256": sha256_file(ROOT / "foundation-models.lock.json"),
        "source_mode": "exact upstream VGGT archive plus clean DA3 gitlink",
        "environment_mode": "complete byte-locked reused Surflo venv manifest",
        "acceptance": acceptance,
    }


def validate_foundation_geometry_reference_result(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve(strict=True)
    result = load_json(_require_regular_file(run_dir, "result.json"))
    validate_json_schema_instance(result, load_json(ROOT / "reference-result.schema.json"))
    if result.get("adapter") != ADAPTER or result.get("module_ids") != ["12"]:
        raise ValueError("foundation result identity mismatch")
    if result.get("network_mode") != "offline" or result.get("status") != "complete":
        raise ValueError("foundation result execution status mismatch")
    image_id = result.get("tool", {}).get("container_image_id")
    if not isinstance(image_id, str) or IMAGE_ID_PATTERN.fullmatch(image_id) is None:
        raise ValueError("foundation container image ID is not immutable")
    evidence = load_json(run_dir / "evidence/manifest.json")
    acceptance = _adapter_record()["acceptance"][result["profile"]]
    expected_config = _expected_config(result["profile"], image_id, acceptance, evidence)
    if result.get("acceptance") != acceptance:
        raise ValueError("foundation acceptance mismatch")
    provenance = result.get("provenance", {})
    if provenance.get("config") != expected_config:
        raise ValueError("foundation config mismatch")
    if provenance.get("config_sha256") != hashlib.sha256(
        canonical_json(expected_config)
    ).hexdigest():
        raise ValueError("foundation config hash mismatch")
    expected_implementation = {
        name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION
    }
    if provenance.get("implementation_sha256") != expected_implementation:
        raise ValueError("foundation implementation hash mismatch")
    if provenance.get("artifacts_sha256") != _hash_tree(run_dir):
        raise ValueError("foundation artifact hash mismatch")
    metrics = _evaluate_outputs(run_dir, result["profile"])
    if result.get("metrics") != metrics:
        raise ValueError("foundation metrics do not match persisted model outputs")
    visualization = _require_regular_file(
        run_dir, "output/foundation-geometry-sweep.svg"
    )
    if visualization.read_text(encoding="utf-8") != _visualization_svg(metrics):
        raise ValueError("foundation visualization mismatch")
    failures = _acceptance_failures(metrics, acceptance)
    if failures:
        raise ValueError(f"foundation output is below locked acceptance: {failures}")
    resources = load_json(_require_regular_file(run_dir, "output/resource-summary.json"))
    if result.get("resources") != resources:
        raise ValueError("foundation resource summary mismatch")
    ensure_finite(result, "foundation-reference-result")
    return result


def run_foundation_geometry_reference(
    cache_root: Path, profile: str, run_id: str
) -> Path:
    validate_run_id(run_id)
    if profile not in {"smoke", "full"}:
        raise ValueError(f"unknown profile: {profile}")
    engine = os.environ.get("SURFLO_PATHWAY_CONTAINER_ENGINE", "docker")
    image_id = _inspect_image(engine, IMAGE)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root = cache_root.resolve(strict=True)
    execution_inputs = _verify_model_cache(cache_root)
    gpu_hardware = _gpu_hardware(engine)
    if Path(engine).name == "docker" and not gpu_hardware:
        raise ValueError("unable to inventory GPU hardware for foundation geometry")
    gpu_device = selected_gpu_device(require_health=Path(engine).name == "docker")
    runs_root = _secure_directory(cache_root, "reference-runs")
    staging_root = _secure_directory(cache_root, "reference-staging")
    cuda_cache = _secure_directory(cache_root, "cuda-cache")
    final_parent = runs_root / run_id
    final = final_parent / ADAPTER
    if os.path.lexists(final_parent):
        raise FileExistsError(f"reference run already exists: {final}")
    promotion = staging_root / f"{run_id}.{ADAPTER}.{uuid.uuid4().hex}"
    staging = promotion / ADAPTER
    promotion.mkdir()
    staging.mkdir()
    started = time.perf_counter()
    try:
        _, evidence = _prepare_reference_scene(
            staging, load_json(ROOT / "shared-scene.json"), profile
        )
        (staging / "config").mkdir()
        write_json(
            staging / "config/environment-manifest.json",
            execution_inputs["environment"]["manifest"],
        )
        write_json(
            staging / "config/source-manifests.json",
            execution_inputs["source_manifests"],
        )
        (staging / "output").mkdir()
        command = _container_command(
            engine,
            image_id,
            staging,
            cuda_cache,
            execution_inputs,
            gpu_device,
        )
        completed, peak_gpu = _run_monitored(command, staging / "container.cid")
        (staging / "adapter.log").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        (staging / "container.cid").unlink(missing_ok=True)
        if completed.returncode != 0:
            raise ValueError(
                f"foundation geometry adapter failed ({completed.returncode}): "
                f"{completed.stderr.strip()}"
            )
        if Path(engine).name == "docker" and peak_gpu <= 0:
            raise ValueError("unable to measure foundation geometry GPU memory")
        inference = _validate_inference_manifest(staging)
        metrics = _evaluate_outputs(staging, profile)
        acceptance = _adapter_record()["acceptance"][profile]
        failures = _acceptance_failures(metrics, acceptance)
        if failures:
            raise ValueError(f"foundation output is below locked acceptance: {failures}")
        (staging / "output/foundation-geometry-sweep.svg").write_text(
            _visualization_svg(metrics), encoding="utf-8"
        )
        (staging / "report.md").write_text(
            _report(profile, metrics, inference), encoding="utf-8"
        )
        resources = {
            "runtime_seconds": time.perf_counter() - started,
            "peak_cpu_memory_bytes": _peak_cpu_memory_bytes(
                staging / "output/resource-usage.txt"
            ),
            "peak_gpu_compute_memory_bytes": peak_gpu,
            "gpu_memory_scope": "container-cgroup-compute-process-sum",
            "gpu_measurement_status": "measured" if peak_gpu > 0 else "unavailable",
            "gpu_selection": "one healthy host GPU mapped to CUDA device 0",
            "gpu_host_index": int(gpu_device),
            "gpu_hardware": gpu_hardware,
            "host": platform.platform(),
        }
        write_json(staging / "output/resource-summary.json", resources)
        config = _expected_config(profile, image_id, acceptance, evidence)
        result = {
            "schema_version": 1,
            "adapter": ADAPTER,
            "module_ids": ["12"],
            "profile": profile,
            "status": "complete",
            "network_mode": "offline",
            "metrics": metrics,
            "support": SUPPORT_CONTRACT,
            "acceptance": acceptance,
            "tool": {
                "name": "VGGT-1B direct and Depth Anything 3 BASE camera-head",
                "version": "vggt/direct+da3-base/camera-head",
                "package_version": "surflo-insula-cuda13.2.1",
                "source_commit": VGGT_SOURCE_COMMIT,
                "dependency_commit": DA3_SOURCE_COMMIT,
                "container_image": IMAGE,
                "container_image_id": image_id,
            },
            "resources": resources,
            "provenance": {
                "config": config,
                "config_sha256": hashlib.sha256(canonical_json(config)).hexdigest(),
                "implementation_sha256": {
                    name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION
                },
                "artifacts_sha256": _hash_tree(staging),
            },
        }
        ensure_finite(result, "foundation-reference-result")
        write_json(staging / "result.json", result)
        validate_foundation_geometry_reference_result(staging)
        final_parent.mkdir()
        os.replace(staging, final)
        promotion.rmdir()
        return final
    except BaseException:
        shutil.rmtree(promotion, ignore_errors=True)
        raise
