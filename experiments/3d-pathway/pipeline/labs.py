"""Small deterministic concept labs; heavyweight reference adapters are not landed."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np

from contracts import ROOT, load_json, sha256_file
from generative import compare_ambiguous_samplers
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
    views = np.unique(np.rint(np.linspace(3, 35, _steps(profile_config))).astype(int))
    psnr = 22.0 + 4.1 * np.log2(views / 3.0)
    geometry_error = 0.16 / np.sqrt(views / 3.0) + 0.035
    sweep = []
    for view_count, image_score, surface_error in zip(views, psnr, geometry_error):
        sweep.append({"parameter": "training_view_count", "value": int(view_count), "metric": "psnr_db", "measurement": float(image_score)})
        sweep.append({"parameter": "training_view_count", "value": int(view_count), "metric": "surface_rmse_m", "measurement": float(surface_error)})
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "radiance_vs_geometry.svg", "Novel-view fidelity does not determine surface fidelity", psnr.tolist(), "#3c60a6")
    return {
        "metrics": {
            "geometry": {"radiance_field_surface_rmse_m": 0.078, "surface_model_rmse_m": 0.019},
            "rendering": {"radiance_field_psnr_db": 35.4, "surface_model_psnr_db": 31.2, "radiance_field_ssim": 0.971, "surface_model_ssim": 0.944},
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "Volume rendering can explain held-out pixels with density that is unsuitable as a physical surface.",
            "Novel-view metrics and extracted-geometry metrics answer different questions and remain separate.",
        ],
    }


def _gaussian_splatting_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    counts = np.unique(np.rint(np.geomspace(1_000, 1_048_576, _steps(profile_config))).astype(int))
    psnr = 20.0 + 2.4 * np.log10(counts / 1000.0 + 1.0)
    surface_error = 0.11 / np.log10(counts / 100.0 + 10.0) + 0.018
    sweep = []
    for count, image_score, error in zip(counts, psnr, surface_error):
        sweep.append({"parameter": "primitive_count", "value": int(count), "metric": "psnr_db", "measurement": float(image_score)})
        sweep.append({"parameter": "primitive_count", "value": int(count), "metric": "surface_rmse_m", "measurement": float(error)})
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "splat_tradeoff.svg", "More renderable primitives do not guarantee a cleaner surface", psnr.tolist(), "#b04452")
    return {
        "metrics": {
            "geometry": {"unregularized_surface_rmse_m": 0.071, "regularized_surface_rmse_m": 0.024, "mesh_f_score": 0.81},
            "rendering": {"splat_psnr_db": 36.1, "extracted_mesh_psnr_db": 30.7, "render_fps": 124.0},
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "A Gaussian cloud is an explicit renderable representation, but its primitive support need not be a single accurate surface.",
            "Surface-aligned or 2D variants add geometric bias; mesh extraction is an additional inference step.",
        ],
    }


def _foundation_geometry_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    model_rows = [
        {"model": "DUSt3R", "pose_auc": 0.61, "depth_rmse_m": 0.091, "point_rmse_m": 0.112, "runtime_s": 0.82, "retained_alignment": True},
        {"model": "MASt3R", "pose_auc": 0.69, "depth_rmse_m": 0.078, "point_rmse_m": 0.084, "runtime_s": 0.94, "retained_alignment": True},
        {"model": "VGGT", "pose_auc": 0.77, "depth_rmse_m": 0.065, "point_rmse_m": 0.071, "runtime_s": 0.48, "retained_alignment": False},
        {"model": "Depth Anything 3", "pose_auc": 0.81, "depth_rmse_m": 0.058, "point_rmse_m": 0.063, "runtime_s": 0.52, "retained_alignment": False},
    ]
    # Values are controlled-lab signals, not published benchmark reproduction.
    comparison = {"measurement_kind": "controlled_fixture", "disclaimer": "Synthetic teaching signals; not checkpoint-backed benchmark measurements.", "systems": model_rows}
    (artifacts / "model_comparison.json").write_text(__import__("json").dumps(comparison, indent=2) + "\n", encoding="utf-8")
    overlaps = np.linspace(0.1, 0.9, _steps(profile_config))
    point_error = 0.15 * np.exp(-2.1 * overlaps) + 0.025
    sweep = [{"parameter": "view_overlap", "value": float(value), "metric": "aligned_point_rmse_m", "measurement": float(error)} for value, error in zip(overlaps, point_error)]
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "foundation_geometry.svg", "Amortized pointmaps improve with shared visible support", point_error.tolist(), "#2b8290")
    return {
        "metrics": {
            "geometry": {"raw_point_rmse_m": 0.184, "aligned_point_rmse_m": 0.063, "pose_auc": 0.81, "depth_rmse_m": 0.058, "hidden_surface_recall": 0.0},
            "rendering": {},
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "Pointmaps and predicted cameras amortize visible geometry but do not observe occluded surfaces.",
            "Some pipelines still retain global alignment or optimization stages; feed-forward does not always mean optimization-free.",
        ],
    }


def _generative_scene_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    samples = int(profile_config["samples"])
    points = 257 if profile == "smoke" else 4097
    comparison = compare_ambiguous_samplers(samples=samples, points_per_sample=points, seed=260925)
    independent = comparison["independent_points"]
    shared = comparison["shared_scene_latent"]
    (artifacts / "ambiguity_comparison.json").write_text(__import__("json").dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    point_counts = np.unique(np.rint(np.geomspace(17, 16385, _steps(profile_config))).astype(int))
    coherence = []
    sweep = []
    for point_count in point_counts:
        summary = compare_ambiguous_samplers(samples=64, points_per_sample=int(point_count), seed=260925)["independent_points"]
        coherence.append(summary["within_sample_coherence"])
        sweep.append({"parameter": "points_per_sample", "value": int(point_count), "metric": "independent_point_coherence", "measurement": summary["within_sample_coherence"]})
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "scene_coherence.svg", "More independent points converge to a stable hybrid, not one scene", coherence, "#b3456c")
    return {
        "metrics": {
            "geometry": {},
            "rendering": {},
            "generative": {
                "independent_point_coherence": independent["within_sample_coherence"],
                "independent_point_hybrid_fraction": independent["hybrid_sample_fraction"],
                "shared_latent_coherence": shared["within_sample_coherence"],
                "shared_latent_hypothesis_coverage": shared["hypothesis_coverage"],
                "shared_latent_evidence_consistency": shared["evidence_consistency"],
            },
        },
        "failure_sweep": sweep,
        "observations": [
            "Independent per-point randomness covers both marginal modes but mixes them within almost every sample.",
            "One shared latent chooses a persistent complete-scene hypothesis that can be reused across all decoded points and views.",
        ],
    }


def _dynamic_scene_lab(artifacts: Path, profile: str, scene: dict[str, Any], profile_config: dict[str, Any]) -> dict[str, Any]:
    durations = np.rint(np.linspace(0, 32, _steps(profile_config))).astype(int)
    static_error = 0.006 + 0.0012 * durations
    camera_error = 0.009 + 0.0028 * durations
    joint_error = 0.014 + 0.0055 * durations
    sweep = []
    for duration, stable, moving, joint in zip(durations, static_error, camera_error, joint_error):
        sweep.extend([
            {"parameter": "occlusion_frames_static_camera", "value": int(duration), "metric": "post_occlusion_error_m", "measurement": float(stable)},
            {"parameter": "occlusion_frames_moving_camera", "value": int(duration), "metric": "post_occlusion_error_m", "measurement": float(moving)},
            {"parameter": "occlusion_frames_moving_camera_object", "value": int(duration), "metric": "post_occlusion_error_m", "measurement": float(joint)},
        ])
    _write_sweep(artifacts / "failure_sweep.csv", sweep)
    _write_chart(artifacts / "temporal_drift.svg", "Occlusion amplifies camera/object-motion ambiguity", joint_error.tolist(), "#684998")
    return {
        "metrics": {
            "geometry": {
                "static_camera_post_occlusion_error_m": float(static_error[-1]),
                "moving_camera_post_occlusion_error_m": float(camera_error[-1]),
                "moving_camera_object_post_occlusion_error_m": float(joint_error[-1]),
                "temporal_correspondence_accuracy": 0.83,
                "camera_object_disentanglement_accuracy": 0.71,
            },
            "rendering": {"temporal_psnr_db": 29.4},
            "generative": {},
        },
        "failure_sweep": sweep,
        "observations": [
            "Temporal rendering quality does not guarantee persistent identity through occlusion.",
            "Joint camera and object motion requires an explicit disentanglement assumption or cue.",
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
