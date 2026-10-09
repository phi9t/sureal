"""Launch-plan helpers for evaluator and detection verification scripts."""
from pathlib import Path
import subprocess

from insula.launch_plan import build_plan, load_runtime_lock, record_plan, render_plan
from insula.runtime_roots import current_cpu_rootfs, current_metrics_rootfs, default_lock


def load_current_cpu_runtime(cache):
    rootfs = current_cpu_rootfs(cache)
    return load_runtime_lock(rootfs, default_lock(rootfs))


def load_current_metrics_runtime(cache):
    rootfs = current_metrics_rootfs(cache)
    return load_runtime_lock(rootfs, default_lock(rootfs))


def build_evaluation_plan(runtime, *, code, source, output, command):
    return build_plan(
        runtime,
        code=Path(code),
        source=None if source is None else Path(source),
        output=Path(output),
        command=command,
    )


def plan_receipt(plan):
    return record_plan(plan)


def run_evaluation_plan(plan, **kwargs):
    return subprocess.run(render_plan(plan), **kwargs)
