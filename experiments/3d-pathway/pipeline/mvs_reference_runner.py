"""Offline, hash-recorded COLMAP dense-MVS reference execution."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import stat
import struct
import subprocess
import tempfile
import time
import uuid
from typing import Any

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
from fetch import extract_locked_asset
from reference_runner import (
    _format_shell_number,
    _hash_tree,
    _inspect_image,
    _parse_colmap_text,
    _parse_key_value_manifest,
    _require_regular_file,
    _secure_directory,
    _validate_sqlite_database,
)
from reference_scene import generate_colmap_mvs_scene


ADAPTER = "colmap-mvs"
IMAGE = "surflo-pathway-classical-mvs:1"
PINNED_COLMAP_VERSION = "4.2.0"
PINNED_COLMAP_COMMIT = "be5e29168d4aff238409d60424812df66aac919f"
PINNED_INSULA_MANIFEST = {
    "schema_version": "1",
    "kind": "classical-mvs",
    "ubuntu": "24.04",
    "cuda": "12.9.1",
    "cuda_architectures": "100",
    "colmap": PINNED_COLMAP_VERSION,
    "colmap_commit": PINNED_COLMAP_COMMIT,
    "network_policy": "build-and-fetch-only",
}
EVALUATION_MAX_POINTS = 8192
EVALUATION_VOXEL_M = 0.01
EVALUATION_SAMPLE_SEED = 260925
FSCORE_THRESHOLD_M = 0.10
METRIC_RELATIVE_TOLERANCE = 1e-9
METRIC_ABSOLUTE_TOLERANCE = 1e-12
MIDDLEBURY_ASSET_ID = "middlebury-mvs"
MIDDLEBURY_ARCHIVE_SHA256 = "b4684adcfda53b47b0964355b4142c53cb28940bbb448e0e974f92748e428de9"
MIDDLEBURY_TREE_SHA256 = "44eff8468fb2f807397f02449ae20b67262ec23c30b71477ee09d2532134acc5"
MIDDLEBURY_VIEW_COUNT = 16
MIDDLEBURY_DEPTH_NEAR_SCALE = 0.5
MIDDLEBURY_DEPTH_FAR_SCALE = 1.5
REFERENCE_IMPLEMENTATION = (
    "pipeline/cli.py",
    "pipeline/contracts.py",
    "pipeline/reference_runner.py",
    "pipeline/mvs_reference_runner.py",
    "pipeline/reference_scene.py",
    "insulas/build.sh",
    "insulas/classical-mvs/Dockerfile",
    "insulas/locks.json",
    "reference-result.schema.json",
    "shared-scene.json",
    "reference-adapters.json",
    "assets.lock.json",
)


def _middlebury_record() -> dict[str, Any]:
    matches = [
        item
        for item in load_json(ROOT / "assets.lock.json")["assets"]
        if item.get("id") == MIDDLEBURY_ASSET_ID
    ]
    if len(matches) != 1:
        raise ValueError("Middlebury MVS asset registry mismatch")
    record = matches[0]
    if (
        record.get("mode") != "download"
        or record.get("sha256") != MIDDLEBURY_ARCHIVE_SHA256
        or record.get("byte_size") != 4004383
        or record.get("digest_status") != "verified_2026-09-27"
        or record.get("archive_format") != "zip"
        or record.get("extraction")
        != {"mode": "zip", "roots": ["templeSparseRing"]}
        or record.get("tree_sha256") != MIDDLEBURY_TREE_SHA256
        or record.get("tree_file_count") != 19
        or record.get("tree_byte_size") != 4009956
        or record.get("consumers") != ["colmap-mvs-reference"]
    ):
        raise ValueError("Middlebury MVS asset lock mismatch")
    return record


def _locked_middlebury(cache_root: Path) -> tuple[Path, dict[str, Any]]:
    record = _middlebury_record()
    assets = cache_root / "assets"
    archive = assets / f"{MIDDLEBURY_ASSET_ID}.archive"
    try:
        mode = archive.lstat().st_mode
    except FileNotFoundError as error:
        raise FileNotFoundError(
            f"missing Middlebury archive: {archive}; "
            f"run `run.sh fetch --asset {MIDDLEBURY_ASSET_ID}`"
        ) from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ValueError("Middlebury archive must be a regular non-symlink file")
    if archive.stat().st_size != record["byte_size"] or sha256_file(archive) != record["sha256"]:
        raise ValueError("Middlebury archive hash or byte-size mismatch")
    extracted = extract_locked_asset(record, archive, assets)
    extraction = load_json(assets / f"{MIDDLEBURY_ASSET_ID}.extraction.json")
    if (
        extraction.get("archive_sha256") != record["sha256"]
        or extraction.get("tree_sha256") != record["tree_sha256"]
        or extraction.get("file_count") != record["tree_file_count"]
        or sum(item.get("size", -1) for item in extraction.get("files", []))
        != record["tree_byte_size"]
    ):
        raise ValueError("Middlebury extraction tree does not match its lock")
    source = extracted / "templeSparseRing"
    _require_regular_file(source, "templeSR_par.txt")
    return source, extraction


def _rotation_to_colmap_quaternion(rotation: np.ndarray) -> np.ndarray:
    if rotation.shape != (3, 3) or not np.isfinite(rotation).all():
        raise ValueError("Middlebury rotation must be finite 3x3")
    if not np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-7, rtol=1e-7):
        raise ValueError("Middlebury rotation is not orthonormal")
    if not math.isclose(float(np.linalg.det(rotation)), 1.0, abs_tol=1e-7):
        raise ValueError("Middlebury rotation is not proper")
    trace = float(np.trace(rotation))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        quaternion = np.array(
            [
                0.25 * scale,
                (rotation[2, 1] - rotation[1, 2]) / scale,
                (rotation[0, 2] - rotation[2, 0]) / scale,
                (rotation[1, 0] - rotation[0, 1]) / scale,
            ],
            dtype=np.float64,
        )
    else:
        diagonal = int(np.argmax(np.diag(rotation)))
        if diagonal == 0:
            scale = math.sqrt(1.0 + rotation[0, 0] - rotation[1, 1] - rotation[2, 2]) * 2.0
            quaternion = np.array(
                [
                    (rotation[2, 1] - rotation[1, 2]) / scale,
                    0.25 * scale,
                    (rotation[0, 1] + rotation[1, 0]) / scale,
                    (rotation[0, 2] + rotation[2, 0]) / scale,
                ]
            )
        elif diagonal == 1:
            scale = math.sqrt(1.0 + rotation[1, 1] - rotation[0, 0] - rotation[2, 2]) * 2.0
            quaternion = np.array(
                [
                    (rotation[0, 2] - rotation[2, 0]) / scale,
                    (rotation[0, 1] + rotation[1, 0]) / scale,
                    0.25 * scale,
                    (rotation[1, 2] + rotation[2, 1]) / scale,
                ]
            )
        else:
            scale = math.sqrt(1.0 + rotation[2, 2] - rotation[0, 0] - rotation[1, 1]) * 2.0
            quaternion = np.array(
                [
                    (rotation[1, 0] - rotation[0, 1]) / scale,
                    (rotation[0, 2] + rotation[2, 0]) / scale,
                    (rotation[1, 2] + rotation[2, 1]) / scale,
                    0.25 * scale,
                ]
            )
    quaternion /= np.linalg.norm(quaternion)
    if quaternion[0] < 0.0:
        quaternion *= -1.0
    return quaternion


def _middlebury_patch_match_rows(frame_names: list[str]) -> list[str]:
    source_offsets = (-1, 1, -2, 2, -3, 3, -4, 4)
    rows: list[str] = []
    for index, name in enumerate(frame_names):
        source_names = [
            frame_names[(index + offset) % len(frame_names)]
            for offset in source_offsets
        ]
        rows.extend([name, ",".join(source_names)])
    return rows


def _prepare_middlebury_input(
    source: Path, destination: Path, extraction: dict[str, Any]
) -> dict[str, Any]:
    lines = _require_regular_file(source, "templeSR_par.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    if not lines or lines[0].strip() != str(MIDDLEBURY_VIEW_COUNT):
        raise ValueError("Middlebury calibration view count mismatch")
    records = [line.split() for line in lines[1:] if line.strip()]
    if len(records) != MIDDLEBURY_VIEW_COUNT or any(len(record) != 22 for record in records):
        raise ValueError("Middlebury calibration row mismatch")
    images = destination / "images"
    model = destination / "model"
    images.mkdir(parents=True)
    model.mkdir()
    camera_rows = ["# Camera list"]
    image_rows = ["# Image list, two lines per image"]
    frame_names: list[str] = []
    origin_depths: list[float] = []
    input_hashes: dict[str, str] = {}
    for image_id, record in enumerate(records, 1):
        name = record[0]
        if name != f"templeSR{image_id:04d}.png":
            raise ValueError("Middlebury image ordering mismatch")
        try:
            values = np.asarray([float(value) for value in record[1:]], dtype=np.float64)
        except ValueError as error:
            raise ValueError("Middlebury calibration is not numeric") from error
        if not np.isfinite(values).all():
            raise ValueError("Middlebury calibration must be finite")
        intrinsics = values[:9].reshape(3, 3)
        rotation = values[9:18].reshape(3, 3)
        translation = values[18:21]
        if (
            not np.allclose(intrinsics[[0, 1], [1, 0]], 0.0, atol=1e-12)
            or not np.allclose(intrinsics[2], [0.0, 0.0, 1.0], atol=1e-12)
            or intrinsics[0, 0] <= 0.0
            or intrinsics[1, 1] <= 0.0
        ):
            raise ValueError("Middlebury pinhole intrinsics mismatch")
        quaternion = _rotation_to_colmap_quaternion(rotation)
        if translation[2] <= 0.0:
            raise ValueError("Middlebury world origin must be in front of every camera")
        origin_depths.append(float(translation[2]))
        source_image = _require_regular_file(source, name)
        target_image = images / name
        shutil.copy2(source_image, target_image)
        input_hashes[f"images/{name}"] = sha256_file(target_image)
        camera_rows.append(
            f"{image_id} PINHOLE 640 480 "
            f"{_format_shell_number(intrinsics[0, 0], 'fx')} "
            f"{_format_shell_number(intrinsics[1, 1], 'fy')} "
            f"{_format_shell_number(intrinsics[0, 2], 'cx')} "
            f"{_format_shell_number(intrinsics[1, 2], 'cy')}"
        )
        pose = [*quaternion.tolist(), *translation.tolist()]
        image_rows.extend(
            [
                f"{image_id} {' '.join(_format_shell_number(value, 'pose') for value in pose)} {image_id} {name}",
                "",
            ]
        )
        frame_names.append(name)
    (model / "cameras.txt").write_text("\n".join(camera_rows) + "\n", encoding="utf-8")
    (model / "images.txt").write_text("\n".join(image_rows) + "\n", encoding="utf-8")
    (model / "points3D.txt").write_text("# 3D point list\n", encoding="utf-8")
    patch_match_rows = _middlebury_patch_match_rows(frame_names)
    patch_match_config = destination / "patch-match.cfg"
    patch_match_config.write_text(
        "\n".join(patch_match_rows) + "\n", encoding="utf-8"
    )
    calibration = destination / "templeSR_par.txt"
    shutil.copy2(source / "templeSR_par.txt", calibration)
    input_hashes["templeSR_par.txt"] = sha256_file(calibration)
    for name in ("model/cameras.txt", "model/images.txt", "model/points3D.txt"):
        input_hashes[name] = sha256_file(destination / name)
    input_hashes["patch-match.cfg"] = sha256_file(patch_match_config)
    manifest = {
        "schema_version": 1,
        "asset_id": MIDDLEBURY_ASSET_ID,
        "archive_sha256": MIDDLEBURY_ARCHIVE_SHA256,
        "extraction_tree_sha256": MIDDLEBURY_TREE_SHA256,
        "dataset": "templeSparseRing",
        "calibrated_views": MIDDLEBURY_VIEW_COUNT,
        "image_size": [640, 480],
        "frame_names": frame_names,
        "source_view_strategy": "cyclic_neighbors_offsets_-1_1_-2_2_-3_3_-4_4",
        "source_views_per_reference": 8,
        "depth_range_derivation": (
            "0.5 * minimum and 1.5 * maximum camera-space depth of world origin"
        ),
        "origin_depth_range_dataset_units": [min(origin_depths), max(origin_depths)],
        "depth_range_dataset_units": [
            MIDDLEBURY_DEPTH_NEAR_SCALE * min(origin_depths),
            MIDDLEBURY_DEPTH_FAR_SCALE * max(origin_depths),
        ],
        "patch_match_output": "photometric",
        "fusion_min_num_pixels": 1,
        "poisson_depth": 8,
        "fusion_scope": (
            "structural execution support; cross-view geometry is scored on the controlled scene"
        ),
        "input_sha256": input_hashes,
    }
    write_json(destination / "manifest.json", manifest)
    return manifest


def _container_script(
    manifest: dict[str, Any],
    profile: str,
    middlebury_manifest: dict[str, Any] | None = None,
) -> str:
    intrinsics = manifest["intrinsics"]
    parameters = ",".join(
        _format_shell_number(intrinsics[key], key) for key in ("fx", "fy", "cx", "cy")
    )
    minimum_matches = 8 if profile == "smoke" else 12
    max_image_size = max(int(intrinsics["width"]), int(intrinsics["height"]))
    script = f"""set -euo pipefail
