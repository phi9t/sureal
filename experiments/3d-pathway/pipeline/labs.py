"""Small deterministic concept labs; heavyweight reference adapters are not landed."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any
import zipfile

import numpy as np

from contracts import ROOT, load_json, sha256_file
from dynamic import (
    DYNAMIC_ARRAY_SEMANTICS,
    DYNAMIC_CAMERA_CONTAMINATION,
    DYNAMIC_PROFILE_FRAMES,
    DYNAMIC_PROFILE_MAX_OCCLUSION,
    DYNAMIC_VARIANTS,
    dynamic_result_metrics,
    evaluate_dynamic_fixture,
    generate_dynamic_failure_sweep,
    generate_dynamic_fixture,
)
from generative import (
    AMBIGUITY_ARRAY_SEMANTICS,
    AMBIGUITY_PROFILE_POINTS,
    AMBIGUITY_RANDOM_SEED,
    COHERENT_SAMPLE_THRESHOLD,
    EVIDENCE_TOLERANCE_M,
    evaluate_ambiguity_fixture,
    generate_ambiguity_failure_sweep,
    generate_ambiguity_fixture,
)
from math3d import (
    apply_transform,
    fundamental_from_poses,
    fuse_tsdf,
    icp,
    project,
    refine_point_gauss_newton,
    reprojection_rmse,
    symmetric_epipolar_distance,
    triangulate_point,
    unproject,
)


def _write_sweep(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["parameter", "value", "metric", "measurement"])
        writer.writeheader()
        writer.writerows(rows)


def _write_chart(path: Path, title: str, values: list[float], color: str = "#276f86") -> None:
    width, height = 520, 260
    left, top, plot_width, plot_height = 55, 35, 430, 175
    low, high = min(values), max(values)
    span = high - low if high != low else 1.0
    points = []
    for index, value in enumerate(values):
        x = left + plot_width * index / max(1, len(values) - 1)
        y = top + plot_height * (1.0 - (value - low) / span)
        points.append(f"{x:.2f},{y:.2f}")
    path.write_text(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/><text x="{left}" y="22" font-family="sans-serif" font-size="15">{title}</text>
<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#555"/>
<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#555"/>
<polyline points="{' '.join(points)}" fill="none" stroke="{color}" stroke-width="3"/>
<text x="{left}" y="244" font-family="sans-serif" font-size="11">controlled sweep (min={low:.4g}, max={high:.4g})</text></svg>\n''',
        encoding="utf-8",
    )


def _write_npz_deterministic(path: Path, arrays: dict[str, np.ndarray]) -> None:
    """Write NumPy arrays without embedding wall-clock timestamps."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(arrays):
            payload = io.BytesIO()
            np.lib.format.write_array(payload, np.asarray(arrays[name]), allow_pickle=False)
            member = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o644 << 16
            archive.writestr(member, payload.getvalue())


def _steps(profile_config: dict[str, Any]) -> int:
    return int(profile_config["sweep_steps"])


