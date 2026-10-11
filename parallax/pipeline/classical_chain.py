"""End-to-end classical reconstruction chain for the Parallax curriculum."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import time
from typing import Any
import zipfile

import numpy as np
from scipy.spatial import cKDTree

from camera.pose import camera_center
from evaluation.pose_metrics import rotation_error_degrees, umeyama_sim3
from evaluation.surface_metrics import surface_metrics
from fusion.marching_tetrahedra import Mesh, marching_tetrahedra
from fusion.tsdf import TSDFVolume, fuse_depth_maps
from geometry.triangulate import triangulate_point
from pipeline.contracts import canonical_json, sha256_file
from scene.orbit import generate_orbit_scene
from sfm.incremental import (
    reconstruct_orbit_scene,
    score_orbit_reconstruction,
    write_reconstruction_artifacts,
)
from sfm.reconstruction import CameraPose, Observation, Reconstruction
from stereo.plane_sweep import (
    DepthMapResult,
    StereoView,
    load_orbit_views,
    profile_depth_count,
    reconstruct_depth_maps,
    score_orbit_depths,
)


@dataclass(frozen=True)
class _ChainSettings:
    voxel_size_m: float
    truncation_m: float
    padding_m: float
    surface_tau_m: float


@dataclass(frozen=True)
class _SurfaceBranchResult:
    depth_maps: dict[str, DepthMapResult]
    depth_metrics: dict[str, Any]
    volume: TSDFVolume
    mesh: Mesh
    mesh_metrics: dict[str, float]
    camera_aligned_metrics: dict[str, float]
    icp_refinement: _IcpRefinement
    depth_maps_sha256: str
    mesh_sha256: str
    mvs_runtime_seconds: float
    fusion_runtime_seconds: float
    meshing_runtime_seconds: float


@dataclass(frozen=True)
class _GaugeParameters:
    depth_hypotheses_m: np.ndarray
    voxel_size_m: float
    truncation_m: float
    padding_m: float
    median_sparse_depth_m: float
    nominal_working_distance_m: float
    gauge_units_per_nominal_meter: float


@dataclass(frozen=True)
class _IcpRefinement:
    vertices: np.ndarray
    metrics: dict[str, float]
    scale: float
    rotation_deg: float
    translation_m: float
    iterations: int
    trim_fraction: float


_PROFILE_SETTINGS = {
    "smoke": _ChainSettings(
        voxel_size_m=0.12,
        truncation_m=0.24,
        padding_m=0.24,
        surface_tau_m=0.18,
    ),
    "full": _ChainSettings(
        voxel_size_m=0.08,
        truncation_m=0.18,
        padding_m=0.20,
        surface_tau_m=0.12,
    ),
}

_NOMINAL_WORKING_DISTANCE_M = {
    "smoke": 4.8,
    "full": 4.8,
}


def _write_npz_deterministic(path: Path, arrays: dict[str, np.ndarray]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(arrays):
            payload = io.BytesIO()
            np.lib.format.write_array(
                payload,
                np.asarray(arrays[name]),
                allow_pickle=False,
            )
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


def _profile_settings(profile: str) -> _ChainSettings:
    try:
        return _PROFILE_SETTINGS[profile]
    except KeyError as error:
        raise ValueError(f"unknown classical-chain profile: {profile}") from error


def _manifest_without_estimation_ground_truth(
    manifest: dict[str, Any],
) -> dict[str, Any]:
    score_only_fields = {
        "azimuth_degrees",
        "elevation_degrees",
        "R_world_to_camera",
        "t_world_to_camera_m",
        "camera_center_world_m",
        "depth_path",
        "normal_path",
        "surface_points_path",
        "surface_normals_path",
    }
    hidden = dict(manifest)
    hidden["frames"] = [
        {
            key: value
            for key, value in frame.items()
            if key not in score_only_fields
        }
        for frame in manifest["frames"]
    ]
    return hidden


def _camera_center_alignment(
    reconstruction: Reconstruction,
    manifest: dict[str, Any],
) -> tuple[list[str], float, np.ndarray, np.ndarray]:
    truth_frames = {
        str(frame["id"]): frame
        for frame in manifest["frames"]
        if "camera_center_world_m" in frame
    }
    view_ids = [
        view_id
        for view_id in reconstruction.registered_view_ids
        if view_id in reconstruction.cameras and view_id in truth_frames
    ]
    if len(view_ids) < 3:
        raise ValueError("Sim(3) alignment requires at least three registered views")
    estimated_centers = np.array(
        [
            camera_center(
                reconstruction.cameras[view_id].rotation,
                reconstruction.cameras[view_id].translation,
            )
            for view_id in view_ids
        ],
        dtype=np.float64,
    )
    truth_centers = np.array(
        [
            np.asarray(
                truth_frames[view_id]["camera_center_world_m"],
                dtype=np.float64,
            )
            for view_id in view_ids
        ],
        dtype=np.float64,
    )
    scale, rotation, translation = umeyama_sim3(estimated_centers, truth_centers)
    return view_ids, scale, rotation, translation


def _apply_sim3(
    points: np.ndarray,
    scale: float,
    rotation: np.ndarray,
    translation: np.ndarray,
) -> np.ndarray:
    return (scale * (rotation @ np.asarray(points, dtype=np.float64).T)).T + translation


def _sample_points(points: np.ndarray, max_points: int) -> np.ndarray:
    cloud = np.asarray(points, dtype=np.float64)
    if len(cloud) <= max_points:
        return cloud
    indices = np.linspace(0, len(cloud) - 1, max_points, dtype=np.int64)
    return cloud[indices]


def _refine_surface_alignment(
    camera_aligned_vertices: np.ndarray,
    truth_points: np.ndarray,
    *,
    tau: float,
    max_iterations: int = 6,
    trim_fraction: float = 0.80,
    max_sample_count: int = 8192,
) -> _IcpRefinement:
    """Refine score-side mesh alignment with bounded trimmed similarity ICP."""
    if not 0.0 < trim_fraction <= 1.0:
        raise ValueError("trim_fraction must be in (0, 1]")
    source = _sample_points(
        np.asarray(camera_aligned_vertices, dtype=np.float64),
        max_sample_count,
    )
    target = _sample_points(np.asarray(truth_points, dtype=np.float64), max_sample_count)
    if len(source) < 3 or len(target) < 3:
        raise ValueError("surface alignment needs at least three source and target points")
    tree = cKDTree(target)
    scale = 1.0
    rotation = np.eye(3, dtype=np.float64)
    translation = np.zeros(3, dtype=np.float64)
    completed_iterations = 0
    previous_rmse: float | None = None
    for _ in range(max_iterations):
        transformed = _apply_sim3(source, scale, rotation, translation)
        distances, indices = tree.query(transformed, k=1)
        finite = np.isfinite(distances)
        if int(np.count_nonzero(finite)) < 3:
            break
        finite_indices = np.nonzero(finite)[0]
        keep_count = max(3, int(np.ceil(len(finite_indices) * trim_fraction)))
        keep = finite_indices[np.argsort(distances[finite_indices])[:keep_count]]
        matched = target[indices[keep]]
        delta_scale, delta_rotation, delta_translation = umeyama_sim3(
            transformed[keep],
            matched,
        )
        if not np.isfinite(delta_scale) or delta_scale <= 0.0:
            break
        scale = float(delta_scale) * scale
        rotation = delta_rotation @ rotation
        translation = float(delta_scale) * (delta_rotation @ translation) + delta_translation
        completed_iterations += 1
        rmse = float(np.sqrt(np.mean(distances[keep] * distances[keep])))
        if previous_rmse is not None and abs(previous_rmse - rmse) < 1e-6:
            break
        previous_rmse = rmse

    refined_vertices = _apply_sim3(
        np.asarray(camera_aligned_vertices, dtype=np.float64),
        scale,
        rotation,
        translation,
    )
    return _IcpRefinement(
        vertices=refined_vertices,
        metrics=surface_metrics(refined_vertices, truth_points, tau=tau),
        scale=float(scale),
        rotation_deg=rotation_error_degrees(rotation, np.eye(3, dtype=np.float64)),
        translation_m=float(np.linalg.norm(translation)),
        iterations=completed_iterations,
        trim_fraction=float(trim_fraction),
    )


def _registered_views_in_sfm_gauge(
    truth_views: list[StereoView],
    reconstruction: Reconstruction,
    view_ids: list[str],
) -> list[StereoView]:
    truth_by_id = {view.view_id: view for view in truth_views}
    views = []
    for view_id in view_ids:
        truth = truth_by_id[view_id]
        pose = reconstruction.cameras[view_id]
        views.append(
            StereoView(
                view_id,
                truth.image,
                reconstruction.intrinsic,
                pose.rotation,
                pose.translation,
                None,
            )
        )
    if len(views) < 2:
        raise ValueError("classical MVS requires at least two SfM-registered views")
    return views


def _truth_registered_views(
    truth_views: list[StereoView],
    view_ids: list[str],
) -> list[StereoView]:
    truth_by_id = {view.view_id: view for view in truth_views}
    return [truth_by_id[view_id] for view_id in view_ids]


def _registered_sparse_depths(
    reconstruction: Reconstruction,
    view_ids: list[str],
) -> np.ndarray:
    if not reconstruction.points:
        return np.array([], dtype=np.float64)
    points = np.vstack(list(reconstruction.points.values())).astype(np.float64)
    depths = []
    for view_id in view_ids:
        pose = reconstruction.cameras[view_id]
        camera_points = (pose.rotation @ points.T).T + pose.translation
        depths.append(camera_points[:, 2])
    finite = np.concatenate(depths)
    return finite[np.isfinite(finite) & (finite > 1e-4)]


def _reconstruction_in_diagnostic_pose_gauge(
    reconstruction: Reconstruction,
    truth_views: list[StereoView],
    view_ids: list[str],
) -> Reconstruction:
    truth_by_id = {view.view_id: view for view in truth_views}
    selected_ids = [view_id for view_id in view_ids if view_id in truth_by_id]
    observations_by_track: dict[int, list[Observation]] = {}
    for observation in reconstruction.observations:
        if observation.camera_id in selected_ids:
            observations_by_track.setdefault(observation.track_id, []).append(
                observation
            )
    points: dict[int, np.ndarray] = {}
    for track_id, observations in observations_by_track.items():
        best: tuple[float, np.ndarray] | None = None
        for left_index, left in enumerate(observations):
            left_view = truth_by_id[left.camera_id]
            left_center = camera_center(
                left_view.R_world_to_camera,
                left_view.t_world_to_camera_m,
            )
            for right in observations[left_index + 1 :]:
                right_view = truth_by_id[right.camera_id]
                right_center = camera_center(
                    right_view.R_world_to_camera,
                    right_view.t_world_to_camera_m,
                )
                try:
                    point = triangulate_point(
                        left.pixel,
                        right.pixel,
                        left_view.K,
                        left_view.R_world_to_camera,
                        left_view.t_world_to_camera_m,
                        right_view.K,
                        right_view.R_world_to_camera,
                        right_view.t_world_to_camera_m,
                    )
                except ValueError:
                    continue
                left_depth = (
                    left_view.R_world_to_camera @ point
                    + left_view.t_world_to_camera_m
                )[2]
                right_depth = (
                    right_view.R_world_to_camera @ point
                    + right_view.t_world_to_camera_m
                )[2]
                if left_depth <= 1e-4 or right_depth <= 1e-4:
                    continue
                baseline = float(np.linalg.norm(left_center - right_center))
                if best is None or baseline > best[0]:
                    best = (baseline, point)
        if best is not None:
            points[track_id] = best[1]
    cameras = {
        view_id: CameraPose(
            truth_by_id[view_id].R_world_to_camera,
            truth_by_id[view_id].t_world_to_camera_m,
        )
        for view_id in selected_ids
    }
    return Reconstruction(
        reconstruction.intrinsic,
        cameras,
        points,
        reconstruction.observations,
        registered_view_ids=selected_ids,
        initial_reprojection_rmse_px=reconstruction.initial_reprojection_rmse_px,
        final_reprojection_rmse_px=reconstruction.final_reprojection_rmse_px,
        diagnostics=reconstruction.diagnostics,
    )


def _nominal_working_distance_m(profile: str) -> float:
    try:
        return _NOMINAL_WORKING_DISTANCE_M[profile]
    except KeyError as error:
        raise ValueError(f"unknown classical-chain profile: {profile}") from error


def _sparse_depth_hypotheses(
    sparse_depths_m: np.ndarray,
    depth_count: int,
    nominal_working_distance_m: float,
) -> np.ndarray:
    if depth_count < 2:
        raise ValueError("depth_count must be at least two")
    finite = np.asarray(sparse_depths_m, dtype=np.float64)
    finite = finite[np.isfinite(finite) & (finite > 1e-4)]
    if len(finite) < 8:
        raise ValueError(
            "at least eight sparse depths are required for scale-free parameters"
        )
    low = float(np.quantile(finite, 0.01))
    high = float(np.quantile(finite, 0.99))
    if high <= low:
        high = low + 1.0
    margin = max(0.10, 0.20 * (high - low))
    return np.linspace(max(1e-3, low - margin), high + margin, depth_count)


def _parameters_from_gauge(
    depth_hypotheses_m: np.ndarray,
    *,
    median_sparse_depth_m: float,
    nominal_working_distance_m: float,
    settings: _ChainSettings,
) -> _GaugeParameters:
    if (
        nominal_working_distance_m <= 0.0
        or not np.isfinite(nominal_working_distance_m)
    ):
        raise ValueError("nominal working distance must be finite and positive")
    gauge_units_per_nominal_meter = float(median_sparse_depth_m) / float(
        nominal_working_distance_m
    )
    if (
        not np.isfinite(gauge_units_per_nominal_meter)
        or gauge_units_per_nominal_meter <= 0.0
    ):
        raise ValueError("invalid reconstruction gauge scale")
    return _GaugeParameters(
        depth_hypotheses_m=np.asarray(depth_hypotheses_m, dtype=np.float64),
        voxel_size_m=settings.voxel_size_m * gauge_units_per_nominal_meter,
        truncation_m=settings.truncation_m * gauge_units_per_nominal_meter,
        padding_m=settings.padding_m * gauge_units_per_nominal_meter,
        median_sparse_depth_m=float(median_sparse_depth_m),
        nominal_working_distance_m=float(nominal_working_distance_m),
        gauge_units_per_nominal_meter=gauge_units_per_nominal_meter,
    )


def _derive_gauge_parameters(
    reconstruction: Reconstruction,
    view_ids: list[str],
    settings: _ChainSettings,
    *,
    profile: str = "smoke",
    depth_count: int | None = None,
) -> _GaugeParameters:
    nominal_working_distance = _nominal_working_distance_m(profile)
    sparse_depths = _registered_sparse_depths(reconstruction, view_ids)
    if len(sparse_depths) < 8:
        raise ValueError(
            "at least eight sparse depths are required for scale-free parameters"
        )
    median_sparse_depth = float(np.median(sparse_depths))
    return _parameters_from_gauge(
        _sparse_depth_hypotheses(
            sparse_depths,
            profile_depth_count(profile) if depth_count is None else depth_count,
            nominal_working_distance,
        ),
        median_sparse_depth_m=median_sparse_depth,
        nominal_working_distance_m=nominal_working_distance,
        settings=settings,
    )


def _depth_archive(path: Path, depths: dict[str, DepthMapResult]) -> None:
    arrays: dict[str, np.ndarray] = {}
    for view_id, result in depths.items():
        arrays[f"{view_id}_depth_m"] = result.depth.astype(np.float32)
        arrays[f"{view_id}_valid_mask"] = result.valid_mask.astype(np.uint8)
        arrays[f"{view_id}_cost"] = result.cost.astype(np.float32)
    _write_npz_deterministic(path, arrays)


def _save_mesh(
    path: Path,
    mesh: Mesh,
    aligned_vertices: np.ndarray,
    refined_vertices: np.ndarray,
) -> None:
    _write_npz_deterministic(
        path,
        {
            "vertices_sfm_gauge": mesh.vertices.astype(np.float32),
            "vertices_camera_aligned_m": aligned_vertices.astype(np.float32),
            "vertices_icp_refined_m": refined_vertices.astype(np.float32),
            "triangles": mesh.triangles.astype(np.int64),
        },
    )


def _depth_map_arrays(
    depth_maps: dict[str, DepthMapResult],
) -> dict[str, np.ndarray]:
    return {
        view_id: result.depth
        for view_id, result in depth_maps.items()
    }


def _depth_valid_masks(
    depth_maps: dict[str, DepthMapResult],
) -> dict[str, np.ndarray]:
    return {
        view_id: result.valid_mask
        for view_id, result in depth_maps.items()
    }


def _scaled_depths(
    depth_maps: dict[str, DepthMapResult],
    scale: float,
) -> dict[str, DepthMapResult]:
    return {
        view_id: DepthMapResult(
            result.depth * float(scale),
            result.valid_mask,
            result.cost,
        )
        for view_id, result in depth_maps.items()
    }


def _run_surface_branch(
    output: Path,
    *,
    label: str,
    views: list[StereoView],
    truth_views: list[StereoView],
    parameters: _GaugeParameters,
    surface_tau_m: float,
    truth_points: np.ndarray,
    scale_to_truth: float,
    rotation_to_truth: np.ndarray,
    translation_to_truth: np.ndarray,
    depth_archive_name: str,
    mesh_name: str,
) -> _SurfaceBranchResult:
    started = time.perf_counter()
    depth_maps = reconstruct_depth_maps(
        views,
        depth_count=len(parameters.depth_hypotheses_m),
        max_neighbours=2,
        window_radius=2,
        consistency_neighbours=1,
        depth_hypotheses_m=parameters.depth_hypotheses_m,
    )
    depth_archive = output / depth_archive_name
    _depth_archive(depth_archive, depth_maps)

    depth_metrics_for_truth = score_orbit_depths(
        truth_views,
        _scaled_depths(depth_maps, scale_to_truth),
        texture_gradient_threshold=3.0,
    )
    mvs_runtime_seconds = time.perf_counter() - started

    started = time.perf_counter()
    volume = fuse_depth_maps(
        views,
        _depth_map_arrays(depth_maps),
        voxel_size_m=parameters.voxel_size_m,
        truncation_m=parameters.truncation_m,
        padding_m=parameters.padding_m,
        valid_masks=_depth_valid_masks(depth_maps),
    )
    fusion_runtime_seconds = time.perf_counter() - started

    started = time.perf_counter()
    mesh = marching_tetrahedra(
        volume.values,
        origin_m=volume.origin_m,
        voxel_size_m=volume.voxel_size_m,
        valid_mask=volume.weights > 0.0,
    )
    meshing_runtime_seconds = time.perf_counter() - started
    if len(mesh.vertices) == 0:
        raise ValueError(f"{label} branch produced an empty fused mesh")
    aligned_vertices = _apply_sim3(
        mesh.vertices,
        scale_to_truth,
        rotation_to_truth,
        translation_to_truth,
    )
    mesh_path = output / mesh_name
    camera_aligned_metrics = surface_metrics(
        aligned_vertices,
        truth_points,
        tau=surface_tau_m,
    )
    refinement = _refine_surface_alignment(
        aligned_vertices,
        truth_points,
        tau=surface_tau_m,
    )
    _save_mesh(mesh_path, mesh, aligned_vertices, refinement.vertices)
    return _SurfaceBranchResult(
        depth_maps=depth_maps,
        depth_metrics=depth_metrics_for_truth,
        volume=volume,
        mesh=mesh,
        mesh_metrics=refinement.metrics,
        camera_aligned_metrics=camera_aligned_metrics,
        icp_refinement=refinement,
        depth_maps_sha256=sha256_file(depth_archive),
        mesh_sha256=sha256_file(mesh_path),
        mvs_runtime_seconds=mvs_runtime_seconds,
        fusion_runtime_seconds=fusion_runtime_seconds,
        meshing_runtime_seconds=meshing_runtime_seconds,
    )


def _surface_diagnostic(
    branch: _SurfaceBranchResult,
    parameters: _GaugeParameters,
) -> dict[str, int | float]:
    return {
        "depth_absrel": float(branch.depth_metrics["mean_absrel"]),
        "depth_delta_lt_1_25": float(branch.depth_metrics["mean_delta_lt_1_25"]),
        "valid_pixel_fraction": float(
            branch.depth_metrics["mean_valid_pixel_fraction"]
        ),
        "surface_chamfer_m": float(branch.mesh_metrics["chamfer_distance"]),
        "surface_accuracy_m": float(branch.mesh_metrics["accuracy"]),
        "surface_completeness_m": float(branch.mesh_metrics["completeness"]),
        "surface_f_score_tau": float(branch.mesh_metrics["f_score"]),
        "camera_aligned_surface_chamfer_m": float(
            branch.camera_aligned_metrics["chamfer_distance"]
        ),
        "camera_aligned_surface_accuracy_m": float(
            branch.camera_aligned_metrics["accuracy"]
        ),
        "camera_aligned_surface_completeness_m": float(
            branch.camera_aligned_metrics["completeness"]
        ),
        "camera_aligned_surface_f_score_tau": float(
            branch.camera_aligned_metrics["f_score"]
        ),
        "icp_refined_surface_chamfer_m": float(branch.mesh_metrics["chamfer_distance"]),
        "icp_refined_surface_accuracy_m": float(branch.mesh_metrics["accuracy"]),
        "icp_refined_surface_completeness_m": float(
            branch.mesh_metrics["completeness"]
        ),
        "icp_refined_surface_f_score_tau": float(branch.mesh_metrics["f_score"]),
        "icp_refinement_rotation_deg": float(branch.icp_refinement.rotation_deg),
        "icp_refinement_translation_m": float(branch.icp_refinement.translation_m),
        "icp_refinement_scale": float(branch.icp_refinement.scale),
        "icp_refinement_iterations": int(branch.icp_refinement.iterations),
        "icp_refinement_trim_fraction": float(branch.icp_refinement.trim_fraction),
        "depth_hypothesis_count": int(len(parameters.depth_hypotheses_m)),
        "voxel_size_sfm_gauge": float(parameters.voxel_size_m),
        "truncation_sfm_gauge": float(parameters.truncation_m),
        "padding_sfm_gauge": float(parameters.padding_m),
        "median_sparse_depth_gauge": float(
            parameters.median_sparse_depth_m
        ),
        "nominal_working_distance_m": float(
            parameters.nominal_working_distance_m
        ),
        "gauge_units_per_nominal_meter": float(
            parameters.gauge_units_per_nominal_meter
        ),
        "mesh_vertex_count": int(branch.mesh.vertices.shape[0]),
        "mesh_triangle_count": int(branch.mesh.triangles.shape[0]),
        "observed_voxel_count": branch.volume.observed_voxel_count,
    }


def _pose_attribution_sweep(
    sfm_pose: dict[str, int | float],
    ground_truth_pose: dict[str, int | float],
) -> list[dict[str, float | int | str]]:
    rows = []
    for pose_index, pose_metrics in enumerate((sfm_pose, ground_truth_pose)):
        for metric in (
            "surface_chamfer_m",
            "surface_accuracy_m",
            "surface_completeness_m",
            "surface_f_score_tau",
        ):
            rows.append(
                {
                    "parameter": "pose_attribution_index",
                    "value": pose_index,
                    "metric": metric,
                    "measurement": float(pose_metrics[metric]),
                }
            )
    return rows


def run_classical_chain_profile(
    output: Path,
    profile: str,
    *,
    include_pose_attribution: bool = False,
    hide_estimation_ground_truth: bool = False,
) -> dict[str, Any]:
    """Run images -> SfM poses -> plane-sweep depth -> TSDF mesh -> metrics."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    settings = _profile_settings(profile)
    scene_root = output / "orbit-scene"
    manifest = generate_orbit_scene(scene_root, profile)
    truth_views = load_orbit_views(scene_root)

    started = time.perf_counter()
    estimation_manifest = (
        _manifest_without_estimation_ground_truth(manifest)
        if hide_estimation_ground_truth
        else manifest
    )
    reconstruction = reconstruct_orbit_scene(scene_root, estimation_manifest, profile)
    sfm_runtime_seconds = time.perf_counter() - started
    sfm_metrics = score_orbit_reconstruction(reconstruction, manifest)
    sfm_metrics["runtime_seconds"] = sfm_runtime_seconds
    sfm_artifacts = write_reconstruction_artifacts(
        output / "sfm",
        reconstruction,
        sfm_metrics,
    )
    view_ids, scale, rotation, translation = _camera_center_alignment(
        reconstruction,
        manifest,
    )

    mvs_views = _registered_views_in_sfm_gauge(truth_views, reconstruction, view_ids)
    primary_parameters = _derive_gauge_parameters(
        reconstruction,
        view_ids,
        settings,
        profile=profile,
    )

    truth_by_id = {view.view_id: view for view in truth_views}
    truth_registered_views = [truth_by_id[view_id] for view_id in view_ids]
    truth_points = np.load(
        scene_root / manifest["surface_truth"]["points_path"],
        allow_pickle=False,
    )
    primary = _run_surface_branch(
        output,
        label="sfm_pose",
        views=mvs_views,
        truth_views=truth_registered_views,
        parameters=primary_parameters,
        surface_tau_m=settings.surface_tau_m,
        truth_points=truth_points,
        scale_to_truth=scale,
        rotation_to_truth=rotation,
        translation_to_truth=translation,
        depth_archive_name="depth-maps.npz",
        mesh_name="classical-chain-mesh.npz",
    )
    scaled_depth_metrics = primary.depth_metrics
    mesh_metrics = primary.mesh_metrics

    metrics = {
        "registered_view_count": int(sfm_metrics["registered_view_count"]),
        "sparse_point_count": int(sfm_metrics["sparse_point_count"]),
        "track_observation_count": int(sfm_metrics["track_observation_count"]),
        "ate_m": float(sfm_metrics["ate_m"]),
        "mean_rotation_error_deg": float(sfm_metrics["mean_rotation_error_deg"]),
        "max_rotation_error_deg": float(sfm_metrics["max_rotation_error_deg"]),
        "ba_initial_reprojection_rmse_px": float(
            sfm_metrics["initial_reprojection_rmse_px"]
        ),
        "ba_final_reprojection_rmse_px": float(
            sfm_metrics["final_reprojection_rmse_px"]
        ),
        "depth_absrel": float(scaled_depth_metrics["mean_absrel"]),
        "depth_delta_lt_1_25": float(scaled_depth_metrics["mean_delta_lt_1_25"]),
        "valid_pixel_fraction": float(
            scaled_depth_metrics["mean_valid_pixel_fraction"]
        ),
        "evaluated_view_count": int(scaled_depth_metrics["evaluated_view_count"]),
        "evaluated_pixel_count": int(scaled_depth_metrics["evaluated_pixel_count"]),
        "valid_pixel_count": int(scaled_depth_metrics["valid_pixel_count"]),
        "surface_chamfer_m": float(mesh_metrics["chamfer_distance"]),
        "surface_accuracy_m": float(mesh_metrics["accuracy"]),
        "surface_completeness_m": float(mesh_metrics["completeness"]),
        "surface_f_score_tau": float(mesh_metrics["f_score"]),
        "camera_aligned_surface_chamfer_m": float(
            primary.camera_aligned_metrics["chamfer_distance"]
        ),
        "camera_aligned_surface_accuracy_m": float(
            primary.camera_aligned_metrics["accuracy"]
        ),
        "camera_aligned_surface_completeness_m": float(
            primary.camera_aligned_metrics["completeness"]
        ),
        "camera_aligned_surface_f_score_tau": float(
            primary.camera_aligned_metrics["f_score"]
        ),
        "icp_refined_surface_chamfer_m": float(mesh_metrics["chamfer_distance"]),
        "icp_refined_surface_accuracy_m": float(mesh_metrics["accuracy"]),
        "icp_refined_surface_completeness_m": float(mesh_metrics["completeness"]),
        "icp_refined_surface_f_score_tau": float(mesh_metrics["f_score"]),
        "icp_refinement_rotation_deg": float(primary.icp_refinement.rotation_deg),
        "icp_refinement_translation_m": float(primary.icp_refinement.translation_m),
        "icp_refinement_scale": float(primary.icp_refinement.scale),
        "icp_refinement_iterations": int(primary.icp_refinement.iterations),
        "icp_refinement_trim_fraction": float(primary.icp_refinement.trim_fraction),
        "sim3_scale_m_per_sfm_unit": float(scale),
        "depth_hypothesis_count": int(len(primary_parameters.depth_hypotheses_m)),
        "voxel_size_sfm_gauge": float(primary_parameters.voxel_size_m),
        "truncation_sfm_gauge": float(primary_parameters.truncation_m),
        "padding_sfm_gauge": float(primary_parameters.padding_m),
        "median_sparse_depth_sfm_gauge": float(
            primary_parameters.median_sparse_depth_m
        ),
        "nominal_working_distance_m": float(
            primary_parameters.nominal_working_distance_m
        ),
        "gauge_units_per_nominal_meter": float(
            primary_parameters.gauge_units_per_nominal_meter
        ),
        "mesh_vertex_count": int(primary.mesh.vertices.shape[0]),
        "mesh_triangle_count": int(primary.mesh.triangles.shape[0]),
        "observed_voxel_count": primary.volume.observed_voxel_count,
        "sfm_runtime_seconds": float(sfm_runtime_seconds),
        "plane_sweep_runtime_seconds": float(primary.mvs_runtime_seconds),
        "fusion_runtime_seconds": float(primary.fusion_runtime_seconds),
        "meshing_runtime_seconds": float(primary.meshing_runtime_seconds),
    }
    failure_sweep = []
    for index, row in enumerate(scaled_depth_metrics["per_view"]):
        failure_sweep.extend(
            [
                {
                    "parameter": "view_index",
                    "value": index,
                    "metric": "absrel",
                    "measurement": float(row["absrel"]),
                },
                {
                    "parameter": "view_index",
                    "value": index,
                    "metric": "delta_lt_1_25",
                    "measurement": float(row["delta_lt_1_25"]),
                },
                {
                    "parameter": "view_index",
                    "value": index,
                    "metric": "valid_pixel_fraction",
                    "measurement": float(row["valid_pixel_fraction"]),
                },
            ]
        )
    failure_sweep.extend(
        [
            {
                "parameter": "mesh_alignment",
                "value": "camera_center_sim3",
                "metric": "camera_aligned_surface_chamfer_m",
                "measurement": metrics["camera_aligned_surface_chamfer_m"],
            },
            {
                "parameter": "mesh_alignment",
                "value": "camera_center_sim3",
                "metric": "camera_aligned_surface_f_score_tau",
                "measurement": metrics["camera_aligned_surface_f_score_tau"],
            },
            {
                "parameter": "mesh_alignment",
                "value": "bounded_trimmed_similarity_icp",
                "metric": "surface_chamfer_m",
                "measurement": metrics["surface_chamfer_m"],
            },
            {
                "parameter": "mesh_alignment",
                "value": "bounded_trimmed_similarity_icp",
                "metric": "surface_f_score_tau",
                "measurement": metrics["surface_f_score_tau"],
            },
        ]
    )
    pose_attribution = None
    if include_pose_attribution:
        truth_pose_views = _truth_registered_views(truth_views, view_ids)
        diagnostic_reconstruction = _reconstruction_in_diagnostic_pose_gauge(
            reconstruction,
            truth_views,
            view_ids,
        )
        diagnostic_parameters = _derive_gauge_parameters(
            diagnostic_reconstruction,
            view_ids,
            settings,
            profile=profile,
        )
        ground_truth_pose = _run_surface_branch(
            output,
            label="ground_truth_pose",
            views=truth_pose_views,
            truth_views=truth_registered_views,
            parameters=diagnostic_parameters,
            surface_tau_m=settings.surface_tau_m,
            truth_points=truth_points,
            scale_to_truth=1.0,
            rotation_to_truth=np.eye(3, dtype=np.float64),
            translation_to_truth=np.zeros(3, dtype=np.float64),
            depth_archive_name="ground-truth-pose-depth-maps.npz",
            mesh_name="ground-truth-pose-mesh.npz",
        )
        sfm_pose_metrics = _surface_diagnostic(primary, primary_parameters)
        ground_truth_pose_metrics = _surface_diagnostic(
            ground_truth_pose,
            diagnostic_parameters,
        )
        pose_attribution = {
            "estimate_use": "diagnostic_only_not_used_by_sfm_pose_chain",
            "substitution": "ground_truth_poses_only",
            "depth_hypotheses": (
                "sparse depth quantiles in each branch pose gauge"
            ),
            "metrics": {
                "sfm_pose": sfm_pose_metrics,
                "ground_truth_pose": ground_truth_pose_metrics,
            },
            "artifacts": {
                "ground_truth_pose_depth_maps_sha256": (
                    ground_truth_pose.depth_maps_sha256
                ),
                "ground_truth_pose_mesh_sha256": ground_truth_pose.mesh_sha256,
            },
        }
        failure_sweep.extend(
            _pose_attribution_sweep(
                sfm_pose_metrics,
                ground_truth_pose_metrics,
            )
        )
    summary = {
        "schema_version": 1,
        "profile": profile,
        "scene": manifest["scene"]["name"],
        "view_count": len(truth_views),
        "registered_view_ids": view_ids,
        "mesh_alignment": "sim3_to_ground_truth_then_score_only_icp",
        "settings": {
            "voxel_size_m": settings.voxel_size_m,
            "truncation_m": settings.truncation_m,
            "padding_m": settings.padding_m,
            "surface_tau_m": settings.surface_tau_m,
            "parameter_rule": (
                "voxel, truncation and padding are profile fractions of median "
                "registered sparse-point depth; Sim3 scale is scoring-only"
            ),
            "sfm_gauge": {
                "voxel_size": float(primary_parameters.voxel_size_m),
                "truncation": float(primary_parameters.truncation_m),
                "padding": float(primary_parameters.padding_m),
                "median_sparse_depth": float(
                    primary_parameters.median_sparse_depth_m
                ),
                "nominal_working_distance_m": float(
                    primary_parameters.nominal_working_distance_m
                ),
                "gauge_units_per_nominal_meter": float(
                    primary_parameters.gauge_units_per_nominal_meter
                ),
                "fractions_of_median_sparse_depth": {
                    "voxel_size": float(
                        settings.voxel_size_m
                        / primary_parameters.nominal_working_distance_m
                    ),
                    "truncation": float(
                        settings.truncation_m
                        / primary_parameters.nominal_working_distance_m
                    ),
                    "padding": float(
                        settings.padding_m
                        / primary_parameters.nominal_working_distance_m
                    ),
                },
            },
        },
        "metrics": metrics,
        "depth_metrics": scaled_depth_metrics,
        "failure_sweep": failure_sweep,
        "observations": [
            "The same generated RGB views feed incremental SfM, plane-sweep MVS, TSDF fusion and tetrahedral meshing.",
            "Depth hypotheses are derived from sparse SfM point depths, keeping MVS in the SfM gauge.",
            "Surface metrics report both camera-center Sim(3) alignment and a bounded score-only similarity ICP refinement.",
        ],
        "artifacts": {
            "scene_manifest_sha256": sha256_file(scene_root / "manifest.json"),
            "truth_surface_points_sha256": manifest["surface_truth"]["points_sha256"],
            "sfm_artifact_count": int(sfm_artifacts["artifact_count"]),
            "sfm_artifact_tree_sha256": sfm_artifacts["artifact_tree_sha256"],
            "depth_maps_sha256": primary.depth_maps_sha256,
            "mesh_sha256": primary.mesh_sha256,
        },
    }
    if pose_attribution is not None:
        summary["pose_attribution_diagnostic"] = pose_attribution
    (output / "classical-chain-metrics.json").write_bytes(canonical_json(summary))
    artifact_count, artifact_tree_sha256 = _tree_digest(
        output,
        exclude={"classical-chain-metrics.json"},
    )
    summary["artifacts"]["generated_artifact_count"] = artifact_count
    summary["artifacts"]["generated_artifact_tree_sha256"] = artifact_tree_sha256
    (output / "classical-chain-metrics.json").write_bytes(canonical_json(summary))
    return summary
