"""Shared bwrap sandbox plan construction for Insula entrypoints."""
from dataclasses import dataclass
from pathlib import Path


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
    root, experiment, source, output = reject_overlapping_mounts(root, experiment, source, output)
    return compose_bwrap_plan(
        unshare_flags=["--unshare-all", "--die-with-parent"],
        mounts_before_devices=[
            ["--ro-bind", root, "/"],
            ["--ro-bind", experiment, "/experiment"],
            ["--ro-bind", source, "/source"],
            ["--bind", output, "/outputs"],
        ],
        mounts_after_devices=[
            ["--tmpfs", "/tmp"],
        ],
        environment=[
            ["--setenv", "HOME", "/tmp/private-home"],
            ["--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin"],
            ["--setenv", "PYTHONNOUSERSITE", "1"],
            ["--setenv", "PYTHONDONTWRITEBYTECODE", "1"],
            ["--setenv", "PYTHONPATH", "/experiment"],
        ],
        chdir="/experiment",
        command=command,
    )