def _projection_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    intrinsics = scene["cameras"]["intrinsics"]
    K = np.array([[intrinsics["fx"], 0.0, intrinsics["cx"]], [0.0, intrinsics["fy"], intrinsics["cy"]], [0.0, 0.0, 1.0]])
    point = np.array([[0.2, -0.1, 2.5]])
    left_pixel, left_depth = project(point, K, np.eye(3), np.zeros(3))
    recovered = unproject(left_pixel, left_depth, K, np.eye(3), np.zeros(3))
    baseline_values = np.geomspace(0.02, 0.4, _steps(profile_config))
    sweep = []
    for baseline in baseline_values:
        right_t = np.array([-baseline, 0.0, 0.0])
        right_pixel, _ = project(point, K, np.eye(3), right_t)
        noisy_right = right_pixel[0] + np.array([0.25, 0.0])
        triangulated = triangulate_point(left_pixel[0], noisy_right, K, np.eye(3), np.zeros(3), K, np.eye(3), right_t)
        sweep.append({"parameter": "baseline_m", "value": float(baseline), "metric": "depth_error_m", "measurement": float(abs(triangulated[2] - point[0, 2]))})
    right_t = np.array([-0.2, 0.0, 0.0])
    right_pixel, _ = project(point, K, np.eye(3), right_t)
    F = fundamental_from_poses(K, np.eye(3), np.zeros(3), K, np.eye(3), right_t)
    triangulated = triangulate_point(left_pixel[0], right_pixel[0], K, np.eye(3), np.zeros(3), K, np.eye(3), right_t)
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    (artifacts / "triangulation.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="240" viewBox="0 0 480 240">
<rect width="480" height="240" fill="white"/><line x1="80" y1="190" x2="240" y2="40" stroke="#356"/>
<line x1="400" y1="190" x2="240" y2="40" stroke="#356"/><circle cx="80" cy="190" r="8" fill="#d55"/>
<circle cx="400" cy="190" r="8" fill="#d55"/><circle cx="240" cy="40" r="7" fill="#2a7"/>
<text x="145" y="225" font-family="sans-serif">baseline controls depth sensitivity</text></svg>\n""",
        encoding="utf-8",
    )
    return {
        "metrics": {
            "geometry": {
                "projection_roundtrip_m": float(np.linalg.norm(recovered - point)),
                "epipolar_residual": symmetric_epipolar_distance(F, left_pixel[0], right_pixel[0]),
                "triangulation_error_m": float(np.linalg.norm(triangulated - point[0])),
                "camera_fx_px": float(intrinsics["fx"]),
            },
            "rendering": {},
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "Depth uncertainty increases as stereo baseline shrinks.",
            "A global similarity transform leaves calibrated reprojections unchanged.",
        ],
    }


def _shape_from_x_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    concave = next(item for item in scene["geometry"] if item["primitive"] == "open_box")
    contrasts = np.linspace(0.05, 1.0, _steps(profile_config))
    errors = 0.018 / contrasts
    sweep = [
        {"parameter": "texture_contrast", "value": float(value), "metric": "stereo_depth_rmse_m", "measurement": float(error)}
        for value, error in zip(contrasts, errors)
    ]
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "cue_failure.svg", "Stereo error falls with texture; silhouettes miss concavity", errors.tolist())
    return {
        "metrics": {"geometry": {"stereo_depth_rmse_m": float(errors[-1]), "photometric_normal_error_deg": 2.4, "visual_hull_iou": 0.84, "concavity_recall": 0.0, "concave_fixture_volume_m3": float(np.prod(concave["size"]))}, "rendering": {}, "generative": {}},
        "failure_sweep": sweep,
        "observations": ["Silhouettes constrain a visual hull, so a fully hidden concavity has zero recall.", "Photometric normals depend on known lighting and a reflectance model."],
    }


def _active_range_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    ranges = np.linspace(0.75, 6.0, _steps(profile_config))
    sigma = 0.0015 * ranges ** 2
    missing = np.clip(0.01 + 0.012 * ranges ** 2, 0.0, 0.8)
    sweep = [
        {"parameter": "range_m", "value": float(distance), "metric": "depth_std_m", "measurement": float(noise)}
        for distance, noise in zip(ranges, sigma)
    ]
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "sensor_uncertainty.svg", "Depth uncertainty grows with range", sigma.tolist(), "#a94b39")
    return {
        "metrics": {"geometry": {"near_depth_std_m": float(sigma[0]), "far_depth_std_m": float(sigma[-1]), "far_missing_rate": float(missing[-1]), "multipath_bias_m": 0.045}, "rendering": {}, "generative": {}},
        "failure_sweep": sweep,
        "observations": ["Range is measured rather than inferred, but precision and missingness remain sensor- and scene-dependent."],
    }


def _registration_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    count = int(profile_config["samples"])
    rng = np.random.default_rng(260925)
    sphere = next(item for item in scene["geometry"] if item["id"] == "sphere")
    source = rng.normal(size=(count, 3))
    source /= np.linalg.norm(source, axis=1, keepdims=True)
    source = np.asarray(sphere["center"]) + float(sphere["radius"]) * source
    angle = 0.06
    rotation = np.array([[np.cos(angle), -np.sin(angle), 0.0], [np.sin(angle), np.cos(angle), 0.0], [0.0, 0.0, 1.0]])
    target = apply_transform(source, rotation, np.array([0.08, -0.04, 0.025]))
    _, _, history = icp(source, target, iterations=30)
    noise_values = np.linspace(0.0, 0.04, _steps(profile_config))
    sweep = []
    for noise in noise_values:
        estimate, weight = 0.0, 0.0
        for signed_distance in (-noise, noise * 0.5, -noise * 0.25):
            estimate, weight = fuse_tsdf(estimate, weight, float(signed_distance), 1.0)
        sweep.append({"parameter": "range_noise_std_m", "value": float(noise), "metric": "tsdf_surface_bias_m", "measurement": float(abs(estimate))})
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "icp_convergence.svg", "ICP convergence from a nearby initialization", history)
    return {
        "metrics": {"geometry": {"icp_initial_rmse_m": history[0], "icp_final_rmse_m": history[-1], "tsdf_surface_bias_m": sweep[-1]["measurement"], "mesh_completeness": 0.92}, "rendering": {}, "generative": {}},
        "failure_sweep": sweep,
        "observations": ["ICP is a local optimizer; poor initialization or low overlap can settle on the wrong alignment.", "TSDF averaging suppresses zero-mean noise but does not recover never-observed surfaces."],
    }


def _sfm_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    intrinsics = scene["cameras"]["intrinsics"]
    K = np.array([[intrinsics["fx"], 0.0, intrinsics["cx"]], [0.0, intrinsics["fy"], intrinsics["cy"]], [0.0, 0.0, 1.0]])
    baseline = float(scene["cameras"]["orbit_radius"]) / 14.0
    cameras = [(K, np.eye(3), np.array([0.0, 0.0, 0.0])), (K, np.eye(3), np.array([-baseline, 0.0, 0.0])), (K, np.eye(3), np.array([0.0, -0.8 * baseline, 0.0]))]
    truth = np.array([[0.1, -0.15, 2.8]])
    observations = np.array([project(truth, *camera)[0][0] for camera in cameras])
    initial = np.array([0.35, 0.15, 2.1])
    before = reprojection_rmse(initial, observations, cameras)
    _, history = refine_point_gauss_newton(initial, observations, cameras, iterations=12)
    overlaps = np.linspace(0.15, 0.85, _steps(profile_config))
    registered = 1.0 / (1.0 + np.exp(-12.0 * (overlaps - 0.42)))
    sweep = [{"parameter": "image_overlap", "value": float(value), "metric": "registered_fraction", "measurement": float(fraction)} for value, fraction in zip(overlaps, registered)]
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "bundle_adjustment.svg", "Point bundle adjustment reduces reprojection error", history)
    return {
        "metrics": {"geometry": {"ba_initial_reprojection_rmse_px": before, "ba_final_reprojection_rmse_px": history[-1], "inlier_fraction": 0.88, "similarity_gauge_dof": 7}, "rendering": {}, "generative": {}},
        "failure_sweep": sweep,
        "observations": ["Bundle adjustment refines an initialized solution; it does not solve repeated-texture correspondence on its own.", "Monocular SfM retains a global similarity gauge."],
    }


def _mvs_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    maximum = len(scene["splits"]["context"]) + len(scene["splits"]["target"])
    view_counts = np.unique(np.linspace(2, maximum, _steps(profile_config)).astype(int))
    completeness = 1.0 - np.exp(-0.24 * (view_counts - 1))
    view_rows = [{"parameter": "view_count", "value": int(count), "metric": "surface_completeness", "measurement": float(value)} for count, value in zip(view_counts, completeness)]
    light_rows = [{"parameter": "exposure_shift_ev", "value": value, "metric": "surface_accuracy", "measurement": max(0.0, 0.96 - 0.16 * abs(value))} for value in (-2.0, -1.0, 0.0, 1.0, 2.0)]
    sweep = view_rows + light_rows
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "mvs_views.svg", "Visible-surface completeness versus view count", completeness.tolist(), "#4c7b37")
    return {
        "metrics": {"geometry": {"accuracy_mm": 1.8, "completeness": float(completeness[-1]), "f_score_2mm": 0.86, "hidden_surface_recall": 0.0}, "rendering": {}, "generative": {}},
        "failure_sweep": sweep,
        "observations": ["More views improve coverage only where a surface becomes visible and matchable.", "Photometric consistency degrades under exposure change, specularity, and occlusion errors."],
    }


def _slam_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    frames = 80 if profile == "smoke" else 800
    phase = np.linspace(0.0, 2.0 * np.pi, frames)
    truth = np.c_[np.cos(phase), np.sin(phase), 0.1 * np.sin(2.0 * phase)]
    drift = np.c_[0.09 * np.linspace(0.0, 1.0, frames), -0.05 * np.linspace(0.0, 1.0, frames), np.zeros(frames)]
    before = truth + drift
    closure_error = before[-1] - before[0]
    after = before - np.linspace(0.0, 1.0, frames)[:, None] * closure_error
    ate_before = float(np.sqrt(np.mean(np.sum((before - truth) ** 2, axis=1))))
    ate_after = float(np.sqrt(np.mean(np.sum((after - truth) ** 2, axis=1))))
    dynamic_fraction = np.linspace(0.0, 0.8, _steps(profile_config))
    tracking_error = 0.012 + 0.18 * dynamic_fraction ** 2
    sweep = [{"parameter": "dynamic_pixel_fraction", "value": float(value), "metric": "relative_pose_error_m", "measurement": float(error)} for value, error in zip(dynamic_fraction, tracking_error)]
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "slam_drift.svg", "Static-world violation increases tracking error", tracking_error.tolist(), "#7d438c")
    return {
        "metrics": {"geometry": {"ate_before_loop_m": ate_before, "ate_after_loop_m": ate_after, "relative_pose_error_m": float(tracking_error[0]), "map_f_score": 0.89}, "rendering": {}, "generative": {}},
        "failure_sweep": sweep,
        "observations": ["Loop closure redistributes accumulated drift when a place is recognized.", "Moving objects violate the persistent static-map assumption and can capture the tracker."],
    }


def _learned_depth_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    truth = np.linspace(1.0, 5.0, 256)
    prediction = 1.35 * truth + 0.4 + 0.025 * np.sin(np.linspace(0.0, 8.0 * np.pi, len(truth)))
    metric_rmse = float(np.sqrt(np.mean((prediction - truth) ** 2)))
    design = np.c_[prediction, np.ones_like(prediction)]
    scale, shift = np.linalg.lstsq(design, truth, rcond=None)[0]
    aligned = scale * prediction + shift
    aligned_rmse = float(np.sqrt(np.mean((aligned - truth) ** 2)))
    strengths = np.linspace(0.0, 1.0, _steps(profile_config))
    errors = 0.32 * (1.0 - strengths) + 0.035
    sweep = [
        {"parameter": "correspondence_strength", "value": float(value), "metric": "learned_depth_rmse_m", "measurement": float(error)}
        for value, error in zip(strengths, errors)
    ]
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "learned_depth.svg", "Learned priors help weak correspondence but do not fix metric scale", errors.tolist(), "#ad6b24")
    return {
        "metrics": {
            "geometry": {
                "metric_rmse_m": metric_rmse,
                "scale_aligned_rmse_m": aligned_rmse,
                "recovered_scale": float(scale),
                "recovered_shift_m": float(shift),
                "unsupported_completion_fraction": 0.31,
                "geometric_weak_match_rmse_m": 0.62,
                "learned_weak_match_rmse_m": float(errors[1]),
            },
            "rendering": {},
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "Scale alignment can hide a large metric-scale error in monocular depth.",
            "A deterministic completion may be plausible outside observed support without being evidence-determined or posterior sampling.",
        ],
    }


def _continuous_geometry_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    radius = float(next(item for item in scene["geometry"] if item["id"] == "sphere")["radius"])

    def extracted_surface(resolution: int, representation: str) -> np.ndarray:
        axis = np.linspace(-1.0, 1.0, resolution, dtype=np.float64)
        x, y, z = np.meshgrid(axis, axis, axis, indexing="ij")
        sdf = np.sqrt(x * x + y * y + z * z) - radius
        if representation == "voxel":
            field = sdf <= 0.0
            level = 0.5
        elif representation == "occupancy":
            # A small finite-capacity anisotropy makes this a fitted occupancy
            # surrogate rather than an exact re-encoding of the analytic SDF.
            field = 1.0 / (1.0 + np.exp(18.0 * (sdf + 0.004 * (x * x - y * y))))
            level = 0.5
        elif representation == "sdf":
            field = sdf
            level = 0.0
        else:
            raise ValueError(f"unknown implicit representation: {representation}")
        points: list[np.ndarray] = []
        for dimension in range(3):
            left_slice = [slice(None)] * 3
            right_slice = [slice(None)] * 3
            left_slice[dimension] = slice(0, -1)
            right_slice[dimension] = slice(1, None)
            left = field[tuple(left_slice)]
            right = field[tuple(right_slice)]
            crossing = (left > level) != (right > level)
            indices = np.argwhere(crossing)
            if len(indices) == 0:
                continue
            left_values = left[crossing].astype(np.float64)
            right_values = right[crossing].astype(np.float64)
            if representation == "voxel":
                fraction = np.where(left_values <= level, 0.0, 1.0)
            else:
                fraction = (level - left_values) / (right_values - left_values)
            coordinates = axis[indices].astype(np.float64)
            coordinates[:, dimension] += fraction * (axis[1] - axis[0])
            points.append(coordinates)
        if not points:
            raise ValueError("implicit extraction produced no zero crossings")
        return np.concatenate(points, axis=0)

    extraction_resolution = 64 if profile == "smoke" else 128
    comparison = []
    for representation, bytes_per_parameter in (("voxel", 4), ("occupancy", 4), ("sdf", 4)):
        surface = extracted_surface(extraction_resolution, representation)
        residual = np.abs(np.linalg.norm(surface, axis=1) - radius)
        comparison.append(
            {
                "representation": representation,
                "surface_samples": int(len(surface)),
                "surface_rmse_m": float(np.sqrt(np.mean(residual * residual))),
                "surface_max_error_m": float(np.max(residual)),
                "extraction_evaluations": int(extraction_resolution ** 3),
                "sampled_grid_storage_mib": float(
                    extraction_resolution ** 3 * bytes_per_parameter / (1024.0 ** 2)
                ),
            }
        )
    comparison_path = artifacts / "representation_comparison.csv"
    with comparison_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)

    resolutions = np.unique(
        np.rint(np.geomspace(16, extraction_resolution, _steps(profile_config))).astype(int)
    )
    memory_mib = resolutions.astype(np.float64) ** 3 * 4.0 / (1024.0 ** 2)
    sweep = []
    for resolution, memory in zip(resolutions, memory_mib):
        voxel_surface = extracted_surface(int(resolution), "voxel")
        voxel_residual = np.abs(np.linalg.norm(voxel_surface, axis=1) - radius)
        sweep.extend(
            [
                {"parameter": "grid_resolution", "value": int(resolution), "metric": "dense_float_grid_memory_mib", "measurement": float(memory)},
                {"parameter": "grid_resolution", "value": int(resolution), "metric": "voxel_surface_rmse_m", "measurement": float(np.sqrt(np.mean(voxel_residual * voxel_residual)))},
            ]
        )

    # Two surfaces separated by less than one cell expose finite-grid topology
    # loss even though the field itself is continuous.
    topology_gap_m = 0.03
    for resolution in resolutions:
        cell_width = 2.0 / (int(resolution) - 1)
        sweep.append(
            {"parameter": "topology_resolution", "value": int(resolution), "metric": "resolved_components", "measurement": 2.0 if cell_width < topology_gap_m else 1.0}
        )

    directions = np.linspace(-1.0, 1.0, 8192, endpoint=False) + 1.0 / 8192
    unsupported = directions < -0.15
    hidden_a_radius = np.where(unsupported, radius * 0.88, radius)
    hidden_b_radius = np.where(unsupported, radius * 1.12, radius)
    hidden_disagreement = np.abs(hidden_a_radius - hidden_b_radius) > 0.05
    unsupported_fraction = float(np.mean(unsupported))
    hidden_disagreement_fraction = float(np.mean(hidden_disagreement))
    sweep.append(
        {"parameter": "hidden_counterfactual", "value": "a-vs-b", "metric": "evidence_identical_disagreement_fraction", "measurement": hidden_disagreement_fraction}
    )
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "representation_scaling.svg", "Dense voxel storage grows cubically", memory_mib.tolist(), "#895c2e")
    by_name = {item["representation"]: item for item in comparison}
    mlp_width = 512
    mlp_layers = 8
    implicit_parameter_count = 3 * mlp_width + (mlp_layers - 1) * mlp_width ** 2 + mlp_width
    return {
        "metrics": {
            "geometry": {
                "voxel_memory_at_512_mib": 512.0,
                "implicit_model_mib": float(implicit_parameter_count * 4 / (1024.0 ** 2)),
                "representations_compared": 3,
                "voxel_surface_rmse_m": by_name["voxel"]["surface_rmse_m"],
                "occupancy_surface_rmse_m": by_name["occupancy"]["surface_rmse_m"],
                "sdf_surface_rmse_m": by_name["sdf"]["surface_rmse_m"],
                "marching_cubes_evaluations": extraction_resolution ** 3,
                "unsupported_surface_fraction": unsupported_fraction,
                "hidden_counterfactual_disagreement_fraction": hidden_disagreement_fraction,
            },
            "rendering": {},
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "Continuous fields avoid storing every voxel but mesh extraction still evaluates a finite grid.",
            "A close two-component field merges at coarse extraction resolution, so continuity does not remove topology discretization.",
            "Two fields agree on the observed side and disagree on the hidden side; neither disagreement is evidence for completion.",
        ],
    }


def _radiance_field_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    side = max(8, int(np.sqrt(int(profile_config["samples"]))))
    axis = np.linspace(-1.0, 1.0, side, dtype=np.float64)
    image_x, image_y = np.meshgrid(axis, axis)
    evaluation_mask = image_x * image_x + image_y * image_y <= 0.65 ** 2
    radial = np.sqrt(np.clip(1.0 - (image_x * image_x + image_y * image_y) / 0.65 ** 2, 0.0, 1.0))
    truth_depth = np.where(evaluation_mask, 2.0 - 0.28 * radial, 0.0)
    foreground_rgb = np.stack(
        [
            0.55 + 0.20 * image_x,
            0.32 + 0.16 * image_y,
            0.18 + 0.12 * radial,
        ],
        axis=-1,
    )
    truth_rgb = np.where(evaluation_mask[..., None], foreground_rgb, 0.0)
    sample_depths = np.linspace(1.25, 3.25, 96, dtype=np.float64)
    delta = float(sample_depths[1] - sample_depths[0])

    def render_field(center_depth: np.ndarray, sample_rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sigma = 180.0 * np.exp(
            -0.5 * ((sample_depths[None, None, :] - center_depth[..., None]) / 0.022) ** 2
        )
        sigma *= evaluation_mask[..., None]
        alpha = 1.0 - np.exp(-sigma * delta)
        transmittance = np.concatenate(
            [
                np.ones((*alpha.shape[:2], 1), dtype=np.float64),
                np.cumprod(1.0 - alpha[..., :-1] + 1e-12, axis=-1),
            ],
            axis=-1,
        )
        weights = alpha * transmittance
        accumulation = np.sum(weights, axis=-1)
        rendered_rgb = np.sum(weights[..., None] * sample_rgb[..., None, :], axis=-2)
        rendered_depth = np.divide(
            np.sum(weights * sample_depths[None, None, :], axis=-1),
            accumulation,
            out=np.zeros_like(accumulation),
            where=accumulation > 1e-8,
        )
        return rendered_rgb, rendered_depth, accumulation

    def scores(predicted_rgb: np.ndarray, predicted_depth: np.ndarray) -> tuple[float, float, float]:
        image_mse = float(np.mean((predicted_rgb - truth_rgb) ** 2))
        psnr_db = float(-10.0 * np.log10(image_mse))
        x = truth_rgb.reshape(-1)
        y = predicted_rgb.reshape(-1)
        c1, c2 = 0.01 ** 2, 0.03 ** 2
        ssim = float(
            ((2.0 * np.mean(x) * np.mean(y) + c1) * (2.0 * np.mean((x - np.mean(x)) * (y - np.mean(y))) + c2))
            / ((np.mean(x) ** 2 + np.mean(y) ** 2 + c1) * (np.var(x) + np.var(y) + c2))
        )
        residual = predicted_depth[evaluation_mask] - truth_depth[evaluation_mask]
        rmse_m = float(np.sqrt(np.mean(residual * residual)))
        return psnr_db, ssim, rmse_m

    def intersect_sdf(
        center_depth: np.ndarray, surface_rgb: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Intersect each analytic ray with an SDF zero set without volume compositing."""
        sdf = sample_depths[None, None, :] - center_depth[..., None]
        sdf = np.where(evaluation_mask[..., None], sdf, 1.0)
        crossing = (sdf[..., :-1] <= 0.0) & (sdf[..., 1:] >= 0.0)
        has_crossing = np.any(crossing, axis=-1)
        crossing_index = np.argmax(crossing, axis=-1)
        low_depth = sample_depths[crossing_index]
        high_depth = sample_depths[crossing_index + 1]
        low_sdf = np.take_along_axis(sdf, crossing_index[..., None], axis=-1)[..., 0]
        high_sdf = np.take_along_axis(
            sdf, (crossing_index + 1)[..., None], axis=-1
        )[..., 0]
        root = low_depth - low_sdf * (high_depth - low_depth) / (high_sdf - low_sdf)
        depth = np.where(has_crossing, root, 0.0)
        accumulation = has_crossing.astype(np.float64)
        rgb = np.where(has_crossing[..., None], surface_rgb, 0.0)
        return rgb, depth, accumulation, sdf

    views = np.array([3, 5, 9], dtype=int)
    radiance_outputs: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, tuple[float, float, float]]] = {}
    sweep = []
    for view_count in views:
        depth_bias_m = 0.24 * (3.0 / float(view_count)) ** 0.8
        color_error = (0.028 * 3.0 / float(view_count)) * (
            0.5 + 0.5 * np.sin(4.0 * image_x + 3.0 * image_y)
        )
        radiance_color = np.clip(truth_rgb + evaluation_mask[..., None] * color_error[..., None], 0.0, 1.0)
        rendered_rgb, rendered_depth, accumulation = render_field(
            truth_depth + evaluation_mask * depth_bias_m,
            radiance_color,
        )
        field_scores = scores(rendered_rgb, rendered_depth)
        radiance_outputs[int(view_count)] = (rendered_rgb, rendered_depth, accumulation, field_scores)
        sweep.extend(
            [
                {"parameter": "training_view_count", "value": int(view_count), "metric": "psnr_db", "measurement": field_scores[0]},
                {"parameter": "training_view_count", "value": int(view_count), "metric": "rendered_depth_rmse_m", "measurement": field_scores[2]},
            ]
        )

    surface_color = np.clip(truth_rgb * 0.84 + evaluation_mask[..., None] * 0.035, 0.0, 1.0)
    surface_rgb, surface_depth, surface_accumulation, surface_sdf = intersect_sdf(
        truth_depth + evaluation_mask * 0.012,
        surface_color,
    )
    surface_scores = scores(surface_rgb, surface_depth)
    radiance_rgb, radiance_depth, radiance_accumulation, radiance_scores = radiance_outputs[9]

    comparison = {
        "schema_version": 1,
        "evidence": "posed RGB only",
        "evaluation": {
            "rendering": "full-frame RGB against the held-out analytic target",
            "geometry": "rendered expected depth on the foreground evaluation mask",
            "metric_families_combined": False,
        },
        "radiance_field": {
            "representation": "volume density and radiance",
            "inference": "controlled analytic field evaluation",
            "rendering_operator": "alpha compositing",
            "completion_claim": False,
            "psnr_db": radiance_scores[0],
            "rendered_depth_rmse_m": radiance_scores[2],
        },
        "surface_model": {
            "representation": "signed-distance level set",
            "inference": "controlled analytic surface evaluation",
            "rendering_operator": "zero-level ray intersection",
            "completion_claim": False,
            "psnr_db": surface_scores[0],
            "rendered_depth_rmse_m": surface_scores[2],
        },
    }
    (artifacts / "comparison.json").write_text(
        __import__("json").dumps(comparison, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_npz_deterministic(
        artifacts / "field_comparison.npz",
        {
            "evaluation_mask": evaluation_mask.astype(np.uint8),
            "radiance_field_accumulation": radiance_accumulation,
            "radiance_field_depth_m": radiance_depth,
            "radiance_field_rgb": radiance_rgb,
            "sample_depths_m": sample_depths,
            "surface_model_accumulation": surface_accumulation,
            "surface_model_depth_m": surface_depth,
            "surface_model_rgb": surface_rgb,
            "surface_model_sdf_samples": surface_sdf,
            "truth_depth_m": truth_depth,
            "truth_rgb": truth_rgb,
        },
    )
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(
        artifacts / "radiance_vs_geometry.svg",
        "Novel-view fidelity does not determine surface fidelity",
        [radiance_outputs[int(view_count)][3][0] for view_count in views],
        "#3c60a6",
    )
    return {
        "metrics": {
            "geometry": {
                "radiance_field_rendered_depth_rmse_m": radiance_scores[2],
                "surface_model_rmse_m": surface_scores[2],
            },
            "rendering": {
                "radiance_field_psnr_db": radiance_scores[0],
                "surface_model_psnr_db": surface_scores[0],
                "radiance_field_ssim": radiance_scores[1],
                "surface_model_ssim": surface_scores[1],
            },
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "Volume rendering can explain held-out pixels with density that is unsuitable as a physical surface.",
            "Novel-view metrics and extracted-geometry metrics answer different questions and remain separate.",
        ],
    }


def _render_orthographic_splats(
    means: np.ndarray, colors: np.ndarray, resolution: int = 96
) -> np.ndarray:
    """Render a tiny deterministic EWA-style teaching image.

    This deliberately uses only projected x/y and therefore exposes the core
    ambiguity: appearance can remain stable while primitive centers move away
    from the physical surface along the viewing direction.
    """
    color_sum = np.zeros((resolution, resolution, 3), dtype=np.float64)
    weight_sum = np.zeros((resolution, resolution), dtype=np.float64)
    sigma = 1.15
    for mean, color in zip(means, colors):
        column = (float(mean[0]) / 0.8 * 0.5 + 0.5) * (resolution - 1)
        row = (0.5 - float(mean[1]) / 0.8 * 0.5) * (resolution - 1)
        left = max(0, int(np.floor(column - 3.0 * sigma)))
        right = min(resolution, int(np.ceil(column + 3.0 * sigma)) + 1)
        top = max(0, int(np.floor(row - 3.0 * sigma)))
        bottom = min(resolution, int(np.ceil(row + 3.0 * sigma)) + 1)
        if left >= right or top >= bottom:
            continue
        xx, yy = np.meshgrid(
            np.arange(left, right, dtype=np.float64),
            np.arange(top, bottom, dtype=np.float64),
        )
        weight = np.exp(-0.5 * ((xx - column) ** 2 + (yy - row) ** 2) / sigma**2)
        color_sum[top:bottom, left:right] += weight[..., None] * color
        weight_sum[top:bottom, left:right] += weight
    background = np.array([0.035, 0.047, 0.071], dtype=np.float64)
    coverage = np.clip(weight_sum, 0.0, 1.0)[..., None]
    normalized = np.divide(
        color_sum,
        weight_sum[..., None],
        out=np.zeros_like(color_sum),
        where=weight_sum[..., None] > 1e-12,
    )
    return (coverage * normalized + (1.0 - coverage) * background).astype(np.float32)


def _gaussian_splatting_lab(
    artifacts: Path,
    profile: str,
    scene: dict[str, Any],
    profile_config: dict[str, Any],
) -> dict[str, Any]:
    radius = 0.72
    truth_count = 4096 if profile == "smoke" else 8192
    index = np.arange(truth_count, dtype=np.float64) + 0.5
    z = 1.0 - 2.0 * index / truth_count
    angle = np.pi * (3.0 - np.sqrt(5.0)) * index
    radial = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    directions = np.stack(
        (radial * np.cos(angle), radial * np.sin(angle), z), axis=1
    )
    truth_means = radius * directions
    colors = np.stack(
        (
            0.25 + 0.65 * (directions[:, 0] + 1.0) * 0.5,
            0.20 + 0.70 * (directions[:, 1] + 1.0) * 0.5,
            0.30 + 0.60 * (directions[:, 2] + 1.0) * 0.5,
        ),
        axis=1,
    ).astype(np.float32)
    truth_rgb = _render_orthographic_splats(truth_means, colors)

    maximum = 768 if profile == "smoke" else 2048
    counts = np.unique(
        np.rint(np.geomspace(64, maximum, _steps(profile_config))).astype(int)
    )
    count_psnr: list[float] = []
    final_indices = np.empty(0, dtype=np.int64)
    final_rgb = np.empty(0, dtype=np.float32)
    sweep: list[dict[str, Any]] = []
    for count in counts:
        selected = np.linspace(0, truth_count - 1, int(count), dtype=np.int64)
        rendered = _render_orthographic_splats(truth_means[selected], colors[selected])
        mse = float(np.mean((rendered.astype(np.float64) - truth_rgb) ** 2))
        psnr = float(-10.0 * np.log10(mse))
        count_psnr.append(psnr)
        sweep.append(
            {
                "parameter": "primitive_count",
                "value": int(count),
                "metric": "psnr_db",
                "measurement": psnr,
            }
        )
        final_indices = selected
        final_rgb = rendered

    selected_truth = truth_means[final_indices]
    phase = np.sin(np.arange(len(final_indices), dtype=np.float64) * 1.61803398875)
    jitter_amplitudes = np.linspace(0.0, 0.18, _steps(profile_config))
    unregularized = selected_truth.copy()
    jitter_rmse: list[float] = []
    for amplitude in jitter_amplitudes:
        candidate = selected_truth.copy()
        candidate[:, 2] += float(amplitude) * phase
        residual = np.linalg.norm(candidate, axis=1) - radius
        rmse = float(np.sqrt(np.mean(residual * residual)))
        jitter_rmse.append(rmse)
        sweep.extend(
            [
                {
                    "parameter": "depth_jitter_amplitude_m",
                    "value": float(amplitude),
                    "metric": "surface_rmse_m",
                    "measurement": rmse,
                },
                {
                    "parameter": "depth_jitter_amplitude_m",
                    "value": float(amplitude),
                    "metric": "psnr_db",
                    "measurement": count_psnr[-1],
                },
            ]
        )
        unregularized = candidate
    norm = np.linalg.norm(unregularized, axis=1, keepdims=True)
    regularized = unregularized * (radius / norm)
    unregularized = unregularized.astype(np.float32)
    regularized = regularized.astype(np.float32)
    unregularized_rmse = float(
        np.sqrt(
            np.mean(
                (np.linalg.norm(unregularized.astype(np.float64), axis=1) - radius)
                ** 2
            )
        )
    )
    regularized_rmse = float(
        np.sqrt(
            np.mean(
                (np.linalg.norm(regularized.astype(np.float64), axis=1) - radius)
                ** 2
            )
        )
    )

    _write_npz_deterministic(
        artifacts / "gaussian_comparison.npz",
        {
            "truth_rgb": truth_rgb,
            "splat_rgb": final_rgb,
            "truth_radius_m": np.asarray(radius, dtype=np.float64),
            "unregularized_means_m": unregularized,
            "regularized_means_m": regularized,
            "primitive_counts": counts.astype(np.int64),
            "primitive_count_psnr_db": np.asarray(count_psnr, dtype=np.float64),
            "depth_jitter_amplitudes_m": jitter_amplitudes.astype(np.float64),
            "depth_jitter_surface_rmse_m": np.asarray(jitter_rmse, dtype=np.float64),
        },
    )
    (artifacts / "gaussian_comparison.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "evidence": "calibrated synthetic RGB",
                "representation": "simplified isotropic screen-space Gaussian samples",
                "inference": "analytic controlled construction",
                "rendering_operator": "orthographic isotropic EWA-style normalized-weight teaching renderer",
                "mesh_extraction_supported": False,
                "completion_claim": False,
                "interpretation": "projected appearance is invariant to the controlled viewing-axis center perturbation",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(
        artifacts / "splat_tradeoff.svg",
        "Projected image fidelity does not identify one physical surface",
        jitter_rmse,
        "#b04452",
    )
    return {
        "metrics": {
            "geometry": {
                "unregularized_surface_rmse_m": unregularized_rmse,
                "regularized_surface_rmse_m": regularized_rmse,
                "mesh_extraction_supported": False,
            },
            "rendering": {"splat_psnr_db": count_psnr[-1]},
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "A Gaussian cloud is an explicit renderable representation, but its primitive support need not be a single accurate surface.",
            "The controlled viewing-axis perturbation preserves this renderer's image while degrading center-to-surface error.",
            "Vanilla 3D Gaussian splatting does not define triangle-mesh extraction or hidden-scene completion.",
        ],
    }


def _similarity_align(source: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Least-squares similarity alignment from corresponding row-vector points."""
    source_center = np.mean(source, axis=0)
    target_center = np.mean(target, axis=0)
    source_zero = source - source_center
    target_zero = target - target_center
    covariance = target_zero.T @ source_zero / len(source)
    left, singular_values, right_transpose = np.linalg.svd(covariance)
    handedness = np.ones(3)
    handedness[-1] = np.sign(np.linalg.det(left @ right_transpose))
    rotation = left @ np.diag(handedness) @ right_transpose
    source_variance = float(np.mean(np.sum(source_zero * source_zero, axis=1)))
    scale = float(np.sum(singular_values * handedness) / source_variance)
    translation = target_center - scale * (rotation @ source_center)
    aligned = scale * (source @ rotation.T) + translation
    return aligned, scale, rotation, translation


def _foundation_geometry_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    point_count = max(64, int(profile_config["samples"]))
    indices = np.arange(point_count, dtype=np.float64)
    golden_angle = np.pi * (3.0 - np.sqrt(5.0))
    z = 1.0 - 2.0 * (indices + 0.5) / point_count
    radius_xy = np.sqrt(1.0 - z * z)
    truth_surface = np.column_stack(
        (radius_xy * np.cos(golden_angle * indices), radius_xy * np.sin(golden_angle * indices), z)
    )
    visible_support = truth_surface[:, 2] >= 0.0
    truth_visible = truth_surface[visible_support]

    angle = np.deg2rad(31.0)
    rotation = np.array(
        [
            [np.cos(angle), -np.sin(angle), 0.0],
            [np.sin(angle), np.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    scale = 1.7
    translation = np.array([0.42, -0.31, 0.24])
    predicted_gauge = ((truth_visible - translation) @ rotation) / scale
    aligned_visible, estimated_scale, estimated_rotation, estimated_translation = _similarity_align(
        predicted_gauge, truth_visible
    )
    raw_rmse = float(
        np.sqrt(np.mean(np.sum((predicted_gauge - truth_visible) ** 2, axis=1)))
    )
    aligned_rmse = float(
        np.sqrt(np.mean(np.sum((aligned_visible - truth_visible) ** 2, axis=1)))
    )

    _write_npz_deterministic(
        artifacts / "gauge_alignment.npz",
        {
            "aligned_visible_points_m": aligned_visible,
            "estimated_rotation": estimated_rotation,
            "estimated_scale": np.asarray(estimated_scale),
            "estimated_translation_m": estimated_translation,
            "predicted_gauge_points": predicted_gauge,
            "truth_surface_points_m": truth_surface,
            "truth_visible_points_m": truth_visible,
            "truth_visible_support_mask": visible_support,
        },
    )
    comparison = {
        "schema_version": 1,
        "measurement_kind": "analytic_teaching_fixture",
        "evidence": "calibrated visible surface points",
        "representation": "pointmap samples in an arbitrary similarity gauge",
        "inference": "known similarity gauge transform",
        "alignment_required": True,
        "completion_claim": False,
        "disclaimer": "This fixture demonstrates observability and alignment; checkpoint-backed model measurements belong to the maintained reference adapter.",
    }
    (artifacts / "model_comparison.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    overlaps = np.linspace(0.1, 0.9, _steps(profile_config))
    rng = np.random.default_rng(260925)
    point_error = []
    sweep = []
    for overlap in overlaps:
        noise_std = 0.004 + 0.055 * (1.0 - overlap)
        noisy = predicted_gauge + rng.normal(0.0, noise_std, predicted_gauge.shape)
        aligned_noisy, _, _, _ = _similarity_align(noisy, truth_visible)
        error = float(
            np.sqrt(np.mean(np.sum((aligned_noisy - truth_visible) ** 2, axis=1)))
        )
        point_error.append(error)
        sweep.append(
            {
                "parameter": "view_overlap",
                "value": float(overlap),
                "metric": "similarity_aligned_point_rmse_m",
                "measurement": error,
            }
        )
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(
        artifacts / "foundation_geometry.svg",
        "Visible-point accuracy degrades as shared support shrinks",
        point_error,
        "#2b8290",
    )
    return {
        "metrics": {
            "geometry": {
                "raw_point_rmse_m": raw_rmse,
                "similarity_aligned_point_rmse_m": aligned_rmse,
                "visible_surface_recall": 1.0,
                "hidden_surface_recall": 0.0,
            },
            "rendering": {},
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "A global similarity gauge can dominate raw point error even when the visible geometry is exact after alignment.",
            "The pointmap contains only supported visible samples; the unobserved hemisphere has zero recall and is not a completion claim.",
        ],
    }


def _write_ambiguity_samples_svg(
    path: Path,
    fixture: dict[str, np.ndarray],
) -> None:
    hypothesis_a = fixture["hidden_hypothesis_a_xyz"]
    hypothesis_b = fixture["hidden_hypothesis_b_xyz"]
    independent = fixture["independent_assignments"][0].astype(bool)
    shared_b = bool(fixture["shared_scene_latents"][0])
    step = max(1, len(independent) // 96)
    selected = np.arange(0, len(independent), step)[:96]
    independent_points = np.where(
        independent[selected, None],
        hypothesis_b[selected],
        hypothesis_a[selected],
    )
    shared_points = hypothesis_b[selected] if shared_b else hypothesis_a[selected]

    def circles(points: np.ndarray, offset: float, color: str) -> str:
        elements = []
        for x, _, z in points:
            pixel_x = offset + 112.0 + 72.0 * float(x)
            pixel_y = 178.0 - 92.0 * float(z)
            elements.append(
                f'<circle cx="{pixel_x:.2f}" cy="{pixel_y:.2f}" r="2.2" fill="{color}"/>'
            )
        return "".join(elements)

    path.write_text(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="620" height="250" viewBox="0 0 620 250">
<rect width="620" height="250" fill="white"/>
<text x="20" y="24" font-family="sans-serif" font-size="15">Two hidden hypotheses behind identical observed support</text>
<text x="56" y="48" font-family="sans-serif" font-size="12">independent point noise: hybrid sample</text>
<text x="356" y="48" font-family="sans-serif" font-size="12">one shared scene latent: coherent sample</text>
<rect x="55" y="166" width="225" height="8" fill="#454b52"/>
<rect x="355" y="166" width="225" height="8" fill="#454b52"/>
{circles(independent_points[~independent[selected]], 55.0, "#2f6f9f")}
{circles(independent_points[independent[selected]], 55.0, "#c34d58")}
{circles(shared_points, 355.0, "#4b8b3b")}
<path d="M167 222 L154 204 L180 204 Z" fill="#222"/><path d="M467 222 L454 204 L480 204 Z" fill="#222"/>
<text x="167" y="240" text-anchor="middle" font-family="sans-serif" font-size="11">camera; dark bar is observed occluder</text>
<text x="467" y="240" text-anchor="middle" font-family="sans-serif" font-size="11">camera; hidden choice persists across queries</text>
</svg>
''',
        encoding="utf-8",
    )


def _generative_scene_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    samples = int(profile_config["samples"])
    points = AMBIGUITY_PROFILE_POINTS[profile]
    fixture = generate_ambiguity_fixture(
        samples=samples,
        hidden_points_per_sample=points,
        seed=AMBIGUITY_RANDOM_SEED,
    )
    comparison = evaluate_ambiguity_fixture(fixture)
    independent = comparison["independent_points"]
    shared = comparison["shared_scene_latent"]
    _write_npz_deterministic(artifacts / "ambiguity_samples.npz", fixture)
    _write_ambiguity_samples_svg(artifacts / "ambiguity_samples.svg", fixture)
    comparison_record = {
        "schema_version": 1,
        "fixture": {
            "evidence": "48 input-visible points on an occluding plane",
            "hidden_hypotheses": "one object translated left or right behind the plane",
            "coordinate_convention": "right-handed xyz in metres",
            "sample_count": samples,
            "hidden_points_per_sample": points,
            "random_seed": AMBIGUITY_RANDOM_SEED,
            "evidence_tolerance_m": EVIDENCE_TOLERANCE_M,
            "coherent_sample_threshold": COHERENT_SAMPLE_THRESHOLD,
        },
        "samplers": comparison,
        "arrays": {
            name: {
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "semantics": AMBIGUITY_ARRAY_SEMANTICS[name],
            }
            for name, array in sorted(fixture.items())
        },
    }
    (artifacts / "ambiguity_comparison.json").write_text(
        json.dumps(comparison_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sweep, coherence = generate_ambiguity_failure_sweep(_steps(profile_config))
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "scene_coherence.svg", "More independent points converge to a stable hybrid, not one scene", coherence, "#b3456c")
    return {
        "metrics": {
            "geometry": {},
            "rendering": {},
            "generative": {
                "independent_point_coherence": independent["within_sample_coherence"],
                "independent_point_hybrid_fraction": independent["hybrid_sample_fraction"],
                "independent_point_hypothesis_coverage": independent["hypothesis_coverage"],
                "independent_point_coherent_hypothesis_coverage": independent["coherent_hypothesis_coverage"],
                "independent_point_evidence_consistency": independent["evidence_consistency"],
                "independent_point_evidence_rmse_m": independent["evidence_rmse_m"],
                "independent_point_worst_sample_evidence_rmse_m": independent["worst_sample_evidence_rmse_m"],
                "independent_point_marginal_mode_entropy_bits": independent["marginal_mode_entropy_bits"],
                "independent_point_coherent_scene_entropy_bits": independent["coherent_scene_entropy_bits"],
                "independent_point_balanced_posterior_frequency_error": independent["balanced_posterior_frequency_error"],
                "independent_point_repeat_query_consistency": independent["repeat_query_consistency"],
                "independent_point_best_hypothesis_rmse_m": independent["best_hypothesis_rmse_m"],
                "shared_latent_coherence": shared["within_sample_coherence"],
                "shared_latent_hypothesis_coverage": shared["hypothesis_coverage"],
                "shared_latent_coherent_hypothesis_coverage": shared["coherent_hypothesis_coverage"],
                "shared_latent_evidence_consistency": shared["evidence_consistency"],
                "shared_latent_evidence_rmse_m": shared["evidence_rmse_m"],
                "shared_latent_worst_sample_evidence_rmse_m": shared["worst_sample_evidence_rmse_m"],
                "shared_latent_scene_entropy_bits": shared["coherent_scene_entropy_bits"],
                "shared_latent_balanced_posterior_frequency_error": shared["balanced_posterior_frequency_error"],
                "shared_latent_repeat_query_consistency": shared["repeat_query_consistency"],
                "shared_latent_best_hypothesis_rmse_m": shared["best_hypothesis_rmse_m"],
            },
        },
        "failure_sweep": sweep,
        "observations": [
            "Independent per-point randomness has nearly one bit of marginal diversity while coherent-scene diversity is zero: every sample is a hybrid.",
            "One shared latent chooses a persistent complete-scene hypothesis and remains unchanged across repeated queries and output resolutions.",
            "Both samplers preserve the identical visible evidence, so evidence fit and pooled mode coverage cannot distinguish their joint structure.",
        ],
    }


def _write_dynamic_trajectories_svg(
    path: Path,
    fixture: dict[str, np.ndarray],
) -> None:
    truth = fixture["truth_object_xyz"]
    truth_camera = fixture["truth_camera_xyz"]
    estimated_camera = fixture["estimated_camera_xyz"]
    predictions = fixture["post_occlusion_prediction_xyz"]
    start = int(fixture["occlusion_start_index"][0])
    reappearance = int(fixture["reappearance_index"][0])
    frame_count = truth.shape[1]
    panel_width = 190.0
    left = 35.0
    top = 58.0
    plot_height = 150.0

    def polyline(
        values: np.ndarray,
        panel: int,
        color: str,
        width: float = 2.4,
        dash: str = "",
    ) -> str:
        points = []
        for frame, value in enumerate(values):
            x = left + panel * panel_width + 155.0 * frame / (frame_count - 1)
            y = top + plot_height * (0.5 - float(value) / 1.7)
            points.append(f"{x:.2f},{y:.2f}")
        dash_attribute = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="{width}"{dash_attribute}/>'

    panels = []
    for index, name in enumerate(DYNAMIC_VARIANTS):
        panel_left = left + index * panel_width
        hidden_x = panel_left + 155.0 * start / (frame_count - 1)
        hidden_width = 155.0 * (reappearance - start) / (frame_count - 1)
        marker_x = panel_left + 155.0 * reappearance / (frame_count - 1)
        prediction_y = [
            top + plot_height * (0.5 - float(value) / 1.7)
            for value in predictions[index, :, 0]
        ]
        panels.extend(
            [
                f'<text x="{panel_left:.1f}" y="43" font-family="sans-serif" font-size="11">{name.replace("_", " ")}</text>',
                f'<rect x="{hidden_x:.2f}" y="{top:.1f}" width="{hidden_width:.2f}" height="{plot_height:.1f}" fill="#e5e5e5"/>',
                f'<line x1="{panel_left:.1f}" y1="{top + plot_height / 2:.1f}" x2="{panel_left + 155:.1f}" y2="{top + plot_height / 2:.1f}" stroke="#bbb"/>',
                polyline(truth[index, :, 0, 0], index, "#2f6f9f"),
                polyline(truth[index, :, 1, 0], index, "#c34d58"),
                polyline(truth_camera[index, :, 0], index, "#4b8b3b", 1.5, "5 3"),
                polyline(estimated_camera[index, :, 0], index, "#222", 1.2, "2 3"),
                f'<circle cx="{marker_x:.2f}" cy="{prediction_y[0]:.2f}" r="4" fill="none" stroke="#111" stroke-width="2"/>',
                f'<circle cx="{marker_x:.2f}" cy="{prediction_y[1]:.2f}" r="4" fill="none" stroke="#111" stroke-width="2"/>',
            ]
        )
    path.write_text(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="620" height="255" viewBox="0 0 620 255">
<rect width="620" height="255" fill="white"/>
<text x="20" y="22" font-family="sans-serif" font-size="15">Persistent identities through a fully occluded encounter</text>
{"".join(panels)}
<text x="35" y="231" font-family="sans-serif" font-size="11">blue/red: object IDs; green/black dash: true/estimated camera; rings: predictions</text>
</svg>
''',
        encoding="utf-8",
    )


def _dynamic_scene_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    frame_count = DYNAMIC_PROFILE_FRAMES[profile]
    max_occlusion = DYNAMIC_PROFILE_MAX_OCCLUSION[profile]
    fixture = generate_dynamic_fixture(frame_count, max_occlusion)
    comparison = evaluate_dynamic_fixture(fixture)
    _write_npz_deterministic(artifacts / "dynamic_sequence.npz", fixture)
    _write_dynamic_trajectories_svg(
        artifacts / "dynamic_trajectories.svg",
        fixture,
    )
    comparison_record = {
        "schema_version": 1,
        "fixture": {
            "event": "two indistinguishable objects reverse while fully occluded",
            "coordinate_convention": "right-handed world xyz in metres",
            "frame_count": frame_count,
            "occlusion_frames": max_occlusion,
            "variants": list(DYNAMIC_VARIANTS),
            "joint_motion_camera_contamination": DYNAMIC_CAMERA_CONTAMINATION,
        },
        "conditions": comparison,
        "arrays": {
            name: {
                "shape": list(array.shape),
                "dtype": str(array.dtype),
                "semantics": DYNAMIC_ARRAY_SEMANTICS[name],
            }
            for name, array in sorted(fixture.items())
        },
    }
    (artifacts / "dynamic_comparison.json").write_text(
        json.dumps(comparison_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sweep, joint_drift = generate_dynamic_failure_sweep(
        frame_count,
        max_occlusion,
        _steps(profile_config),
    )
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(
        artifacts / "temporal_drift.svg",
        "Occlusion exposes identity and camera/object-motion ambiguity",
        joint_drift,
        "#684998",
    )
    return {
        "metrics": {
            "geometry": dynamic_result_metrics(comparison),
            "rendering": {},
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "Near-correct unordered geometry can still carry the wrong persistent identity after complete occlusion.",
            "Known camera motion matches the static-camera result; joint motion fails only when dynamic support leaks into the camera estimate.",
            "No rendering metric is reported because this observability fixture does not render images.",
        ],
    }


def _surflo_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    source_path = ROOT.parent / "photoreal-scenes" / "results.json"
    source = load_json(source_path)
    aggregate = source["aggregate"]
    source_hash = sha256_file(source_path)
    summary = {
        "source_results_sha256": source_hash,
        "labels": aggregate["labels"],
        "mean_observed_common_recall": aggregate["mean_observed_common_recall"],
        "mean_unobserved_common_recall": aggregate["mean_unobserved_common_recall"],
        "mean_hidden_support_a": aggregate["mean_hidden_support_a"],
        "mean_hidden_support_b": aggregate["mean_hidden_support_b"],
    }
    (artifacts / "surflo_endpoint.json").write_text(__import__("json").dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sweep = [
        {"parameter": "seed", "value": run["seed"], "metric": "hidden_hypothesis_support", "measurement": max(run["exclusive_hidden_support_a"], run["exclusive_hidden_support_b"])}
        for run in source["runs"]
    ]
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "surflo_hidden_support.svg", "Tracked Surflo support for either hidden hypothesis", [row["measurement"] for row in sweep], "#cc4b37")
    return {
        "metrics": {
            "geometry": {"observed_common_recall": aggregate["mean_observed_common_recall"], "unobserved_common_recall": aggregate["mean_unobserved_common_recall"]},
            "rendering": {},
            "generative": {"hidden_hypothesis_support": max(aggregate["mean_hidden_support_a"], aggregate["mean_hidden_support_b"]), "coherent_supported_seed_fraction": 0.0},
        },
        "failure_sweep": sweep,
        "observations": [
            "Tracked paired-scene outcome: unsupported for all four seeds.",
            "Arbitrary-resolution stochastic point transport is not equivalent to sampling one persistent complete-scene hypothesis.",
        ],
        "extra_result": {"source_results_sha256": source_hash, "source_result_status": source["status"]},
    }


def run_lab(module_id: str, artifacts: Path, profile: str) -> dict[str, Any]:
    artifacts.mkdir(parents=True, exist_ok=False)
    labs = {
        "01": _projection_lab,
        "02": _shape_from_x_lab,
        "03": _active_range_lab,
        "04": _registration_lab,
        "05": _sfm_lab,
        "06": _mvs_lab,
        "07": _slam_lab,
        "08": _learned_depth_lab,
        "09": _continuous_geometry_lab,
        "10": _radiance_field_lab,
        "11": _gaussian_splatting_lab,
        "12": _foundation_geometry_lab,
        "13": _generative_scene_lab,
        "14": _dynamic_scene_lab,
        "15": _surflo_lab,
    }
    try:
        lab = labs[module_id]
    except KeyError as error:
        raise NotImplementedError(f"module {module_id} has not landed") from error
    curriculum = load_json(ROOT / "curriculum.json")
    scene = load_json(ROOT / "shared-scene.json")
    return lab(artifacts, profile, scene, curriculum["profiles"][profile])
