"""Run and validate the pinned ORB-SLAM3 RGB-D reference adapter."""

from __future__ import annotations

import csv
import hashlib
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
    sha256_file,
    validate_json_schema_instance,
    validate_run_id,
    write_json,
)
from fetch import _extraction_manifest


ADAPTER = "orb-slam"
IMAGE = "surflo-pathway-orb-slam:1"
PINNED_ORB_SLAM3_COMMIT = "4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4"
PINNED_PANGOLIN_COMMIT = "dd801d244db3a8e27b7fe8020cd751404aa818fd"
PINNED_INSULA_MANIFEST = {
    "schema_version": "1",
    "kind": "rgbd-slam",
    "ubuntu": "22.04",
    "orb_slam3_commit": PINNED_ORB_SLAM3_COMMIT,
    "pangolin_commit": PINNED_PANGOLIN_COMMIT,
    "network_policy": "build-and-fetch-only",
}
PROFILE_FRAME_LIMIT = {"smoke": 300, "full": None}
GROUND_TRUTH_MAX_DELTA_SECONDS = 0.05
REFERENCE_IMPLEMENTATION = (
    "curriculum.json",
    "pipeline/cli.py",
    "pipeline/contracts.py",
    "pipeline/fetch.py",
    "pipeline/reference_runner.py",
    "pipeline/slam_reference_runner.py",
    "insulas/orb-slam/Dockerfile",
    "insulas/orb-slam/run-rgbd.sh",
    "insulas/orb-slam/surflo_rgbd.cc",
    "insulas/locks.json",
    "reference-result.schema.json",
    "assets.lock.json",
    "reference-adapters.json",
)
TRACKING_STATES = {0: "NO_IMAGES_YET", 1: "NOT_INITIALIZED", 2: "OK", 3: "RECENTLY_LOST", 4: "LOST", 5: "OK_KLT"}
TRACKED_STATES = {2, 5}


TrajectoryRecord = tuple[float, np.ndarray, np.ndarray]


def _quaternion_to_rotation(quaternion: np.ndarray) -> np.ndarray:
    x, y, z, w = quaternion
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def parse_tum_trajectory(path: Path) -> list[TrajectoryRecord]:
    records: list[TrajectoryRecord] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 8:
            raise ValueError(f"malformed TUM trajectory record at line {line_number}")
        try:
            values = np.asarray([float(field) for field in fields], dtype=np.float64)
        except ValueError as error:
            raise ValueError(f"malformed TUM trajectory record at line {line_number}") from error
        if not np.isfinite(values).all():
            raise ValueError(f"non-finite TUM trajectory record at line {line_number}")
        timestamp = float(values[0])
        quaternion = values[4:8]
        norm = float(np.linalg.norm(quaternion))
        if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1e-3):
            raise ValueError(f"TUM trajectory requires a unit quaternion at line {line_number}")
        if records and timestamp <= records[-1][0]:
            raise ValueError(f"TUM trajectory timestamps must be strictly increasing: {path}")
        records.append((timestamp, values[1:4], quaternion / norm))
    if not records:
        raise ValueError("TUM trajectory is empty")
    return records


def _associate(
    estimated: list[TrajectoryRecord], truth: list[TrajectoryRecord], max_delta_seconds: float
) -> list[tuple[TrajectoryRecord, TrajectoryRecord]]:
    candidates = []
    for estimated_index, estimate in enumerate(estimated):
        for truth_index, reference in enumerate(truth):
            delta = abs(estimate[0] - reference[0])
            if delta <= max_delta_seconds:
                candidates.append((delta, estimated_index, truth_index))
    matches = []
    used_estimated: set[int] = set()
    used_truth: set[int] = set()
    for _, estimated_index, truth_index in sorted(candidates):
        if estimated_index in used_estimated or truth_index in used_truth:
            continue
        used_estimated.add(estimated_index)
        used_truth.add(truth_index)
        matches.append((estimated[estimated_index], truth[truth_index]))
    return sorted(matches, key=lambda pair: pair[0][0])


