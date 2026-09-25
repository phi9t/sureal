#!/usr/bin/env python3
"""Blender-side renderer for one complete paired-scene episode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import shutil
import sys
import time

# Blender does not add a --python script's directory to sys.path.
PIPELINE_ROOT = Path(__file__).resolve().parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

import bpy  # type: ignore
import numpy as np

from contracts import PROFILES
from scene import (
    build_blender_scene,
    camera_specs,
    evaluated_geometry_and_surface,
    hardlink_render_tree,
    label_surface_visibility,
    object_table,
    render_views,
)


def _arguments() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--profile", choices=tuple(PROFILES), required=True)
    parser.add_argument("--device", choices=("CPU", "OPTIX"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    return parser.parse_args(arguments)


def _rewrite_records(
    records: list[dict[str, object]], source_prefix: str, destination_prefix: str
) -> list[dict[str, object]]:
    rewritten = []
    for record in records:
        item = {}
        for key, value in record.items():
            if isinstance(value, str) and value.startswith(source_prefix + "/"):
                item[key] = destination_prefix + value[len(source_prefix) :]
            else:
                item[key] = value
        rewritten.append(item)
    return rewritten


def main() -> None:
    args = _arguments()
    started = time.perf_counter()
    args.output.mkdir(parents=True, exist_ok=True)
    settings = PROFILES[args.profile]
    context_cameras, target_cameras = camera_specs(
        width=int(settings["width"]), height=int(settings["height"])
    )

    context_renderer = build_blender_scene(
        "scene_a",
        asset_root=args.asset_root,
        profile=args.profile,
        device=args.device,
        seed=args.seed,
        include_hidden=False,
    )["renderer"]
    shared_root = args.output / "shared_context"
    shared_records = render_views(shared_root, context_cameras, relative_to=args.output)
    hardlink_render_tree(shared_root, args.output / "scene_a" / "context")
    hardlink_render_tree(shared_root, args.output / "scene_b" / "context")
    context_records = _rewrite_records(shared_records, "shared_context", "scene_a/context")
    shutil.rmtree(shared_root)

    target_records: dict[str, list[dict[str, object]]] = {}
    visibility = {}
    selected_devices = set(context_renderer["devices"])
    for scene_name in ("scene_a", "scene_b"):
        renderer = build_blender_scene(
            scene_name,
            asset_root=args.asset_root,
            profile=args.profile,
            device=args.device,
            seed=args.seed,
            include_hidden=True,
        )["renderer"]
        selected_devices.update(renderer["devices"])
        scene_root = args.output / scene_name
        target_records[scene_name] = render_views(
            scene_root / "target", target_cameras, relative_to=args.output
        )
        geometry, surface = evaluated_geometry_and_surface(
            scene_name, seed=args.seed + 1
        )
        visibility[scene_name] = label_surface_visibility(
            surface,
            context_root=scene_root / "context",
            target_root=scene_root / "target",
            context_cameras=context_cameras,
            target_cameras=target_cameras,
        )
        np.savez_compressed(scene_root / "geometry.npz", **geometry)
        np.savez_compressed(scene_root / "surface.npz", **surface)
        (scene_root / "objects.json").write_text(
            json.dumps(object_table(scene_name), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    payload = {
        "views": {
            "shared_context": context_records,
            "scene_a_target": target_records["scene_a"],
            "scene_b_target": target_records["scene_b"],
        },
        "visibility": visibility,
        "renderer": {
            "blender_version": bpy.app.version_string,
            "cycles_version": bpy.app.version_string,
            "gpu": sorted(selected_devices),
            "runtime_seconds": time.perf_counter() - started,
            "peak_memory_bytes": int(peak_kib * 1024),
        },
    }
    (args.output / "renderer_job.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
