#!/usr/bin/env python3
"""Fetch only locked downloadable assets; all lab execution remains offline."""

from __future__ import annotations

import argparse
from pathlib import Path
import time
from urllib.request import urlopen

from contracts import ROOT, load_json, sha256_file


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
            continue
        try:
            candidate = download_candidate(asset, destination)
            promote_candidate(candidate, target, asset["sha256"], asset["id"])
        except Exception as error:
            failures.append(f"{asset['id']}: {error}")
    if failures:
        raise RuntimeError("fetch failures:\n" + "\n".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