def _rigid_alignment(source: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    source_center = source.mean(axis=0)
    target_center = target.mean(axis=0)
    covariance = (source - source_center).T @ (target - target_center)
    left, _, right_t = np.linalg.svd(covariance)
    rotation = right_t.T @ left.T
    if np.linalg.det(rotation) < 0:
        right_t[-1, :] *= -1
        rotation = right_t.T @ left.T
    translation = target_center - rotation @ source_center
    return rotation, translation


def _rotation_angle_degrees(rotation: np.ndarray) -> float:
    cosine = min(1.0, max(-1.0, (float(np.trace(rotation)) - 1.0) / 2.0))
    return math.degrees(math.acos(cosine))


def evaluate_trajectory(
    estimated: list[TrajectoryRecord], truth: list[TrajectoryRecord], max_delta_seconds: float = 0.02
) -> tuple[dict[str, float | int], dict[str, np.ndarray]]:
    matches = _associate(estimated, truth, max_delta_seconds)
    if len(matches) < 3:
        raise ValueError(f"trajectory has too few timestamp matches: {len(matches)}")
    source = np.stack([estimate[1] for estimate, _ in matches])
    target = np.stack([reference[1] for _, reference in matches])
    rotation, translation = _rigid_alignment(source, target)
    aligned = (rotation @ source.T).T + translation
    residuals = np.linalg.norm(aligned - target, axis=1)
    translation_errors = []
    rotation_errors = []
    for index in range(len(matches) - 1):
        estimate_first, truth_first = matches[index]
        estimate_second, truth_second = matches[index + 1]
        estimated_delta = _quaternion_to_rotation(estimate_first[2]).T @ (
            estimate_second[1] - estimate_first[1]
        )
        truth_delta = _quaternion_to_rotation(truth_first[2]).T @ (
            truth_second[1] - truth_first[1]
        )
        translation_errors.append(float(np.linalg.norm(estimated_delta - truth_delta)))
        estimated_relative = (
            _quaternion_to_rotation(estimate_first[2]).T
            @ _quaternion_to_rotation(estimate_second[2])
        )
        truth_relative = (
            _quaternion_to_rotation(truth_first[2]).T
            @ _quaternion_to_rotation(truth_second[2])
        )
        rotation_errors.append(_rotation_angle_degrees(estimated_relative.T @ truth_relative))
    metrics: dict[str, float | int] = {
        "trajectory_matches": len(matches),
        "ate_rmse_m": float(np.sqrt(np.mean(residuals * residuals))),
        "rpe_translation_rmse_m": float(np.sqrt(np.mean(np.square(translation_errors)))),
        "rpe_rotation_rmse_deg": float(np.sqrt(np.mean(np.square(rotation_errors)))),
        "endpoint_drift_m": float(
            np.linalg.norm(
                _quaternion_to_rotation(matches[0][0][2]).T @ (source[-1] - source[0])
                - _quaternion_to_rotation(matches[0][1][2]).T @ (target[-1] - target[0])
            )
        ),
        "endpoint_rotation_drift_deg": _rotation_angle_degrees(
            (
                _quaternion_to_rotation(matches[0][0][2]).T
                @ _quaternion_to_rotation(matches[-1][0][2])
            ).T
            @ (
                _quaternion_to_rotation(matches[0][1][2]).T
                @ _quaternion_to_rotation(matches[-1][1][2])
            )
        ),
    }
    return metrics, {"rotation": rotation, "translation": translation}


def _nearest_distances(query: np.ndarray, target: np.ndarray) -> np.ndarray:
    if len(query) == 0 or len(target) == 0:
        raise ValueError("point-cloud evaluation requires non-empty clouds")
    target_norm = np.sum(target * target, axis=1)
    result = np.empty(len(query), dtype=np.float64)
    for start in range(0, len(query), 256):
        batch = query[start : start + 256]
        squared = np.sum(batch * batch, axis=1, keepdims=True) + target_norm - 2.0 * batch @ target.T
        result[start : start + len(batch)] = np.sqrt(np.maximum(np.min(squared, axis=1), 0.0))
    return result


def evaluate_point_clouds(
    estimate: np.ndarray, truth: np.ndarray, threshold_m: float = 0.1
) -> dict[str, float | int]:
    estimate = np.asarray(estimate, dtype=np.float64)
    truth = np.asarray(truth, dtype=np.float64)
    if (
        estimate.ndim != 2
        or truth.ndim != 2
        or estimate.shape[1:] != (3,)
        or truth.shape[1:] != (3,)
        or not np.isfinite(estimate).all()
        or not np.isfinite(truth).all()
        or threshold_m <= 0.0
    ):
        raise ValueError("invalid point-cloud evaluation input")
    accuracy = _nearest_distances(estimate, truth)
    completeness = _nearest_distances(truth, estimate)
    precision = float(np.mean(accuracy <= threshold_m))
    recall = float(np.mean(completeness <= threshold_m))
    fscore = 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)
    metrics: dict[str, float | int] = {
        "map_points": int(len(estimate)),
        "map_truth_points": int(len(truth)),
        "map_accuracy_mean_m": float(np.mean(accuracy)),
        "map_completeness_mean_m": float(np.mean(completeness)),
        "map_precision_10cm": precision,
        "map_recall_10cm": recall,
        "map_fscore_10cm": fscore,
    }
    ensure_finite(metrics, "SLAM point-cloud metrics")
    return metrics


