#!/usr/bin/env python3
"""Validate the tracked photoreal benchmark recipe and optional cache evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from pipeline.model_lock import ModelLockError, load_model_lock, model_provenance
from pipeline.provenance import ProvenanceError, resolve_source_provenance


class RecipeError(ValueError):
    pass


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise RecipeError(f"{key} must be an object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_validation_report(path: Path, episode_root: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("status") != "pass":
        raise RecipeError("cached validation report did not pass")
    artifacts = report.get("artifact_sha256")
    if not isinstance(artifacts, dict) or not artifacts:
        raise RecipeError("cached validation report has no artifact hashes")
    current = {
        str(item.relative_to(episode_root)): item
        for item in sorted(episode_root.rglob("*"))
        if item.is_file() and item.name != "validation.json"
    }
    if set(artifacts) != set(current):
        raise RecipeError("cached episode artifact set differs from validation report")
    for relative, item in current.items():
        if artifacts.get(relative) != _sha256(item):
            raise RecipeError(f"cached episode artifact hash mismatch: {relative}")
    manifest = episode_root / "manifest.json"
    if report.get("episode_manifest_sha256") != _sha256(manifest):
        raise RecipeError("cached validation report manifest hash is stale")
    return report


def validate_recipe(
    recipe_path: Path, *, cache_root: Path, strict_artifacts: bool = False
) -> dict[str, Any]:
    recipe_path = Path(recipe_path)
    root = recipe_path.resolve().parent
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    if recipe.get("schema_version") != 1:
        raise RecipeError("schema_version must be 1")
    _mapping(recipe, "source")
    source_provenance = resolve_source_provenance(recipe_path)
    episode = _mapping(recipe, "episode")
    if episode.get("profile") != "benchmark" or episode.get("device") != "OPTIX":
        raise RecipeError("benchmark episode must use OPTIX")
    if (episode.get("width"), episode.get("height"), episode.get("samples")) != (512, 384, 256):
        raise RecipeError("benchmark episode must use 512x384 at 256 samples")
    probe = _mapping(recipe, "probe")
    if probe.get("seeds") != [0, 1, 2, 3]:
        raise RecipeError("probe seeds must be 0,1,2,3")
    if (
        probe.get("inference_mode") != "plain"
        or probe.get("num_query_points") != 100_000
        or probe.get("num_steps") != 100
    ):
        raise RecipeError("probe must use 100000 queries and 100 ODE steps")
    model_lock_reference = probe.get("model_lock")
    if not isinstance(model_lock_reference, str):
        raise RecipeError("probe.model_lock must be a path")
    model_lock_path = Path(model_lock_reference)
    if not model_lock_path.is_absolute():
        model_lock_path = root / model_lock_path
    expected_model = model_provenance(load_model_lock(model_lock_path))
    checkpoint_hash = expected_model["checkpoint_sha256"]
    expected_vggt = expected_model["vggt"]

    stages = recipe.get("stages")
    expected_stages = ["build", "fetch", "render", "validate", "probe"]
    if not isinstance(stages, list) or [stage.get("id") for stage in stages] != expected_stages:
        raise RecipeError("stages must be build, fetch, render, validate, probe")
    by_id = {stage["id"]: stage for stage in stages}
    if by_id["fetch"].get("network_mode") != "networked":
        raise RecipeError("fetch stage must be networked")
    for stage_id in ("render", "validate", "probe"):
        if by_id[stage_id].get("network_mode") != "offline":
            raise RecipeError(f"{stage_id} stage must be offline")

    renderer = _mapping(recipe, "renderer_insula")
    surflo = _mapping(recipe, "surflo_insula")
    assets = _mapping(recipe, "assets")
    evidence = _mapping(recipe, "evidence")
    references = (
        recipe.get("executor"),
        renderer.get("build"),
        renderer.get("enter"),
        renderer.get("dockerfile"),
        surflo.get("enter"),
        surflo.get("probe"),
        assets.get("lock"),
        model_lock_reference,
        recipe.get("analytic_baseline"),
        evidence.get("tracked_results"),
    )
    for relative in references:
        if not isinstance(relative, str) or not (root / relative).is_file():
            raise RecipeError(f"referenced file is missing: {relative}")
    baseline = json.loads((root / recipe["analytic_baseline"]).read_text(encoding="utf-8"))
    baseline_behavior = _mapping(baseline, "aggregate").get("baseline_behavior")
    tracked = json.loads((root / evidence["tracked_results"]).read_text(encoding="utf-8"))
    if tracked.get("status") not in {"pending", "pass"}:
        raise RecipeError("tracked results status must be pending or pass")
    if _mapping(tracked, "comparison").get("analytic_baseline_behavior") != baseline_behavior:
        raise RecipeError("tracked results analytic baseline does not match")
    if tracked.get("status") == "pass":
        tracked_episode = _mapping(tracked, "episode")
        if (
            tracked_episode.get("schema_version") != 2
            or tracked_episode.get("profile") != episode["profile"]
            or tracked_episode.get("device") != episode["device"]
        ):
            raise RecipeError("tracked pass results must use benchmark OPTIX schema-v2 evidence")
        tracked_settings = _mapping(tracked, "settings")
        if (
            tracked_settings.get("inference_mode") != probe["inference_mode"]
            or tracked_settings.get("seeds") != probe["seeds"]
            or tracked_settings.get("num_query_points") != probe["num_query_points"]
            or tracked_settings.get("num_steps") != probe["num_steps"]
        ):
            raise RecipeError("tracked pass results do not match the probe recipe")
        acceptance = _mapping(tracked, "acceptance")
        if not acceptance.get("all_four_seeds_complete") or not acceptance.get(
            "valid_measurements"
        ):
            raise RecipeError("tracked pass results must contain four valid measurements")
        runs = tracked.get("runs")
        if not isinstance(runs, list) or [run.get("seed") for run in runs] != probe["seeds"]:
            raise RecipeError("tracked pass results must contain the four recipe seeds")
        measurement_fields = (
            "observed_common_recall",
            "unobserved_common_recall",
            "exclusive_hidden_support_a",
            "exclusive_hidden_support_b",
            "completion_candidate_precision_to_either_hypothesis",
            "camera_rmse_after_observed_alignment",
            "label",
            "wall_seconds",
            "peak_vram_gib",
        )
        if any(
            not isinstance(run, dict) or any(field not in run for field in measurement_fields)
            for run in runs
        ):
            raise RecipeError("tracked pass results are missing required measurements")
        for container, field in (
            (tracked_episode, "manifest_sha256"),
            (_mapping(tracked, "artifacts"), "raw_results_sha256"),
            (_mapping(tracked, "artifacts"), "validation_report_sha256"),
        ):
            value = container.get(field)
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise RecipeError(f"tracked pass results have invalid {field}")
        tracked_model_provenance = _mapping(tracked, "model_provenance")
        if (
            tracked.get("checkpoint_sha256") != checkpoint_hash
            or tracked_model_provenance.get("checkpoint_sha256") != checkpoint_hash
        ):
            raise RecipeError("checkpoint pin does not match tracked evidence")
        if tracked_model_provenance.get("vggt") != expected_vggt:
            raise RecipeError("VGGT pins do not match tracked evidence")
        if tracked.get("source") != source_provenance:
            raise RecipeError("source overlay does not match tracked evidence")

    episode_manifest = Path(cache_root) / str(evidence.get("episode_manifest_cache_path", ""))
    episode_validation = Path(cache_root) / str(
        evidence.get("episode_validation_cache_path", "")
    )
    raw_probe = Path(cache_root) / str(evidence.get("probe_results_cache_path", ""))
    episode_present = episode_manifest.is_file()
    validation_present = episode_validation.is_file()
    probe_present = raw_probe.is_file()
    if strict_artifacts and not episode_present:
        raise RecipeError(f"episode manifest is missing: {episode_manifest}")
    if strict_artifacts and not validation_present:
        raise RecipeError(f"episode validation is missing: {episode_validation}")
    if strict_artifacts and not probe_present:
        raise RecipeError(f"probe results are missing: {raw_probe}")
    if tracked.get("status") == "pass":
        if episode_present and _sha256(episode_manifest) != _mapping(tracked, "episode").get("manifest_sha256"):
            raise RecipeError("cached episode manifest does not match tracked evidence")
        if probe_present and _sha256(raw_probe) != _mapping(tracked, "artifacts").get("raw_results_sha256"):
            raise RecipeError("cached raw probe does not match tracked evidence")
        if validation_present and _sha256(episode_validation) != _mapping(tracked, "artifacts").get(
            "validation_report_sha256"
        ):
            raise RecipeError("cached validation report does not match tracked evidence")
    if probe_present:
        raw = json.loads(raw_probe.read_text(encoding="utf-8"))
        if _mapping(raw, "settings").get("inference_mode") != probe["inference_mode"]:
            raise RecipeError("raw probe inference mode does not match recipe")
        if _mapping(raw, "checkpoint").get("sha256") != checkpoint_hash:
            raise RecipeError("checkpoint pin does not match raw probe evidence")
        if raw.get("vggt") != expected_vggt:
            raise RecipeError("VGGT pins do not match raw probe evidence")
        if raw.get("source") != source_provenance:
            raise RecipeError("source overlay does not match raw probe evidence")
    if strict_artifacts:
        _verify_validation_report(episode_validation, episode_manifest.parent)

    return {
        "status": "pass",
        "recipe": str(recipe_path.resolve()),
        "source": source_provenance,
        "stages": [{"id": stage["id"], "network_mode": stage["network_mode"]} for stage in stages],
        "probe": {
            "inference_mode": probe["inference_mode"],
            "seeds": probe["seeds"],
            "num_query_points": probe["num_query_points"],
            "num_steps": probe["num_steps"],
            "model_provenance": expected_model,
        },
        "analytic_baseline": {"baseline_behavior": baseline_behavior},
        "tracked_results_status": tracked["status"],
        "artifacts": {
            "episode_manifest": {
                "path": str(episode_manifest),
                "present": episode_present,
                "sha256": _sha256(episode_manifest) if episode_present else None,
            },
            "episode_validation": {
                "path": str(episode_validation),
                "present": validation_present,
                "sha256": _sha256(episode_validation) if validation_present else None,
            },
            "probe_results": {
                "path": str(raw_probe),
                "present": probe_present,
                "sha256": _sha256(raw_probe) if probe_present else None,
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, default=Path(__file__).with_name("recipe.json"))
    parser.add_argument(
        "--cache-root", type=Path, default=Path.home() / ".cache" / "surflo" / "insula-scout"
    )
    parser.add_argument("--strict-artifacts", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        payload = validate_recipe(
            args.recipe,
            cache_root=args.cache_root.expanduser().resolve(),
            strict_artifacts=args.strict_artifacts,
        )
    except (
        OSError,
        json.JSONDecodeError,
        ModelLockError,
        ProvenanceError,
        RecipeError,
    ) as error:
        print(f"recipe validation failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"recipe validation: {payload['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
