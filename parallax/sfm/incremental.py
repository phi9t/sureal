"""Incremental structure-from-motion over generated orbit images."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Any

import numpy as np

from camera.pose import camera_center
from evaluation.pose_metrics import ate_sim3, rotation_error_degrees
from features.describe import describe_patches
from features.detect import detect_harris
from geometry.pnp import refine_pnp, solve_pnp
from geometry.ransac import ransac
from geometry.triangulate import triangulate_point
from sfm.bundle_adjust import bundle_adjust
from sfm.initialize import (
    PairMatch,
    SfmView,
    _refine_right_points_subpixel,
    choose_initial_pair,
    match_view_pair,
)
from sfm.reconstruction import CameraPose, Observation, Reconstruction
from sfm.tracks import TrackGraph, TrackObservation


MIN_PNP_INLIERS = 12
PNP_RANSAC_REPROJECTION_THRESHOLD_PX = 3.0
PNP_REFINED_REPROJECTION_THRESHOLD_PX = 2.0
PREDICTED_MATCH_RADIUS_PX = 6.0
PREDICTED_MATCH_RATIO = 0.8
POSE_GROWTH_EPIPOLAR_THRESHOLD_PX = 1.5
BA_OUTLIER_REPROJECTION_THRESHOLD_PX = 2.0
MIN_TRACK_TRIANGULATION_ANGLE_DEG = 1.0
RejectedObservationKey = tuple[str, int]


@dataclass(frozen=True)
class _ProjectedTrack:
    track_id: int
    point: np.ndarray
    predicted_pixel: np.ndarray
    descriptor: np.ndarray
    source_observation: TrackObservation


@dataclass(frozen=True)
class _PnpSupport:
    object_points: np.ndarray
    image_points: np.ndarray
    track_ids: list[int]
    candidate_feature_indices: list[int]
    candidate_pixels: np.ndarray
    diagnostics: dict[str, object]


@dataclass(frozen=True)
class _RegistrationCandidate:
    candidate_index: int
    pair: PairMatch | None
    pose: CameraPose
    pnp_inliers: np.ndarray
    rmse: float
    support: _PnpSupport
    predicted: bool


def _read_pgm(path: Path) -> np.ndarray:
    payload = path.read_bytes()
    header, width_height, max_value, data = payload.split(b"\n", 3)
    if header != b"P5" or max_value != b"255":
        raise ValueError(f"unsupported PGM image: {path}")
    width, height = (int(item) for item in width_height.split())
    return np.frombuffer(data, dtype=np.uint8).reshape(height, width)


def _feature_budget(profile: str) -> int:
    return 2200 if profile == "smoke" else 3200


def _detect_view(scene_root: Path, frame: dict[str, Any], profile: str) -> SfmView:
    image = _read_pgm(scene_root / str(frame["image_path"]))
    radius = 3
    keypoints = detect_harris(
        image,
        max_keypoints=_feature_budget(profile),
        quality=0.0,
        min_distance=1,
        border=radius,
        window_radius=1,
        require_local_maximum=False,
    )
    described = describe_patches(image, keypoints, radius=radius)
    return SfmView(
        str(frame["id"]),
        image.astype(np.float64),
        np.asarray(frame["K"], dtype=np.float64),
        described.keypoints,
        described.descriptors,
        radius,
    )


def _positive_depth(point: np.ndarray, pose: CameraPose) -> bool:
    return bool((pose.rotation @ point + pose.translation)[2] > 1e-8)


def _view_by_id(views: list[SfmView]) -> dict[str, SfmView]:
    return {view.view_id: view for view in views}


def _compose_world_to_camera(
    relative_rotation: np.ndarray,
    relative_translation: np.ndarray,
    pose: CameraPose,
) -> CameraPose:
    return CameraPose(
        relative_rotation @ pose.rotation,
        relative_rotation @ pose.translation + relative_translation,
    )


def _relative_world_to_camera_pose(
    left: CameraPose,
    right: CameraPose,
) -> tuple[np.ndarray, np.ndarray]:
    rotation = right.rotation @ left.rotation.T
    translation = right.translation - rotation @ left.translation
    return rotation, translation


def _invert_relative_pose(
    relative_rotation: np.ndarray,
    relative_translation: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    inverse_rotation = relative_rotation.T
    return inverse_rotation, -(inverse_rotation @ relative_translation)


def _predict_constant_velocity_pose(
    view_order: list[str],
    candidate_index: int,
    registered_indices: set[int],
    cameras: dict[str, CameraPose],
) -> tuple[CameraPose, tuple[str, str]] | None:
    """Predict an unregistered world-to-camera pose from adjacent estimates."""
    if candidate_index - 1 in registered_indices and candidate_index - 2 in registered_indices:
        older_id = view_order[candidate_index - 2]
        newer_id = view_order[candidate_index - 1]
        relative_rotation, relative_translation = _relative_world_to_camera_pose(
            cameras[older_id],
            cameras[newer_id],
        )
        return (
            _compose_world_to_camera(
                relative_rotation,
                relative_translation,
                cameras[newer_id],
            ),
            (older_id, newer_id),
        )
    if candidate_index + 1 in registered_indices and candidate_index + 2 in registered_indices:
        older_id = view_order[candidate_index + 2]
        newer_id = view_order[candidate_index + 1]
        backward_rotation, backward_translation = _relative_world_to_camera_pose(
            cameras[older_id],
            cameras[newer_id],
        )
        return (
            _compose_world_to_camera(
                backward_rotation,
                backward_translation,
                cameras[newer_id],
            ),
            (older_id, newer_id),
        )
    if candidate_index - 1 in registered_indices and candidate_index + 1 in registered_indices:
        left_id = view_order[candidate_index - 1]
        right_id = view_order[candidate_index + 1]
        relative_rotation, relative_translation = _relative_world_to_camera_pose(
            cameras[left_id],
            cameras[right_id],
        )
        half_rotation = _matrix_power(relative_rotation, 0.5)
        half_translation = 0.5 * relative_translation
        return (
            _compose_world_to_camera(
                half_rotation,
                half_translation,
                cameras[left_id],
            ),
            (left_id, right_id),
        )
    return None


def _matrix_power(rotation: np.ndarray, exponent: float) -> np.ndarray:
    values, vectors = np.linalg.eig(rotation)
    powered = vectors @ np.diag(values**float(exponent)) @ np.linalg.inv(vectors)
    left, _, right = np.linalg.svd(np.real(powered))
    result = left @ right
    if np.linalg.det(result) < 0.0:
        left[:, -1] *= -1.0
        result = left @ right
    return result


def _ray_world(pixel: np.ndarray, view: SfmView, pose: CameraPose) -> np.ndarray:
    homogeneous = np.r_[np.asarray(pixel, dtype=np.float64).reshape(2), 1.0]
    camera_ray = np.linalg.inv(view.intrinsic) @ homogeneous
    camera_ray /= np.linalg.norm(camera_ray)
    world_ray = pose.rotation.T @ camera_ray
    return world_ray / np.linalg.norm(world_ray)


def _triangulation_angle_degrees(
    left_observation,
    right_observation,
    cameras: dict[str, CameraPose],
    views_by_id: dict[str, SfmView],
) -> float:
    left_ray = _ray_world(
        left_observation.pixel,
        views_by_id[left_observation.view_id],
        cameras[left_observation.view_id],
    )
    right_ray = _ray_world(
        right_observation.pixel,
        views_by_id[right_observation.view_id],
        cameras[right_observation.view_id],
    )
    cosine = float(np.clip(left_ray @ right_ray, -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def _canonical_rejected_observations(
    graph: TrackGraph,
    rejected_observations: set[RejectedObservationKey],
) -> set[RejectedObservationKey]:
    return {
        (view_id, graph.find(track_id))
        for view_id, track_id in rejected_observations
    }


def _usable_track_observations(
    graph: TrackGraph,
    track_id: int,
    observations,
    cameras: dict[str, CameraPose],
    rejected_observations: set[RejectedObservationKey],
) -> list:
    root = graph.find(track_id)
    return [
        observation
        for observation in observations
        if observation.view_id in cameras
        and (observation.view_id, root) not in rejected_observations
    ]


def _track_triangulation_angles_degrees(
    observations,
    cameras: dict[str, CameraPose],
    views_by_id: dict[str, SfmView],
) -> list[float]:
    angles = []
    for left_index, left_observation in enumerate(observations):
        for right_observation in observations[left_index + 1 :]:
            angles.append(
                _triangulation_angle_degrees(
                    left_observation,
                    right_observation,
                    cameras,
                    views_by_id,
                )
            )
    return angles


def _best_track_triangulation(
    observations,
    cameras: dict[str, CameraPose],
    views_by_id: dict[str, SfmView],
    *,
    min_angle_degrees: float,
) -> tuple[np.ndarray, float, tuple[str, str]] | None:
    best: tuple[np.ndarray, float, tuple[str, str]] | None = None
    for left_index, left_observation in enumerate(observations):
        for right_observation in observations[left_index + 1 :]:
            angle = _triangulation_angle_degrees(
                left_observation,
                right_observation,
                cameras,
                views_by_id,
            )
            if angle < min_angle_degrees:
                continue
            left_view = views_by_id[left_observation.view_id]
            right_view = views_by_id[right_observation.view_id]
            left_pose = cameras[left_observation.view_id]
            right_pose = cameras[right_observation.view_id]
            try:
                point = triangulate_point(
                    left_observation.pixel,
                    right_observation.pixel,
                    left_view.intrinsic,
                    left_pose.rotation,
                    left_pose.translation,
                    right_view.intrinsic,
                    right_pose.rotation,
                    right_pose.translation,
                )
            except ValueError:
                continue
            if not (
                _positive_depth(point, left_pose)
                and _positive_depth(point, right_pose)
            ):
                continue
            if best is None or angle > best[1]:
                best = (
                    point,
                    angle,
                    (left_observation.view_id, right_observation.view_id),
                )
    return best


def _retriangulate_track_points(
    graph: TrackGraph,
    cameras: dict[str, CameraPose],
    views: list[SfmView],
    rejected_observations: set[RejectedObservationKey],
    *,
    track_ids: set[int] | None = None,
    min_angle_degrees: float = MIN_TRACK_TRIANGULATION_ANGLE_DEG,
) -> tuple[dict[int, np.ndarray], dict[int, dict[str, object]]]:
    views_by_id = _view_by_id(views)
    rejected = _canonical_rejected_observations(graph, rejected_observations)
    requested = (
        None
        if track_ids is None
        else {graph.find(track_id) for track_id in track_ids}
    )
    points: dict[int, np.ndarray] = {}
    metadata: dict[int, dict[str, object]] = {}
    for track_id, observations in graph.tracks().items():
        root = graph.find(track_id)
        if requested is not None and root not in requested:
            continue
        usable = _usable_track_observations(
            graph,
            root,
            observations,
            cameras,
            rejected,
        )
        if len({observation.view_id for observation in usable}) < 2:
            continue
        triangulated = _best_track_triangulation(
            usable,
            cameras,
            views_by_id,
            min_angle_degrees=min_angle_degrees,
        )
        if triangulated is None:
            continue
        point, angle, source_pair = triangulated
        points[root] = point
        metadata[root] = {
            "source_pair": [source_pair[0], source_pair[1]],
            "triangulation_angle_deg": float(angle),
        }
    return points, metadata


def _median_track_triangulation_angle(
    track_ids: list[int],
    graph: TrackGraph,
    cameras: dict[str, CameraPose],
    views: list[SfmView],
    rejected_observations: set[RejectedObservationKey],
) -> float:
    views_by_id = _view_by_id(views)
    rejected = _canonical_rejected_observations(graph, rejected_observations)
    angles = []
    for track_id in track_ids:
        root = graph.find(track_id)
        observations = graph.tracks().get(root, [])
        usable = _usable_track_observations(
            graph,
            root,
            observations,
            cameras,
            rejected,
        )
        if len({observation.view_id for observation in usable}) < 2:
            continue
        track_angles = _track_triangulation_angles_degrees(
            usable,
            cameras,
            views_by_id,
        )
        if track_angles:
            angles.append(float(np.max(track_angles)))
    return float(np.median(angles)) if angles else 0.0


def _track_reprojection_errors(
    point: np.ndarray,
    observations,
    cameras: dict[str, CameraPose],
    views_by_id: dict[str, SfmView],
) -> dict[str, float]:
    errors = {}
    for observation in observations:
        camera = cameras[observation.view_id]
        errors[observation.view_id] = float(
            _project_residuals(
                (camera.rotation, camera.translation),
                point.reshape(1, 3),
                observation.pixel.reshape(1, 2),
                views_by_id[observation.view_id].intrinsic,
            )[0]
        )
    return errors


def _error_summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(len(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95.0)),
        "max": float(np.max(array)),
    }


def _track_source_pair_key(source_pair: tuple[str, str] | None) -> str:
    if source_pair is None:
        return "untriangulated"
    return f"{source_pair[0]}->{source_pair[1]}"


def _project_pixel(
    point: np.ndarray,
    pose: CameraPose,
    intrinsic: np.ndarray,
) -> np.ndarray | None:
    camera_point = pose.rotation @ np.asarray(point, dtype=np.float64).reshape(3)
    camera_point = camera_point + pose.translation
    if float(camera_point[2]) <= 1e-8:
        return None
    homogeneous = intrinsic @ camera_point
    return (homogeneous[:2] / homogeneous[2]).astype(np.float64)


def _pixel_inside_view(pixel: np.ndarray, view: SfmView) -> bool:
    height, width = view.image.shape
    x_coord, y_coord = (float(pixel[0]), float(pixel[1]))
    return 0.0 <= x_coord < float(width) and 0.0 <= y_coord < float(height)


def _empty_pnp_support(diagnostics: dict[str, object] | None = None) -> _PnpSupport:
    return _PnpSupport(
        np.empty((0, 3), dtype=np.float64),
        np.empty((0, 2), dtype=np.float64),
        [],
        [],
        np.empty((0, 2), dtype=np.float64),
        dict(diagnostics or {}),
    )


def _nearest_track_observation(
    observations: list[TrackObservation],
    candidate_index: int,
    view_indices: dict[str, int],
) -> TrackObservation:
    return min(
        observations,
        key=lambda observation: abs(
            view_indices.get(observation.view_id, candidate_index) - candidate_index
        ),
    )


def _candidate_feature_rows(candidate: SfmView) -> dict[int, list[int]]:
    rows: dict[int, list[int]] = {}
    for feature_index, point in enumerate(candidate.keypoints):
        rows.setdefault(int(round(float(point[1]))), []).append(feature_index)
    return rows


def _candidate_features_near_projection(
    candidate: SfmView,
    rows: dict[int, list[int]],
    projected_pixel: np.ndarray,
    *,
    radius: float,
) -> np.ndarray:
    candidate_indices: list[int] = []
    row_start = int(np.floor(float(projected_pixel[1]) - radius))
    row_stop = int(np.ceil(float(projected_pixel[1]) + radius))
    for row in range(row_start, row_stop + 1):
        candidate_indices.extend(rows.get(row, ()))
    if not candidate_indices:
        return np.empty(0, dtype=np.int64)
    possible = np.asarray(candidate_indices, dtype=np.int64)
    deltas = candidate.keypoints[possible] - projected_pixel.reshape(1, 2)
    inside = np.linalg.norm(deltas, axis=1) <= float(radius)
    return possible[inside]


def _match_projected_tracks(
    projected_tracks: list[_ProjectedTrack],
    candidate: SfmView,
    *,
    radius: float,
    ratio: float,
) -> tuple[np.ndarray, dict[str, int]]:
    if len(projected_tracks) == 0 or len(candidate.keypoints) < 2:
        return (
            np.empty((0, 2), dtype=np.int64),
            {
                "predicted_matches_before_ratio": 0,
                "predicted_matches_after_ratio": 0,
                "predicted_matches_after_mutual_check": 0,
            },
        )
    rows = _candidate_feature_rows(candidate)
    forward_best = np.full(len(projected_tracks), -1, dtype=np.int64)
    candidate_best_track = np.full(len(candidate.keypoints), -1, dtype=np.int64)
    candidate_best_distance = np.full(len(candidate.keypoints), np.inf, dtype=np.float64)
    before_ratio = 0
    after_ratio = 0
    for track_index, projected in enumerate(projected_tracks):
        candidates = _candidate_features_near_projection(
            candidate,
            rows,
            projected.predicted_pixel,
            radius=radius,
        )
        if len(candidates) == 0:
            continue
        distances = np.linalg.norm(
            candidate.descriptors[candidates] - projected.descriptor.reshape(1, -1),
            axis=1,
        )
        for feature_index, distance in zip(candidates, distances):
            if float(distance) < float(candidate_best_distance[feature_index]):
                candidate_best_distance[feature_index] = float(distance)
                candidate_best_track[feature_index] = track_index
        if len(candidates) < 2:
            continue
        before_ratio += 1
        order = np.argsort(distances)
        best_distance = float(distances[order[0]])
        second_distance = float(distances[order[1]])
        if best_distance <= float(ratio) * second_distance:
            forward_best[track_index] = int(candidates[order[0]])
            after_ratio += 1
    matches = [
        (track_index, int(feature_index))
        for track_index, feature_index in enumerate(forward_best)
        if feature_index >= 0
        and int(candidate_best_track[int(feature_index)]) == track_index
    ]
    matched = np.asarray(matches, dtype=np.int64).reshape(-1, 2)
    return (
        matched,
        {
            "predicted_matches_before_ratio": before_ratio,
            "predicted_matches_after_ratio": after_ratio,
            "predicted_matches_after_mutual_check": len(matched),
        },
    )


def _build_predicted_pnp_support(
    candidate: SfmView,
    candidate_index: int,
    predicted_pose: CameraPose,
    views: list[SfmView],
    cameras: dict[str, CameraPose],
    graph: TrackGraph,
    points: dict[int, np.ndarray],
    rejected_observations: set[RejectedObservationKey],
) -> _PnpSupport:
    """Match current 3D tracks into a new view using a predicted pose only."""
    view_indices = {view.view_id: index for index, view in enumerate(views)}
    views_by_id = _view_by_id(views)
    rejected = _canonical_rejected_observations(graph, rejected_observations)
    projected_tracks: list[_ProjectedTrack] = []
    support_errors: list[float] = []
    support_errors_by_view: dict[str, list[float]] = {}
    rejected_existing = 0
    behind_camera = 0
    out_of_frame = 0
    no_registered_observation = 0
    canonical_points = graph.canonicalize_points(points)
    tracks = graph.tracks()
    for track_id, point in canonical_points.items():
        root = graph.find(track_id)
        observations = tracks.get(root, [])
        usable_observations = _usable_track_observations(
            graph,
            root,
            observations,
            cameras,
            rejected,
        )
        if not usable_observations:
            no_registered_observation += 1
            continue
        existing_errors = _track_reprojection_errors(
            point,
            usable_observations,
            cameras,
            views_by_id,
        )
        if existing_errors:
            max_existing_error = max(existing_errors.values())
            support_errors.append(max_existing_error)
            for view_id, error in existing_errors.items():
                support_errors_by_view.setdefault(view_id, []).append(error)
            if max_existing_error > BA_OUTLIER_REPROJECTION_THRESHOLD_PX:
                rejected_existing += 1
                continue
        predicted_pixel = _project_pixel(point, predicted_pose, candidate.intrinsic)
        if predicted_pixel is None:
            behind_camera += 1
            continue
        if not _pixel_inside_view(predicted_pixel, candidate):
            out_of_frame += 1
            continue
        source_observation = _nearest_track_observation(
            usable_observations,
            candidate_index,
            view_indices,
        )
        source_view = views_by_id[source_observation.view_id]
        projected_tracks.append(
            _ProjectedTrack(
                root,
                np.asarray(point, dtype=np.float64).reshape(3),
                predicted_pixel,
                source_view.descriptors[source_observation.feature_index],
                source_observation,
            )
        )
    matches, match_diagnostics = _match_projected_tracks(
        projected_tracks,
        candidate,
        radius=PREDICTED_MATCH_RADIUS_PX,
        ratio=PREDICTED_MATCH_RATIO,
    )
    if len(matches) == 0:
        return _empty_pnp_support(
            {
                "predicted_projected_track_count": len(projected_tracks),
                "predicted_stale_track_count": rejected_existing,
                "predicted_behind_camera_track_count": behind_camera,
                "predicted_out_of_frame_track_count": out_of_frame,
                "predicted_no_registered_observation_track_count": no_registered_observation,
                "pre_pnp_rejected_point_count": rejected_existing,
                "pre_pnp_reprojection_error_px": _error_summary(support_errors),
                "pre_pnp_reprojection_error_by_view_px": {
                    view_id: _error_summary(errors)
                    for view_id, errors in sorted(support_errors_by_view.items())
                },
                **match_diagnostics,
            }
        )
    matched_tracks = [projected_tracks[int(track_index)] for track_index, _ in matches]
    candidate_features = [int(feature_index) for _, feature_index in matches]
    refined_pixels = []
    for projected, feature_index in zip(matched_tracks, candidate_features):
        source_view = views_by_id[projected.source_observation.view_id]
        refined = _refine_right_points_subpixel(
            source_view.image,
            candidate.image,
            projected.source_observation.pixel.reshape(1, 2),
            candidate.keypoints[feature_index].reshape(1, 2),
            radius=min(source_view.descriptor_radius, candidate.descriptor_radius),
        )
        refined_pixels.append(refined[0])
    return _PnpSupport(
        np.asarray([projected.point for projected in matched_tracks], dtype=np.float64),
        np.asarray(refined_pixels, dtype=np.float64).reshape(-1, 2),
        [projected.track_id for projected in matched_tracks],
        candidate_features,
        np.asarray(refined_pixels, dtype=np.float64).reshape(-1, 2),
        {
            "predicted_projected_track_count": len(projected_tracks),
            "predicted_stale_track_count": rejected_existing,
            "predicted_behind_camera_track_count": behind_camera,
            "predicted_out_of_frame_track_count": out_of_frame,
            "predicted_no_registered_observation_track_count": no_registered_observation,
            "pre_pnp_rejected_point_count": rejected_existing,
            "pre_pnp_reprojection_error_px": _error_summary(support_errors),
            "pre_pnp_reprojection_error_by_view_px": {
                view_id: _error_summary(errors)
                for view_id, errors in sorted(support_errors_by_view.items())
            },
            **match_diagnostics,
        },
    )


def _build_pair_pnp_support(
    pair: PairMatch,
    graph: TrackGraph,
    points: dict[int, np.ndarray],
    point_sources: dict[int, dict[str, object]],
    cameras: dict[str, CameraPose],
    views: list[SfmView],
    rejected_observations: set[RejectedObservationKey],
) -> _PnpSupport:
    object_points = []
    image_points = []
    object_track_ids = []
    candidate_feature_indices = []
    candidate_pixels = []
    candidate_track_count = 0
    support_errors = []
    support_errors_by_view: dict[str, list[float]] = {}
    source_pairs: Counter[str] = Counter()
    rejected = _canonical_rejected_observations(
        graph,
        rejected_observations,
    )
    views_by_id = _view_by_id(views)
    for match_index, is_inlier in enumerate(pair.inlier_mask):
        if not bool(is_inlier):
            continue
        reference_feature = int(pair.left_feature_indices[match_index])
        track_id = graph.feature_track(
            pair.left_view_id,
            reference_feature,
        )
        if track_id is None:
            continue
        canonical = graph.find(track_id)
        if canonical not in points:
            continue
        if (pair.left_view_id, canonical) in rejected:
            continue
        candidate_track_count += 1
        observations = graph.tracks().get(canonical, [])
        usable_observations = _usable_track_observations(
            graph,
            canonical,
            observations,
            cameras,
            rejected,
        )
        existing_errors = _track_reprojection_errors(
            points[canonical],
            usable_observations,
            cameras,
            views_by_id,
        )
        if existing_errors:
            max_existing_error = max(existing_errors.values())
            support_errors.append(max_existing_error)
            for view_id, error in existing_errors.items():
                support_errors_by_view.setdefault(view_id, []).append(error)
            if max_existing_error > BA_OUTLIER_REPROJECTION_THRESHOLD_PX:
                continue
        object_points.append(points[canonical])
        image_points.append(pair.right_points[match_index])
        object_track_ids.append(canonical)
        candidate_feature_indices.append(int(pair.right_feature_indices[match_index]))
        candidate_pixels.append(pair.right_points[match_index])
        source_pair = point_sources.get(canonical, {}).get("source_pair")
        source_pairs[_track_source_pair_key(source_pair)] += 1
    return _PnpSupport(
        np.asarray(object_points, dtype=np.float64).reshape(-1, 3),
        np.asarray(image_points, dtype=np.float64).reshape(-1, 2),
        object_track_ids,
        candidate_feature_indices,
        np.asarray(candidate_pixels, dtype=np.float64).reshape(-1, 2),
        {
            "pnp_correspondence_count": len(object_points),
            "pre_pnp_rejected_point_count": candidate_track_count
            - len(object_points),
            "pre_pnp_reprojection_error_px": _error_summary(support_errors),
            "pre_pnp_reprojection_error_by_view_px": {
                view_id: _error_summary(errors)
                for view_id, errors in sorted(support_errors_by_view.items())
            },
            "pnp_track_source_pairs": dict(sorted(source_pairs.items())),
        },
    )


def _support_registration_diagnostics(
    support: _PnpSupport,
    graph: TrackGraph,
    point_sources: dict[int, dict[str, object]],
    cameras: dict[str, CameraPose],
    views: list[SfmView],
    rejected_observations: set[RejectedObservationKey],
    *,
    method: str,
    predicted_pose_source: tuple[str, str] | None = None,
) -> dict[str, object]:
    source_pairs: Counter[str] = Counter()
    for track_id in support.track_ids:
        source_pair = point_sources.get(graph.find(track_id), {}).get("source_pair")
        source_pairs[_track_source_pair_key(source_pair)] += 1
    diagnostics = dict(support.diagnostics)
    diagnostics.update(
        {
            "registration_method": method,
            "pnp_correspondence_count": len(support.object_points),
            "pnp_track_source_pairs": dict(sorted(source_pairs.items())),
            "median_triangulation_angle_deg": float(
                _median_track_triangulation_angle(
                    support.track_ids,
                    graph,
                    cameras,
                    views,
                    rejected_observations,
                )
            ),
        }
    )
    if predicted_pose_source is not None:
        diagnostics["predicted_pose_source_view_ids"] = [
            predicted_pose_source[0],
            predicted_pose_source[1],
        ]
    return diagnostics


def _add_pnp_inlier_observations(
    graph: TrackGraph,
    candidate: SfmView,
    support: _PnpSupport,
    inlier_mask: np.ndarray,
) -> set[int]:
    changed: set[int] = set()
    for support_index, is_inlier in enumerate(inlier_mask):
        if not bool(is_inlier):
            continue
        candidate_track = graph.add_feature(
            candidate.view_id,
            support.candidate_feature_indices[support_index],
            support.candidate_pixels[support_index],
        )
        conflicts_before = graph.conflict_count
        graph.union(support.track_ids[support_index], candidate_track)
        if graph.conflict_count == conflicts_before:
            merged = graph.find(support.track_ids[support_index])
            if graph.find(candidate_track) == merged:
                changed.add(merged)
    return changed


def _match_nearest_registered_pair(
    views: list[SfmView],
    candidate_index: int,
    registered_indices: set[int],
) -> PairMatch:
    errors: list[str] = []
    for reference_index in sorted(
        registered_indices,
        key=lambda item: abs(item - candidate_index),
    ):
        if abs(reference_index - candidate_index) != 1:
            continue
        try:
            return match_view_pair(
                views,
                reference_index,
                candidate_index,
                max_trials=280,
            )
        except (ValueError, np.linalg.LinAlgError) as error:
            errors.append(
                f"{views[reference_index].view_id}->{views[candidate_index].view_id}: {error}"
            )
    detail = "; ".join(errors) if errors else "no adjacent registered reference"
    raise ValueError(detail)


def _skew_symmetric(vector: np.ndarray) -> np.ndarray:
    x_coord, y_coord, z_coord = np.asarray(vector, dtype=np.float64).reshape(3)
    return np.array(
        [
            [0.0, -z_coord, y_coord],
            [z_coord, 0.0, -x_coord],
            [-y_coord, x_coord, 0.0],
        ],
        dtype=np.float64,
    )


def _fundamental_from_camera_poses(
    left: SfmView,
    right: SfmView,
    cameras: dict[str, CameraPose],
) -> np.ndarray | None:
    if left.view_id not in cameras or right.view_id not in cameras:
        return None
    relative_rotation, relative_translation = _relative_world_to_camera_pose(
        cameras[left.view_id],
        cameras[right.view_id],
    )
    essential = _skew_symmetric(relative_translation) @ relative_rotation
    norm = float(np.linalg.norm(essential))
    if norm <= 1e-12:
        return None
    fundamental = (
        np.linalg.inv(right.intrinsic).T
        @ (essential / norm)
        @ np.linalg.inv(left.intrinsic)
    )
    fundamental_norm = float(np.linalg.norm(fundamental))
    if fundamental_norm <= 1e-12:
        return None
    return fundamental / fundamental_norm


def _symmetric_epipolar_distance(
    fundamental: np.ndarray,
    left_pixel: np.ndarray,
    right_pixel: np.ndarray,
) -> float:
    left = np.r_[np.asarray(left_pixel, dtype=np.float64).reshape(2), 1.0]
    right = np.r_[np.asarray(right_pixel, dtype=np.float64).reshape(2), 1.0]
    line_right = fundamental @ left
    line_left = fundamental.T @ right
    numerator = float(right @ fundamental @ left) ** 2
    denominator = (
        1.0 / max(float(line_left[:2] @ line_left[:2]), 1e-12)
        + 1.0 / max(float(line_right[:2] @ line_right[:2]), 1e-12)
    )
    return float(np.sqrt(numerator * denominator))


def _triangulate_inlier_tracks(
    graph: TrackGraph,
    points: dict[int, np.ndarray],
    pair: PairMatch,
    cameras: dict[str, CameraPose],
    views: list[SfmView],
    rejected_observations: set[RejectedObservationKey],
    *,
    new_tracks_only: bool = False,
    pose_inlier_threshold_px: float | None = None,
) -> None:
    def canonicalize_current_points() -> None:
        canonical = graph.canonicalize_points(points)
        points.clear()
        points.update(canonical)

    changed_track_ids: set[int] = set()
    rejected = _canonical_rejected_observations(graph, rejected_observations)
    left_view = views[pair.left_index]
    right_view = views[pair.right_index]
    pose_fundamental = (
        None
        if pose_inlier_threshold_px is None
        else _fundamental_from_camera_poses(left_view, right_view, cameras)
    )
    for match_index, is_inlier in enumerate(pair.inlier_mask):
        if not bool(is_inlier):
            continue
        if pose_fundamental is not None:
            pose_error = _symmetric_epipolar_distance(
                pose_fundamental,
                pair.left_points[match_index],
                pair.right_points[match_index],
            )
            if float(pose_error) > float(pose_inlier_threshold_px):
                continue
        left_feature = int(pair.left_feature_indices[match_index])
        right_feature = int(pair.right_feature_indices[match_index])
        left_track = graph.feature_track(pair.left_view_id, left_feature)
        right_track = graph.feature_track(pair.right_view_id, right_feature)
        if new_tracks_only and (left_track is not None or right_track is not None):
            continue
        if (
            left_track is not None
            and (pair.left_view_id, graph.find(left_track)) in rejected
        ):
            continue
        track_id = graph.add_match(
            pair.left_view_id,
            left_feature,
            pair.left_points[match_index],
            pair.right_view_id,
            right_feature,
            pair.right_points[match_index],
        )
        if track_id is None:
            continue
        canonicalize_current_points()
        changed_track_ids.add(graph.find(track_id))
    if not changed_track_ids:
        return
    updates, _ = _retriangulate_track_points(
        graph,
        cameras,
        views,
        rejected_observations,
        track_ids=changed_track_ids,
    )
    points.update(updates)


def _project_residuals(
    pose: tuple[np.ndarray, np.ndarray],
    points3d: np.ndarray,
    pixels: np.ndarray,
    intrinsic: np.ndarray,
) -> np.ndarray:
    rotation, translation = pose
    camera = (rotation @ points3d.T).T + translation
    valid = camera[:, 2] > 1e-8
    projected = np.empty_like(pixels, dtype=np.float64)
    projected[:] = 1e6
    if np.any(valid):
        homogeneous = (intrinsic @ camera[valid].T).T
        projected[valid] = homogeneous[:, :2] / homogeneous[:, 2, None]
    return np.linalg.norm(projected - pixels, axis=1)


def _estimate_pnp(
    points3d: np.ndarray,
    pixels: np.ndarray,
    intrinsic: np.ndarray,
    *,
    initial_pose: CameraPose | None = None,
) -> tuple[CameraPose, np.ndarray, float]:
    if len(points3d) < 6:
        raise ValueError("PnP registration needs at least six 3D-2D matches")
    indices = np.arange(len(points3d), dtype=np.int64)

    def refine_candidate(
        seed_rotation: np.ndarray,
        seed_translation: np.ndarray,
        seed_inliers: np.ndarray,
    ) -> tuple[CameraPose, np.ndarray, float]:
        rotation, translation, rmse = refine_pnp(
            points3d[seed_inliers],
            pixels[seed_inliers],
            intrinsic,
            seed_rotation,
            seed_translation,
            iterations=25,
        )
        refined_errors = _project_residuals(
            (rotation, translation),
            points3d,
            pixels,
            intrinsic,
        )
        refined_inliers = (
            np.isfinite(refined_errors)
            & (refined_errors <= PNP_REFINED_REPROJECTION_THRESHOLD_PX)
        )
        if int(np.sum(refined_inliers)) < MIN_PNP_INLIERS:
            relaxed_inliers = (
                np.isfinite(refined_errors)
                & (refined_errors <= PNP_RANSAC_REPROJECTION_THRESHOLD_PX)
            )
            if int(np.sum(relaxed_inliers)) >= MIN_PNP_INLIERS:
                refined_inliers = relaxed_inliers
            else:
                refined_inliers = seed_inliers
        if np.any(refined_inliers != seed_inliers):
            rotation, translation, rmse = refine_pnp(
                points3d[refined_inliers],
                pixels[refined_inliers],
                intrinsic,
                rotation,
                translation,
                iterations=15,
            )
        return CameraPose(rotation, translation), refined_inliers, rmse

    def fit(sample: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        rotation, translation, _ = solve_pnp(
            points3d[sample],
            pixels[sample],
            intrinsic,
            refine=False,
        )
        return rotation, translation

    def residuals(model: tuple[np.ndarray, np.ndarray], sample: np.ndarray) -> np.ndarray:
        return _project_residuals(model, points3d[sample], pixels[sample], intrinsic)

    candidates: list[tuple[CameraPose, np.ndarray, float]] = []
    try:
        result = ransac(
            indices,
            sample_size=6,
            fit_model=fit,
            residuals=residuals,
            threshold=PNP_RANSAC_REPROJECTION_THRESHOLD_PX,
            max_trials=260,
            seed=310159,
            min_inliers=MIN_PNP_INLIERS,
        )
        inlier_mask = result.inlier_mask
        seed_rotation, seed_translation = result.model
        candidates.append(refine_candidate(seed_rotation, seed_translation, inlier_mask))
    except ValueError:
        if initial_pose is None:
            raise
    if initial_pose is not None:
        errors = _project_residuals(
            (initial_pose.rotation, initial_pose.translation),
            points3d,
            pixels,
            intrinsic,
        )
        inlier_mask = np.isfinite(errors) & (errors <= 8.0)
        if int(np.sum(inlier_mask)) < MIN_PNP_INLIERS:
            inlier_mask = np.ones(len(points3d), dtype=bool)
        candidates.append(
            refine_candidate(
                initial_pose.rotation,
                initial_pose.translation,
                inlier_mask,
            )
        )
    if not candidates:
        raise ValueError("PnP registration could not produce a pose candidate")
    best_inlier_count = max(int(np.sum(inliers)) for _, inliers, _ in candidates)
    viable = [
        candidate
        for candidate in candidates
        if int(np.sum(candidate[1])) >= max(MIN_PNP_INLIERS, int(0.8 * best_inlier_count))
    ]
    if initial_pose is not None and viable:
        pose, inliers, rmse = min(
            viable,
            key=lambda candidate: rotation_error_degrees(
                candidate[0].rotation,
                initial_pose.rotation,
            ),
        )
        return pose, inliers, rmse
    return max(
        candidates,
        key=lambda candidate: (int(np.sum(candidate[1])), -candidate[2]),
    )


def _build_reconstruction(
    intrinsic: np.ndarray,
    cameras: dict[str, CameraPose],
    points: dict[int, np.ndarray],
    graph: TrackGraph,
    view_order: list[str],
    diagnostics: dict[str, object],
    rejected_observations: set[RejectedObservationKey],
) -> Reconstruction:
    rejected = _canonical_rejected_observations(graph, rejected_observations)
    canonical_points = graph.canonicalize_points(points)
    observations = []
    for track_id, track_observations in graph.tracks().items():
        root = graph.find(track_id)
        if root not in canonical_points:
            continue
        for observation in track_observations:
            if observation.view_id in cameras:
                if (observation.view_id, root) in rejected:
                    continue
                observations.append(
                    Observation(observation.view_id, root, observation.pixel)
                )
    return Reconstruction(
        intrinsic,
        cameras,
        canonical_points,
        observations,
        registered_view_ids=[view_id for view_id in view_order if view_id in cameras],
        diagnostics=diagnostics,
    )


def _observation_error(
    reconstruction: Reconstruction,
    observation: Observation,
) -> float:
    camera = reconstruction.cameras[observation.camera_id]
    point = reconstruction.points[observation.track_id]
    return float(
        _project_residuals(
            (camera.rotation, camera.translation),
            point.reshape(1, 3),
            observation.pixel.reshape(1, 2),
            reconstruction.intrinsic,
        )[0]
    )


def _prune_bundle_adjustment_outliers(
    reconstruction: Reconstruction,
    graph: TrackGraph,
    views: list[SfmView],
    view_order: list[str],
    rejected_observations: set[RejectedObservationKey],
    diagnostics: dict[str, object],
) -> tuple[Reconstruction, set[RejectedObservationKey], dict[str, object]]:
    rejected = _canonical_rejected_observations(graph, rejected_observations)
    updated_rejected = set(rejected)
    for observation in reconstruction.observations:
        if (
            _observation_error(reconstruction, observation)
            > BA_OUTLIER_REPROJECTION_THRESHOLD_PX
        ):
            updated_rejected.add(
                (observation.camera_id, graph.find(observation.track_id))
            )
    retriangulated, track_metadata = _retriangulate_track_points(
        graph,
        reconstruction.cameras,
        views,
        updated_rejected,
        min_angle_degrees=MIN_TRACK_TRIANGULATION_ANGLE_DEG,
    )
    pruned = _build_reconstruction(
        reconstruction.intrinsic,
        reconstruction.cameras,
        retriangulated,
        graph,
        view_order,
        diagnostics,
        updated_rejected,
    )
    stats: dict[str, object] = {
        "dropped_observation_count": len(updated_rejected) - len(rejected),
        "dropped_point_count": len(reconstruction.points) - len(retriangulated),
        "remaining_observation_count": len(pruned.observations),
        "remaining_point_count": len(pruned.points),
        "median_triangulation_angle_deg": (
            float(
                np.median(
                    [
                        float(item["triangulation_angle_deg"])
                        for item in track_metadata.values()
                    ]
                )
            )
            if track_metadata
            else 0.0
        ),
    }
    return pruned, updated_rejected, stats


def _bundle_adjust_with_pruning(
    reconstruction: Reconstruction,
    graph: TrackGraph,
    views: list[SfmView],
    view_order: list[str],
    rejected_observations: set[RejectedObservationKey],
    *,
    max_iterations: int,
) -> tuple[Reconstruction, set[RejectedObservationKey], float, dict[str, object]]:
    adjusted = bundle_adjust(
        reconstruction,
        fixed_camera_ids=(_first_registered_view_id(view_order, reconstruction.cameras),),
        max_iterations=max_iterations,
        robust_loss="huber",
        robust_scale_px=BA_OUTLIER_REPROJECTION_THRESHOLD_PX,
    )
    pruned, updated_rejected, stats = _prune_bundle_adjustment_outliers(
        adjusted.reconstruction,
        graph,
        views,
        view_order,
        rejected_observations,
        reconstruction.diagnostics,
    )
    should_rerun = (
        int(stats["dropped_observation_count"]) > 0
        or int(stats["dropped_point_count"]) > 0
    )
    stats["reran_after_pruning"] = False
    if should_rerun and len(pruned.points) >= 6 and pruned.observations:
        rerun = bundle_adjust(
            pruned,
            fixed_camera_ids=(_first_registered_view_id(view_order, pruned.cameras),),
            max_iterations=max_iterations,
            robust_loss="huber",
            robust_scale_px=BA_OUTLIER_REPROJECTION_THRESHOLD_PX,
        )
        stats["reran_after_pruning"] = True
        return (
            rerun.reconstruction,
            updated_rejected,
            rerun.final_rmse_px,
            stats,
        )
    return (
        adjusted.reconstruction if not should_rerun else pruned,
        updated_rejected,
        adjusted.final_rmse_px,
        stats,
    )


def _serialized_cameras(
    view_order: list[str],
    cameras: dict[str, CameraPose],
) -> dict[str, dict[str, list[float] | list[list[float]]]]:
    return {
        view_id: {
            "rotation": cameras[view_id].rotation.tolist(),
            "translation": cameras[view_id].translation.tolist(),
        }
        for view_id in view_order
        if view_id in cameras
    }


def _record_pose_stage(
    diagnostics: dict[str, object],
    *,
    stage: str,
    view_order: list[str],
    cameras: dict[str, CameraPose],
    view_id: str | None = None,
    reference_view_id: str | None = None,
    extra: dict[str, object] | None = None,
) -> None:
    stages = diagnostics.setdefault("pose_stages", [])
    assert isinstance(stages, list)
    record: dict[str, object] = {
        "stage": stage,
        "registered_view_ids": [view for view in view_order if view in cameras],
        "cameras": _serialized_cameras(view_order, cameras),
    }
    if view_id is not None:
        record["view_id"] = view_id
    if reference_view_id is not None:
        record["reference_view_id"] = reference_view_id
    if extra:
        record.update(extra)
    stages.append(record)


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


def _first_registered_view_id(
    view_order: list[str],
    cameras: dict[str, CameraPose],
) -> str:
    return next(view_id for view_id in view_order if view_id in cameras)


def reconstruct_orbit_scene(
    scene_root: Path,
    manifest: dict[str, Any],
    profile: str,
    *,
    bundle_interval: int = 2,
) -> Reconstruction:
    """Estimate all orbit camera poses without pose, azimuth or depth metadata."""
    frames = list(manifest["frames"])
    if len(frames) < 2:
        raise ValueError("incremental SfM needs at least two frames")
    views = [_detect_view(scene_root, frame, profile) for frame in frames]
    view_order = [view.view_id for view in views]
    graph = TrackGraph()
    points: dict[int, np.ndarray] = {}
    point_sources: dict[int, dict[str, object]] = {}
    rejected_observations: set[RejectedObservationKey] = set()
    initial_pair = choose_initial_pair(
        views,
        candidate_pairs=[(index, index + 1) for index in range(len(views) - 1)],
    )
    cameras = {
        initial_pair.left_view_id: CameraPose(np.eye(3), np.zeros(3)),
        initial_pair.right_view_id: CameraPose(
            initial_pair.pose.rotation,
            initial_pair.pose.translation,
        ),
    }
    _triangulate_inlier_tracks(
        graph,
        points,
        initial_pair,
        cameras,
        views,
        rejected_observations,
    )
    point_sources.update(
        _retriangulate_track_points(
            graph,
            cameras,
            views,
            rejected_observations,
            track_ids=set(points),
        )[1]
    )
    registered_indices = {initial_pair.left_index, initial_pair.right_index}
    diagnostics: dict[str, object] = {
        "initial_pair": [initial_pair.left_view_id, initial_pair.right_view_id],
        "initial_pair_inliers": initial_pair.inlier_count,
        "registrations": [],
        "bundle_adjustment_runs": 0,
        "match_bounds": "coarse_to_fine_image_displacement",
    }
    _record_pose_stage(
        diagnostics,
        stage="initial_pair",
        view_order=view_order,
        cameras=cameras,
        view_id=initial_pair.right_view_id,
        reference_view_id=initial_pair.left_view_id,
    )

    while len(registered_indices) < len(views):
        best_registration: _RegistrationCandidate | None = None
        failure_notes: list[str] = []
        for candidate_index, candidate in enumerate(views):
            if candidate_index in registered_indices:
                continue
            predicted = _predict_constant_velocity_pose(
                view_order,
                candidate_index,
                registered_indices,
                cameras,
            )
            if predicted is None:
                failure_notes.append(
                    f"{candidate.view_id}: no sequence-neighbour pose prediction"
                )
                continue
            predicted_pose, predicted_source = predicted
            support = _build_predicted_pnp_support(
                candidate,
                candidate_index,
                predicted_pose,
                views,
                cameras,
                graph,
                points,
                rejected_observations,
            )
            if len(support.object_points) < MIN_PNP_INLIERS:
                failure_notes.append(
                    f"{candidate.view_id}: predicted 2D-3D support has "
                    f"{len(support.object_points)} matches"
                )
                continue
            try:
                pose, pnp_inliers, rmse = _estimate_pnp(
                    support.object_points,
                    support.image_points,
                    candidate.intrinsic,
                    initial_pose=predicted_pose,
                )
            except (ValueError, np.linalg.LinAlgError) as error:
                failure_notes.append(
                    f"{candidate.view_id}: predicted PnP failed with "
                    f"{len(support.object_points)} matches: {error}"
                )
                continue
            score = int(np.sum(pnp_inliers))
            if score < MIN_PNP_INLIERS:
                failure_notes.append(
                    f"{candidate.view_id}: predicted PnP kept {score} inliers"
                )
                continue
            diagnostics_for_support = _support_registration_diagnostics(
                support,
                graph,
                point_sources,
                cameras,
                views,
                rejected_observations,
                method="pose_predicted_2d3d",
                predicted_pose_source=predicted_source,
            )
            if best_registration is None or score > int(
                np.sum(best_registration.pnp_inliers)
            ):
                best_registration = _RegistrationCandidate(
                    candidate_index,
                    None,
                    pose,
                    pnp_inliers,
                    rmse,
                    _PnpSupport(
                        support.object_points,
                        support.image_points,
                        support.track_ids,
                        support.candidate_feature_indices,
                        support.candidate_pixels,
                        diagnostics_for_support,
                    ),
                    True,
                )

        if best_registration is None:
            for candidate_index, candidate in enumerate(views):
                if candidate_index in registered_indices:
                    continue
                for reference_index in sorted(
                    registered_indices,
                    key=lambda item: abs(item - candidate_index),
                ):
                    if abs(reference_index - candidate_index) != 1:
                        continue
                    try:
                        pair = match_view_pair(
                            views,
                            reference_index,
                            candidate_index,
                            max_trials=280,
                        )
                    except (ValueError, np.linalg.LinAlgError):
                        failure_notes.append(
                            f"{views[reference_index].view_id}->{candidate.view_id}: pair match failed"
                        )
                        continue
                    support = _build_pair_pnp_support(
                        pair,
                        graph,
                        points,
                        point_sources,
                        cameras,
                        views,
                        rejected_observations,
                    )
                    if len(support.object_points) < MIN_PNP_INLIERS:
                        failure_notes.append(
                            f"{pair.left_view_id}->{pair.right_view_id}: "
                            f"{len(support.object_points)} known 3D tracks from "
                            f"{pair.inlier_count} inliers"
                        )
                        continue
                    reference_pose = cameras[pair.left_view_id]
                    initial_pose = CameraPose(
                        pair.pose.rotation @ reference_pose.rotation,
                        pair.pose.rotation @ reference_pose.translation
                        + pair.pose.translation,
                    )
                    try:
                        pose, pnp_inliers, rmse = _estimate_pnp(
                            support.object_points,
                            support.image_points,
                            candidate.intrinsic,
                            initial_pose=initial_pose,
                        )
                    except (ValueError, np.linalg.LinAlgError) as error:
                        failure_notes.append(
                            f"{pair.left_view_id}->{pair.right_view_id}: "
                            f"PnP failed with {len(support.object_points)} known tracks: {error}"
                        )
                        continue
                    score = int(np.sum(pnp_inliers))
                    if score < MIN_PNP_INLIERS:
                        failure_notes.append(
                            f"{pair.left_view_id}->{pair.right_view_id}: "
                            f"PnP kept {score} inliers"
                        )
                        continue
                    diagnostics_for_support = _support_registration_diagnostics(
                        support,
                        graph,
                        point_sources,
                        cameras,
                        views,
                        rejected_observations,
                        method="pair_guided_pnp",
                    )
                    if best_registration is None or score > int(
                        np.sum(best_registration.pnp_inliers)
                    ):
                        best_registration = _RegistrationCandidate(
                            candidate_index,
                            pair,
                            pose,
                            pnp_inliers,
                            rmse,
                            _PnpSupport(
                                support.object_points,
                                support.image_points,
                                support.track_ids,
                                support.candidate_feature_indices,
                                support.candidate_pixels,
                                diagnostics_for_support,
                            ),
                            False,
                        )
        if best_registration is None:
            detail = "; ".join(failure_notes) if failure_notes else "no candidates"
            raise ValueError(f"incremental SfM could not register every view: {detail}")
        candidate_index = best_registration.candidate_index
        candidate = views[candidate_index]
        support_diagnostics = best_registration.support.diagnostics
        growth_pair = best_registration.pair
        if best_registration.predicted:
            try:
                growth_pair = _match_nearest_registered_pair(
                    views,
                    candidate_index,
                    registered_indices,
                )
            except (ValueError, np.linalg.LinAlgError) as error:
                support_diagnostics = {
                    **support_diagnostics,
                    "post_registration_pair_match_failed": str(error),
                }
        cameras[candidate.view_id] = best_registration.pose
        if best_registration.predicted:
            changed_tracks = _add_pnp_inlier_observations(
                graph,
                candidate,
                best_registration.support,
                best_registration.pnp_inliers,
            )
            if changed_tracks:
                updates, _ = _retriangulate_track_points(
                    graph,
                    cameras,
                    views,
                    rejected_observations,
                    track_ids=changed_tracks,
                )
                points.update(updates)
        if growth_pair is not None:
            _triangulate_inlier_tracks(
                graph,
                points,
                growth_pair,
                cameras,
                views,
                rejected_observations,
                new_tracks_only=best_registration.predicted,
                pose_inlier_threshold_px=(
                    POSE_GROWTH_EPIPOLAR_THRESHOLD_PX
                    if best_registration.predicted
                    else None
                ),
            )
        points = graph.canonicalize_points(points)
        point_sources = {
            graph.find(track_id): dict(metadata)
            for track_id, metadata in point_sources.items()
            if graph.find(track_id) in points
        }
        point_sources.update(
            _retriangulate_track_points(
                graph,
                cameras,
                views,
                rejected_observations,
                track_ids=set(points),
            )[1]
        )
        registered_indices.add(candidate_index)
        reference_view_id = (
            growth_pair.left_view_id
            if growth_pair is not None
            else None
        )
        _record_pose_stage(
            diagnostics,
            stage="pnp_registration",
            view_order=view_order,
            cameras=cameras,
            view_id=candidate.view_id,
            reference_view_id=reference_view_id,
            extra={
                **support_diagnostics,
                "pnp_inlier_count": int(np.sum(best_registration.pnp_inliers)),
                "pnp_rmse_px": float(best_registration.rmse),
            },
        )
        registrations = diagnostics["registrations"]
        assert isinstance(registrations, list)
        registrations.append(
            {
                "view_id": candidate.view_id,
                "reference_view_id": reference_view_id,
                **support_diagnostics,
                "pnp_inliers": int(np.sum(best_registration.pnp_inliers)),
                "pnp_rmse_px": float(best_registration.rmse),
            }
        )
        if bundle_interval > 0 and len(registered_indices) % bundle_interval == 0:
            reconstruction = _build_reconstruction(
                views[0].intrinsic,
                cameras,
                points,
                graph,
                view_order,
                diagnostics,
                rejected_observations,
            )
            if len(reconstruction.points) >= 6 and reconstruction.observations:
                (
                    adjusted,
                    rejected_observations,
                    _,
                    prune_stats,
                ) = _bundle_adjust_with_pruning(
                    reconstruction,
                    graph,
                    views,
                    view_order,
                    rejected_observations,
                    max_iterations=4,
                )
                cameras = adjusted.cameras
                points = adjusted.points
                point_sources = {
                    graph.find(track_id): dict(metadata)
                    for track_id, metadata in point_sources.items()
                    if graph.find(track_id) in points
                }
                point_sources.update(
                    _retriangulate_track_points(
                        graph,
                        cameras,
                        views,
                        rejected_observations,
                        track_ids=set(points),
                    )[1]
                )
                diagnostics["bundle_adjustment_runs"] = int(
                    diagnostics["bundle_adjustment_runs"]
                ) + 1
                pruning = diagnostics.setdefault("bundle_adjustment_pruning", [])
                assert isinstance(pruning, list)
                pruning.append(
                    {"stage": "periodic_bundle_adjustment", **prune_stats}
                )
                _record_pose_stage(
                    diagnostics,
                    stage="periodic_bundle_adjustment",
                    view_order=view_order,
                    cameras=cameras,
                )

    reconstruction = _build_reconstruction(
        views[0].intrinsic,
        cameras,
        points,
        graph,
        view_order,
        diagnostics,
        rejected_observations,
    )
    initial_rmse = reconstruction.reprojection_rmse()
    _record_pose_stage(
        diagnostics,
        stage="before_final_bundle_adjustment",
        view_order=view_order,
        cameras=cameras,
    )
    adjusted, rejected_observations, final_rmse, prune_stats = (
        _bundle_adjust_with_pruning(
            reconstruction,
            graph,
            views,
            view_order,
            rejected_observations,
            max_iterations=8,
        )
    )
    pruning = diagnostics.setdefault("bundle_adjustment_pruning", [])
    assert isinstance(pruning, list)
    pruning.append({"stage": "final_bundle_adjustment", **prune_stats})
    _record_pose_stage(
        diagnostics,
        stage="after_final_bundle_adjustment",
        view_order=view_order,
        cameras=adjusted.cameras,
    )
    return adjusted.with_updates(
        initial_reprojection_rmse_px=initial_rmse,
        final_reprojection_rmse_px=final_rmse,
        diagnostics={
            **diagnostics,
            "bundle_adjustment_runs": int(diagnostics["bundle_adjustment_runs"]) + 1,
            "sparse_point_count": len(adjusted.points),
            "track_conflict_count": graph.conflict_count,
        },
    )


def score_orbit_reconstruction(
    reconstruction: Reconstruction,
    manifest: dict[str, Any],
) -> dict[str, float | int]:
    """Score an estimated reconstruction against exact orbit ground truth."""
    truth_frames = {
        str(frame["id"]): frame
        for frame in manifest["frames"]
        if "R_world_to_camera" in frame and "camera_center_world_m" in frame
    }
    camera_ids = [
        camera_id
        for camera_id in reconstruction.registered_view_ids
        if camera_id in truth_frames
    ]
    if not camera_ids:
        raise ValueError("no registered views have scoring ground truth")
    estimated_centers = np.array(
        [
            camera_center(
                reconstruction.cameras[camera_id].rotation,
                reconstruction.cameras[camera_id].translation,
            )
            for camera_id in camera_ids
        ],
        dtype=np.float64,
    )
    truth_centers = np.array(
        [
            np.asarray(truth_frames[camera_id]["camera_center_world_m"], dtype=np.float64)
            for camera_id in camera_ids
        ],
        dtype=np.float64,
    )
    rotation_errors = []
    for left, right in zip(camera_ids, camera_ids[1:]):
        estimated_relative = (
            reconstruction.cameras[right].rotation
            @ reconstruction.cameras[left].rotation.T
        )
        truth_relative = (
            np.asarray(truth_frames[right]["R_world_to_camera"], dtype=np.float64)
            @ np.asarray(truth_frames[left]["R_world_to_camera"], dtype=np.float64).T
        )
        rotation_errors.append(
            rotation_error_degrees(estimated_relative, truth_relative)
        )
    if not rotation_errors:
        rotation_errors = [0.0]
    return {
        "registered_view_count": len(reconstruction.registered_view_ids),
        "sparse_point_count": len(reconstruction.points),
        "track_observation_count": len(reconstruction.observations),
        "ate_m": ate_sim3(estimated_centers, truth_centers),
        "mean_rotation_error_deg": float(np.mean(rotation_errors)),
        "max_rotation_error_deg": float(np.max(rotation_errors)),
        "initial_reprojection_rmse_px": float(
            reconstruction.initial_reprojection_rmse_px
            if reconstruction.initial_reprojection_rmse_px is not None
            else reconstruction.reprojection_rmse()
        ),
        "final_reprojection_rmse_px": float(
            reconstruction.final_reprojection_rmse_px
            if reconstruction.final_reprojection_rmse_px is not None
            else reconstruction.reprojection_rmse()
        ),
    }


def _stage_camera_pose(stage_camera: dict[str, object]) -> CameraPose:
    return CameraPose(
        np.asarray(stage_camera["rotation"], dtype=np.float64),
        np.asarray(stage_camera["translation"], dtype=np.float64),
    )


def score_relative_rotation_stages(
    reconstruction: Reconstruction,
    manifest: dict[str, Any],
) -> list[dict[str, object]]:
    """Score estimated per-stage camera rotations against ground truth."""
    truth_frames = {
        str(frame["id"]): frame
        for frame in manifest["frames"]
        if "R_world_to_camera" in frame
    }
    stages = reconstruction.diagnostics.get("pose_stages", [])
    if not isinstance(stages, list):
        return []
    conflict_count = reconstruction.diagnostics.get("track_conflict_count")
    scored: list[dict[str, object]] = []
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        camera_records = stage.get("cameras")
        if not isinstance(camera_records, dict):
            continue
        cameras = {
            str(view_id): _stage_camera_pose(record)
            for view_id, record in camera_records.items()
            if isinstance(record, dict) and str(view_id) in truth_frames
        }
        registered = [
            str(view_id)
            for view_id in stage.get("registered_view_ids", [])
            if str(view_id) in cameras
        ]
        pair_errors = []
        for left, right in zip(registered, registered[1:]):
            estimated_relative = cameras[right].rotation @ cameras[left].rotation.T
            truth_relative = (
                np.asarray(truth_frames[right]["R_world_to_camera"], dtype=np.float64)
                @ np.asarray(truth_frames[left]["R_world_to_camera"], dtype=np.float64).T
            )
            pair_errors.append(
                {
                    "left_view_id": left,
                    "right_view_id": right,
                    "relative_rotation_error_deg": rotation_error_degrees(
                        estimated_relative,
                        truth_relative,
                    ),
                }
            )
        scored_stage = {
            "stage": stage.get("stage"),
            "view_id": stage.get("view_id"),
            "reference_view_id": stage.get("reference_view_id"),
            "registered_view_ids": registered,
            "relative_rotation_errors": pair_errors,
            "mean_relative_rotation_error_deg": (
                float(
                    np.mean(
                        [item["relative_rotation_error_deg"] for item in pair_errors]
                    )
                )
                if pair_errors
                else 0.0
            ),
            "max_relative_rotation_error_deg": (
                float(
                    np.max(
                        [item["relative_rotation_error_deg"] for item in pair_errors]
                    )
                )
                if pair_errors
                else 0.0
            ),
        }
        for key in (
            "pnp_correspondence_count",
            "pnp_inlier_count",
            "pnp_rmse_px",
            "median_triangulation_angle_deg",
            "pre_pnp_rejected_point_count",
            "pre_pnp_reprojection_error_px",
            "pre_pnp_reprojection_error_by_view_px",
            "pnp_track_source_pairs",
        ):
            if key in stage:
                scored_stage[key] = stage[key]
        if conflict_count is not None:
            scored_stage["track_conflict_count"] = conflict_count
        scored.append(scored_stage)
    return scored


def write_reconstruction_artifacts(
    artifacts: Path,
    reconstruction: Reconstruction,
    metrics: dict[str, float | int],
) -> dict[str, str]:
    artifacts.mkdir(parents=True, exist_ok=True)
    summary = {
        "registered_view_ids": reconstruction.registered_view_ids,
        "metrics": metrics,
        "diagnostics": reconstruction.diagnostics,
    }
    (artifacts / "reconstruction.json").write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    with (artifacts / "failure_sweep.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["parameter", "value", "metric", "measurement"],
        )
        writer.writeheader()
        for index, rmse in enumerate(
            (
                metrics["initial_reprojection_rmse_px"],
                metrics["final_reprojection_rmse_px"],
            )
        ):
            writer.writerow(
                {
                    "parameter": "bundle_adjustment_stage",
                    "value": index,
                    "metric": "reprojection_rmse_px",
                    "measurement": float(rmse),
                }
            )
        writer.writerow(
            {
                "parameter": "registered_views",
                "value": int(metrics["registered_view_count"]),
                "metric": "ate_m",
                "measurement": float(metrics["ate_m"]),
            }
        )
    count, digest = _tree_digest(artifacts)
    return {"artifact_count": str(count), "artifact_tree_sha256": digest}


def run_orbit_sfm_profile(artifacts: Path, profile: str) -> dict[str, Any]:
    """Run repo-owned incremental SfM on the generated orbit profile."""
    from scene.orbit import generate_orbit_scene

    started = time.perf_counter()
    scene_root = artifacts / "orbit-scene"
    manifest = generate_orbit_scene(scene_root, profile)
    reconstruction = reconstruct_orbit_scene(scene_root, manifest, profile)
    metrics = score_orbit_reconstruction(reconstruction, manifest)
    metrics["runtime_seconds"] = time.perf_counter() - started
    artifacts_summary = write_reconstruction_artifacts(
        artifacts,
        reconstruction,
        metrics,
    )
    rotation_stage_scores = score_relative_rotation_stages(
        reconstruction,
        manifest,
    )
    return {
        "metrics": metrics,
        "failure_sweep": [
            {
                "parameter": "bundle_adjustment_stage",
                "value": 0,
                "metric": "reprojection_rmse_px",
                "measurement": float(metrics["initial_reprojection_rmse_px"]),
            },
            {
                "parameter": "bundle_adjustment_stage",
                "value": 1,
                "metric": "reprojection_rmse_px",
                "measurement": float(metrics["final_reprojection_rmse_px"]),
            },
            {
                "parameter": "registered_views",
                "value": int(metrics["registered_view_count"]),
                "metric": "ate_m",
                "measurement": float(metrics["ate_m"]),
            },
        ],
        "observations": [
            "Incremental SfM bootstraps from image matches, registers remaining views by PnP, and refines with sparse Schur-complement bundle adjustment.",
            "Ground-truth poses, azimuths and depths are consumed only by the scoring step.",
        ],
        "extra_result": {
            "sfm_diagnostics": {
                **reconstruction.diagnostics,
                **artifacts_summary,
                "relative_rotation_error_by_stage": rotation_stage_scores,
            }
        },
    }