def _read_ascii_ply(path: Path) -> np.ndarray:
    with path.open("r", encoding="ascii") as stream:
        if stream.readline().strip() != "ply" or stream.readline().strip() != "format ascii 1.0":
            raise ValueError(f"unsupported PLY format: {path}")
        count: int | None = None
        properties: list[str] = []
        in_vertex = False
        while True:
            line = stream.readline()
            if not line:
                raise ValueError(f"truncated PLY header: {path}")
            fields = line.strip().split()
            if fields[:2] == ["element", "vertex"] and len(fields) == 3:
                count = int(fields[2])
                in_vertex = True
            elif fields[:1] == ["element"]:
                in_vertex = False
            elif in_vertex and fields[:2] == ["property", "float"] and len(fields) == 3:
                properties.append(fields[2])
            elif fields == ["end_header"]:
                break
        if count is None or count <= 0 or properties[:3] != ["x", "y", "z"]:
            raise ValueError(f"invalid PLY vertex declaration: {path}")
        points = []
        for _ in range(count):
            line = stream.readline()
            if not line:
                raise ValueError(f"truncated PLY body: {path}")
            fields = line.split()
            if len(fields) < len(properties):
                raise ValueError(f"malformed PLY vertex: {path}")
            points.append([float(fields[0]), float(fields[1]), float(fields[2])])
        if any(line.strip() for line in stream):
            raise ValueError(f"unexpected trailing PLY records: {path}")
    result = np.asarray(points, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError(f"non-finite PLY vertex: {path}")
    return result


def _parse_stream(path: Path) -> list[tuple[float, str]]:
    records = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2:
            raise ValueError(f"malformed TUM stream index {path.name}:{line_number}")
        timestamp = float(fields[0])
        relative = Path(fields[1])
        if not math.isfinite(timestamp) or relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe TUM stream index {path.name}:{line_number}")
        if records and timestamp <= records[-1][0]:
            raise ValueError(f"non-increasing TUM stream index: {path.name}")
        records.append((timestamp, relative.as_posix()))
    if not records:
        raise ValueError(f"empty TUM stream index: {path.name}")
    return records


def _data_record_count(path: Path) -> int:
    return sum(
        bool(line.strip()) and not line.lstrip().startswith("#")
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _nearest_record(records: list[tuple[float, Any]], timestamp: float, maximum_delta: float) -> tuple[float, Any]:
    record = min(records, key=lambda item: abs(item[0] - timestamp))
    if abs(record[0] - timestamp) > maximum_delta:
        raise ValueError(f"TUM streams are not synchronized near {timestamp:.9f}")
    return record


def _prepare_dataset_contract(dataset: Path, profile: str, staging: Path) -> dict[str, Any]:
    rgb = _parse_stream(dataset / "rgb.txt")
    depth = _parse_stream(dataset / "depth.txt")
    truth_records = parse_tum_trajectory(dataset / "groundtruth.txt")
    frame_limit = PROFILE_FRAME_LIMIT[profile]
    selected = rgb if frame_limit is None else rgb[:frame_limit]
    associations = []
    truth_lines = []
    consumed = {"rgb.txt", "depth.txt", "groundtruth.txt"}
    for rgb_timestamp, rgb_path in selected:
        depth_timestamp, depth_path = _nearest_record(depth, rgb_timestamp, 0.03)
        truth_timestamp, truth_position, truth_quaternion = min(
            truth_records, key=lambda item: abs(item[0] - rgb_timestamp)
        )
        if abs(truth_timestamp - rgb_timestamp) > GROUND_TRUTH_MAX_DELTA_SECONDS:
            raise ValueError(f"ground truth is not synchronized near {rgb_timestamp:.9f}")
        for relative in (rgb_path, depth_path):
            path = dataset / relative
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"missing or unsafe TUM frame: {relative}")
            consumed.add(relative)
        associations.append(f"{rgb_timestamp:.9f} {rgb_path} {depth_timestamp:.9f} {depth_path}")
        values = [*truth_position.tolist(), *truth_quaternion.tolist()]
        truth_lines.append(f"{rgb_timestamp:.9f} " + " ".join(f"{value:.12g}" for value in values))
    if len(associations) < 4:
        raise ValueError("TUM profile has too few associated RGB-D frames")
    config = staging / "config"
    config.mkdir()
    (config / "associations.txt").write_text("\n".join(associations) + "\n", encoding="utf-8")
    (config / "groundtruth-prefix.txt").write_text("\n".join(truth_lines) + "\n", encoding="utf-8")
    (config / "insula-manifest.expected").write_text(
        "".join(f"{key}={value}\n" for key, value in PINNED_INSULA_MANIFEST.items()), encoding="utf-8"
    )
    contract = {
        "schema_version": 1,
        "dataset": "TUM RGB-D freiburg1_xyz",
        "profile": profile,
        "frame_count": len(associations),
        "association_sha256": sha256_file(config / "associations.txt"),
        "groundtruth_sha256": sha256_file(config / "groundtruth-prefix.txt"),
        "consumed_paths": sorted(consumed),
    }
    input_root = staging / "input"
    input_root.mkdir()
    write_json(input_root / "dataset-contract.json", contract)
    return contract


def _parse_tracking(path: Path) -> dict[str, float | int]:
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    expected = {"timestamp", "state", "tracked_map_points", "runtime_seconds"}
    if not rows or set(rows[0]) != expected:
        raise ValueError("invalid ORB-SLAM tracking log schema")
    timestamps: list[float] = []
    states: list[int] = []
    for row in rows:
        timestamp = float(row["timestamp"])
        state = int(row["state"])
        points = int(row["tracked_map_points"])
        runtime = float(row["runtime_seconds"])
        if (
            not math.isfinite(timestamp)
            or (timestamps and timestamp <= timestamps[-1])
            or state not in TRACKING_STATES
            or points < 0
            or not math.isfinite(runtime)
            or runtime < 0.0
        ):
            raise ValueError("invalid ORB-SLAM tracking log record")
        timestamps.append(timestamp)
        states.append(state)
    tracked = sum(state in TRACKED_STATES for state in states)
    lost = sum(state in {3, 4} for state in states)
    recoveries = sum(
        states[index - 1] in {3, 4} and states[index] in TRACKED_STATES
        for index in range(1, len(states))
    )
    return {
        "input_frames": len(rows),
        "tracked_frames": tracked,
        "tracking_coverage": tracked / len(rows),
        "lost_frames": lost,
        "tracking_recoveries": recoveries,
    }


def _parse_manifest(path: Path) -> dict[str, str]:
    result = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw or "=" not in raw:
            raise ValueError(f"malformed Insula manifest: {path}")
        key, value = raw.split("=", 1)
        if not key or key in result or not value:
            raise ValueError(f"malformed Insula manifest: {path}")
        result[key] = value
    return result


def _hash_tree(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        relative = path.relative_to(root).as_posix()
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink artifact is forbidden: {relative}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"non-regular artifact is forbidden: {relative}")
        if path.name != "result.json":
            result[relative] = sha256_file(path)
    return result


def _secure_directory(root: Path, name: str) -> Path:
    path = root / name
    if os.path.lexists(path):
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f"cache descendant must be a real directory: {path}")
    else:
        path.mkdir()
    path.resolve(strict=True).relative_to(root)
    return path


