"""Analytic camera/object-motion and occlusion observability fixture."""

from __future__ import annotations

from typing import Any

import numpy as np


DYNAMIC_VARIANTS = (
    "static_camera",
    "moving_camera",
    "moving_camera_object",
)
DYNAMIC_PROFILE_FRAMES = {"smoke": 33, "full": 129}
DYNAMIC_PROFILE_MAX_OCCLUSION = {"smoke": 8, "full": 32}
DYNAMIC_CAMERA_CONTAMINATION = 0.35
DYNAMIC_ARRAY_SEMANTICS = {
    "time_s": "uniform frame times in seconds",
    "variant_names": "ordered camera/object-motion condition names",
    "truth_camera_xyz": "ground-truth world-frame camera centers",
    "estimated_camera_xyz": "world-frame camera centers used to recover world motion",
    "truth_object_xyz": "persistent world-frame object identities through time",
    "observed_object_camera_xyz": "camera-relative object centers; zero where occluded",
    "observed_mask": "whether each camera-relative object center is visible",
    "estimated_visible_object_xyz": "world centers recovered from visible observations; zero where occluded",
    "post_occlusion_prediction_xyz": "identity-labelled constant-velocity predictions at reappearance",
    "post_occlusion_detection_xyz": "unordered reconstructed detections at reappearance",
    "post_occlusion_detection_source_ids": "true persistent identity behind each unordered detection",
    "post_occlusion_assignment": "detection index assigned to each predicted persistent identity",
    "camera_motion_contamination": "fraction of dynamic-object motion leaked into camera translation",
    "occlusion_start_index": "first hidden frame index",
    "reappearance_index": "first visible frame after the hidden interval",
}


def _assignment(predictions: np.ndarray, detections: np.ndarray) -> np.ndarray:
    costs = np.linalg.norm(
        predictions[:, None, :] - detections[None, :, :],
        axis=-1,
    )
    identity_cost = float(costs[0, 0] + costs[1, 1])
    swap_cost = float(costs[0, 1] + costs[1, 0])
    return np.array([0, 1] if identity_cost <= swap_cost else [1, 0], dtype=np.uint8)


