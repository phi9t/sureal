#!/usr/bin/env python3
"""Deterministic provenance for the executable benchmark source overlay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence


class ProvenanceError(ValueError):
    pass


def compute_implementation_sha256(root: Path, files: Sequence[str]) -> str:
    """Hash declared path names, byte lengths, and contents without ambiguity."""
    if not isinstance(files, list) or not files:
        raise ProvenanceError("source.implementation_files must be a non-empty list")
    if any(not isinstance(item, str) or not item for item in files):
        raise ProvenanceError("source.implementation_files entries must be paths")
    if len(set(files)) != len(files) or files != sorted(files):
        raise ProvenanceError("source.implementation_files must be unique and sorted")

    digest = hashlib.sha256()
    root = Path(root).resolve()
    for declared in files:
        candidate = Path(declared)
        path = candidate if candidate.is_absolute() else root / candidate
        path = path.resolve()
        if not path.is_file():
            raise ProvenanceError(f"implementation source is missing: {declared}")
        payload = path.read_bytes()
        label = declared.encode("utf-8")
        digest.update(len(label).to_bytes(8, "big"))
        digest.update(label)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def resolve_source_provenance(recipe_path: Path) -> dict[str, Any]:
    """Read and verify the base-plus-overlay source identity from a recipe."""
    recipe_path = Path(recipe_path).resolve()
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    source = recipe.get("source")
    if not isinstance(source, dict):
        raise ProvenanceError("source must be an object")
    base_revision = source.get("base_revision")
    implementation_sha256 = source.get("implementation_sha256")
    worktree_state = source.get("worktree_state")
    if (
        not isinstance(base_revision, str)
        or len(base_revision) != 40
        or any(character not in "0123456789abcdef" for character in base_revision)
    ):
        raise ProvenanceError("source.base_revision must be a lowercase Git SHA")
    if worktree_state != "uncommitted_overlay":
        raise ProvenanceError("source.worktree_state must be uncommitted_overlay")
    files = source.get("implementation_files")
    actual = compute_implementation_sha256(recipe_path.parent, files)
    if implementation_sha256 != actual:
        raise ProvenanceError("source implementation digest does not match executable files")
    return {
        "base_revision": base_revision,
        "implementation_sha256": actual,
        "worktree_state": worktree_state,
    }
