#!/usr/bin/env python3
"""PROTOTYPE: measure stock Surflo on a paired hidden-scene episode."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import time
from typing import Sequence


@dataclass(frozen=True)
class EpisodePaths:
    root: Path
    schema_version: int
    manifest_path: Path
    manifest: dict[str, object]
    context_rgb: Path
    cameras: Path
    surface_a: Path
    surface_b: Path


def resolve_episode(episode_dir: Path) -> EpisodePaths:
    """Resolve the stable v1 layout shared by manifest schemas v1 and v2."""
    root = Path(episode_dir).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"episode manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema_version = int(manifest.get("schema_version", 1))
    if schema_version not in (1, 2):
        raise RuntimeError(f"unsupported episode schema: {schema_version}")
    paths = EpisodePaths(
        root=root,
        schema_version=schema_version,
        manifest_path=manifest_path,
        manifest=manifest,
        context_rgb=root / "scene_a" / "context" / "rgb",
        cameras=root / "cameras.npz",
        surface_a=root / "scene_a" / "surface.npz",
        surface_b=root / "scene_b" / "surface.npz",
    )
    for path in (paths.context_rgb, paths.cameras, paths.surface_a, paths.surface_b):
        if not path.exists():
            raise FileNotFoundError(f"episode input is missing: {path}")
    return paths


def target_new_mask(surface):
    """Read the v1 alias first, with the schema-v2 canonical fallback."""
    if "new_in_target" in surface:
        return surface["new_in_target"].astype(bool)
    if "target_only_visible" in surface:
        return surface["target_only_visible"].astype(bool)
    raise KeyError("surface is missing target-only visibility")


def resolve_source_provenance(recipe_path: Path) -> dict[str, object]:
    """Use the benchmark's shared digest implementation without coupling v1 probes."""
    module_path = Path(recipe_path).resolve().parent / "pipeline" / "provenance.py"
    spec = importlib.util.spec_from_file_location("photoreal_source_provenance", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load source provenance module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resolve_source_provenance(recipe_path)


def resolve_model_provenance(lock_path: Path) -> dict[str, object]:
    """Read the same model lock used for cache verification and recipe audit."""
    module_path = Path(lock_path).resolve().parent / "pipeline" / "model_lock.py"
    spec = importlib.util.spec_from_file_location("photoreal_model_lock", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model lock module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.model_provenance(module.load_model_lock(lock_path))


def classify_hypothesis(support_a: float, support_b: float) -> dict[str, float | str]:
    """Classify whether a reconstruction supports zero, one, or both hidden scenes."""
    largest = max(float(support_a), float(support_b))
    smallest = min(float(support_a), float(support_b))
    total = float(support_a) + float(support_b)
    coherence = abs(float(support_a) - float(support_b)) / max(total, 1e-12)
    minority_ratio = smallest / max(largest, 1e-12)
    if largest < 0.10:
        label = "unsupported"
    elif minority_ratio >= 0.60:
        label = "hybrid"
    elif support_a > support_b:
        label = "scene_a"
    else:
        label = "scene_b"
    return {
        "label": label,
        "coherence": coherence,
        "minority_ratio": minority_ratio,
        "total_support": total,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nearest_distances(queries, references):
    import numpy as np
    from scipy.spatial import cKDTree

    if len(queries) == 0:
        return np.empty(0, dtype=np.float64)
    if len(references) == 0:
        return np.full(len(queries), np.inf, dtype=np.float64)
    distances, _ = cKDTree(references).query(queries, k=1, workers=-1)
    return distances


def _recall(target, prediction, tau: float) -> float:
    if len(target) == 0:
        return 0.0
    return float((_nearest_distances(target, prediction) < tau).mean())


def _camera_centers_numpy(extrinsics):
    import numpy as np

    rotations = extrinsics[:, :3, :3]
    translations = extrinsics[:, :3, 3]
    return -np.einsum("nji,nj->ni", rotations, translations)


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / max(len(values), 1))


def run_probe(
    *,
    episode_dir: Path,
    checkpoint: Path,
    output_dir: Path,
    seeds: Sequence[int],
    num_query_points: int,
    num_steps: int,
    vggt_provenance: dict[str, object] | None = None,
    source_provenance: dict[str, object] | None = None,
) -> dict[str, object]:
    import numpy as np
    import torch

    from surflo import Surflo
    from surflo.metrics.eval_alignment import (
        align_pred_to_gt,
        apply_similarity,
        camera_centers_from_extrinsics,
    )

    episode = resolve_episode(episode_dir)
    episode_dir = episode.root
    checkpoint = checkpoint.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = episode.manifest_path
    manifest = episode.manifest
    if manifest["paired_context"]["pixel_mismatches"] != 0:
        raise RuntimeError("paired context is not identical; refusing an ambiguity probe")

    surface_a = np.load(episode.surface_a)
    surface_b = np.load(episode.surface_b)
    points_a = surface_a["points"].astype(np.float32)
    points_b = surface_b["points"].astype(np.float32)
    hidden_a_mask = surface_a["hidden_hypothesis"].astype(bool)
    hidden_b_mask = surface_b["hidden_hypothesis"].astype(bool)
    common_observed = points_a[
        ~hidden_a_mask & surface_a["context_visible"].astype(bool)
    ]
    common_new = points_a[
        ~hidden_a_mask & target_new_mask(surface_a)
    ]
    common_all = points_a[~hidden_a_mask]
    hidden_a = points_a[
        hidden_a_mask & surface_a["target_visible"].astype(bool)
    ]
    hidden_b = points_b[
        hidden_b_mask & surface_b["target_visible"].astype(bool)
    ]

    all_points = np.concatenate([common_all, hidden_a, hidden_b], axis=0)
    scene_diagonal = float(np.linalg.norm(all_points.max(axis=0) - all_points.min(axis=0)))
    tau = 0.01 * scene_diagonal
    hidden_a_exclusive = hidden_a[_nearest_distances(hidden_a, hidden_b) > 2.0 * tau]
    hidden_b_exclusive = hidden_b[_nearest_distances(hidden_b, hidden_a) > 2.0 * tau]
    if len(hidden_a_exclusive) == 0 or len(hidden_b_exclusive) == 0:
        raise RuntimeError("hidden hypotheses have no exclusive target-visible surfaces")

    camera_data = np.load(episode.cameras)
    gt_extrinsics = torch.from_numpy(camera_data["context_extrinsics"]).cuda().float()
    gt_camera_centers = camera_centers_from_extrinsics(gt_extrinsics)
    gt_observed = torch.from_numpy(common_observed).cuda().float()

    model = Surflo.from_checkpoint(str(checkpoint), device="cuda")
    scene = model.encode(
        episode.context_rgb,
        n_images=len(manifest["context_views"]),
        target_size=518,
        cull_radius=10.0,
    )
    pred_extrinsics = scene.extrinsics.float()
    pred_camera_centers = camera_centers_from_extrinsics(pred_extrinsics)
    latent_bytes = scene.global_state.detach().float().cpu().numpy().tobytes()
    latent_sha256 = hashlib.sha256(latent_bytes).hexdigest()

    runs = []
    for seed in seeds:
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        result = scene.reconstruct(
            mode="plain",
            num_steps=num_steps,
            num_query_points=num_query_points,
            num_points_per_batch=num_query_points,
            seed=int(seed),
            return_source=False,
            profile=True,
        )
        torch.cuda.synchronize()
        wall_seconds = time.perf_counter() - started
        prediction = result["points"].float()

        alignment = align_pred_to_gt(
            pred_points=prediction,
            gt_points=gt_observed,
            pred_cam_centers=pred_camera_centers,
            gt_cam_centers=gt_camera_centers,
            icp_iters=20,
            icp_trim_frac=0.30,
            icp_init_max_dist_frac=0.08,
            icp_final_max_dist_frac=0.01,
            voxel_frac=0.003,
        )
        aligned = alignment.pred_aligned.detach().cpu().numpy().astype(np.float32)
        np.savez_compressed(
            output_dir / f"prediction_seed_{int(seed):04d}.npz",
            points=aligned,
        )

        camera_after_um = apply_similarity(
            pred_camera_centers, alignment.s, alignment.R_um, alignment.t_um,
        )
        camera_after = camera_after_um @ alignment.R_icp.T + alignment.t_icp
        camera_rmse = float(
            torch.sqrt(((camera_after - gt_camera_centers) ** 2).sum(dim=1).mean()).item()
        )

        observed_recall = _recall(common_observed, aligned, tau)
        new_common_recall = _recall(common_new, aligned, tau)
        support_a = _recall(hidden_a_exclusive, aligned, tau)
        support_b = _recall(hidden_b_exclusive, aligned, tau)

        union_min = np.minimum(
            _nearest_distances(aligned, hidden_a),
            _nearest_distances(aligned, hidden_b),
        )
        common_distance = _nearest_distances(aligned, common_all)
        hidden_lo = np.minimum(hidden_a.min(axis=0), hidden_b.min(axis=0)) - tau
        hidden_hi = np.maximum(hidden_a.max(axis=0), hidden_b.max(axis=0)) + tau
        in_hidden_bounds = np.all((aligned >= hidden_lo) & (aligned <= hidden_hi), axis=1)
        completion_candidates = in_hidden_bounds & (common_distance > tau)
        candidate_count = int(completion_candidates.sum())
        candidate_precision = (
            float((union_min[completion_candidates] < tau).mean())
            if candidate_count else 0.0
        )
        classification = classify_hypothesis(support_a, support_b)
        timings = result.get("timings") or {}
        runs.append(
            {
                "seed": int(seed),
                "points": int(aligned.shape[0]),
                "wall_seconds": wall_seconds,
                "peak_vram_gib": float(torch.cuda.max_memory_allocated() / (1024 ** 3)),
                "camera_rmse_after_observed_alignment": camera_rmse,
                "observed_common_recall": observed_recall,
                "unobserved_common_recall": new_common_recall,
                "exclusive_hidden_support_a": support_a,
                "exclusive_hidden_support_b": support_b,
                "completion_candidate_points": candidate_count,
                "completion_candidate_precision_to_either_hypothesis": candidate_precision,
                "hypothesis": classification,
                "timings": timings,
            }
        )

    labels = [run["hypothesis"]["label"] for run in runs]
    max_hidden_support = max(
        max(run["exclusive_hidden_support_a"], run["exclusive_hidden_support_b"])
        for run in runs
    )
    if max_hidden_support < 0.10:
        baseline_behavior = "no_supported_hidden_completion"
    elif "hybrid" in labels:
        baseline_behavior = "at_least_one_hybrid_completion"
    elif len(set(labels) & {"scene_a", "scene_b"}) > 1:
        baseline_behavior = "seed_dependent_coherent_hypotheses"
    else:
        baseline_behavior = "single_dominant_hypothesis"

    payload = {
        "schema_version": 1,
        "prototype": True,
        "question": "Does stock Surflo express coherent scene-level alternatives under identical ambiguous context?",
        "source": source_provenance,
        "episode_manifest_sha256": _sha256(manifest_path),
        "checkpoint": {"path": str(checkpoint), "sha256": _sha256(checkpoint)},
        "vggt": vggt_provenance,
        "settings": {
            "inference_mode": "plain",
            "seeds": [int(seed) for seed in seeds],
            "num_query_points": num_query_points,
            "num_steps": num_steps,
            "tau_scene_diagonal_fraction": 0.01,
            "tau": tau,
            "alignment_supervision": "context cameras plus context-visible common surfaces only",
        },
        "input": {
            "context_sha256": manifest["paired_context"]["sha256_a"],
            "global_state_sha256": latent_sha256,
            "predicted_camera_centers": _camera_centers_numpy(
                pred_extrinsics.detach().cpu().numpy()
            ).tolist(),
        },
        "surface_counts": {
            "common_observed": int(len(common_observed)),
            "common_new": int(len(common_new)),
            "hidden_a_target_visible": int(len(hidden_a)),
            "hidden_b_target_visible": int(len(hidden_b)),
            "hidden_a_exclusive": int(len(hidden_a_exclusive)),
            "hidden_b_exclusive": int(len(hidden_b_exclusive)),
        },
        "runs": runs,
        "aggregate": {
            "mean_observed_common_recall": _mean([run["observed_common_recall"] for run in runs]),
            "mean_unobserved_common_recall": _mean([run["unobserved_common_recall"] for run in runs]),
            "mean_hidden_support_a": _mean([run["exclusive_hidden_support_a"] for run in runs]),
            "mean_hidden_support_b": _mean([run["exclusive_hidden_support_b"] for run in runs]),
            "labels": labels,
            "baseline_behavior": baseline_behavior,
        },
        "interpretation_guardrail": (
            "The two ground-truth hidden scenes are observationally indistinguishable from the context. "
            "This probe measures completion support and coherence, not recovery of a uniquely correct hidden scene."
        ),
    }
    results_path = output_dir / "results.json"
    results_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", default="0,1,2,3")
    parser.add_argument("--query-points", type=int, default=100_000)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--source-recipe", type=Path)
    parser.add_argument("--model-lock", type=Path)
    args = parser.parse_args()
    seeds = [int(value) for value in args.seeds.split(",") if value.strip()]
    if not seeds:
        raise SystemExit("--seeds must contain at least one integer")
    model_provenance = resolve_model_provenance(args.model_lock) if args.model_lock else None
    vggt_provenance = model_provenance["vggt"] if model_provenance else None
    source_provenance = (
        resolve_source_provenance(args.source_recipe) if args.source_recipe else None
    )
    payload = run_probe(
        episode_dir=args.episode,
        checkpoint=args.checkpoint,
        output_dir=args.output,
        seeds=seeds,
        num_query_points=args.query_points,
        num_steps=args.steps,
        vggt_provenance=vggt_provenance,
        source_provenance=source_provenance,
    )
    print(json.dumps(payload["aggregate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
