#!/usr/bin/env python3
"""In-Insula orchestration for offline render, validation, and promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Callable

import numpy as np

import assets
from contact_sheet import make_contact_sheet
from contracts import PROFILES, validate_device
from run_store import begin_run, promote_run
from scene import camera_specs
from schema import build_manifest_skeleton
from validator import validate_episode


ROOT = Path(__file__).resolve().parents[1]
ASSET_LOCK = ROOT / "assets.lock.json"
DEFAULT_SEED = 20260925


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def require_renderer_job(staging: Path) -> dict[str, object]:
    path = Path(staging) / "renderer_job.json"
    if not path.is_file():
        raise RuntimeError(
            "Blender did not produce its renderer success record; inspect the Blender log"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not {"views", "visibility", "renderer"}.issubset(payload):
        raise RuntimeError("Blender renderer success record is incomplete")
    return payload


def blender_command(
    *, output: Path, asset_root: Path, profile: str, device: str, seed: int
) -> list[str]:
    device = validate_device(profile, device)
    return [
        "blender",
        "--background",
        "--factory-startup",
        "--python",
        str(ROOT / "pipeline" / "blender_job.py"),
        "--",
        "--output",
        str(output),
        "--asset-root",
        str(asset_root),
        "--profile",
        profile,
        "--device",
        device,
        "--seed",
        str(seed),
    ]


def write_contact_sheets(episode: Path) -> dict[str, str]:
    sheet_root = episode / "contact_sheets"
    outputs = {
        "shared_context": sheet_root / "shared_context.png",
        "scene_a_target": sheet_root / "scene_a_target.png",
        "scene_b_target": sheet_root / "scene_b_target.png",
    }
    make_contact_sheet(
        sorted((episode / "scene_a" / "context" / "rgb").glob("*.png")),
        outputs["shared_context"],
        columns=4,
    )
    make_contact_sheet(
        sorted((episode / "scene_a" / "target" / "rgb").glob("*.png")),
        outputs["scene_a_target"],
        columns=4,
    )
    make_contact_sheet(
        sorted((episode / "scene_b" / "target" / "rgb").glob("*.png")),
        outputs["scene_b_target"],
        columns=4,
    )
    return {key: str(path.relative_to(episode)) for key, path in outputs.items()}


def _finalize_manifest(staging: Path, *, profile: str, device: str, seed: int) -> None:
    settings = PROFILES[profile]
    context_cameras, target_cameras = camera_specs(
        width=int(settings["width"]), height=int(settings["height"])
    )
    manifest = build_manifest_skeleton(
        profile=profile,
        device=device,
        seed=seed,
        asset_lock_sha256=_sha256(ASSET_LOCK),
        context_cameras=context_cameras,
        target_cameras=target_cameras,
    )
    job = require_renderer_job(staging)
    manifest["views"] = job["views"]
    for scene_name in ("scene_a", "scene_b"):
        manifest["scenes"][scene_name]["visibility"] = job["visibility"][scene_name]
    manifest["renderer"].update(job["renderer"])
    context_a = sorted((staging / "scene_a" / "context" / "rgb").glob("*.png"))
    context_b = sorted((staging / "scene_b" / "context" / "rgb").glob("*.png"))
    target_a = sorted((staging / "scene_a" / "target" / "rgb").glob("*.png"))
    target_b = sorted((staging / "scene_b" / "target" / "rgb").glob("*.png"))
    manifest["paired_context"].update(
        {
            "pixel_mismatches": 0,
            "sha256_a": _hash_files(context_a),
            "sha256_b": _hash_files(context_b),
        }
    )
    manifest["paired_targets"] = {
        "sha256_a": _hash_files(target_a),
        "sha256_b": _hash_files(target_b),
    }
    manifest["contact_sheets"] = write_contact_sheets(staging)
    (staging / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    context_matrices = [camera.matrices() for camera in context_cameras]
    target_matrices = [camera.matrices() for camera in target_cameras]
    np.savez_compressed(
        staging / "cameras.npz",
        context_intrinsics=np.stack([item[0] for item in context_matrices]).astype(np.float32),
        context_extrinsics=np.stack([item[1] for item in context_matrices]).astype(np.float32),
        target_intrinsics=np.stack([item[0] for item in target_matrices]).astype(np.float32),
        target_extrinsics=np.stack([item[1] for item in target_matrices]).astype(np.float32),
    )


def render_episode(
    *,
    profile: str,
    device: str,
    run_id: str,
    overwrite: bool,
    asset_root: Path,
    run_root: Path,
    seed: int = DEFAULT_SEED,
    runner: Callable[..., object] = subprocess.run,
) -> Path:
    device = validate_device(profile, device)
    # Offline renders only verify. Network access exists solely in `fetch`.
    assets.verify(ASSET_LOCK, Path(asset_root))
    staging, final = begin_run(Path(run_root), run_id, overwrite=overwrite)
    command = blender_command(
        output=staging,
        asset_root=Path(asset_root),
        profile=profile,
        device=device,
        seed=seed,
    )
    try:
        runner(command, check=True)
        require_renderer_job(staging)
        _finalize_manifest(staging, profile=profile, device=device, seed=seed)
        report = validate_episode(staging, asset_lock_path=ASSET_LOCK)
        (staging / "validation.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        promote_run(staging, final, validated=True, overwrite=overwrite)
    except Exception:
        print(f"staging run retained after failure: {staging}", file=sys.stderr)
        raise
    return final


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("render-draft", "render", "validate", "contact-sheets", "test")
    )
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--run-id", default="phase-a-v1")
    parser.add_argument("--device", default="OPTIX")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command in {"render-draft", "render"}:
        profile = "draft" if args.command == "render-draft" else "benchmark"
        output = render_episode(
            profile=profile,
            device=args.device,
            run_id=args.run_id,
            overwrite=args.overwrite,
            asset_root=args.asset_root,
            run_root=args.run_root,
            seed=args.seed,
        )
        print(json.dumps({"status": "pass", "episode": str(output)}, sort_keys=True))
    elif args.command == "validate":
        episode = args.run_root / args.run_id
        report = validate_episode(episode, asset_lock_path=ASSET_LOCK)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "contact-sheets":
        print(json.dumps(write_contact_sheets(args.run_root / args.run_id), sort_keys=True))
    else:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
            check=False,
        )
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
