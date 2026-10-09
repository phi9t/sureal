#!/usr/bin/env python3
"""Execute the GPU runtime probe through a checked GPU launch plan."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

from evidence.source_snapshot import file_sha256 as sha
from insula.launch_plan import build_plan, load_runtime_lock, record_plan, render_plan
from insula.runtime_roots import current_gpu_rootfs, default_lock


HERE = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".cache/waystone/waymo-perception"
GPU_INDEX = 1


def load_gpu_runtime(cache: Path = CACHE):
    rootfs = current_gpu_rootfs(Path(cache))
    return load_runtime_lock(rootfs, default_lock(rootfs))


def gpu_probe_plan(runtime, output: Path):
    return build_plan(
        runtime,
        code=HERE,
        output=Path(output),
        gpu_index=GPU_INDEX,
        command=["/opt/waymo/bin/python", "/experiment/insula/gpu_probe.py"],
    )


def artifact_hashes(output: Path) -> dict[str, str]:
    return {path.name: sha(path) for path in output.iterdir() if path.is_file()}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if len(argv) != 1:
        raise SystemExit("usage: verify_gpu_live.py OUTPUT_DIR")
    output = Path(argv[0]).resolve()
    output.mkdir(parents=True, exist_ok=False)

    runtime = load_gpu_runtime()
    plan = gpu_probe_plan(runtime, output)
    command = render_plan(plan)
    started = datetime.now(timezone.utc).isoformat()
    begin = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True)
    (output / "probe.stdout").write_text(result.stdout)
    (output / "probe.stderr").write_text(result.stderr)
    receipt = {
        "stage": "gpu-runtime-probe",
        "launch_plan": record_plan(plan),
        "exit_code": result.returncode,
        "started_utc": started,
        "ended_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.monotonic() - begin,
        "candidate_hashes": {
            str(path.relative_to(HERE)): sha(path)
            for path in [Path(__file__), HERE / "insula/gpu_probe.py"]
        },
        "artifacts": artifact_hashes(output),
        "scope": "computation probe only; isolation and independent receipt verification pending",
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(result.stdout, result.stderr, flush=True)
    if result.returncode:
        raise RuntimeError("GPU live computation failed")


if __name__ == "__main__":
    main()