def generate_dynamic_fixture(
    frame_count: int,
    occlusion_frames: int,
) -> dict[str, np.ndarray]:
    """Create three views of the same identity-ambiguous dynamic event.

    Two indistinguishable objects approach and reverse behind a complete
    occluder. A constant-velocity tracker instead predicts that they pass
    through one another. Those hypotheses have nearly identical unordered
    geometry at reappearance but opposite persistent identities.
    """
    if frame_count < 17 or frame_count % 2 == 0:
        raise ValueError("dynamic fixture needs an odd frame count of at least 17")
    if occlusion_frames < 0 or occlusion_frames > frame_count // 3:
        raise ValueError("occlusion duration is outside the supported event window")

    time_s = np.linspace(-1.0, 1.0, frame_count, dtype=np.float64)
    center = frame_count // 2
    occlusion_start = center - occlusion_frames // 2
    reappearance = occlusion_start + occlusion_frames
    if occlusion_start < 2 or reappearance >= frame_count:
        raise ValueError("occlusion leaves insufficient trajectory context")

    separation = 0.02 + 0.72 * np.abs(time_s)
    objects = np.zeros((frame_count, 2, 3), dtype=np.float64)
    objects[:, 0, 0] = -separation
    objects[:, 1, 0] = separation
    objects[:, :, 2] = 1.4

    moving_camera = np.stack(
        [
            0.22 * time_s + 0.08 * np.sin(np.pi * time_s),
            0.05 * np.cos(np.pi * time_s),
            np.zeros(frame_count, dtype=np.float64),
        ],
        axis=-1,
    )
    truth_camera = np.stack(
        [np.zeros_like(moving_camera), moving_camera, moving_camera],
        axis=0,
    )
    truth_objects = np.broadcast_to(
        objects[None, :, :, :],
        (len(DYNAMIC_VARIANTS), *objects.shape),
    ).copy()

    contamination = np.array(
        [0.0, 0.0, DYNAMIC_CAMERA_CONTAMINATION],
        dtype=np.float64,
    )
    dynamic_camera_bias = -(
        objects[:, 0, :] - objects[0, 0, :]
    )
    estimated_camera = truth_camera + contamination[:, None, None] * dynamic_camera_bias[None, :, :]

    relative_observations = truth_objects - truth_camera[:, :, None, :]
    observed_mask = np.ones(
        (len(DYNAMIC_VARIANTS), frame_count, 2),
        dtype=np.bool_,
    )
    observed_mask[:, occlusion_start:reappearance, :] = False
    observed = np.where(observed_mask[:, :, :, None], relative_observations, 0.0)
    estimated_visible = np.where(
        observed_mask[:, :, :, None],
        observed + estimated_camera[:, :, None, :],
        0.0,
    )

    last_visible = occlusion_start - 1
    forecast_steps = reappearance - last_visible
    velocity = (
        estimated_visible[:, last_visible, :, :]
        - estimated_visible[:, last_visible - 1, :, :]
    )
    predictions = (
        estimated_visible[:, last_visible, :, :]
        + forecast_steps * velocity
    )
    detection_source_ids = np.tile(
        np.array([1, 0], dtype=np.uint8),
        (len(DYNAMIC_VARIANTS), 1),
    )
    reconstructed_reappearance = (
        relative_observations[:, reappearance, :, :]
        + estimated_camera[:, reappearance, None, :]
    )
    detections = np.take_along_axis(
        reconstructed_reappearance,
        detection_source_ids[:, :, None],
        axis=1,
    )
    assignments = np.stack(
        [_assignment(predictions[index], detections[index]) for index in range(len(DYNAMIC_VARIANTS))]
    )

    return {
        "time_s": time_s,
        "variant_names": np.asarray(DYNAMIC_VARIANTS),
        "truth_camera_xyz": truth_camera,
        "estimated_camera_xyz": estimated_camera,
        "truth_object_xyz": truth_objects,
        "observed_object_camera_xyz": observed,
        "observed_mask": observed_mask,
        "estimated_visible_object_xyz": estimated_visible,
        "post_occlusion_prediction_xyz": predictions,
        "post_occlusion_detection_xyz": detections,
        "post_occlusion_detection_source_ids": detection_source_ids,
        "post_occlusion_assignment": assignments,
        "camera_motion_contamination": contamination,
        "occlusion_start_index": np.array([occlusion_start], dtype=np.int64),
        "reappearance_index": np.array([reappearance], dtype=np.int64),
    }


