#!/usr/bin/env python3
"""Validate the tracked Surflo scout recipe and any available cached inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ALLOWED_DRIVER_MODES = {
    "verify",
    "sample",
    "eval",
    "train-smoke",
    "synthetic-generate",
    "synthetic-probe",
    "synthetic",
    "all",
    "fetch-checkpoint",
    "photoreal-probe",
}


class RecipeError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise RecipeError(f"{key} must be an object")
    return value


def validate_recipe(
    recipe_path: Path,
    *,
    cache_root: Path,
    strict_artifacts: bool = False,
) -> dict[str, Any]:
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    if recipe.get("schema_version") != 1:
        raise RecipeError("schema_version must be 1")
    if not isinstance(recipe.get("id"), str) or not recipe["id"]:
        raise RecipeError("id must be a non-empty string")

    source = _require_mapping(recipe, "source")
    revision = source.get("revision")
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise RecipeError("source.revision must be a 40-character lowercase Git SHA")

    stages = recipe.get("stages")
    if not isinstance(stages, list) or not stages:
        raise RecipeError("stages must be a non-empty array")
    seen_ids: set[str] = set()
    normalized_stages = []
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            raise RecipeError(f"stages[{index}] must be an object")
        stage_id = stage.get("id")
        mode = stage.get("driver_mode")
        if not isinstance(stage_id, str) or not stage_id:
            raise RecipeError(f"stages[{index}].id must be a non-empty string")
        if stage_id in seen_ids:
            raise RecipeError(f"duplicate stage id: {stage_id}")
        seen_ids.add(stage_id)
        if mode not in ALLOWED_DRIVER_MODES:
            raise RecipeError(f"unknown driver_mode for {stage_id}: {mode}")
        normalized_stages.append({"id": stage_id, "driver_mode": mode})

    bundle_root = recipe_path.resolve().parent
    referenced_files = [
        recipe.get("executor"),
        _require_mapping(recipe, "insula").get("build"),
        recipe["insula"].get("enter"),
        recipe["insula"].get("dockerfile"),
        _require_mapping(_require_mapping(recipe, "inputs"), "synthetic_episode").get("generator"),
        _require_mapping(recipe, "evidence").get("released_paths"),
        recipe["evidence"].get("synthetic_probe"),
    ]
    for relative in referenced_files:
        if not isinstance(relative, str) or not (bundle_root / relative).is_file():
            raise RecipeError(f"referenced bundle file is missing: {relative}")

    checkpoint = _require_mapping(recipe["inputs"], "checkpoint")
    expected_hash = checkpoint.get("sha256")
    if not isinstance(expected_hash, str) or re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
        raise RecipeError("inputs.checkpoint.sha256 must be a lowercase SHA-256")
    checkpoint_path = cache_root / str(checkpoint.get("cache_path", ""))
    checkpoint_present = checkpoint_path.is_file()
    checkpoint_observed_hash = _sha256(checkpoint_path) if checkpoint_present else None
    if checkpoint_present and checkpoint_observed_hash != expected_hash:
        raise RecipeError(
            f"checkpoint hash mismatch: expected {expected_hash}, got {checkpoint_observed_hash}"
        )
    if strict_artifacts and not checkpoint_present:
        raise RecipeError(f"checkpoint is missing: {checkpoint_path}")

    evidence_path = bundle_root / str(recipe["evidence"]["released_paths"])
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence.get("surflo_commit") != revision:
        raise RecipeError("results.json Surflo commit does not match recipe source revision")
    if _require_mapping(evidence, "checkpoint").get("sha256") != expected_hash:
        raise RecipeError("results.json checkpoint hash does not match recipe input")

    synthetic_path = bundle_root / str(recipe["evidence"]["synthetic_probe"])
    synthetic = json.loads(synthetic_path.read_text(encoding="utf-8"))
    if synthetic.get("surflo_revision") != revision:
        raise RecipeError("synthetic_results.json Surflo revision does not match recipe source")
    if synthetic.get("checkpoint_sha256") != expected_hash:
        raise RecipeError("synthetic_results.json checkpoint hash does not match recipe input")
    episode_evidence = _require_mapping(synthetic, "episode")
    if episode_evidence.get("paired_context_pixel_mismatches") != 0:
        raise RecipeError("synthetic evidence does not have identical paired context images")
    aggregate = _require_mapping(synthetic, "aggregate")
    labels = aggregate.get("labels")
    if not isinstance(labels, list) or not labels:
        raise RecipeError("synthetic aggregate labels must be a non-empty array")

    synthetic_config = _require_mapping(recipe["inputs"], "synthetic_episode")
    episode_manifest_path = cache_root / str(synthetic_config.get("manifest_cache_path", ""))
    episode_manifest_present = episode_manifest_path.is_file()
    episode_manifest_hash = _sha256(episode_manifest_path) if episode_manifest_present else None
    expected_manifest_hash = episode_evidence.get("manifest_sha256")
    if episode_manifest_present and episode_manifest_hash != expected_manifest_hash:
        raise RecipeError(
            "synthetic episode manifest hash mismatch: "
            f"expected {expected_manifest_hash}, got {episode_manifest_hash}"
        )

    raw_probe_path = cache_root / str(recipe["evidence"].get("synthetic_probe_cache_path", ""))
    raw_probe_present = raw_probe_path.is_file()
    raw_probe_hash = _sha256(raw_probe_path) if raw_probe_present else None
    expected_raw_probe_hash = synthetic.get("raw_results_sha256")
    if raw_probe_present and raw_probe_hash != expected_raw_probe_hash:
        raise RecipeError(
            "raw synthetic probe hash mismatch: "
            f"expected {expected_raw_probe_hash}, got {raw_probe_hash}"
        )
    if strict_artifacts and not episode_manifest_present:
        raise RecipeError(f"synthetic episode manifest is missing: {episode_manifest_path}")
    if strict_artifacts and not raw_probe_present:
        raise RecipeError(f"raw synthetic probe is missing: {raw_probe_path}")

    return {
        "status": "pass",
        "recipe": str(recipe_path.resolve()),
        "id": recipe["id"],
        "source_revision": revision,
        "stages": normalized_stages,
        "artifacts": {
            "checkpoint": {
                "path": str(checkpoint_path),
                "present": checkpoint_present,
                "sha256": checkpoint_observed_hash,
            },
            "synthetic_episode_manifest": {
                "path": str(episode_manifest_path),
                "present": episode_manifest_present,
                "sha256": episode_manifest_hash,
            },
            "synthetic_probe_raw": {
                "path": str(raw_probe_path),
                "present": raw_probe_present,
                "sha256": raw_probe_hash,
            },
        },
        "evidence": {
            "synthetic_probe": {
                "baseline_behavior": aggregate.get("baseline_behavior"),
                "labels": labels,
                "paired_context_pixel_mismatches": episode_evidence[
                    "paired_context_pixel_mismatches"
                ],
            }
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, default=Path(__file__).with_name("recipe.json"))
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=Path.home() / ".cache" / "surflo" / "insula-scout",
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
    except (OSError, json.JSONDecodeError, RecipeError) as error:
        print(f"recipe validation failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"recipe validation: {payload['status']}")
        print(f"recipe: {payload['recipe']}")
        print(f"source: {payload['source_revision']}")
        print("stages: " + ", ".join(stage["id"] for stage in payload["stages"]))
        checkpoint = payload["artifacts"]["checkpoint"]
        print(f"checkpoint: {'present' if checkpoint['present'] else 'not cached'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
