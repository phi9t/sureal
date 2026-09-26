#!/usr/bin/env python3
"""Fetch only locked downloadable assets; all lab execution remains offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
import time
import uuid
from urllib.request import urlopen

from contracts import ROOT, load_json, sha256_file


def _write_json_atomic(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _extraction_manifest(root: Path, archive: Path, declared_root: str) -> dict[str, object]:
    files = []
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        relative = path.relative_to(root).as_posix()
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError(f"unsafe extracted entry: {relative}")
        if stat.S_ISREG(mode):
            files.append({"path": relative, "size": path.stat().st_size, "sha256": sha256_file(path)})
    tree_hash = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "archive_sha256": sha256_file(archive),
        "root": declared_root,
        "file_count": len(files),
        "tree_sha256": tree_hash,
        "files": files,
    }


def extract_locked_asset(asset: dict[str, object], archive: Path, destination: Path) -> Path:
    """Safely and atomically extract a hash-verified tar asset below destination."""
    extraction = asset.get("extraction")
    if not isinstance(extraction, dict) or extraction.get("mode") != "tar":
        raise ValueError(f"asset has no supported extraction contract: {asset.get('id')}")
    asset_id = str(asset["id"])
    declared_root = str(extraction.get("root", ""))
    if not declared_root or "/" in declared_root or declared_root in {".", ".."}:
        raise ValueError(f"invalid extraction root for {asset_id}")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / asset_id
    manifest_path = destination / f"{asset_id}.extraction.json"
    if target.is_dir() and manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("archive_sha256") == sha256_file(archive):
            actual = _extraction_manifest(target, archive, declared_root)
            if actual == existing:
                return target
        raise ValueError(f"existing extraction does not match locked archive: {asset_id}")
    if os.path.lexists(target) or os.path.lexists(manifest_path):
        raise ValueError(f"incomplete extraction already exists: {asset_id}")

    staging = destination / f".{asset_id}.extracting.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle.getmembers():
                parts = Path(member.name).parts
                if (
                    not parts
                    or Path(member.name).is_absolute()
                    or ".." in parts
                    or parts[0] != declared_root
                    or member.issym()
                    or member.islnk()
                    or not (member.isdir() or member.isfile())
                ):
                    raise ValueError(f"unsafe archive member: {member.name}")
                relative_parts = parts[1:]
                if not relative_parts:
                    if not member.isdir():
                        raise ValueError(f"unsafe archive member: {member.name}")
                    continue
                output = staging.joinpath(*relative_parts)
                if member.isdir():
                    output.mkdir(parents=True, exist_ok=True)
                    continue
                output.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                if source is None:
                    raise ValueError(f"unreadable archive member: {member.name}")
                with source, output.open("xb") as stream:
                    shutil.copyfileobj(source, stream)
                output.chmod(0o644)
        manifest = _extraction_manifest(staging, archive, declared_root)
        os.replace(staging, target)
        _write_json_atomic(manifest_path, manifest)
        return target
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def promote_candidate(candidate: Path, target: Path, expected_sha256: str, asset_id: str) -> None:
    actual = sha256_file(candidate)
    if actual != expected_sha256:
        raise ValueError(
            f"hash mismatch for {asset_id}: expected {expected_sha256}, actual {actual}; "
            f"candidate retained at {candidate}"
        )
    candidate.replace(target)


def download_candidate(asset: dict[str, str], destination: Path, retries: int = 3) -> Path:
    candidate = destination / f"{asset['id']}.{asset['sha256'][:12]}.candidate"
    if candidate.is_file():
        return candidate
    partial = candidate.with_suffix(".part")
    errors: list[str] = []
    for attempt in range(1, retries + 1):
        partial.unlink(missing_ok=True)
        try:
            with urlopen(asset["source"], timeout=60) as response, partial.open("wb") as stream:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
            partial.replace(candidate)
            return candidate
        except Exception as error:
            partial.unlink(missing_ok=True)
            errors.append(f"attempt {attempt}: {type(error).__name__}: {error}")
            if attempt < retries:
                time.sleep(min(attempt, 2))
    raise RuntimeError(f"download failed for {asset['id']}: {'; '.join(errors)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--asset", action="append", dest="assets")
    args = parser.parse_args()
    destination = args.cache_root / "assets"
    destination.mkdir(parents=True, exist_ok=True)
    registry = load_json(ROOT / "assets.lock.json")["assets"]
    known = {asset["id"] for asset in registry if asset["mode"] == "download"}
    requested = set(args.assets or known)
    unknown = requested - known
    if unknown:
        raise ValueError(f"unknown downloadable assets: {sorted(unknown)}")
    failures: list[str] = []
    for asset in registry:
        if asset["mode"] != "download":
            continue
        if asset["id"] not in requested:
            continue
        target = destination / f"{asset['id']}.archive"
        if target.is_file() and sha256_file(target) == asset["sha256"]:
            if isinstance(asset.get("extraction"), dict):
                extract_locked_asset(asset, target, destination)
            continue
        try:
            candidate = download_candidate(asset, destination)
            promote_candidate(candidate, target, asset["sha256"], asset["id"])
            if isinstance(asset.get("extraction"), dict):
                extract_locked_asset(asset, target, destination)
        except Exception as error:
            failures.append(f"{asset['id']}: {error}")
    if failures:
        raise RuntimeError("fetch failures:\n" + "\n".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
