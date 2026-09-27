"""Deterministic byte manifests for resolved Python environments."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def environment_tree_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    records: list[dict[str, Any]] = []
    total_bytes = 0
    native_binaries = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            records.append({"path": relative, "symlink": os.readlink(path)})
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        record = {"path": relative, "size": size, "sha256": sha256_file(path)}
        records.append(record)
        total_bytes += size
        if ".so" in path.name:
            native_binaries.append(record)
    digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    distributions = []
    for metadata in sorted(root.glob("lib/python*/site-packages/*.dist-info/METADATA")):
        name = None
        version = None
        for line in metadata.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Name: ") and name is None:
                name = line[6:]
            elif line.startswith("Version: ") and version is None:
                version = line[9:]
            if name is not None and version is not None:
                break
        if name is not None and version is not None:
            distributions.append({"name": name, "version": version})
    return {
        "schema_version": 1,
        "root_kind": "resolved-python-environment",
        "tree_sha256": digest,
        "file_count": len(records),
        "byte_size": total_bytes,
        "files": records,
        "exclusions": ["__pycache__", "*.pyc"],
        "distributions": distributions,
        "native_binaries": native_binaries,
    }
