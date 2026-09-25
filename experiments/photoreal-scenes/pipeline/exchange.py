#!/usr/bin/env python3
"""Publish a validated episode into the Surflo exchange cache atomically."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from run_store import RUN_ID_RE


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_validation_report(source: Path, validation: dict[str, object]) -> None:
    artifacts = validation.get("artifact_sha256")
    if not isinstance(artifacts, dict) or not artifacts:
        raise RuntimeError("stale validation: artifact hash map is missing")
    current = {
        str(path.relative_to(source)): path
        for path in sorted(source.rglob("*"))
        if path.is_file() and path.name != "validation.json"
    }
    if set(artifacts) != set(current):
        raise RuntimeError("stale validation: episode artifact set changed")
    for relative, path in current.items():
        if artifacts.get(relative) != _sha256(path):
            raise RuntimeError(f"stale validation: artifact changed: {relative}")
    manifest_hash = _sha256(source / "manifest.json")
    if validation.get("episode_manifest_sha256") != manifest_hash:
        raise RuntimeError("stale validation: manifest digest changed")


def _link_or_copy(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        shutil.copy2(source, destination)


def publish_episode(
    source: Path,
    exchange_root: Path,
    run_id: str,
    *,
    overwrite: bool,
) -> Path:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError(f"unsafe run id: {run_id!r}")
    source = Path(source)
    if not (source / "manifest.json").is_file():
        raise FileNotFoundError(f"episode manifest is missing: {source}")
    validation_path = source / "validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if validation.get("status") != "pass":
        raise RuntimeError("refusing to publish an episode without passing validation")
    verify_validation_report(source, validation)

    episodes = Path(exchange_root) / "photoreal-scenes" / "episodes"
    episodes.mkdir(parents=True, exist_ok=True)
    destination = episodes / run_id
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"published episode already exists: {destination}; pass --overwrite to replace it"
        )
    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}.tmp-", dir=episodes))
    try:
        published_inode_targets: dict[tuple[int, int], Path] = {}
        for path in source.rglob("*"):
            relative = path.relative_to(source)
            target = staging / relative
            if path.is_symlink():
                raise RuntimeError(f"episode contains unsupported symlink: {relative}")
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                stat = path.stat()
                inode_key = (stat.st_dev, stat.st_ino)
                prior_target = published_inode_targets.get(inode_key)
                if prior_target is None:
                    _link_or_copy(path, target)
                    published_inode_targets[inode_key] = target
                else:
                    # Preserve source hard-link groups even when the first file
                    # crossed a bind-mount boundary and had to be copied.
                    os.link(prior_target, target)

        backup = destination.with_name(f".{run_id}.old-{os.getpid()}")
        if backup.exists():
            raise FileExistsError(f"publication backup already exists: {backup}")
        if destination.exists():
            destination.rename(backup)
        try:
            staging.rename(destination)
        except Exception:
            if backup.exists() and not destination.exists():
                backup.rename(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--exchange-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    destination = publish_episode(
        args.run_root / args.run_id,
        args.exchange_root,
        args.run_id,
        overwrite=args.overwrite,
    )
    print(json.dumps({"status": "pass", "episode": str(destination)}, sort_keys=True))


if __name__ == "__main__":
    main()