def _validate_fixture(fixture: dict[str, np.ndarray]) -> tuple[int, int, int]:
    if set(fixture) != set(DYNAMIC_ARRAY_SEMANTICS):
        missing = sorted(set(DYNAMIC_ARRAY_SEMANTICS) - set(fixture))
        extra = sorted(set(fixture) - set(DYNAMIC_ARRAY_SEMANTICS))
        raise ValueError(f"dynamic fixture members mismatch: missing={missing}, extra={extra}")
    time_s = np.asarray(fixture["time_s"], dtype=np.float64)
    variants = np.asarray(fixture["variant_names"])
    if time_s.ndim != 1 or len(time_s) < 17 or len(time_s) % 2 == 0:
        raise ValueError("dynamic time axis must contain an odd number of at least 17 frames")
    if list(variants) != list(DYNAMIC_VARIANTS):
        raise ValueError("dynamic variants are missing or out of order")
    variant_count, frame_count, object_count = len(variants), len(time_s), 2
    expected_shapes = {
        "truth_camera_xyz": (variant_count, frame_count, 3),
        "estimated_camera_xyz": (variant_count, frame_count, 3),
        "truth_object_xyz": (variant_count, frame_count, object_count, 3),
        "observed_object_camera_xyz": (variant_count, frame_count, object_count, 3),
        "observed_mask": (variant_count, frame_count, object_count),
        "estimated_visible_object_xyz": (variant_count, frame_count, object_count, 3),
        "post_occlusion_prediction_xyz": (variant_count, object_count, 3),
        "post_occlusion_detection_xyz": (variant_count, object_count, 3),
        "post_occlusion_detection_source_ids": (variant_count, object_count),
        "post_occlusion_assignment": (variant_count, object_count),
        "camera_motion_contamination": (variant_count,),
        "occlusion_start_index": (1,),
        "reappearance_index": (1,),
    }
    for name, shape in expected_shapes.items():
        array = np.asarray(fixture[name])
        if array.shape != shape:
            raise ValueError(f"{name} must have shape {shape}")
        if not np.all(np.isfinite(array)):
            raise ValueError(f"{name} contains non-finite values")
    if not np.all(np.isfinite(time_s)) or not np.all(np.diff(time_s) > 0.0):
        raise ValueError("dynamic time axis must be finite and increasing")
    mask = np.asarray(fixture["observed_mask"])
    if mask.dtype != np.bool_:
        raise ValueError("observed mask must be boolean")
    start = int(np.asarray(fixture["occlusion_start_index"])[0])
    reappearance = int(np.asarray(fixture["reappearance_index"])[0])
    if start < 2 or reappearance < start or reappearance >= frame_count:
        raise ValueError("invalid dynamic occlusion interval")
    expected_mask = np.ones_like(mask)
    expected_mask[:, start:reappearance, :] = False
    if not np.array_equal(mask, expected_mask):
        raise ValueError("observed mask does not match the occlusion interval")
    for name in ("post_occlusion_detection_source_ids", "post_occlusion_assignment"):
        values = np.asarray(fixture[name])
        if np.any((values != 0) & (values != 1)):
            raise ValueError(f"{name} must contain binary object indices")
        if not np.all(np.sort(values, axis=1) == np.array([0, 1])):
            raise ValueError(f"{name} must contain one-to-one assignments")
    return variant_count, frame_count, object_count


