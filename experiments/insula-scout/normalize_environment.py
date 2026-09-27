#!/usr/bin/env python3
"""Remove known build-time entropy from a locked Surflo environment."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import re


NVCC_TEMP_NAME = re.compile(rb"tmpxft_[0-9A-Fa-f]{8}_")
NVCC_CANONICAL_NAME = b"tmpxft_00000000_"
GRADIO_SEED = "0" * 64


def _site_packages(environment: Path) -> Path:
    candidates = sorted(
        {
            path.resolve()
            for path in [
            *environment.glob("lib/python*/site-packages"),
            *environment.glob("lib64/python*/site-packages"),
            ]
        }
    )
    if len(candidates) != 1:
        raise ValueError(f"expected one site-packages directory, found {len(candidates)}")
    return candidates[0]


def _record_digest(path: Path) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(path.read_bytes()).digest())
    return "sha256=" + encoded.rstrip(b"=").decode("ascii")


def normalize_environment(environment: Path) -> dict[str, int]:
    site_packages = _site_packages(environment)
    modified: set[Path] = set()
    native_binary_count = 0
    for path in sorted(site_packages.rglob("*.so")):
        original = path.read_bytes()
        normalized, substitutions = NVCC_TEMP_NAME.subn(NVCC_CANONICAL_NAME, original)
        if substitutions:
            path.write_bytes(normalized)
            modified.add(path.resolve())
            native_binary_count += 1

    seed_path = site_packages / "gradio" / "hash_seed.txt"
    if seed_path.is_file() and seed_path.read_text(encoding="utf-8") != GRADIO_SEED:
        seed_path.write_text(GRADIO_SEED, encoding="utf-8")
        modified.add(seed_path.resolve())

    cache_metadata_count = 0
    for path in sorted(site_packages.glob("*.dist-info/uv_cache.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if "timestamp" not in value:
            continue
        value["timestamp"] = {"secs_since_epoch": 0, "nanos_since_epoch": 0}
        normalized = json.dumps(value, sort_keys=True, separators=(",", ":"))
        if path.read_text(encoding="utf-8") != normalized:
            path.write_text(normalized, encoding="utf-8")
            modified.add(path.resolve())
            cache_metadata_count += 1

    record_count = 0
    for record in sorted(site_packages.glob("*.dist-info/RECORD")):
        rows = list(csv.reader(io.StringIO(record.read_text(encoding="utf-8"))))
        changed = False
        for row in rows:
            if len(row) != 3:
                raise ValueError(f"malformed wheel RECORD row: {record}")
            installed_path = (site_packages / row[0]).resolve()
            if installed_path not in modified:
                continue
            row[1] = _record_digest(installed_path)
            row[2] = str(installed_path.stat().st_size)
            changed = True
        if not changed:
            continue
        output = io.StringIO(newline="")
        csv.writer(output, lineterminator="\n").writerows(rows)
        record.write_text(output.getvalue(), encoding="utf-8", newline="")
        record_count += 1

    return {
        "cache_metadata_files": cache_metadata_count,
        "modified_files": len(modified),
        "native_binaries": native_binary_count,
        "records": record_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", type=Path)
    args = parser.parse_args()
    print(json.dumps(normalize_environment(args.environment), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