def _inspect_image(engine: str) -> str:
    if shutil.which(engine) is None:
        raise ValueError(f"container engine not found: {engine}")
    completed = subprocess.run(
        [engine, "image", "inspect", "--format", "{{.Id}}", IMAGE],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise ValueError(f"ORB-SLAM Insula is not built: {IMAGE}; run `run.sh build` first")
    return completed.stdout.strip()


def _adapter_record() -> dict[str, Any]:
    return next(
        item for item in load_json(ROOT / "reference-adapters.json")["adapters"]
        if item["id"] == "orb-slam-reference"
    )


def _verify_tum_asset(cache_root: Path) -> tuple[Path, dict[str, Any]]:
    asset = next(item for item in load_json(ROOT / "assets.lock.json")["assets"] if item["id"] == "tum-rgbd")
    assets = cache_root / "assets"
    archive = assets / "tum-rgbd.archive"
    dataset = assets / "tum-rgbd"
    manifest_path = assets / "tum-rgbd.extraction.json"
    if not archive.is_file() or sha256_file(archive) != asset["sha256"]:
        raise ValueError("locked TUM RGB-D archive is missing or corrupt; run `run.sh fetch --asset tum-rgbd`")
    if not dataset.is_dir() or dataset.is_symlink() or not manifest_path.is_file():
        raise ValueError("locked TUM RGB-D extraction is missing; run `run.sh fetch --asset tum-rgbd`")
    manifest = load_json(manifest_path)
    actual = _extraction_manifest(dataset, archive, str(asset["extraction"]["root"]))
    if manifest != actual:
        raise ValueError("TUM RGB-D extraction manifest mismatch")
    return dataset, manifest


def _geometry_metrics(run_dir: Path) -> dict[str, float | int]:
    tracking = _parse_tracking(run_dir / "output/tracking.csv")
    estimate = parse_tum_trajectory(run_dir / "output/CameraTrajectory.txt")
    keyframes = parse_tum_trajectory(run_dir / "output/KeyFrameTrajectory.txt")
    estimate_timestamps = np.asarray([record[0] for record in estimate])
    if any(float(np.min(np.abs(estimate_timestamps - record[0]))) > 1e-5 for record in keyframes):
        raise ValueError("keyframe trajectory is not a subset of the camera trajectory")
    truth = parse_tum_trajectory(run_dir / "config/groundtruth-prefix.txt")
    trajectory, transform = evaluate_trajectory(estimate, truth)
    estimated_map = _read_ascii_ply(run_dir / "output/map.ply")
    truth_map = _read_ascii_ply(run_dir / "output/ground-truth-map.ply")
    aligned_map = (transform["rotation"] @ estimated_map.T).T + transform["translation"]
    metrics = {
        **tracking,
        "keyframes": len(keyframes),
        **trajectory,
        **evaluate_point_clouds(aligned_map, truth_map),
    }
    ensure_finite(metrics, "ORB-SLAM metrics")
    return metrics


def _acceptance_failures(metrics: dict[str, Any], acceptance: dict[str, Any]) -> list[str]:
    checks = (
        (metrics["input_frames"] >= acceptance["input_frames_min"], "input_frames"),
        (metrics["tracking_coverage"] >= acceptance["tracking_coverage_min"], "tracking_coverage"),
        (metrics["trajectory_matches"] >= acceptance["trajectory_matches_min"], "trajectory_matches"),
        (metrics["ate_rmse_m"] <= acceptance["ate_rmse_m_max"], "ate_rmse_m"),
        (metrics["map_points"] >= acceptance["map_points_min"], "map_points"),
        (metrics["map_fscore_10cm"] >= acceptance["map_fscore_10cm_min"], "map_fscore_10cm"),
    )
    return [name for passed, name in checks if not passed]


FAILURE_TRAJECTORIES = {
    "occlusion": "output/CameraTrajectory-occlusion.txt",
    "dynamic-object": "output/CameraTrajectory-dynamic-object.txt",
}
FAILURE_TRAJECTORY_METRICS = (
    "trajectory_matches",
    "ate_rmse_m",
    "rpe_translation_rmse_m",
    "rpe_rotation_rmse_deg",
    "endpoint_drift_m",
    "endpoint_rotation_drift_deg",
)


def _validate_failure_sweep(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "output/failure-sweep.json"
    value = load_json(path)
    variants = value.get("variants")
    if not isinstance(variants, list) or {item.get("id") for item in variants} != {"occlusion", "dynamic-object"}:
        raise ValueError("SLAM failure sweep must contain occlusion and dynamic-object variants")
    truth = parse_tum_trajectory(run_dir / "config/groundtruth-prefix.txt")
    for item in variants:
        coverage = item.get("tracking_coverage")
        if isinstance(coverage, bool) or not isinstance(coverage, (int, float)) or not 0.0 <= coverage <= 1.0:
            raise ValueError("invalid SLAM failure-sweep coverage")
        if not isinstance(item.get("lost_during_perturbation"), bool):
            raise ValueError("invalid SLAM failure-sweep loss flag")
        if not isinstance(item.get("tracking_resumed"), bool):
            raise ValueError("invalid SLAM failure-sweep resume flag")
        if not isinstance(item.get("same_map_relocalized"), bool):
            raise ValueError("invalid SLAM failure-sweep relocalization flag")
        map_ids = (item.get("map_id_before_perturbation"), item.get("map_id_after_resume"))
        if any(isinstance(map_id, bool) or not isinstance(map_id, int) or map_id < -1 for map_id in map_ids):
            raise ValueError("invalid SLAM failure-sweep map identity")
        if item["tracking_resumed"] and not item["lost_during_perturbation"]:
            raise ValueError("SLAM tracking cannot resume without a recorded loss")
        expected_same_map = (
            item["tracking_resumed"]
            and map_ids[0] >= 0
            and map_ids[0] == map_ids[1]
        )
        if item["same_map_relocalized"] != expected_same_map:
            raise ValueError("SLAM same-map relocalization flag does not match map identities")
        trajectory = parse_tum_trajectory(run_dir / FAILURE_TRAJECTORIES[item["id"]])
        if not math.isclose(
            float(coverage), len(trajectory) / len(truth), rel_tol=1e-12, abs_tol=1e-12
        ):
            raise ValueError("SLAM failure-sweep coverage does not match its trajectory")
        actual, _ = evaluate_trajectory(trajectory, truth)
        expected = {name: actual[name] for name in FAILURE_TRAJECTORY_METRICS}
        if not _metrics_match(item.get("trajectory", {}), expected):
            raise ValueError("SLAM failure-sweep trajectory metric mismatch")
    return value


def _record_failure_sweep_metrics(run_dir: Path) -> None:
    path = run_dir / "output/failure-sweep.json"
    value = load_json(path)
    variants = value.get("variants")
    if not isinstance(variants, list):
        raise ValueError("invalid raw SLAM failure sweep")
    truth = parse_tum_trajectory(run_dir / "config/groundtruth-prefix.txt")
    for item in variants:
        variant_id = item.get("id")
        if variant_id not in FAILURE_TRAJECTORIES:
            raise ValueError("invalid raw SLAM failure-sweep variant")
        trajectory = parse_tum_trajectory(run_dir / FAILURE_TRAJECTORIES[variant_id])
        actual, _ = evaluate_trajectory(trajectory, truth)
        item["trajectory"] = {name: actual[name] for name in FAILURE_TRAJECTORY_METRICS}
    write_json(path, value)


def _require_file(run_dir: Path, relative: str) -> Path:
    path = run_dir / relative
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or unsafe reference artifact: {relative}")
    path.resolve(strict=True).relative_to(run_dir.resolve(strict=True))
    return path


def _metrics_match(recorded: dict[str, Any], actual: dict[str, Any]) -> bool:
    if set(recorded) != set(actual):
        return False
    for key, expected in actual.items():
        value = recorded[key]
        if isinstance(expected, int):
            if isinstance(value, bool) or value != expected:
                return False
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isclose(
            float(value), float(expected), rel_tol=1e-9, abs_tol=1e-12
        ):
            return False
    return True


def validate_slam_reference_result(run_dir: Path) -> dict[str, Any]:
    result = load_json(_require_file(run_dir, "result.json"))
    validate_json_schema_instance(result, load_json(ROOT / "reference-result.schema.json"), "reference-result")
    ensure_finite(result, "reference-result")
    if result.get("adapter") != ADAPTER or result.get("module_ids") != ["07"]:
        raise ValueError("module scope mismatch: ORB-SLAM belongs to module 07")
    if result.get("status") != "complete" or result.get("network_mode") != "offline":
        raise ValueError("SLAM reference result is not a complete offline record")
    if result["tool"].get("name") != "ORB-SLAM3" or result["tool"].get("container_image") != IMAGE:
        raise ValueError("tool identity mismatch")
    if (
        result["tool"].get("source_commit") != PINNED_ORB_SLAM3_COMMIT
        or result["tool"].get("version") != f"ORB-SLAM3@{PINNED_ORB_SLAM3_COMMIT[:12]}"
        or result["tool"].get("package_version") != "source-build"
    ):
        raise ValueError("tool source commit mismatch")
    for relative in (
        "adapter.log", "report.md", "trajectory.svg", "input/dataset-contract.json",
        "config/associations.txt", "config/groundtruth-prefix.txt", "config/insula-manifest.expected",
        "output/CameraTrajectory.txt", "output/KeyFrameTrajectory.txt", "output/tracking.csv",
        "output/CameraTrajectory-occlusion.txt", "output/CameraTrajectory-dynamic-object.txt",
        "output/map.ply", "output/ground-truth-map.ply", "output/source-commit.txt",
        "output/insula-manifest.txt", "output/failure-sweep.json", "output/resource-summary.txt",
        "output/resources.json",
    ):
        _require_file(run_dir, relative)
    if _parse_manifest(run_dir / "output/insula-manifest.txt") != PINNED_INSULA_MANIFEST:
        raise ValueError("ORB-SLAM Insula manifest mismatch")
    if (run_dir / "output/source-commit.txt").read_text(encoding="utf-8").strip() != PINNED_ORB_SLAM3_COMMIT:
        raise ValueError("ORB-SLAM source commit mismatch")
    _validate_failure_sweep(run_dir)
    metrics = _geometry_metrics(run_dir)
    if not _metrics_match(result.get("metrics", {}), metrics):
        raise ValueError("ORB-SLAM metric mismatch")
    acceptance = _adapter_record()["acceptance"][result["profile"]]
    if result.get("acceptance") != acceptance or _acceptance_failures(metrics, acceptance):
        raise ValueError("ORB-SLAM result is below the locked acceptance threshold")
    provenance = result["provenance"]
    config = provenance["config"]
    if provenance.get("config_sha256") != hashlib.sha256(canonical_json(config)).hexdigest():
        raise ValueError("config hash mismatch")
    validate_run_id(config.get("run_id", ""))
    if (
        config.get("adapter") != ADAPTER
        or config.get("profile") != result["profile"]
        or config.get("module_ids") != ["07"]
        or config.get("image") != IMAGE
        or config.get("image_id") != result["tool"]["container_image_id"]
        or config.get("acceptance") != acceptance
        or config.get("trajectory_association_max_delta_seconds") != 0.02
        or config.get("rpe_delta_frames") != 1
        or config.get("ground_truth_association_max_delta_seconds") != GROUND_TRUTH_MAX_DELTA_SECONDS
        or config.get("map_fscore_threshold_m") != 0.1
    ):
        raise ValueError("reference config binding mismatch")
    dataset_contract = load_json(run_dir / "input/dataset-contract.json")
    if config.get("dataset_contract") != dataset_contract:
        raise ValueError("dataset contract binding mismatch")
    if (
        dataset_contract.get("profile") != result["profile"]
        or dataset_contract.get("frame_count") != metrics["input_frames"]
        or dataset_contract.get("frame_count")
        != _data_record_count(run_dir / "config/associations.txt")
        or dataset_contract.get("frame_count")
        != len(parse_tum_trajectory(run_dir / "config/groundtruth-prefix.txt"))
        or dataset_contract.get("association_sha256") != sha256_file(run_dir / "config/associations.txt")
        or dataset_contract.get("groundtruth_sha256") != sha256_file(run_dir / "config/groundtruth-prefix.txt")
    ):
        raise ValueError("dataset contract binding mismatch")
    if (
        config.get("asset_archive_sha256") != provenance.get("asset_archive_sha256")
        or config.get("asset_tree_sha256") != provenance.get("asset_tree_sha256")
    ):
        raise ValueError("asset provenance binding mismatch")
    asset_lock = next(
        item for item in load_json(ROOT / "assets.lock.json")["assets"] if item["id"] == "tum-rgbd"
    )
    if provenance.get("asset_archive_sha256") != asset_lock["sha256"]:
        raise ValueError("asset provenance does not match the TUM RGB-D lock")
    resource_summary = load_json(run_dir / "output/resources.json")
    if result["resources"] != resource_summary:
        raise ValueError("resource summary mismatch")
    runtime = resource_summary.get("runtime_seconds")
    peak_memory = resource_summary.get("peak_cpu_memory_bytes")
    if (
        isinstance(runtime, bool)
        or not isinstance(runtime, (int, float))
        or runtime < 0.0
        or isinstance(peak_memory, bool)
        or not isinstance(peak_memory, int)
        or peak_memory <= 0
        or peak_memory != _resource_memory(run_dir / "output/resource-summary.txt")
    ):
        raise ValueError("invalid SLAM resource measurement")
    implementation = {name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION}
    if provenance.get("implementation_sha256") != implementation:
        raise ValueError("implementation hash mismatch")
    if provenance.get("artifacts_sha256") != _hash_tree(run_dir):
        raise ValueError("artifact hash mismatch")
    return result


def _resource_memory(path: Path) -> int:
    match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("resource summary lacks peak CPU memory")
    return int(match.group(1)) * 1024


def _write_trajectory_svg(
    path: Path,
    estimate: list[TrajectoryRecord],
    truth: list[TrajectoryRecord],
    transform: dict[str, np.ndarray],
) -> None:
    estimate = [
        (timestamp, transform["rotation"] @ position + transform["translation"], quaternion)
        for timestamp, position, quaternion in estimate
    ]
    all_points = np.stack([record[1][[0, 2]] for record in estimate + truth])
    minimum = all_points.min(axis=0)
    span = np.maximum(all_points.max(axis=0) - minimum, 1e-9)

    def polyline(records: list[TrajectoryRecord], color: str) -> str:
        points = []
        for _, position, _ in records:
            x, y = 20.0 + 300.0 * (position[[0, 2]] - minimum) / span
            points.append(f"{x:.3f},{340.0 - y:.3f}")
        return f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(points)}"/>'

    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">'
        '<rect width="640" height="360" fill="white"/>'
        '<text x="12" y="20" font-family="sans-serif" font-size="12">Aligned ORB-SLAM3 (red) / truth (black)</text>'
        + polyline(truth, "#222") + polyline(estimate, "#d33") + "</svg>\n",
        encoding="utf-8",
    )


