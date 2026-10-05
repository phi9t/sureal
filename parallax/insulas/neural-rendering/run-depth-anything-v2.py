#!/usr/bin/env python3
"""Run the pinned Depth Anything V2 metric model without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
import torch
import torchvision

from depth_anything_v2.dpt import DepthAnythingV2


SOURCE_COMMIT = "a561b849ebae10a6f5ef49e26c83cbbcd36c71bf"
MODEL_CONFIG = {
    "encoder": "vits",
    "features": 64,
    "out_channels": [48, 96, 192, 384],
    "max_depth": 20.0,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("manifest input path is invalid")
    resolved_root = root.resolve(strict=True)
    try:
        resolved = (resolved_root / relative).resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (FileNotFoundError, ValueError) as error:
        raise ValueError("manifest input path escapes the input root") from error
    if not resolved.is_file():
        raise ValueError("manifest input path is not a file")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--checkpoint-bytes", type=int, required=True)
    parser.add_argument("--input-size", type=int, required=True)
    parser.add_argument("--max-depth", type=float, required=True)
    args = parser.parse_args()

    if args.checkpoint.stat().st_size != args.checkpoint_bytes:
        raise ValueError("checkpoint byte-size mismatch inside Insula")
    if sha256(args.checkpoint) != args.checkpoint_sha256:
        raise ValueError("checkpoint SHA-256 mismatch inside Insula")
    if args.input_size != 518 or args.max_depth != 20.0:
        raise ValueError("model preprocessing contract mismatch")
    if not torch.cuda.is_available():
        raise RuntimeError("Depth Anything maintained reference requires CUDA")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    input_root = args.manifest.parent
    output_root = Path("/work/output")
    predictions = output_root / "predictions"
    predictions.mkdir(parents=True, exist_ok=False)

    torch.manual_seed(260925)
    torch.cuda.manual_seed_all(260925)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    model = DepthAnythingV2(**MODEL_CONFIG)
    state = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    model = model.cuda().eval()

    for case in manifest["cases"]:
        image_path = input_path(input_root, case["image_path"])
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        expected_shape = (int(case["height"]), int(case["width"]))
        if image is None or image.shape[:2] != expected_shape:
            raise ValueError(f"input image shape mismatch: {case['id']}")
        depth = np.asarray(model.infer_image(image, input_size=args.input_size), dtype=np.float32)
        if depth.shape != expected_shape:
            raise ValueError(f"model output shape mismatch: {case['id']}")
        valid = (np.isfinite(depth) & (depth > 0.0)).astype(np.uint8)
        if not valid.all():
            raise ValueError(f"model emitted invalid metric depth: {case['id']}")
        np.save(predictions / f"{case['id']}.depth.npy", depth, allow_pickle=False)
        np.save(predictions / f"{case['id']}.valid.npy", valid, allow_pickle=False)

    shutil.copyfile("/etc/surflo-depth-anything-v2-commit", output_root / "source-commit.txt")
    shutil.copyfile("/etc/surflo-pathway-insula", output_root / "insula-manifest.txt")
    versions = {
        "source_commit": SOURCE_COMMIT,
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "cuda_runtime": torch.version.cuda,
        "device": torch.cuda.get_device_name(torch.cuda.current_device()),
    }
    (output_root / "runtime-versions.json").write_text(
        json.dumps(versions, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
