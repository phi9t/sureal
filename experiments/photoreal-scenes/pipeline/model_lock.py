#!/usr/bin/env python3
"""Read and verify the single machine-readable Surflo model lock."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


class ModelLockError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model_lock(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ModelLockError("model lock schema_version must be 1")
    checkpoint = payload.get("checkpoint")
    vggt = payload.get("vggt")
    if not isinstance(checkpoint, dict) or not isinstance(vggt, dict):
        raise ModelLockError("model lock must contain checkpoint and vggt objects")
    for container, fields in (
        (checkpoint, ("repository", "filename", "cache_path", "sha256")),
        (vggt, ("repository", "revision", "cache_path", "files")),
    ):
        if any(field not in container for field in fields):
            raise ModelLockError("model lock is missing required fields")
    if re.fullmatch(r"[0-9a-f]{64}", str(checkpoint["sha256"])) is None:
        raise ModelLockError("checkpoint SHA-256 is invalid")
    if re.fullmatch(r"[0-9a-f]{40}", str(vggt["revision"])) is None:
        raise ModelLockError("VGGT revision is invalid")
    files = vggt.get("files")
    if not isinstance(files, dict) or set(files) != {"config.json", "model.safetensors"}:
        raise ModelLockError("VGGT files must pin config.json and model.safetensors")
    if any(re.fullmatch(r"[0-9a-f]{64}", str(value)) is None for value in files.values()):
        raise ModelLockError("VGGT file SHA-256 is invalid")
    return payload


def model_provenance(lock: dict[str, Any]) -> dict[str, Any]:
    return {
        "checkpoint_sha256": lock["checkpoint"]["sha256"],
        "vggt": {
            "repository": lock["vggt"]["repository"],
            "revision": lock["vggt"]["revision"],
            "files": lock["vggt"]["files"],
        },
    }


def verify_cache(lock: dict[str, Any], cache_root: Path) -> dict[str, Any]:
    cache_root = Path(cache_root)
    checkpoint = cache_root / lock["checkpoint"]["cache_path"]
    if not checkpoint.is_file() or _sha256(checkpoint) != lock["checkpoint"]["sha256"]:
        raise ModelLockError(f"checkpoint is missing or corrupt: {checkpoint}")
    vggt_root = cache_root / lock["vggt"]["cache_path"]
    revision = lock["vggt"]["revision"]
    ref = vggt_root / "refs" / "main"
    if not ref.is_file() or ref.read_text(encoding="utf-8") != revision:
        raise ModelLockError("VGGT cache ref does not match the locked revision")
    for filename, expected in lock["vggt"]["files"].items():
        path = vggt_root / "snapshots" / revision / filename
        if not path.is_file() or _sha256(path) != expected:
            raise ModelLockError(f"VGGT file is missing or corrupt: {filename}")
    return model_provenance(lock)


def _field(payload: dict[str, Any], dotted: str) -> Any:
    value: Any = payload
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ModelLockError(f"unknown model lock field: {dotted}")
        value = value[part]
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("get", "verify"))
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--field")
    parser.add_argument("--cache-root", type=Path)
    args = parser.parse_args()
    try:
        lock = load_model_lock(args.lock)
        if args.command == "get":
            if not args.field:
                raise ModelLockError("get requires --field")
            print(_field(lock, args.field))
        else:
            if args.cache_root is None:
                raise ModelLockError("verify requires --cache-root")
            print(json.dumps({"status": "pass", **verify_cache(lock, args.cache_root)}, sort_keys=True))
    except (OSError, json.JSONDecodeError, ModelLockError) as error:
        print(f"model lock verification failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
