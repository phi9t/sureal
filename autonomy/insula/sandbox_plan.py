"""Shared bwrap sandbox plan construction for Insula entrypoints."""
from dataclasses import dataclass
from pathlib import Path

from insula.launch_plan import build_plan, plan_data, render_plan, _unchecked_runtime


@dataclass(frozen=True)
class SandboxPlan:
    argv: list[str]
    mounts: list[list[str]]
    environment: list[list[str]]
    command: list[str]


def _strings(items):
    return [str(item) for item in items]


def compose_bwrap_plan(
    *,
    unshare_flags,
    mounts_before_devices,
    mounts_after_devices=(),
    environment,
    chdir,
    command,
):
    argv = ["bwrap", *_strings(unshare_flags)]
    mounts = [_strings(mount) for mount in [*mounts_before_devices, *mounts_after_devices]]
    for mount in mounts_before_devices:
        argv.extend(_strings(mount))
    argv.extend(["--proc", "/proc", "--dev", "/dev"])
    for mount in mounts_after_devices:
        argv.extend(_strings(mount))
    argv.extend(["--clearenv"])
    for item in environment:
        argv.extend(_strings(item))
    argv.extend(["--chdir", str(chdir), "--", *_strings(command)])
    return SandboxPlan(
        argv=argv,
        mounts=mounts,
        environment=[_strings(item) for item in environment],
        command=_strings(command),
    )


def reject_overlapping_mounts(*paths):
    roots = [Path(path).resolve() for path in paths]
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            if left == right or left in right.parents or right in left.parents:
                raise ValueError("unsafe overlapping mounts")
    return roots


def live_gate_plan(root, experiment, source, output, command):
    plan = build_plan(
        _unchecked_runtime(root),
        code=experiment,
        source=source,
        output=output,
        command=command,
    )
    data = plan_data(plan)
    return SandboxPlan(
        argv=render_plan(plan),
        mounts=[_mount_to_argv(mount) for mount in data["mounts"]],
        environment=data["environment"],
        command=data["command"],
    )


def _mount_to_argv(mount):
    if mount["kind"] == "tmpfs":
        return ["--tmpfs", mount["inside_path"]]
    flag = "--dev-bind" if mount["kind"] == "dev-bind" else "--bind" if mount["mode"] == "writable" else "--ro-bind"
    return [flag, mount["host_path"], mount["inside_path"]]