def run_slam_reference(cache_root: Path, profile: str, run_id: str) -> Path:
    validate_run_id(run_id)
    if profile not in PROFILE_FRAME_LIMIT:
        raise ValueError(f"unknown profile: {profile}")
    engine = os.environ.get("SURFLO_PATHWAY_CONTAINER_ENGINE", "docker")
    image_id = _inspect_image(engine)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root = cache_root.resolve(strict=True)
    dataset, asset_manifest = _verify_tum_asset(cache_root)
    runs_root = _secure_directory(cache_root, "reference-runs")
    staging_root = _secure_directory(cache_root, "reference-staging")
    final_parent = runs_root / run_id
    final = final_parent / ADAPTER
    if os.path.lexists(final_parent):
        raise FileExistsError(f"reference run already exists: {final}")
    staging = staging_root / f"{run_id}.{ADAPTER}.{uuid.uuid4().hex}"
    staging.mkdir()
    started = time.perf_counter()
    try:
        dataset_contract = _prepare_dataset_contract(dataset, profile, staging)
        command = [
            engine, "run", "--rm", "--network", "none", "--pull=never",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{staging.resolve()}:/work",
            "-v", f"{dataset.resolve(strict=True)}:/dataset:ro",
            image_id, "bash", "-lc",
            "/opt/surflo/run-rgbd.sh /dataset /work/config/associations.txt "
            "/work/config/groundtruth-prefix.txt /work/output",
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        (staging / "adapter.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise ValueError(f"ORB-SLAM adapter failed ({completed.returncode}): {completed.stderr.strip()}")
        _record_failure_sweep_metrics(staging)
        metrics = _geometry_metrics(staging)
        acceptance = _adapter_record()["acceptance"][profile]
        failures = _acceptance_failures(metrics, acceptance)
        if failures:
            raise ValueError(f"ORB-SLAM result is below acceptance for: {', '.join(failures)}")
        estimate = parse_tum_trajectory(staging / "output/CameraTrajectory.txt")
        truth = parse_tum_trajectory(staging / "config/groundtruth-prefix.txt")
        _, transform = evaluate_trajectory(estimate, truth)
        _write_trajectory_svg(staging / "trajectory.svg", estimate, truth, transform)
        sweep = _validate_failure_sweep(staging)
        (staging / "report.md").write_text(
            "# ORB-SLAM3 RGB-D reference\n\n"
            f"Tracked {metrics['tracked_frames']} of {metrics['input_frames']} frames "
            f"({100.0 * metrics['tracking_coverage']:.1f}%); ATE RMSE "
            f"{metrics['ate_rmse_m']:.4f} m. The persistent sparse map contains "
            f"{metrics['map_points']} landmarks and reaches a 10 cm F-score of "
            f"{metrics['map_fscore_10cm']:.3f}.\n\n"
            "The controlled sweep separately records transient occlusion/relocalization and a moving foreground; "
            f"it is evidence about static-world failure boundaries, not a dense-surface score: `{json.dumps(sweep, sort_keys=True)}`.\n",
            encoding="utf-8",
        )
        config = {
            "adapter": ADAPTER,
            "profile": profile,
            "run_id": run_id,
            "module_ids": ["07"],
            "image": IMAGE,
            "image_id": image_id,
            "dataset_contract": dataset_contract,
            "asset_archive_sha256": asset_manifest["archive_sha256"],
            "asset_tree_sha256": asset_manifest["tree_sha256"],
            "trajectory_association_max_delta_seconds": 0.02,
            "rpe_delta_frames": 1,
            "ground_truth_association_max_delta_seconds": GROUND_TRUTH_MAX_DELTA_SECONDS,
            "map_fscore_threshold_m": 0.1,
            "acceptance": acceptance,
        }
        resources = {
            "runtime_seconds": time.perf_counter() - started,
            "peak_cpu_memory_bytes": _resource_memory(staging / "output/resource-summary.txt"),
            "host": platform.platform(),
        }
        write_json(staging / "output/resources.json", resources)
        result = {
            "schema_version": 1,
            "adapter": ADAPTER,
            "module_ids": ["07"],
            "profile": profile,
            "status": "complete",
            "network_mode": "offline",
            "metrics": metrics,
            "acceptance": acceptance,
            "tool": {
                "name": "ORB-SLAM3",
                "version": f"ORB-SLAM3@{PINNED_ORB_SLAM3_COMMIT[:12]}",
                "package_version": "source-build",
                "source_commit": PINNED_ORB_SLAM3_COMMIT,
                "container_image": IMAGE,
                "container_image_id": image_id,
            },
            "resources": resources,
            "provenance": {
                "config": config,
                "config_sha256": hashlib.sha256(canonical_json(config)).hexdigest(),
                "asset_archive_sha256": asset_manifest["archive_sha256"],
                "asset_tree_sha256": asset_manifest["tree_sha256"],
                "implementation_sha256": {name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION},
                "artifacts_sha256": _hash_tree(staging),
            },
        }
        ensure_finite(result, "reference-result")
        write_json(staging / "result.json", result)
        validate_slam_reference_result(staging)
        final_parent.mkdir()
        os.replace(staging, final)
        return final
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
