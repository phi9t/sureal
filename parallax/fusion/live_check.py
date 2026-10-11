"""Run TSDF fusion and meshing live checks inside the Parallax runtime."""

from __future__ import annotations

import argparse
import hashlib
import io
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from evaluation.surface_metrics import surface_metrics
from fusion.marching_cubes import Mesh, marching_cubes
from fusion.tsdf import fuse_depth_maps
from pipeline.contracts import canonical_json, sha256_file
from scene.orbit import generate_orbit_scene
from stereo.plane_sweep import DepthMapResult, load_orbit_views, profile_depth_count, reconstruct_depth_maps


def _write_npz_deterministic(path: Path, arrays: dict[str, np.ndarray]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(arrays):
            payload = io.BytesIO()
            np.lib.format.write_array(payload, np.asarray(arrays[name]), allow_pickle=False)
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


def _profile_settings(profile: str) -> dict[str, float]:
    if profile == "smoke":
        return {
            "voxel_size_m": 0.12,
            "truncation_m": 0.24,
            "padding_m": 0.24,
            "tau_m": 0.18,
        }
    if profile == "full":
        return {
            "voxel_size_m": 0.08,
            "truncation_m": 0.18,
            "padding_m": 0.20,
            "tau_m": 0.12,
        }
    raise ValueError(f"unknown fusion profile: {profile}")


def _save_mesh(path: Path, mesh: Mesh) -> None:
    _write_npz_deterministic(
        path,
        {
            "vertices": mesh.vertices.astype(np.float32),
            "triangles": mesh.triangles.astype(np.int64),
        },
    )


def _depth_archive(path: Path, depths: dict[str, DepthMapResult]) -> None:
    arrays: dict[str, np.ndarray] = {}
    for view_id, result in depths.items():
        arrays[f"{view_id}_depth_m"] = result.depth.astype(np.float32)
        arrays[f"{view_id}_valid_mask"] = result.valid_mask.astype(np.uint8)
        arrays[f"{view_id}_cost"] = result.cost.astype(np.float32)
    _write_npz_deterministic(path, arrays)


def _fuse_and_score(
    output: Path,
    label: str,
    views: list[Any],
    depth_maps: dict[str, np.ndarray],
    valid_masks: dict[str, np.ndarray],
    truth_points: np.ndarray,
    settings: dict[str, float],
) -> dict[str, Any]:
    started = time.perf_counter()
    volume = fuse_depth_maps(
        views,
        depth_maps,
        voxel_size_m=settings["voxel_size_m"],
        truncation_m=settings["truncation_m"],
        padding_m=settings["padding_m"],
        valid_masks=valid_masks,
    )
    fusion_runtime_seconds = time.perf_counter() - started

    started = time.perf_counter()
    mesh = marching_cubes(
        volume.values,
        origin_m=volume.origin_m,
        voxel_size_m=volume.voxel_size_m,
        valid_mask=volume.weights > 0.0,
    )
    meshing_runtime_seconds = time.perf_counter() - started
    mesh_path = output / f"{label}-mesh.npz"
    _save_mesh(mesh_path, mesh)
    metrics = surface_metrics(mesh.vertices, truth_points, tau=settings["tau_m"])
    return {
        "metrics": metrics,
        "runtime_seconds": fusion_runtime_seconds + meshing_runtime_seconds,
        "fusion_runtime_seconds": fusion_runtime_seconds,
        "meshing_runtime_seconds": meshing_runtime_seconds,
        "volume_shape": list(volume.shape),
        "observed_voxel_count": volume.observed_voxel_count,
        "mesh_vertex_count": int(mesh.vertices.shape[0]),
        "mesh_triangle_count": int(mesh.triangles.shape[0]),
        "mesh_sha256": sha256_file(mesh_path),
    }


def _truth_depth_maps(views: list[Any]) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    depth_maps: dict[str, np.ndarray] = {}
    valid_masks: dict[str, np.ndarray] = {}
    for view in views:
        if view.truth_depth_m is None:
            raise ValueError("truth-depth fusion requires per-view ground truth depths")
        depth_maps[view.view_id] = view.truth_depth_m
        valid_masks[view.view_id] = np.isfinite(view.truth_depth_m) & (view.truth_depth_m > 0.0)
    return depth_maps, valid_masks


def run_orbit_fusion_profile(output: Path, profile: str) -> dict[str, Any]:
    """Fuse truth and ticket-07 MVS depths for one orbit profile and persist artifacts."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    settings = _profile_settings(profile)
    scene_root = output / "orbit-scene"
    scene_manifest = generate_orbit_scene(scene_root, profile)
    views = load_orbit_views(scene_root)
    truth_points = np.load(scene_root / scene_manifest["surface_truth"]["points_path"], allow_pickle=False)

    truth_depth_maps, truth_valid_masks = _truth_depth_maps(views)
    results = {
        "truth_depth": _fuse_and_score(
            output,
            "truth-depth",
            views,
            truth_depth_maps,
            truth_valid_masks,
            truth_points,
            settings,
        )
    }

    started = time.perf_counter()
    mvs_depths = reconstruct_depth_maps(
        views,
        depth_count=profile_depth_count(profile),
        max_neighbours=2,
        window_radius=2,
        consistency_neighbours=1,
    )
    mvs_runtime_seconds = time.perf_counter() - started
    mvs_depth_archive = output / "mvs-depth-maps.npz"
    _depth_archive(mvs_depth_archive, mvs_depths)
    mvs_depth_maps = {view_id: result.depth for view_id, result in mvs_depths.items()}
    mvs_valid_masks = {view_id: result.valid_mask for view_id, result in mvs_depths.items()}
    results["mvs_depth"] = _fuse_and_score(
        output,
        "mvs-depth",
        views,
        mvs_depth_maps,
        mvs_valid_masks,
        truth_points,
        settings,
    )
    results["mvs_depth"]["mvs_runtime_seconds"] = mvs_runtime_seconds
    results["mvs_depth"]["depth_maps_sha256"] = sha256_file(mvs_depth_archive)

    summary = {
        "schema_version": 1,
        "profile": profile,
        "scene": scene_manifest["scene"]["name"],
        "view_count": len(views),
        "truth_surface_sample_count": int(len(truth_points)),
        "settings": settings,
        "results": results,
        "artifacts": {
            "scene_manifest_sha256": sha256_file(scene_root / "manifest.json"),
            "truth_surface_points_sha256": scene_manifest["surface_truth"]["points_sha256"],
        },
    }
    (output / "fusion-metrics.json").write_bytes(canonical_json(summary))
    artifact_count, artifact_tree_sha256 = _tree_digest(
        output,
        exclude={"fusion-metrics.json"},
    )
    summary["artifacts"]["generated_artifact_count"] = artifact_count
    summary["artifacts"]["generated_artifact_tree_sha256"] = artifact_tree_sha256
    (output / "fusion-metrics.json").write_bytes(canonical_json(summary))
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--profile", choices=("smoke", "full"), required=True)
    result.add_argument("--output", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.output is None:
        with tempfile.TemporaryDirectory(prefix=f"parallax-fusion-{args.profile}.") as temporary:
            summary = run_orbit_fusion_profile(Path(temporary) / "artifacts", args.profile)
    else:
        summary = run_orbit_fusion_profile(args.output, args.profile)
    print(canonical_json(summary).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
