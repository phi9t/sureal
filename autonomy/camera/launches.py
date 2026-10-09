"""Launch-plan helpers for camera live scripts."""
from pathlib import Path
import subprocess

from insula.launch_plan import build_plan, load_runtime_lock, record_plan, render_plan
from insula.runtime_roots import current_cpu_rootfs, default_lock


def load_current_cpu_runtime(cache):
    rootfs = current_cpu_rootfs(Path(cache))
    return load_runtime_lock(rootfs, default_lock(rootfs))


def build_camera_plan(
    runtime,
    *,
    code_root,
    output,
    command,
    source=None,
    named_inputs=None,
    writable_inputs=None,
):
    return build_plan(
        runtime,
        code=Path(code_root),
        source=None if source is None else Path(source),
        output=Path(output),
        command=command,
        named_inputs={inside: Path(host) for inside, host in (named_inputs or {}).items()},
        writable_inputs={inside: Path(host) for inside, host in (writable_inputs or {}).items()},
    )


def rendered_command(plan):
    return render_plan(plan)


def run_camera_plan(plan, **kwargs):
    return subprocess.run(render_plan(plan), **kwargs)


def plan_receipt(plan):
    return record_plan(plan)