def evaluate_dynamic_fixture(
    fixture: dict[str, np.ndarray],
) -> dict[str, dict[str, float | int]]:
    """Recompute dynamic observability metrics from persisted arrays."""
    variant_count, frame_count, object_count = _validate_fixture(fixture)
    truth_camera = np.asarray(fixture["truth_camera_xyz"], dtype=np.float64)
    estimated_camera = np.asarray(fixture["estimated_camera_xyz"], dtype=np.float64)
    truth_objects = np.asarray(fixture["truth_object_xyz"], dtype=np.float64)
    observed = np.asarray(fixture["observed_object_camera_xyz"], dtype=np.float64)
    mask = np.asarray(fixture["observed_mask"], dtype=np.bool_)
    estimated_visible = np.asarray(
        fixture["estimated_visible_object_xyz"],
        dtype=np.float64,
    )
    predictions = np.asarray(
        fixture["post_occlusion_prediction_xyz"],
        dtype=np.float64,
    )
    detections = np.asarray(
        fixture["post_occlusion_detection_xyz"],
        dtype=np.float64,
    )
    source_ids = np.asarray(
        fixture["post_occlusion_detection_source_ids"],
        dtype=np.uint8,
    )
    assignments = np.asarray(fixture["post_occlusion_assignment"], dtype=np.uint8)
    contamination = np.asarray(
        fixture["camera_motion_contamination"],
        dtype=np.float64,
    )
    occlusion_start = int(np.asarray(fixture["occlusion_start_index"])[0])
    reappearance = int(np.asarray(fixture["reappearance_index"])[0])

    expected_observed = truth_objects - truth_camera[:, :, None, :]
    if not np.allclose(observed[mask], expected_observed[mask], atol=1e-12, rtol=0.0):
        raise ValueError("camera-relative dynamic observations are inconsistent")
    if np.any(observed[~mask] != 0.0) or np.any(estimated_visible[~mask] != 0.0):
        raise ValueError("occluded dynamic observations must use zero-filled masked storage")
    expected_visible = observed + estimated_camera[:, :, None, :]
    if not np.allclose(
        estimated_visible[mask],
        expected_visible[mask],
        atol=1e-12,
        rtol=0.0,
    ):
        raise ValueError("visible world reconstruction is inconsistent")
    expected_contamination = np.array(
        [0.0, 0.0, DYNAMIC_CAMERA_CONTAMINATION],
        dtype=np.float64,
    )
    if not np.array_equal(contamination, expected_contamination):
        raise ValueError("camera-motion contamination contract is inconsistent")
    object_zero_displacement = (
        truth_objects[:, :, 0, :] - truth_objects[:, 0:1, 0, :]
    )
    expected_estimated_camera = (
        truth_camera
        - contamination[:, None, None] * object_zero_displacement
    )
    if not np.allclose(
        estimated_camera,
        expected_estimated_camera,
        atol=1e-12,
        rtol=0.0,
    ):
        raise ValueError("estimated camera does not match the motion-leakage contract")
    last_visible = occlusion_start - 1
    forecast_steps = reappearance - last_visible
    expected_predictions = (
        estimated_visible[:, last_visible, :, :]
        + forecast_steps
        * (
            estimated_visible[:, last_visible, :, :]
            - estimated_visible[:, last_visible - 1, :, :]
        )
    )
    if not np.allclose(
        predictions,
        expected_predictions,
        atol=1e-12,
        rtol=0.0,
    ):
        raise ValueError("post-occlusion prediction is inconsistent")
    expected_source_ids = np.tile(
        np.array([1, 0], dtype=np.uint8),
        (variant_count, 1),
    )
    if not np.array_equal(source_ids, expected_source_ids):
        raise ValueError("post-occlusion detection identities are inconsistent")
    expected_detections = np.take_along_axis(
        estimated_visible[:, reappearance, :, :],
        source_ids[:, :, None],
        axis=1,
    )
    if not np.allclose(
        detections,
        expected_detections,
        atol=1e-12,
        rtol=0.0,
    ):
        raise ValueError("post-occlusion detections are inconsistent")

    comparison: dict[str, dict[str, float | int]] = {}
    for variant_index, variant in enumerate(DYNAMIC_VARIANTS):
        expected_assignment = _assignment(
            predictions[variant_index],
            detections[variant_index],
        )
        if not np.array_equal(assignments[variant_index], expected_assignment):
            raise ValueError("post-occlusion assignment is inconsistent")
        assigned_source_ids = source_ids[variant_index, expected_assignment]
        identity_truth = truth_objects[variant_index, reappearance]
        truth_set_assignment = _assignment(
            predictions[variant_index],
            identity_truth,
        )
        assigned_truth = identity_truth[truth_set_assignment]
        identity_errors = np.linalg.norm(
            predictions[variant_index] - identity_truth,
            axis=-1,
        )
        set_errors = np.linalg.norm(
            predictions[variant_index] - assigned_truth,
            axis=-1,
        )
        camera_errors = np.linalg.norm(
            estimated_camera[variant_index] - truth_camera[variant_index],
            axis=-1,
        )
        visible_errors = np.linalg.norm(
            estimated_visible[variant_index] - truth_objects[variant_index],
            axis=-1,
        )[mask[variant_index]]
        pair_mask = mask[variant_index, 1:] & mask[variant_index, :-1]
        estimated_delta = np.diff(estimated_visible[variant_index], axis=0)
        truth_delta = np.diff(truth_objects[variant_index], axis=0)
        temporal_errors = np.linalg.norm(
            estimated_delta - truth_delta,
            axis=-1,
        )[pair_mask]
        reprojection = (
            estimated_visible[variant_index]
            - estimated_camera[variant_index, :, None, :]
        )
        observation_errors = np.linalg.norm(
            reprojection - observed[variant_index],
            axis=-1,
        )[mask[variant_index]]
        object_displacement = (
            truth_objects[variant_index, :, 0, :]
            - truth_objects[variant_index, 0, 0, :]
        )
        camera_error_vectors = (
            estimated_camera[variant_index] - truth_camera[variant_index]
        )
        displacement_norm = float(np.linalg.norm(object_displacement))
        leakage = (
            float(np.linalg.norm(camera_error_vectors)) / displacement_norm
            if displacement_norm > 0.0
            else 0.0
        )
        comparison[variant] = {
            "frame_count": frame_count,
            "object_count": object_count,
            "occlusion_frames": reappearance
            - int(np.asarray(fixture["occlusion_start_index"])[0]),
            "camera_ate_m": float(np.sqrt(np.mean(np.square(camera_errors)))),
            "visible_object_rmse_m": float(np.sqrt(np.mean(np.square(visible_errors)))),
            "temporal_displacement_rmse_m": float(
                np.sqrt(np.mean(np.square(temporal_errors)))
            ),
            "camera_relative_observation_rmse_m": float(
                np.sqrt(np.mean(np.square(observation_errors)))
            ),
            "identity_aware_post_occlusion_rmse_m": float(
                np.sqrt(np.mean(np.square(identity_errors)))
            ),
            "set_aligned_reappearance_rmse_m": float(
                np.sqrt(np.mean(np.square(set_errors)))
            ),
            "post_occlusion_identity_accuracy": float(
                np.mean(assigned_source_ids == np.arange(object_count))
            ),
            "camera_object_motion_leakage_fraction": leakage,
        }
    return comparison