export QT_QPA_PLATFORM=offscreen
mkdir -p /work/output/sparse /work/output/text /work/output/dense
colmap -h >/tmp/colmap-help.txt 2>&1
awk 'NF {{print; exit}}' /tmp/colmap-help.txt > /work/output/colmap-version.txt
cat /etc/surflo-pathway-colmap-commit > /work/output/source-commit.txt
cp /etc/surflo-pathway-insula /work/output/insula-manifest.txt
colmap feature_extractor \
  --default_random_seed 260925 \
  --database_path /work/output/database.db \
  --image_path /work/input/images \
  --ImageReader.camera_model PINHOLE \
  --ImageReader.single_camera 1 \
  --ImageReader.camera_params {parameters} \
  --FeatureExtraction.use_gpu 1 \
  --FeatureExtraction.gpu_index 0
colmap exhaustive_matcher \
  --default_random_seed 260925 \
  --database_path /work/output/database.db \
  --FeatureMatching.use_gpu 1 \
  --FeatureMatching.gpu_index 0
colmap mapper \
  --database_path /work/output/database.db \
  --image_path /work/input/images \
  --output_path /work/output/sparse \
  --Mapper.min_num_matches {minimum_matches} \
  --Mapper.random_seed 260925 \
  --Mapper.init_min_num_inliers 20 \
  --Mapper.ba_refine_focal_length 0 \
  --Mapper.ba_refine_principal_point 0 \
  --Mapper.ba_refine_extra_params 0
test -d /work/output/sparse/0
colmap model_converter \
  --input_path /work/output/sparse/0 \
  --output_path /work/output/text \
  --output_type TXT
colmap model_converter \
  --input_path /work/output/sparse/0 \
  --output_path /work/output/sparse.ply \
  --output_type PLY
cp /work/output/text/cameras.txt /work/output/text/images.txt /work/output/text/points3D.txt /work/output/sparse/0/
colmap image_undistorter \
  --image_path /work/input/images \
  --input_path /work/output/sparse/0 \
  --output_path /work/output/dense \
  --output_type COLMAP \
  --max_image_size {max_image_size}
colmap patch_match_stereo \
  --default_random_seed 260925 \
  --workspace_path /work/output/dense \
  --workspace_format COLMAP \
  --PatchMatchStereo.geom_consistency 1 \
  --PatchMatchStereo.max_image_size {max_image_size} \
  --PatchMatchStereo.gpu_index 0
colmap stereo_fusion \
  --workspace_path /work/output/dense \
  --workspace_format COLMAP \
  --input_type geometric \
  --output_path /work/output/dense/fused.ply \
  --StereoFusion.min_num_pixels 3 \
  --StereoFusion.max_reproj_error 2 \
  --StereoFusion.max_depth_error 0.02 \
  --StereoFusion.max_normal_error 10
awk '$1 == "element" && $2 == "vertex" {{found=1; if (($3 + 0) > 0) nonempty=1}} END {{exit !(found && nonempty)}}' /work/output/dense/fused.ply
colmap poisson_mesher \
  --input_path /work/output/dense/fused.ply \
  --output_path /work/output/dense/meshed-poisson.ply \
  --PoissonMeshing.trim 5
"""
    if profile == "full":
        if middlebury_manifest is None:
            raise ValueError("full MVS execution requires the Middlebury input manifest")
        depth_range = middlebury_manifest.get("depth_range_dataset_units")
        if (
            not isinstance(depth_range, list)
            or len(depth_range) != 2
            or not all(isinstance(value, (int, float)) for value in depth_range)
            or not 0.0 < float(depth_range[0]) < float(depth_range[1])
        ):
            raise ValueError("Middlebury depth range is invalid")
        depth_min = _format_shell_number(float(depth_range[0]), "depth_min")
        depth_max = _format_shell_number(float(depth_range[1]), "depth_max")
        script += f"""
mkdir -p /work/output/middlebury/dense
colmap image_undistorter \
  --image_path /work/input/middlebury/images \
  --input_path /work/input/middlebury/model \
  --output_path /work/output/middlebury/dense \
  --output_type COLMAP \
  --max_image_size 640
cp /work/input/middlebury/patch-match.cfg /work/output/middlebury/dense/stereo/patch-match.cfg
colmap patch_match_stereo \
  --default_random_seed 260925 \
  --workspace_path /work/output/middlebury/dense \
  --workspace_format COLMAP \
  --PatchMatchStereo.geom_consistency 0 \
  --PatchMatchStereo.max_image_size 640 \
  --PatchMatchStereo.depth_min {depth_min} \
  --PatchMatchStereo.depth_max {depth_max} \
  --PatchMatchStereo.gpu_index 0
colmap stereo_fusion \
  --workspace_path /work/output/middlebury/dense \
  --workspace_format COLMAP \
  --input_type photometric \
  --output_path /work/output/middlebury/dense/fused.ply \
  --StereoFusion.min_num_pixels 1 \
  --StereoFusion.max_reproj_error 2 \
  --StereoFusion.max_depth_error 0.02 \
  --StereoFusion.max_normal_error 10
awk '$1 == "element" && $2 == "vertex" {{found=1; if (($3 + 0) > 0) nonempty=1}} END {{exit !(found && nonempty)}}' /work/output/middlebury/dense/fused.ply
colmap poisson_mesher \
  --input_path /work/output/middlebury/dense/fused.ply \
  --output_path /work/output/middlebury/dense/meshed-poisson.ply \
  --PoissonMeshing.depth 8 \
  --PoissonMeshing.trim 5
