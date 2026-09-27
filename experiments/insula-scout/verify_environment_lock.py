#!/usr/bin/env python3
"""Validate or describe the content-addressed B200 foundation environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from typing import Any


SCOUT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCOUT_ROOT.parent.parent
PATHWAY_ROOT = REPO_ROOT / "experiments" / "3d-pathway"
sys.path.insert(0, str(PATHWAY_ROOT / "pipeline"))

from environment_manifest import environment_tree_manifest  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _git_object(path: str) -> tuple[str, str]:
    git_environment = os.environ.copy()
    if "SURFLO_GIT_DIR" in os.environ:
        git_environment["GIT_DIR"] = os.environ["SURFLO_GIT_DIR"]
        git_environment["GIT_WORK_TREE"] = os.environ["SURFLO_GIT_WORK_TREE"]
    completed = subprocess.run(
        ["git", "ls-tree", "HEAD", "--", path],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=git_environment,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise ValueError(f"cannot resolve locked source: {path}")
    metadata, actual_path = completed.stdout.rstrip("\n").split("\t", 1)
    mode, kind, object_id = metadata.split(" ")
    if actual_path != path:
        raise ValueError(f"unexpected git tree path: {actual_path}")
    return kind, object_id


def _validate_lock() -> dict[str, Any]:
    lock = _load_json(SCOUT_ROOT / "foundation-environment.lock.json")
    if lock.get("schema_version") != 1:
        raise ValueError("unsupported foundation environment lock schema")
    if not re.fullmatch(
        r"nvidia/cuda@sha256:[0-9a-f]{64}", str(lock.get("cuda_base_image", ""))
    ):
        raise ValueError("CUDA base image must be digest-pinned")
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z", str(lock.get("ubuntu_snapshot", ""))):
        raise ValueError("Ubuntu snapshot timestamp is malformed")
    apt_packages = lock.get("apt_packages")
    if not isinstance(apt_packages, list) or not apt_packages or any(
        not isinstance(package, str) or "=" not in package for package in apt_packages
    ):
        raise ValueError("every apt package must carry an exact version")
    requirements = lock["python_requirements"]
    input_path = SCOUT_ROOT / requirements["input_path"]
    pylock_path = SCOUT_ROOT / requirements["lock_path"]
    if _sha256(input_path) != requirements["input_sha256"]:
        raise ValueError("foundation requirements input hash mismatch")
    if _sha256(pylock_path) != requirements["lock_sha256"]:
        raise ValueError("foundation Python lock hash mismatch")
    pylock = tomllib.loads(pylock_path.read_text(encoding="utf-8"))
    packages = pylock.get("packages")
    if not isinstance(packages, list) or not packages:
        raise ValueError("foundation Python lock contains no packages")
    all_artifacts_hashed = True
    artifact_count = 0
    for package in packages:
        artifacts = []
        if "archive" in package:
            artifacts.append(package["archive"])
        if "sdist" in package:
            artifacts.append(package["sdist"])
        artifacts.extend(package.get("wheels", []))
        if not artifacts:
            all_artifacts_hashed = False
        for artifact in artifacts:
            artifact_count += 1
            digest = artifact.get("hashes", {}).get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                all_artifacts_hashed = False
    if not all_artifacts_hashed:
        raise ValueError("foundation Python lock contains an unhashed artifact")
    sources = lock["source_builds"]
    expected_objects = {
        "depth-anything-3": "submodules/Depth-Anything-3",
        "diff-gaussian-rasterization-surflo": "submodules/diff-gaussian-rasterization-surflo",
        "nvdiffrast": "submodules/nvdiffrast",
    }
    for name, path in expected_objects.items():
        _, object_id = _git_object(path)
        expected = sources[name].get("commit", sources[name].get("tree"))
        if object_id != expected:
            raise ValueError(f"locked source object mismatch: {name}")
    build_scripts = lock.get("build_scripts")
    if not isinstance(build_scripts, dict) or not build_scripts:
        raise ValueError("foundation environment build scripts are not locked")
    for relative, expected_digest in build_scripts.items():
        if not isinstance(relative, str) or not re.fullmatch(
            r"[0-9a-f]{64}", str(expected_digest)
        ):
            raise ValueError("foundation environment build script lock is malformed")
        path = REPO_ROOT / relative
        if not path.is_file() or _sha256(path) != expected_digest:
            raise ValueError(f"foundation environment build script mismatch: {relative}")
    python = lock["python"]
    if (
        not re.fullmatch(r"[0-9a-f]{64}", python.get("sha256", ""))
        or int(python.get("byte_size", 0)) <= 0
    ):
        raise ValueError("standalone Python archive is not content-addressed")
    return {
        "schema_version": 1,
        "cuda_base_image": lock["cuda_base_image"],
        "ubuntu_snapshot": lock["ubuntu_snapshot"],
        "apt_packages": apt_packages,
        "python": python,
        "python_lock": {
            "path": requirements["lock_path"],
            "sha256": requirements["lock_sha256"],
            "format": "pylock.toml",
            "package_count": len(packages),
            "artifact_count": artifact_count,
            "all_artifacts_hashed": all_artifacts_hashed,
        },
        "source_builds": sources,
        "build_scripts": {
            "file_count": len(build_scripts),
            "all_hashes_match": True,
        },
        "local_install_dependency_mode": lock["local_install_dependency_mode"],
        "post_build_verification": lock["post_build_verification"],
    }


def _expected_environment() -> dict[str, Any]:
    return _load_json(PATHWAY_ROOT / "foundation-models.lock.json")["environment"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit-plan", action="store_true")
    mode.add_argument("--verify-environment", type=Path)
    mode.add_argument("--write-manifest", type=Path)
    parser.add_argument("--environment-root", type=Path)
    args = parser.parse_args()
    plan = _validate_lock()
    if args.emit_plan:
        print(json.dumps(plan, sort_keys=True))
        return 0
    if args.write_manifest and args.environment_root is None:
        parser.error("--write-manifest requires --environment-root")
    if not args.write_manifest and args.environment_root is not None:
        parser.error("--environment-root is only valid with --write-manifest")
    environment = args.verify_environment or args.environment_root
    manifest = environment_tree_manifest(environment)
    if args.write_manifest:
        args.write_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.write_manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps({key: manifest[key] for key in ("tree_sha256", "file_count", "byte_size")}, sort_keys=True))
        return 0
    expected = _expected_environment()
    for key in ("tree_sha256", "file_count", "byte_size"):
        if manifest[key] != expected[key]:
            raise ValueError(f"foundation environment {key} mismatch")
    print(json.dumps({key: manifest[key] for key in ("tree_sha256", "file_count", "byte_size")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