def dynamic_result_metrics(
    comparison: dict[str, dict[str, float | int]],
) -> dict[str, float]:
    """Flatten the three condition summaries into the result metric family."""
    metrics: dict[str, float] = {}
    for variant in DYNAMIC_VARIANTS:
        summary = comparison[variant]
        prefix = variant
        metrics[f"{prefix}_post_occlusion_error_m"] = float(
            summary["identity_aware_post_occlusion_rmse_m"]
        )
        for name in (
            "set_aligned_reappearance_rmse_m",
            "post_occlusion_identity_accuracy",
            "camera_ate_m",
            "visible_object_rmse_m",
            "temporal_displacement_rmse_m",
            "camera_relative_observation_rmse_m",
            "camera_object_motion_leakage_fraction",
        ):
            metrics[f"{prefix}_{name}"] = float(summary[name])
    return metrics


def generate_dynamic_failure_sweep(
    frame_count: int,
    max_occlusion_frames: int,
    sweep_steps: int,
) -> tuple[list[dict[str, str | int | float]], list[float]]:
    """Generate the deterministic occlusion-duration failure sweep."""
    if sweep_steps < 2:
        raise ValueError("dynamic failure sweep needs at least two steps")
    durations = np.unique(
        np.rint(np.linspace(0, max_occlusion_frames, sweep_steps)).astype(int)
    )
    rows: list[dict[str, str | int | float]] = []
    joint_drift: list[float] = []
    for duration in durations:
        comparison = evaluate_dynamic_fixture(
            generate_dynamic_fixture(frame_count, int(duration))
        )
        joint_drift.append(
            float(
                comparison["moving_camera_object"][
                    "identity_aware_post_occlusion_rmse_m"
                ]
            )
        )
        for variant in DYNAMIC_VARIANTS:
            summary = comparison[variant]
            for metric in (
                "identity_aware_post_occlusion_rmse_m",
                "set_aligned_reappearance_rmse_m",
                "post_occlusion_identity_accuracy",
            ):
                rows.append(
                    {
                        "parameter": f"occlusion_frames_{variant}",
                        "value": int(duration),
                        "metric": metric,
                        "measurement": float(summary[metric]),
                    }
                )
    return rows, joint_drift