"""
    return script


PLY_SCALAR_TYPES = {
    "char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1",
    "short": "<i2", "int16": "<i2", "ushort": "<u2", "uint16": "<u2",
    "int": "<i4", "int32": "<i4", "uint": "<u4", "uint32": "<u4",
    "float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8",
}
PLY_INTEGER_TYPES = {
    "char", "int8", "uchar", "uint8", "short", "int16", "ushort", "uint16",
    "int", "int32", "uint", "uint32",
}


def _ply_header(
    path: Path,
) -> tuple[str, int, int, list[tuple[str, str]], list[tuple[str, str, str]], int]:
    vertex_count: int | None = None
    face_count = 0
    vertex_properties: list[tuple[str, str]] = []
    face_properties: list[tuple[str, str, str]] = []
    current_element: str | None = None
    with path.open("rb") as stream:
        first = stream.readline()
        if first != b"ply\n":
            raise ValueError(f"malformed PLY header: {path}")
        format_name: str | None = None
        while stream.tell() <= 65536:
            raw = stream.readline()
            if not raw:
                break
            try:
                line = raw.decode("ascii").strip()
            except UnicodeDecodeError as error:
                raise ValueError(f"malformed PLY header: {path}") from error
            fields = line.split()
            if fields[:1] == ["format"] and len(fields) >= 2:
                format_name = fields[1]
            elif fields[:2] == ["element", "vertex"] and len(fields) == 3:
                vertex_count = int(fields[2])
                current_element = "vertex"
            elif fields[:2] == ["element", "face"] and len(fields) == 3:
                face_count = int(fields[2])
                current_element = "face"
            elif fields[:1] == ["element"]:
                current_element = fields[1] if len(fields) > 1 else None
            elif fields[:1] == ["property"] and current_element == "vertex":
                if len(fields) != 3 or fields[1] == "list":
                    raise ValueError(f"unsupported PLY vertex property: {line}")
                vertex_properties.append((fields[2], fields[1]))
            elif fields[:2] == ["property", "list"] and current_element == "face":
                if len(fields) != 5:
                    raise ValueError(f"unsupported PLY face property: {line}")
                face_properties.append((fields[4], fields[2], fields[3]))
            elif line == "end_header":
                if format_name is None or vertex_count is None or vertex_count < 0 or face_count < 0:
                    raise ValueError(f"malformed PLY element counts: {path}")
                return (
                    format_name,
                    vertex_count,
                    face_count,
                    vertex_properties,
                    face_properties,
                    stream.tell(),
                )
    raise ValueError(f"unterminated PLY header: {path}")


def _validate_ply_faces(
    path: Path,
    format_name: str,
    vertices: np.ndarray,
    face_count: int,
    vertex_dtype: np.dtype[Any] | None,
    face_properties: list[tuple[str, str, str]],
    offset: int,
) -> int:
    if face_count == 0:
        return 0
    if len(face_properties) != 1 or face_properties[0][0] != "vertex_indices":
        raise ValueError(f"unsupported PLY face layout: {path}")
    _, count_kind, index_kind = face_properties[0]
    if count_kind not in PLY_INTEGER_TYPES or index_kind not in PLY_INTEGER_TYPES:
        raise ValueError(f"unsupported PLY face scalar type: {path}")
    vertex_count = len(vertices)
    seen_faces: set[tuple[int, ...]] = set()
    valid_face_count = 0

    def validate_indices(indices: np.ndarray, encoding: str) -> bool:
        if (
            len(indices) < 3
            or int(indices.min()) < 0
            or int(indices.max()) >= vertex_count
            or len(np.unique(indices)) != len(indices)
        ):
            raise ValueError(f"invalid {encoding} PLY face indices: {path}")
        canonical = tuple(sorted(int(index) for index in indices))
        if canonical in seen_faces:
            return False
        seen_faces.add(canonical)
        polygon = vertices[indices]
        origin = polygon[0]
        if not any(
            float(np.dot(cross, cross)) > 1e-24
            for cross in (
                np.cross(polygon[index] - origin, polygon[index + 1] - origin)
                for index in range(1, len(polygon) - 1)
            )
        ):
            return False
        return True

    with path.open("rb") as stream:
        stream.seek(offset)
        if format_name == "ascii":
            for _ in range(vertex_count):
                if not stream.readline():
                    raise ValueError(f"truncated ASCII PLY vertices: {path}")
            for face_index in range(face_count):
                raw = stream.readline()
                if not raw:
                    raise ValueError(f"truncated ASCII PLY faces: {path}")
                try:
                    values = [int(value) for value in raw.split()]
                except ValueError as error:
                    raise ValueError(f"malformed ASCII PLY face: {path}") from error
                if not values or values[0] < 3 or len(values) != values[0] + 1:
                    raise ValueError(f"malformed ASCII PLY face: {path}")
                valid_face_count += validate_indices(
                    np.asarray(values[1:], dtype=np.int64), "ASCII"
                )
            if stream.read().strip():
                raise ValueError(f"trailing ASCII PLY payload: {path}")
            return valid_face_count
        if format_name != "binary_little_endian" or vertex_dtype is None:
            raise ValueError(f"unsupported PLY face format: {path}")
        stream.seek(offset + vertex_dtype.itemsize * vertex_count)
        count_dtype = np.dtype(PLY_SCALAR_TYPES[count_kind])
        index_dtype = np.dtype(PLY_SCALAR_TYPES[index_kind])
        for _ in range(face_count):
            raw_count = stream.read(count_dtype.itemsize)
            if len(raw_count) != count_dtype.itemsize:
                raise ValueError(f"truncated binary PLY faces: {path}")
            count = int(np.frombuffer(raw_count, dtype=count_dtype, count=1)[0])
            if count < 3:
                raise ValueError(f"invalid binary PLY face count: {path}")
            raw_indices = stream.read(index_dtype.itemsize * count)
            if len(raw_indices) != index_dtype.itemsize * count:
                raise ValueError(f"truncated binary PLY faces: {path}")
            indices = np.frombuffer(raw_indices, dtype=index_dtype, count=count).astype(np.int64)
            valid_face_count += validate_indices(indices, "binary")
        if stream.read(1):
            raise ValueError(f"trailing binary PLY payload: {path}")
    return valid_face_count


def _read_ply_xyz(
    path: Path, *, require_normals: bool = False, validate_faces: bool = False
) -> tuple[np.ndarray, int]:
    format_name, vertex_count, face_count, properties, face_properties, offset = _ply_header(path)
    names = [name for name, _ in properties]
    if not {"x", "y", "z"} <= set(names):
        raise ValueError(f"PLY lacks XYZ vertices: {path}")
    requested = ["x", "y", "z"]
    if require_normals:
        if not {"nx", "ny", "nz"} <= set(names):
            raise ValueError(f"PLY lacks oriented normals: {path}")
        requested.extend(("nx", "ny", "nz"))
    indices = tuple(names.index(axis) for axis in requested)
    vertex_dtype: np.dtype[Any] | None = None
    if format_name == "ascii":
        with path.open("rb") as stream:
            stream.seek(offset)
            try:
                points = np.loadtxt(stream, dtype=np.float64, usecols=indices, max_rows=vertex_count)
            except ValueError as error:
                raise ValueError(f"malformed ASCII PLY vertices: {path}") from error
    elif format_name == "binary_little_endian":
        try:
            vertex_dtype = np.dtype(
                [(f"field_{index}", PLY_SCALAR_TYPES[kind]) for index, (_, kind) in enumerate(properties)]
            )
        except KeyError as error:
            raise ValueError(f"unsupported binary PLY scalar type: {error.args[0]}") from error
        with path.open("rb") as stream:
            stream.seek(offset)
            records = np.fromfile(stream, dtype=vertex_dtype, count=vertex_count)
        if len(records) != vertex_count:
            raise ValueError(f"truncated binary PLY vertices: {path}")
        points = np.column_stack([records[f"field_{index}"].astype(np.float64) for index in indices])
    else:
        raise ValueError(f"unsupported PLY format {format_name}: {path}")
    points = np.asarray(points, dtype=np.float64).reshape((vertex_count, len(requested)))
    if len(points) != vertex_count or not np.isfinite(points).all():
        raise ValueError(f"invalid PLY vertices: {path}")
    if require_normals and np.any(np.linalg.norm(points[:, 3:6], axis=1) <= 0.0):
        raise ValueError(f"invalid PLY normals: {path}")
    validated_face_count = face_count
    if validate_faces:
        validated_face_count = _validate_ply_faces(
            path,
            format_name,
            points[:, :3],
            face_count,
            vertex_dtype,
            face_properties,
            offset,
        )
    return points[:, :3], validated_face_count


def _quaternion_rotation(values: list[float]) -> np.ndarray:
    quaternion = np.asarray(values, dtype=np.float64)
    norm = np.linalg.norm(quaternion)
    if not math.isfinite(float(norm)) or norm == 0.0:
        raise ValueError("invalid COLMAP image quaternion")
    w, x, y, z = quaternion / norm
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def _colmap_poses(path: Path) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    if not lines or len(lines) % 2:
        raise ValueError("malformed COLMAP image record pairing")
    poses: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for index in range(0, len(lines), 2):
        fields = lines[index].split()
        if len(fields) < 10:
            raise ValueError("malformed COLMAP image record")
        rotation = _quaternion_rotation([float(value) for value in fields[1:5]])
        translation = np.asarray([float(value) for value in fields[5:8]], dtype=np.float64)
        center = -rotation.T @ translation
        name = fields[9]
        if name in poses or not np.isfinite(center).all():
            raise ValueError("invalid COLMAP image pose")
        poses[name] = (rotation, center)
    return poses


def _read_exact(stream: Any, size: int, label: str) -> bytes:
    payload = stream.read(size)
    if len(payload) != size:
        raise ValueError(f"truncated COLMAP binary {label}")
    return payload


def _validate_colmap_binary_model(
    model: Path, expected_names: set[str], expected_points: int
) -> None:
    with (model / "cameras.bin").open("rb") as stream:
        camera_count = struct.unpack("<Q", _read_exact(stream, 8, "camera count"))[0]
        if camera_count == 0:
            raise ValueError("empty COLMAP binary camera model")
        camera_ids: set[int] = set()
        parameter_counts = {0: 3, 1: 4, 2: 4, 3: 5, 4: 8, 5: 8, 6: 12, 7: 5, 8: 4, 9: 5, 10: 12}
        for _ in range(camera_count):
            camera_id, model_id, width, height = struct.unpack(
                "<iiQQ", _read_exact(stream, 24, "camera record")
            )
            if camera_id in camera_ids or model_id not in parameter_counts or width <= 0 or height <= 0:
                raise ValueError("invalid COLMAP binary camera record")
            camera_ids.add(camera_id)
            parameters = struct.unpack(
                f"<{parameter_counts[model_id]}d",
                _read_exact(stream, 8 * parameter_counts[model_id], "camera parameters"),
            )
            if not all(math.isfinite(value) for value in parameters):
                raise ValueError("non-finite COLMAP binary camera parameters")
        if stream.read(1):
            raise ValueError("trailing COLMAP binary camera payload")

    with (model / "images.bin").open("rb") as stream:
        image_count = struct.unpack("<Q", _read_exact(stream, 8, "image count"))[0]
        names: set[str] = set()
        image_ids: set[int] = set()
        for _ in range(image_count):
            values = struct.unpack("<i7di", _read_exact(stream, 64, "image record"))
            image_id, *pose, camera_id = values
            if image_id in image_ids or camera_id not in camera_ids or not all(math.isfinite(value) for value in pose):
                raise ValueError("invalid COLMAP binary image record")
            image_ids.add(image_id)
            name_bytes = bytearray()
            while True:
                character = _read_exact(stream, 1, "image name")
                if character == b"\0":
                    break
                name_bytes.extend(character)
                if len(name_bytes) > 4096:
                    raise ValueError("oversized COLMAP binary image name")
            try:
                name = name_bytes.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError("invalid COLMAP binary image name") from error
            if not name or name in names:
                raise ValueError("duplicate COLMAP binary image name")
            names.add(name)
            observation_count = struct.unpack("<Q", _read_exact(stream, 8, "observation count"))[0]
            observations = _read_exact(stream, observation_count * 24, "image observations")
            if observation_count:
                records = np.frombuffer(
                    observations,
                    dtype=np.dtype([("x", "<f8"), ("y", "<f8"), ("point", "<i8")]),
                )
                if not np.isfinite(records["x"]).all() or not np.isfinite(records["y"]).all():
                    raise ValueError("non-finite COLMAP binary observations")
        if names != expected_names or stream.read(1):
            raise ValueError("COLMAP binary image inventory mismatch")

    with (model / "points3D.bin").open("rb") as stream:
        point_count = struct.unpack("<Q", _read_exact(stream, 8, "point count"))[0]
        if point_count != expected_points:
            raise ValueError("COLMAP binary point count mismatch")
        point_ids: set[int] = set()
        for _ in range(point_count):
            point_id, x, y, z, red, green, blue, error = struct.unpack(
                "<Q3d3Bd", _read_exact(stream, struct.calcsize("<Q3d3Bd"), "point record")
            )
            if point_id in point_ids or not all(math.isfinite(value) for value in (x, y, z, error)) or error < 0:
                raise ValueError("invalid COLMAP binary point record")
            point_ids.add(point_id)
            track_count = struct.unpack("<Q", _read_exact(stream, 8, "track count"))[0]
            track = _read_exact(stream, track_count * 8, "point track")
            if track_count:
                records = np.frombuffer(track, dtype=np.dtype([("image", "<i4"), ("point2D", "<i4")]))
                if not set(int(value) for value in records["image"]) <= image_ids:
                    raise ValueError("COLMAP binary track references unknown image")
        if stream.read(1):
            raise ValueError("trailing COLMAP binary point payload")


def _validate_mvs_database(path: Path, expected_names: set[str]) -> None:
    expected_columns = {
        "cameras": {"camera_id", "model", "width", "height", "params"},
        "images": {"image_id", "name", "camera_id"},
        "keypoints": {"image_id", "rows", "cols", "data"},
        "descriptors": {"image_id", "rows", "cols", "data"},
        "matches": {"pair_id", "rows", "cols", "data"},
        "two_view_geometries": {"pair_id", "rows", "cols", "data", "config"},
    }
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
        try:
            for table, required in expected_columns.items():
                columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
                if not required <= columns:
                    raise ValueError(f"COLMAP SQLite schema mismatch: {table}")
            cameras = list(connection.execute("SELECT camera_id, width, height, params FROM cameras"))
            if not cameras or any(
                int(row[1]) <= 0
                or int(row[2]) <= 0
                or row[3] is None
                or len(row[3]) == 0
                or len(row[3]) % 8
                for row in cameras
            ):
                raise ValueError("COLMAP SQLite camera content mismatch")
            camera_ids = {int(row[0]) for row in cameras}
            images = list(connection.execute("SELECT image_id, name, camera_id FROM images"))
            names = {str(row[1]) for row in images}
            if (
                names != expected_names
                or len(images) != len(names)
                or not {int(row[2]) for row in images} <= camera_ids
            ):
                raise ValueError("COLMAP SQLite image inventory mismatch")
            image_ids = {int(row[0]) for row in images}
            for table in ("keypoints", "descriptors"):
                rows = list(connection.execute(f"SELECT image_id, rows, cols, data FROM {table}"))
                item_size = 4 if table == "keypoints" else 1
                if {int(row[0]) for row in rows} != image_ids or any(
                    int(row[1]) <= 0
                    or int(row[2]) <= 0
                    or row[3] is None
                    or len(row[3]) != int(row[1]) * int(row[2]) * item_size
                    for row in rows
                ):
                    raise ValueError(f"COLMAP SQLite {table} content mismatch")
            for table in ("matches", "two_view_geometries"):
                rows = list(connection.execute(f"SELECT rows, cols, data FROM {table}"))
                if not rows or any(
                    int(row[0]) <= 0
                    or int(row[1]) <= 0
                    or row[2] is None
                    or len(row[2]) != int(row[0]) * int(row[1]) * 4
                    for row in rows
                ):
                    raise ValueError(f"COLMAP SQLite {table} content mismatch")
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise ValueError("invalid COLMAP MVS SQLite database") from error


def _align_similarity(
    poses: dict[str, tuple[np.ndarray, np.ndarray]], manifest: dict[str, Any]
) -> tuple[float, np.ndarray, np.ndarray, float]:
    rotations: list[np.ndarray] = []
    estimated_centers: list[np.ndarray] = []
    truth_centers: list[np.ndarray] = []
    for frame in manifest["frames"]:
        if frame["name"] not in poses:
            continue
        estimated_rotation, estimated_center = poses[frame["name"]]
        truth_rotation = np.asarray(frame["R_world_to_camera"], dtype=np.float64)
        rotations.append(truth_rotation.T @ estimated_rotation)
        estimated_centers.append(estimated_center)
        truth_centers.append(np.asarray(frame["camera_center_m"], dtype=np.float64))
    if len(estimated_centers) < 2:
        raise ValueError("camera alignment requires at least two registered ground-truth views")
    mean_rotation = np.mean(rotations, axis=0)
    left, _, right = np.linalg.svd(mean_rotation)
    rotation = left @ right
    if np.linalg.det(rotation) < 0:
        left[:, -1] *= -1
        rotation = left @ right
    estimated = (rotation @ np.asarray(estimated_centers).T).T
    truth = np.asarray(truth_centers)
    estimated_centered = estimated - estimated.mean(axis=0)
    truth_centered = truth - truth.mean(axis=0)
    denominator = float(np.sum(estimated_centered * estimated_centered))
    if denominator <= 0.0:
        raise ValueError("degenerate COLMAP camera baseline")
    scale = float(np.sum(estimated_centered * truth_centered) / denominator)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("invalid COLMAP camera alignment scale")
    translation = truth.mean(axis=0) - scale * estimated.mean(axis=0)
    aligned = scale * estimated + translation
    rmse = float(np.sqrt(np.mean(np.sum((aligned - truth) ** 2, axis=1))))
    return scale, rotation, translation, rmse


def _manifest_input_path(input_root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("manifest input path escapes the input directory")
    root = input_root.resolve(strict=True)
    try:
        path = (root / relative).resolve(strict=True)
        path.relative_to(root)
    except (FileNotFoundError, ValueError) as error:
        raise ValueError("manifest input path escapes the input directory") from error
    if not path.is_file():
        raise ValueError("manifest input path is not a regular file")
    return path


def _validate_manifest_contract(manifest: dict[str, Any], profile: str) -> set[str]:
    if profile not in {"smoke", "full"}:
        raise ValueError("scene manifest has an invalid profile")
    scene = load_json(ROOT / "shared-scene.json")
    fixture = scene["reference_fixture"]
    intrinsics = scene["cameras"]["intrinsics"]
    camera_xs = fixture[f"camera_x_{profile}_m"]
    width, height = int(intrinsics["width"]), int(intrinsics["height"])
    expected_names = {f"frame-{index:03d}.pgm" for index in range(len(camera_xs))}
    if (
        manifest.get("schema_version") != 1
        or manifest.get("profile") != profile
        or manifest.get("camera_model") != "PINHOLE"
        or manifest.get("intrinsics") != {
            key: intrinsics[key] for key in ("width", "height", "fx", "fy", "cx", "cy")
        }
        or manifest.get("world_frame") != scene["world_frame"]
        or manifest.get("camera_frame") != scene["camera_frame"]
        or manifest.get("fixture") != fixture
        or manifest.get("scene_seed") != scene["seed"]
        or not isinstance(manifest.get("frames"), list)
        or len(manifest["frames"]) != len(camera_xs)
    ):
        raise ValueError("scene manifest does not match the shared-scene profile contract")
    K = [
        [float(intrinsics["fx"]), 0.0, float(intrinsics["cx"])],
        [0.0, float(intrinsics["fy"]), float(intrinsics["cy"])],
        [0.0, 0.0, 1.0],
    ]
    rotation = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]
    for index, (frame, camera_x) in enumerate(zip(manifest["frames"], camera_xs)):
        if (
            frame.get("name") != f"frame-{index:03d}.pgm"
            or frame.get("depth_name") != f"depth/frame-{index:03d}.depth.npy"
            or frame.get("K") != K
            or frame.get("R_world_to_camera") != rotation
            or frame.get("t_world_to_camera_m") != [-float(camera_x), 0.0, 0.0]
            or frame.get("camera_center_m") != [float(camera_x), 0.0, 0.0]
        ):
            raise ValueError("scene-manifest frame does not match the shared-scene profile")
    stride = int(fixture["ground_truth_sample_stride_pixels"])
    expected_vertices = len(camera_xs) * len(range(0, width, stride)) * len(range(0, height, stride))
    ground_truth = manifest.get("ground_truth", {})
    visible = ground_truth.get("visible_surface", {})
    if (
        ground_truth.get("units") != "metres"
        or ground_truth.get("sample_stride_pixels") != stride
        or visible.get("path") != "ground-truth-visible.ply"
        or visible.get("format") != "ply-ascii-xyz"
        or visible.get("vertex_count") != expected_vertices
    ):
        raise ValueError("scene-manifest truth does not match the shared-scene profile")
    return expected_names


def _read_colmap_dense_map(path: Path) -> tuple[int, int, int, np.ndarray]:
    with path.open("rb") as stream:
        fields: list[int] = []
        token = bytearray()
        while len(fields) < 3:
            character = stream.read(1)
            if not character:
                raise ValueError(f"malformed COLMAP dense-map header: {path}")
            if character == b"&":
                try:
                    fields.append(int(token.decode("ascii")))
                except (UnicodeDecodeError, ValueError) as error:
                    raise ValueError(f"malformed COLMAP dense-map header: {path}") from error
                token.clear()
            elif character.isdigit():
                token.extend(character)
            else:
                raise ValueError(f"malformed COLMAP dense-map header: {path}")
        width, height, channels = fields
        if width <= 0 or height <= 0 or channels not in {1, 3}:
            raise ValueError(f"invalid COLMAP dense-map dimensions: {path}")
        payload = stream.read()
    expected = width * height * channels * np.dtype("<f4").itemsize
    if len(payload) != expected:
        raise ValueError(f"COLMAP dense-map payload size mismatch: {path}")
    values = np.frombuffer(payload, dtype="<f4").astype(np.float64)
    if not np.isfinite(values).all():
        raise ValueError(f"non-finite COLMAP dense-map payload: {path}")
    return width, height, channels, values


def _canonical_sample(
    points: np.ndarray, maximum: int = EVALUATION_MAX_POINTS
) -> tuple[np.ndarray, np.ndarray]:
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) == 0 or not np.isfinite(points).all():
        raise ValueError("canonical point sampling requires finite XYZ points")
    quantized = np.rint(points / EVALUATION_VOXEL_M).astype(np.int64)
    voxels, counts = np.unique(quantized, axis=0, return_counts=True)
    centers = voxels.astype(np.float64) * EVALUATION_VOXEL_M
    if len(centers) > maximum:
        generator = np.random.default_rng(EVALUATION_SAMPLE_SEED)
        indices = np.sort(generator.choice(len(centers), size=maximum, replace=False))
        centers = centers[indices]
        counts = counts[indices]
    return centers, counts.astype(np.int64)


def _nearest_distances(query: np.ndarray, target: np.ndarray) -> np.ndarray:
    target_norm = np.sum(target * target, axis=1)
    distances = np.empty(len(query), dtype=np.float64)
    for start in range(0, len(query), 256):
        batch = query[start : start + 256]
        squared = np.sum(batch * batch, axis=1, keepdims=True) + target_norm - 2.0 * batch @ target.T
        distances[start : start + len(batch)] = np.sqrt(np.maximum(np.min(squared, axis=1), 0.0))
    return distances


def _geometry_metrics(run_dir: Path) -> dict[str, float | int]:
    model = run_dir / "output/sparse/0"
    metrics = dict(_parse_colmap_text(model))
    manifest = load_json(run_dir / "input/scene-manifest.json")
    truth_path = _manifest_input_path(
        run_dir / "input", manifest["ground_truth"]["visible_surface"]["path"]
    )
    frame_names = _validate_manifest_contract(manifest, manifest.get("profile", ""))
    reconstructed, _ = _read_ply_xyz(run_dir / "output/dense/fused.ply")
    truth, _ = _read_ply_xyz(truth_path)
    poses = _colmap_poses(model / "images.txt")
    if not set(poses) <= frame_names:
        raise ValueError("registered COLMAP image is not declared by the scene manifest")
    scale, rotation, translation, alignment_rmse = _align_similarity(poses, manifest)
    aligned = scale * (rotation @ reconstructed.T).T + translation
    evaluation_reconstruction, _ = _canonical_sample(aligned)
    evaluation_truth, truth_support = _canonical_sample(truth)
    accuracy = _nearest_distances(evaluation_reconstruction, evaluation_truth)
    completeness = _nearest_distances(evaluation_truth, evaluation_reconstruction)
    precision = float(np.mean(accuracy <= FSCORE_THRESHOLD_M))
    recall = float(np.mean(completeness <= FSCORE_THRESHOLD_M))
    fscore = 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)
    supported = truth_support >= 2
    supported_completeness = float(np.mean(completeness[supported])) if np.any(supported) else 0.0
    undersupported_completeness = (
        float(np.mean(completeness[~supported])) if np.any(~supported) else 0.0
    )
    _, mesh_faces = _read_ply_xyz(
        run_dir / "output/dense/meshed-poisson.ply", validate_faces=True
    )
    metrics.update({
        "dense_points": int(len(reconstructed)),
        "mesh_faces": int(mesh_faces),
        "camera_alignment_rmse_m": alignment_rmse,
        "accuracy_mean_m": float(np.mean(accuracy)),
        "completeness_mean_m": float(np.mean(completeness)),
        "supported_completeness_mean_m": supported_completeness,
        "undersupported_completeness_mean_m": undersupported_completeness,
        "fscore_10cm": fscore,
        "evaluation_sample_points": int(min(len(evaluation_reconstruction), len(evaluation_truth))),
        "evaluation_reconstruction_points": int(len(evaluation_reconstruction)),
        "evaluation_truth_points": int(len(evaluation_truth)),
        "supported_truth_points": int(np.sum(supported)),
        "undersupported_truth_points": int(np.sum(~supported)),
    })
    ensure_finite(metrics, "COLMAP MVS metrics")
    return metrics


def _adapter_record() -> dict[str, Any]:
    return next(
        item for item in load_json(ROOT / "reference-adapters.json")["adapters"]
        if item["id"] == "colmap-mvs-reference"
    )


def _validate_required_artifacts(
    run_dir: Path, metrics: dict[str, Any], profile: str
) -> None:
    manifest_path = _require_regular_file(run_dir, "input/scene-manifest.json")
    manifest = load_json(manifest_path)
    expected_frame_names = _validate_manifest_contract(manifest, profile)
    input_root = run_dir / "input"
    width = int(manifest["intrinsics"]["width"])
    height = int(manifest["intrinsics"]["height"])
    frame_names: set[str] = set()
    for frame in manifest.get("frames", []):
        name = frame.get("name")
        if not isinstance(name, str) or name in frame_names or Path(name).name != name:
            raise ValueError("invalid scene-manifest frame name")
        frame_names.add(name)
        image = _manifest_input_path(input_root, f"images/{name}")
        depth_path = _manifest_input_path(input_root, frame["depth_name"])
        if sha256_file(image) != frame.get("sha256") or sha256_file(depth_path) != frame.get("depth_sha256"):
            raise ValueError("scene-manifest frame hash mismatch")
        depth = np.load(depth_path, allow_pickle=False)
        if (
            depth.shape != (height, width)
            or depth.dtype != np.float32
            or not np.isfinite(depth).all()
            or np.any(depth <= 0.0)
        ):
            raise ValueError("invalid scene-manifest metric depth")
    if frame_names != expected_frame_names:
        raise ValueError("scene-manifest frame inventory mismatch")
    truth_relative = manifest["ground_truth"]["visible_surface"]["path"]
    truth = _manifest_input_path(input_root, truth_relative)
    if sha256_file(truth) != manifest["ground_truth"]["visible_surface"].get("sha256"):
        raise ValueError("ground-truth PLY hash mismatch")
    required = (
        "adapter.log", "report.md", "output/database.db", "output/colmap-version.txt",
        "output/source-commit.txt", "output/insula-manifest.txt", "output/resource-usage.txt",
        "output/resource-summary.json",
        "output/sparse.ply", "output/sparse/0/cameras.bin", "output/sparse/0/images.bin",
        "output/sparse/0/points3D.bin", "output/sparse/0/cameras.txt", "output/sparse/0/images.txt",
        "output/sparse/0/points3D.txt", "output/dense/fused.ply", "output/dense/meshed-poisson.ply",
    )
    paths = {relative: _require_regular_file(run_dir, relative) for relative in required}
    _validate_sqlite_database(paths["output/database.db"])
    _validate_mvs_database(paths["output/database.db"], frame_names)
    truth_points, _ = _read_ply_xyz(truth)
    if len(truth_points) != manifest["ground_truth"]["visible_surface"]["vertex_count"]:
        raise ValueError("ground-truth PLY vertex count mismatch")
    dense_points, _ = _read_ply_xyz(paths["output/dense/fused.ply"], require_normals=True)
    if len(dense_points) != metrics["dense_points"]:
        raise ValueError("dense PLY vertex count mismatch")
    sparse_points, _ = _read_ply_xyz(paths["output/sparse.ply"])
    if len(sparse_points) != metrics["sparse_points"]:
        raise ValueError("sparse PLY vertex count mismatch")
    _, mesh_faces = _read_ply_xyz(paths["output/dense/meshed-poisson.ply"], validate_faces=True)
    if mesh_faces != metrics["mesh_faces"] or mesh_faces <= 0:
        raise ValueError("mesh PLY face count mismatch")
    registered_names = set(_colmap_poses(run_dir / "output/sparse/0/images.txt"))
    if not registered_names <= frame_names:
        raise ValueError("registered COLMAP image is not declared by the scene manifest")
    _validate_colmap_binary_model(run_dir / "output/sparse/0", registered_names, metrics["sparse_points"])
    depth_root = run_dir / "output/dense/stereo/depth_maps"
    normal_root = run_dir / "output/dense/stereo/normal_maps"
    depth_maps = list(depth_root.glob("*.bin"))
    normal_maps = list(normal_root.glob("*.bin"))
    expected_maps = {
        f"{name}.{variant}.bin"
        for name in registered_names
        for variant in ("geometric", "photometric")
    }
    if (
        {path.name for path in depth_maps} != expected_maps
        or {path.name for path in normal_maps} != expected_maps
        or len(registered_names) != metrics["registered_images"]
    ):
        raise ValueError("dense stereo map inventory mismatch")
    for path in depth_maps:
        _require_regular_file(run_dir, path.relative_to(run_dir).as_posix())
        map_width, map_height, channels, values = _read_colmap_dense_map(path)
        if (map_width, map_height, channels) != (width, height, 1) or not np.any(values > 0.0):
            raise ValueError("invalid COLMAP depth map")
    for path in normal_maps:
        _require_regular_file(run_dir, path.relative_to(run_dir).as_posix())
        map_width, map_height, channels, values = _read_colmap_dense_map(path)
        if (map_width, map_height, channels) != (width, height, 3) or not np.any(values != 0.0):
            raise ValueError("invalid COLMAP normal map")
    if _parse_key_value_manifest(paths["output/insula-manifest.txt"]) != PINNED_INSULA_MANIFEST:
        raise ValueError("classical MVS Insula manifest mismatch")


def _acceptance_failures(metrics: dict[str, Any], acceptance: dict[str, Any]) -> list[str]:
    checks = [
        (metrics["registered_images"] >= acceptance["registered_images_min"], "registered_images"),
        (metrics["dense_points"] >= acceptance["dense_points_min"], "dense_points"),
        (metrics["mesh_faces"] >= acceptance["mesh_faces_min"], "mesh_faces"),
        (metrics["camera_alignment_rmse_m"] <= acceptance["camera_alignment_rmse_m_max"], "camera_alignment_rmse_m"),
        (metrics["accuracy_mean_m"] <= acceptance["accuracy_mean_m_max"], "accuracy_mean_m"),
        (metrics["completeness_mean_m"] <= acceptance["completeness_mean_m_max"], "completeness_mean_m"),
        (metrics["fscore_10cm"] >= acceptance["fscore_10cm_min"], "fscore_10cm"),
    ]
    if "middlebury_dense_points_min" in acceptance:
        checks.extend(
            [
                (
                    metrics.get("middlebury_calibrated_views")
                    >= acceptance["middlebury_calibrated_views_min"],
                    "middlebury_calibrated_views",
                ),
                (
                    metrics.get("middlebury_dense_points")
                    >= acceptance["middlebury_dense_points_min"],
                    "middlebury_dense_points",
                ),
                (
                    metrics.get("middlebury_mesh_faces")
                    >= acceptance["middlebury_mesh_faces_min"],
                    "middlebury_mesh_faces",
                ),
            ]
        )
    return [name for passed, name in checks if not passed]


def _middlebury_metrics(run_dir: Path) -> dict[str, int]:
    input_root = run_dir / "input" / "middlebury"
    manifest = load_json(_require_regular_file(input_root, "manifest.json"))
    if (
        manifest.get("schema_version") != 1
        or manifest.get("asset_id") != MIDDLEBURY_ASSET_ID
        or manifest.get("archive_sha256") != MIDDLEBURY_ARCHIVE_SHA256
        or manifest.get("extraction_tree_sha256") != MIDDLEBURY_TREE_SHA256
        or manifest.get("dataset") != "templeSparseRing"
        or manifest.get("calibrated_views") != MIDDLEBURY_VIEW_COUNT
        or manifest.get("image_size") != [640, 480]
        or manifest.get("frame_names")
        != [f"templeSR{index:04d}.png" for index in range(1, 17)]
        or manifest.get("source_view_strategy")
        != "cyclic_neighbors_offsets_-1_1_-2_2_-3_3_-4_4"
        or manifest.get("source_views_per_reference") != 8
        or manifest.get("depth_range_derivation")
        != "0.5 * minimum and 1.5 * maximum camera-space depth of world origin"
        or manifest.get("patch_match_output") != "photometric"
        or manifest.get("fusion_min_num_pixels") != 1
        or manifest.get("poisson_depth") != 8
        or manifest.get("fusion_scope")
        != "structural execution support; cross-view geometry is scored on the controlled scene"
        or not isinstance(manifest.get("input_sha256"), dict)
    ):
        raise ValueError("Middlebury input manifest mismatch")
    expected_paths = {
        "templeSR_par.txt",
        "model/cameras.txt",
        "model/images.txt",
        "model/points3D.txt",
        "patch-match.cfg",
        *(f"images/{name}" for name in manifest["frame_names"]),
    }
    if set(manifest["input_sha256"]) != expected_paths:
        raise ValueError("Middlebury input inventory mismatch")
    for relative, expected_hash in manifest["input_sha256"].items():
        if sha256_file(_require_regular_file(input_root, relative)) != expected_hash:
            raise ValueError(f"Middlebury input hash mismatch: {relative}")
    calibration_lines = _require_regular_file(
        input_root, "templeSR_par.txt"
    ).read_text(encoding="utf-8").splitlines()
    try:
        origin_depths = [
            float(line.split()[21]) for line in calibration_lines[1:] if line.strip()
        ]
    except (IndexError, ValueError) as error:
        raise ValueError("Middlebury depth-range calibration mismatch") from error
    expected_origin_range = [min(origin_depths), max(origin_depths)]
    expected_depth_range = [
        MIDDLEBURY_DEPTH_NEAR_SCALE * expected_origin_range[0],
        MIDDLEBURY_DEPTH_FAR_SCALE * expected_origin_range[1],
    ]
    if (
        len(origin_depths) != MIDDLEBURY_VIEW_COUNT
        or not all(value > 0.0 and math.isfinite(value) for value in origin_depths)
        or manifest.get("origin_depth_range_dataset_units") != expected_origin_range
        or manifest.get("depth_range_dataset_units") != expected_depth_range
    ):
        raise ValueError("Middlebury depth-range calibration mismatch")
    expected_patch_match = "\n".join(
        _middlebury_patch_match_rows(manifest["frame_names"])
    ) + "\n"
    if (input_root / "patch-match.cfg").read_text(encoding="utf-8") != expected_patch_match:
        raise ValueError("Middlebury source-view graph mismatch")
    fused, _ = _read_ply_xyz(
        _require_regular_file(run_dir, "output/middlebury/dense/fused.ply"),
        require_normals=True,
    )
    _, mesh_faces = _read_ply_xyz(
        _require_regular_file(
            run_dir, "output/middlebury/dense/meshed-poisson.ply"
        ),
        validate_faces=True,
    )
    if len(fused) == 0 or mesh_faces == 0:
        raise ValueError("Middlebury dense reconstruction is empty")
    return {
        "middlebury_calibrated_views": MIDDLEBURY_VIEW_COUNT,
        "middlebury_dense_points": int(len(fused)),
        "middlebury_mesh_faces": int(mesh_faces),
    }


def _metrics_match(recorded: dict[str, Any], recomputed: dict[str, Any]) -> bool:
    if set(recorded) != set(recomputed):
        return False
    for key, expected in recomputed.items():
        actual = recorded[key]
        if isinstance(expected, int) and not isinstance(expected, bool):
            if isinstance(actual, bool) or not isinstance(actual, int) or actual != expected:
                return False
        elif (
            isinstance(actual, bool)
            or not isinstance(actual, (int, float))
            or not math.isclose(
                float(actual),
                float(expected),
                rel_tol=METRIC_RELATIVE_TOLERANCE,
                abs_tol=METRIC_ABSOLUTE_TOLERANCE,
            )
        ):
            return False
    return True


def validate_mvs_reference_result(run_dir: Path) -> dict[str, Any]:
    result_path = run_dir / "result.json"
    if not result_path.is_file():
        raise ValueError(f"missing reference result: {result_path}")
    result = load_json(result_path)
    validate_json_schema_instance(result, load_json(ROOT / "reference-result.schema.json"), "reference-result")
    ensure_finite(result, "reference-result")
    if result.get("adapter") != ADAPTER or result.get("module_ids") != ["06"]:
        raise ValueError("module scope mismatch: COLMAP MVS belongs to module 06")
    if result.get("status") != "complete" or result.get("network_mode") != "offline":
        raise ValueError("MVS reference result is not a complete offline record")
    if result["tool"].get("name") != "COLMAP" or result["tool"].get("container_image") != IMAGE:
        raise ValueError("tool identity mismatch")
    provenance = result["provenance"]
    actual_config = hashlib.sha256(canonical_json(provenance["config"])).hexdigest()
    if provenance.get("config_sha256") != actual_config:
        raise ValueError("config hash mismatch")
    config = provenance["config"]
    validate_run_id(config.get("run_id", ""))
    if (
        config.get("adapter") != ADAPTER
        or config.get("profile") != result["profile"]
        or config.get("module_ids") != ["06"]
        or config.get("image") != result["tool"]["container_image"]
        or config.get("image_id") != result["tool"]["container_image_id"]
        or config.get("scene_contract_sha256") != sha256_file(ROOT / "shared-scene.json")
        or config.get("fscore_threshold_m") != FSCORE_THRESHOLD_M
        or config.get("evaluation_max_points") != EVALUATION_MAX_POINTS
        or config.get("evaluation_voxel_m") != EVALUATION_VOXEL_M
        or config.get("evaluation_sample_seed") != EVALUATION_SAMPLE_SEED
        or config.get("validation_float_relative_tolerance") != METRIC_RELATIVE_TOLERANCE
        or config.get("validation_float_absolute_tolerance") != METRIC_ABSOLUTE_TOLERANCE
        or not isinstance(config.get("evaluation_software", {}).get("numpy"), str)
        or not config["evaluation_software"]["numpy"]
        or config.get("cuda_cache") != "persistent-cache-root-mount"
    ):
        raise ValueError("reference config binding mismatch")
    expected_middlebury = (
        None
        if result["profile"] == "smoke"
        else {
            "asset_id": MIDDLEBURY_ASSET_ID,
            "dataset": "templeSparseRing",
            "archive_sha256": MIDDLEBURY_ARCHIVE_SHA256,
            "extraction_tree_sha256": MIDDLEBURY_TREE_SHA256,
            "calibrated_views": MIDDLEBURY_VIEW_COUNT,
            "asset_lock": _middlebury_record(),
        }
    )
    if config.get("canonical_middlebury") != expected_middlebury:
        raise ValueError("Middlebury config binding mismatch")
    implementation = {name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION}
    if provenance.get("implementation_sha256") != implementation:
        raise ValueError("implementation hash mismatch")
    if _hash_tree(run_dir) != provenance.get("artifacts_sha256"):
        raise ValueError("artifact hash mismatch")
    metrics = _geometry_metrics(run_dir)
    if result["profile"] == "full":
        metrics.update(_middlebury_metrics(run_dir))
    if not isinstance(result.get("metrics"), dict) or not _metrics_match(result["metrics"], metrics):
        raise ValueError("COLMAP MVS metric mismatch")
    _validate_required_artifacts(run_dir, metrics, result["profile"])
    version = (run_dir / "output/colmap-version.txt").read_text(encoding="utf-8").strip()
    source_commit = (run_dir / "output/source-commit.txt").read_text(encoding="utf-8").strip()
    if result["tool"].get("version") != version or PINNED_COLMAP_VERSION not in version.split():
        raise ValueError("tool version mismatch")
    if result["tool"].get("source_commit") != source_commit or source_commit != PINNED_COLMAP_COMMIT:
        raise ValueError("tool source commit mismatch")
    adapter_record = _adapter_record()
    acceptance = adapter_record["acceptance"][result["profile"]]
    if result.get("acceptance") != acceptance or config.get("acceptance") != acceptance:
        raise ValueError("acceptance mismatch")
    evaluation_contract = adapter_record.get("evaluation_contract", {})
    if evaluation_contract != {
        "voxel_size_m": EVALUATION_VOXEL_M,
        "maximum_points_per_direction": EVALUATION_MAX_POINTS,
        "sample_seed": EVALUATION_SAMPLE_SEED,
        "support_threshold_observations": 2,
        "canonical_sample": "Middlebury TempleSparseRing",
        "canonical_calibrated_views": MIDDLEBURY_VIEW_COUNT,
        "canonical_ground_truth_status": (
            "laser ground truth is not distributed; report execution and structural support only"
        ),
    }:
        raise ValueError("evaluation contract mismatch")
    failures = _acceptance_failures(metrics, acceptance)
    if failures:
        raise ValueError(f"COLMAP MVS reconstruction is below the locked acceptance threshold: {failures}")
    resources = result["resources"]
    runtime = resources.get("runtime_seconds")
    if isinstance(runtime, bool) or not isinstance(runtime, (int, float)) or runtime < 0:
        raise ValueError("runtime must be a finite non-negative number")
    for key in ("peak_cpu_memory_bytes", "peak_gpu_compute_memory_bytes"):
        value = resources.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer")
    if (
        resources.get("gpu_memory_scope") != "container-cgroup-compute-process-sum"
        or resources.get("gpu_selection") != "one healthy host GPU mapped to CUDA device 0"
        or not isinstance(resources.get("gpu_host_index"), int)
        or resources.get("gpu_measurement_status") not in {"measured", "unavailable"}
        or not isinstance(resources.get("gpu_hardware"), list)
        or not isinstance(resources.get("host"), str)
        or not resources["host"]
    ):
        raise ValueError("invalid MVS resource metadata")
    if resources["gpu_measurement_status"] == "measured":
        if resources["peak_gpu_compute_memory_bytes"] <= 0 or not resources["gpu_hardware"]:
            raise ValueError("measured GPU resources require hardware and a positive peak")
    elif resources["peak_gpu_compute_memory_bytes"] != 0:
        raise ValueError("unavailable GPU measurement must record a zero peak")
    resource_summary = load_json(run_dir / "output/resource-summary.json")
    if resource_summary != resources:
        raise ValueError("resource summary mismatch")
    baseline_environment = adapter_record.get("baseline_environment", {})
    if (
        not isinstance(baseline_environment.get("container_image_id"), str)
        or not baseline_environment["container_image_id"].startswith("sha256:")
        or not isinstance(baseline_environment.get("gpu_model"), str)
        or not isinstance(baseline_environment.get("compute_capability"), (int, float))
        or not isinstance(baseline_environment.get("driver_version"), str)
    ):
        raise ValueError("invalid recorded baseline environment")
    if resources["gpu_measurement_status"] == "measured":
        selected = [
            device
            for device in resources["gpu_hardware"]
            if device.get("index") == resources["gpu_host_index"]
        ]
        if len(selected) != 1 or any(
            not isinstance(selected[0].get(field), value_type)
            or isinstance(selected[0].get(field), bool)
            for field, value_type in (
                ("uuid", str),
                ("name", str),
                ("compute_capability", (int, float)),
                ("driver_version", str),
            )
        ):
            raise ValueError("PatchMatch GPU index 0 is not uniquely attested")
    return result


def _gpu_process_memory_bytes(container_id: str | None, proc_root: Path = Path("/proc")) -> int:
    if container_id is None:
        return 0
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return 0
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-compute-apps=pid,used_gpu_memory",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return 0
    if completed.returncode != 0:
        return 0
    total_mib = 0
    for line in completed.stdout.splitlines():
        try:
            pid_text, memory_text = line.split(",", maxsplit=1)
            cgroup = (proc_root / pid_text.strip() / "cgroup").read_text(encoding="utf-8")
            if container_id not in cgroup:
                continue
            total_mib += int(memory_text.strip())
        except (OSError, ValueError):
            continue
    return total_mib * 1024 * 1024


def _gpu_hardware(engine: str) -> list[dict[str, Any]]:
    if Path(engine).name != "docker":
        return []
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return []
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=index,uuid,name,compute_cap,driver_version",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return []
    if completed.returncode != 0:
        return []
    devices: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 5:
            return []
        try:
            index = int(fields[0])
            compute_capability = float(fields[3])
        except ValueError:
            return []
        devices.append(
            {
                "index": index,
                "uuid": fields[1],
                "name": fields[2],
                "compute_capability": compute_capability,
                "driver_version": fields[4],
            }
        )
    return devices


def _run_monitored(
    command: list[str], cidfile: Path | None = None
) -> tuple[subprocess.CompletedProcess[str], int]:
    # COLMAP can emit megabytes of progress output.  PIPEs are not drained while
    # resource sampling, so using them here can fill the kernel buffer and
    # deadlock an otherwise completed container.  File-backed streams preserve
    # the complete log without imposing a bounded producer/consumer buffer.
    with (
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_file,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_file,
    ):
        process = subprocess.Popen(command, text=True, stdout=stdout_file, stderr=stderr_file)
        peak_gpu = 0
        container_id = None
        while process.poll() is None:
            if container_id is None and cidfile is not None:
                try:
                    candidate = cidfile.read_text(encoding="utf-8").strip()
                except FileNotFoundError:
                    candidate = ""
                if len(candidate) == 64 and all(character in "0123456789abcdef" for character in candidate):
                    container_id = candidate
            peak_gpu = max(peak_gpu, _gpu_process_memory_bytes(container_id))
            time.sleep(0.1)
        process.wait()
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read()
        stderr = stderr_file.read()
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr), peak_gpu


def _peak_cpu_memory_bytes(path: Path) -> int:
    prefix = "Maximum resident set size (kbytes):"
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith(prefix):
            value = int(stripped.removeprefix(prefix).strip())
            if value < 0:
                break
            return value * 1024
    raise ValueError("missing peak CPU memory in resource usage")


def run_mvs_reference(cache_root: Path, profile: str, run_id: str) -> Path:
    validate_run_id(run_id)
    if profile not in {"smoke", "full"}:
        raise ValueError(f"unknown profile: {profile}")
    engine = os.environ.get("SURFLO_PATHWAY_CONTAINER_ENGINE", "docker")
    image_id = _inspect_image(engine, IMAGE)
    gpu_hardware = _gpu_hardware(engine)
    if Path(engine).name == "docker" and not gpu_hardware:
        raise ValueError("unable to inventory GPU hardware for the real MVS reference")
    gpu_device = selected_gpu_device(require_health=Path(engine).name == "docker")
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root = cache_root.resolve(strict=True)
    middlebury_source: Path | None = None
    middlebury_extraction: dict[str, Any] | None = None
    middlebury_manifest: dict[str, Any] | None = None
    if profile == "full":
        middlebury_source, middlebury_extraction = _locked_middlebury(cache_root)
    runs_root = _secure_directory(cache_root, "reference-runs")
    staging_root = _secure_directory(cache_root, "reference-staging")
    cuda_cache = _secure_directory(cache_root, "cuda-cache")
    final_parent = runs_root / run_id
    final = final_parent / ADAPTER
    if os.path.lexists(final_parent):
        raise FileExistsError(f"reference run already exists: {final}")
    staging = staging_root / f"{run_id}.{ADAPTER}.{uuid.uuid4().hex}"
    staging.mkdir()
    started = time.perf_counter()
    try:
        manifest = generate_colmap_mvs_scene(staging / "input", load_json(ROOT / "shared-scene.json"), profile)
        if middlebury_source is not None and middlebury_extraction is not None:
            middlebury_manifest = _prepare_middlebury_input(
                middlebury_source,
                staging / "input" / "middlebury",
                middlebury_extraction,
            )
        (staging / "output").mkdir()
        command = [
            engine, "run", "--rm", "--network", "none", "--pull=never", "--gpus", f"device={gpu_device}",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "--cidfile", str(staging / "container.cid"),
            "-e", "CUDA_CACHE_PATH=/cuda-cache", "-v", f"{cuda_cache}:/cuda-cache",
            "-v", f"{staging.resolve()}:/work",
            image_id, "/usr/bin/time", "-v", "-o", "/work/output/resource-usage.txt",
            "bash", "-lc", _container_script(manifest, profile, middlebury_manifest),
        ]
        completed, peak_gpu = _run_monitored(command, staging / "container.cid")
        (staging / "adapter.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise ValueError(f"COLMAP MVS adapter failed ({completed.returncode}): {completed.stderr.strip()}")
        if Path(engine).name == "docker" and peak_gpu <= 0:
            raise ValueError("unable to measure compute memory for PatchMatch GPU index 0")
        metrics = _geometry_metrics(staging)
        if profile == "full":
            metrics.update(_middlebury_metrics(staging))
        version = (staging / "output/colmap-version.txt").read_text(encoding="utf-8").strip()
        source_commit = (staging / "output/source-commit.txt").read_text(encoding="utf-8").strip()
        if PINNED_COLMAP_VERSION not in version.split():
            raise ValueError(f"COLMAP version mismatch: expected {PINNED_COLMAP_VERSION}, got {version!r}")
        if source_commit != PINNED_COLMAP_COMMIT:
            raise ValueError(f"COLMAP source commit mismatch: expected {PINNED_COLMAP_COMMIT}, got {source_commit!r}")
        acceptance = _adapter_record()["acceptance"][profile]
        if (
            metrics["completeness_mean_m"] > metrics["accuracy_mean_m"]
            and metrics["undersupported_completeness_mean_m"]
            > metrics["supported_completeness_mean_m"] + 0.01
        ):
            support_interpretation = (
                "Under-supported truth voxels have the larger directed error, so this run exposes "
                "a visible-support failure. It is not evidence of complete-scene reconstruction."
            )
        elif metrics["completeness_mean_m"] > metrics["accuracy_mean_m"] + 0.01:
            support_interpretation = (
                "Completeness exceeds accuracy, but the support split does not localize that gap; "
                "the run therefore makes no stronger support-causality claim."
            )
        else:
            support_interpretation = (
                "This run has no material directed accuracy/completeness gap; no support failure "
                "is inferred from these metrics."
            )
        (staging / "report.md").write_text(
            "# COLMAP dense-MVS reference\n\n"
            f"Profile: `{profile}`. Tool: COLMAP {PINNED_COLMAP_VERSION} source commit "
            f"`{PINNED_COLMAP_COMMIT}` in the pinned CUDA/Blackwell Insula. The run executed "
            "offline and similarity-aligned the recovered camera gauge to the declared metric cameras.\n\n"
            f"Registered images: {metrics['registered_images']}; dense points: {metrics['dense_points']}; "
            f"mesh faces: {metrics['mesh_faces']}; aligned accuracy/completeness: "
            f"{metrics['accuracy_mean_m']:.4f}/{metrics['completeness_mean_m']:.4f} m; "
            f"F-score at 10 cm: {metrics['fscore_10cm']:.4f}; camera alignment RMSE: "
            f"{metrics['camera_alignment_rmse_m']:.6f} m.\n\n"
            "Accuracy is fused reconstruction to visible-surface truth; completeness is the reverse. "
            f"Supported/under-supported completeness is {metrics['supported_completeness_mean_m']:.4f}/"
            f"{metrics['undersupported_completeness_mean_m']:.4f} m over "
            f"{metrics['supported_truth_points']}/{metrics['undersupported_truth_points']} sampled truth voxels. "
            f"{support_interpretation}\n"
            + (
                "\n## Canonical Middlebury sample\n\n"
                f"The full profile consumed all {metrics['middlebury_calibrated_views']} calibrated "
                "TempleSparseRing views from the byte- and tree-verified Middlebury archive. "
                f"COLMAP fused {metrics['middlebury_dense_points']} oriented points and extracted "
                f"{metrics['middlebury_mesh_faces']} non-degenerate mesh faces. The benchmark's "
                "laser ground truth is not distributed. This branch therefore uses photometric "
                "PatchMatch depth with a one-view fusion minimum and reports execution/support only, "
                "not cross-view-consistent accuracy or completeness; those geometry claims come from "
                "the controlled scene above.\n"
                if profile == "full"
                else ""
            ),
            encoding="utf-8",
        )
        resources = {
            "runtime_seconds": time.perf_counter() - started,
            "peak_cpu_memory_bytes": _peak_cpu_memory_bytes(staging / "output/resource-usage.txt"),
            "peak_gpu_compute_memory_bytes": peak_gpu,
            "gpu_memory_scope": "container-cgroup-compute-process-sum",
            "gpu_measurement_status": "measured" if peak_gpu > 0 else "unavailable",
            "gpu_selection": "one healthy host GPU mapped to CUDA device 0",
            "gpu_host_index": int(gpu_device),
            "gpu_hardware": gpu_hardware,
            "host": platform.platform(),
        }
        write_json(staging / "output/resource-summary.json", resources)
        config = {
            "adapter": ADAPTER,
            "profile": profile,
            "run_id": run_id,
            "module_ids": ["06"],
            "image": IMAGE,
            "image_id": image_id,
            "scene_contract_sha256": sha256_file(ROOT / "shared-scene.json"),
            "fscore_threshold_m": FSCORE_THRESHOLD_M,
            "evaluation_max_points": EVALUATION_MAX_POINTS,
            "evaluation_voxel_m": EVALUATION_VOXEL_M,
            "evaluation_sample_seed": EVALUATION_SAMPLE_SEED,
            "validation_float_relative_tolerance": METRIC_RELATIVE_TOLERANCE,
            "validation_float_absolute_tolerance": METRIC_ABSOLUTE_TOLERANCE,
            "evaluation_software": {"numpy": np.__version__},
            "cuda_cache": "persistent-cache-root-mount",
            "canonical_middlebury": None
            if profile == "smoke"
            else {
                "asset_id": MIDDLEBURY_ASSET_ID,
                "dataset": "templeSparseRing",
                "archive_sha256": MIDDLEBURY_ARCHIVE_SHA256,
                "extraction_tree_sha256": MIDDLEBURY_TREE_SHA256,
                "calibrated_views": MIDDLEBURY_VIEW_COUNT,
                "asset_lock": _middlebury_record(),
            },
            "acceptance": acceptance,
        }
        result = {
            "schema_version": 1,
            "adapter": ADAPTER,
            "module_ids": ["06"],
            "profile": profile,
            "status": "complete",
            "network_mode": "offline",
            "metrics": metrics,
            "acceptance": acceptance,
            "tool": {
                "name": "COLMAP",
                "version": version,
                "package_version": f"source@{source_commit}",
                "source_commit": source_commit,
                "container_image": IMAGE,
                "container_image_id": image_id,
            },
            "resources": resources,
            "provenance": {
                "config": config,
                "config_sha256": hashlib.sha256(canonical_json(config)).hexdigest(),
                "implementation_sha256": {name: sha256_file(ROOT / name) for name in REFERENCE_IMPLEMENTATION},
                "artifacts_sha256": _hash_tree(staging),
            },
        }
        ensure_finite(result, "reference-result")
        write_json(staging / "result.json", result)
        validate_mvs_reference_result(staging)
        final_parent.mkdir()
        os.replace(staging, final)
        return final
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
