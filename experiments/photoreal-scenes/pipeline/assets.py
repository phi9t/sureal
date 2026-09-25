#!/usr/bin/env python3
"""Fetch and verify every file in the immutable Poly Haven asset lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import urllib.request


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_lock(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("files"), list):
        raise ValueError("asset lock must have schema_version 1 and a files list")
    return payload["files"]


def _destination(asset_root: Path, value: object) -> Path:
    relative = PurePosixPath(str(value))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"unsafe asset local_path: {value!r}")
    destination = asset_root.joinpath(*relative.parts)
    if not destination.resolve().is_relative_to(asset_root.resolve()):
        raise ValueError(f"asset local_path escapes the cache: {value!r}")
    return destination


def verify_file(path: Path, record: dict[str, object]) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"missing locked asset: {path}")
    expected_size = int(record["size_bytes"])
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        raise ValueError(
            f"size mismatch for {path}: expected {expected_size}, got {actual_size}"
        )
    expected_sha = str(record["sha256"])
    actual_sha = _sha256(path)
    if actual_sha != expected_sha:
        raise ValueError(
            f"sha256 mismatch for {path}: expected {expected_sha}, got {actual_sha}"
        )


def verify(lock_path: Path, asset_root: Path) -> int:
    records = _load_lock(lock_path)
    for record in records:
        verify_file(_destination(asset_root, record["local_path"]), record)
    return len(records)


def fetch(lock_path: Path, asset_root: Path) -> int:
    records = _load_lock(lock_path)
    for record in records:
        destination = _destination(asset_root, record["local_path"])
        try:
            verify_file(destination, record)
            continue
        except (FileNotFoundError, ValueError):
            pass
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.part-{os.getpid()}")
        try:
            with urllib.request.urlopen(str(record["source_url"]), timeout=120) as source:
                with temporary.open("wb") as target:
                    while chunk := source.read(1024 * 1024):
                        target.write(chunk)
                    target.flush()
                    os.fsync(target.fileno())
            verify_file(temporary, record)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return verify(lock_path, asset_root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "verify"))
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        count = (
            fetch(args.lock, args.asset_root)
            if args.action == "fetch"
            else verify(args.lock, args.asset_root)
        )
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps({"status": "pass", "verified_files": count}, sort_keys=True))


if __name__ == "__main__":
    main()
