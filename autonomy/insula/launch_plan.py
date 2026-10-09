"""Checked runtime locks and structured Insula launch plans."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping

from evidence.source_snapshot import file_sha256
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import (
    CURRENT_CPU_ROOTFS_NAME,
    CURRENT_CURRICULUM_ROOTFS_NAME,
    CURRENT_GPU_ROOTFS_NAME,
    CURRENT_METRICS_ROOTFS_NAME,
    CURRENT_MOTION_CLI_ROOTFS_NAME,
    CURRENT_MOTION_METRICS_ROOTFS_NAME,
    default_lock,
)


BAZEL_VERSION = "9.2.0"
BAZEL_LINUX_X86_64_SHA256 = (
    "7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694"
)
REPO = Path(__file__).resolve().parents[2]
AUTONOMY = REPO / "autonomy"

_ROOTFS_CONTENT_CACHE: set[tuple[str, str]] = set()
_DEFAULT_PATH = "/usr/local/bin:/usr/bin:/bin"
_GPU_PATH = "/opt/waymo/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"
_MODULE_ENVIRONMENT = {
    "HOME",
    "PATH",
    "PYTHONNOUSERSITE",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONPATH",
    "LD_LIBRARY_PATH",
    "CUDA_VISIBLE_DEVICES",
}
_NAMED_INPUT_PREFIXES = ("/tmp", "/opt", "/srv", "/mnt")
_GPU_DRIVER_PREFIXES = (
    "libcuda.so",
    "libnvidia-ptxjitcompiler.so",
    "libnvidia-nvvm.so",
)
_GPU_CONTROL_DEVICES = {
    "/dev/nvidiactl",
    "/dev/nvidia-uvm",
    "/dev/nvidia-uvm-tools",
    "/dev/nvidia-modeset",
}
_DEFAULT_GPU_DRIVER_LIBRARY_DIRS = (Path("/usr/lib/x86_64-linux-gnu"),)
_GPU_DRIVER_INFO_ROOT = Path("/proc/driver/nvidia/gpus")
_LEGACY_COMMAND_ARITY = {
    "--unshare-all": 0,
    "--die-with-parent": 0,
    "--clearenv": 0,
    "--proc": 1,
    "--dev": 1,
    "--tmpfs": 1,
    "--chdir": 1,
    "--ro-bind": 2,
    "--bind": 2,
    "--dev-bind": 2,
    "--setenv": 2,
    "--symlink": 2,
}
_SPLIT_RUNTIME_MASKED_ENTRIES = {
    "dev",
    "driver",
    "experiment",
    "outputs",
    "proc",
    "source",
    "tmp",
}
class RuntimeLockError(ValueError):
    """Raised when a runtime lock is missing or does not match its rootfs."""


class PlanError(ValueError):
    """Raised when a launch plan violates mount or environment rules."""


@dataclass(frozen=True)
class RuntimeLock:
    rootfs: Path
    lock_path: Path | None
    data: dict
    form: str
    lock_sha256: str


@dataclass(frozen=True)
class Mount:
    role: str
    kind: str
    inside_path: str
    mode: str
    host_path: Path | None = None
    phase: str = "before_devices"
    digest: str | None = None
    symlink_target: str | None = None


@dataclass(frozen=True)
class LaunchPlan:
    runtime: RuntimeLock
    mounts: tuple[Mount, ...]
    environment: tuple[tuple[str, str, str], ...]
    working_directory: str
    command: tuple[str, ...]
    unshare_flags: tuple[str, ...]
    gpu: "GPURequest | None" = None
    source_snapshot_digest: str | None = None
    named_input_digests: tuple[tuple[str, str], ...] = ()
    allow_readonly_inputs_cover_output: bool = False
    clear_environment: bool = True


@dataclass(frozen=True)
class GPURequest:
    requested_index: int
    device_minor: int
    device_uuid: str


@dataclass(frozen=True)
class _RecipeSpec:
    fields: Mapping[str, Path]
    bazel: bool


@dataclass(frozen=True)
class _ImageSpec:
    fields: Mapping[str, Path]
    parent_image_id: str | None = None


def load_runtime_lock(rootfs: Path, lock_path: Path | None = None) -> RuntimeLock:
    """Load and fully check a runtime lock before a launch plan exists."""
    rootfs = Path(rootfs).resolve()
    lock_path = default_lock(rootfs) if lock_path is None else Path(lock_path).resolve()
    try:
        raw = lock_path.read_text()
    except FileNotFoundError as exc:
        raise RuntimeLockError(f"runtime lock missing: {lock_path}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeLockError(f"runtime lock JSON: {exc}") from exc
    if data.get("schema_version") != 1:
        raise RuntimeLockError("schema_version: expected 1")

    lock_sha256 = file_sha256(lock_path)
    if "recipe_hashes" in data:
        form = "image"
        _check_image_lock(rootfs, data)
    else:
        form = "recipe-digest"
        _check_recipe_lock(rootfs, data)
    _check_rootfs_content(rootfs, data, lock_sha256)
    return RuntimeLock(
        rootfs=rootfs,
        lock_path=lock_path,
        data=dict(data),
        form=form,
        lock_sha256=lock_sha256,
    )


def load_default_runtime_lock(rootfs: Path) -> RuntimeLock:
    """Load a root filesystem's runtime lock from its default lock path."""
    rootfs = Path(rootfs)
    return load_runtime_lock(rootfs, default_lock(rootfs))


def build_plan(
    runtime: RuntimeLock,
    *,
    code: Path,
    output: Path,
    command: Iterable[object],
    source: Path | None = None,
    named_inputs: Mapping[str, Path] | None = None,
    named_input_digests: Mapping[str, str] | None = None,
    writable_inputs: Mapping[str, Path] | None = None,
    extra_environment: Mapping[str, object] | None = None,
    gpu_index: int | None = None,
    source_snapshot_digest: str | None = None,
    allow_readonly_inputs_cover_output: bool = False,
    split_runtime_root: bool = False,
) -> LaunchPlan:
    mounts = [*_runtime_mounts(runtime, split_runtime_root)]
    mounts.append(Mount("code", "bind", "/experiment", "read_only", Path(code)))
    if source is not None:
        mounts.append(Mount("source", "bind", "/source", "read_only", Path(source)))
    mounts.append(Mount("output", "bind", "/outputs", "writable", Path(output)))
    for inside, host in (named_inputs or {}).items():
        inside_path = str(PurePosixPath(inside))
        _validate_named_input_path(inside_path)
        mounts.append(Mount(f"input:{inside_path}", "bind", inside_path, "read_only", Path(host)))
    for inside, host in (writable_inputs or {}).items():
        inside_path = str(PurePosixPath(inside))
        _validate_named_input_path(inside_path)
        mounts.append(Mount(f"input:{inside_path}", "bind", inside_path, "writable", Path(host)))

    environment = [
        ("--setenv", "HOME", "/tmp/private-home"),
        ("--setenv", "PATH", _DEFAULT_PATH),
        ("--setenv", "PYTHONNOUSERSITE", "1"),
        ("--setenv", "PYTHONDONTWRITEBYTECODE", "1"),
        ("--setenv", "PYTHONPATH", "/experiment"),
    ]
    if gpu_index is not None:
        gpu_mounts, gpu_environment, gpu = _gpu_mounts_environment_and_request(gpu_index)
        mounts.extend(gpu_mounts)
        environment = [
            item for item in environment if not (item[0] == "--setenv" and item[1] == "PATH")
        ]
        environment.extend(gpu_environment)
    else:
        gpu = None
    environment = _merge_environment(environment, extra_environment)
    mounts.append(Mount("tmp", "tmpfs", "/tmp", "writable", None, "after_devices"))
    plan = _assemble_plan(
        runtime,
        mounts=mounts,
        environment=environment,
        command=command,
        working_directory="/experiment",
        unshare_flags=("--unshare-all", "--die-with-parent"),
        gpu=gpu,
        source_snapshot_digest=source_snapshot_digest,
        named_input_digests=named_input_digests,
        allow_readonly_inputs_cover_output=allow_readonly_inputs_cover_output,
    )
    return plan


def build_custom_plan(
    runtime: RuntimeLock,
    *,
    mounts: Iterable[Mount],
    environment: Mapping[str, object],
    command: Iterable[object],
    working_directory: str,
    unshare_flags: Iterable[object],
    gpu_index: int | None = None,
    gpu: GPURequest | None = None,
    named_input_digests: Mapping[str, str] | None = None,
    allow_readonly_inputs_cover_output: bool = False,
) -> LaunchPlan:
    """Build a validated launch plan for callers with non-standard mount layouts."""
    if gpu_index is not None and gpu is not None:
        raise PlanError("gpu_index and gpu request are mutually exclusive")
    plan_mounts = list(mounts)
    environment_items = _environment_from_mapping(environment)
    if gpu_index is not None:
        gpu_mounts, gpu_environment, gpu = _gpu_mounts_environment_and_request(gpu_index)
        plan_mounts.extend(gpu_mounts)
        environment_items = [
            item for item in environment_items if not (item[0] == "--setenv" and item[1] == "PATH")
        ]
        environment_items.extend(gpu_environment)
    elif gpu is None:
        gpu = None
    return _assemble_plan(
        runtime,
        mounts=plan_mounts,
        environment=environment_items,
        command=command,
        working_directory=working_directory,
        unshare_flags=unshare_flags,
        gpu=gpu,
        named_input_digests=named_input_digests,
        allow_readonly_inputs_cover_output=allow_readonly_inputs_cover_output,
    )


def gpu_mounts_environment_and_request(gpu_index: int) -> tuple[list[Mount], dict[str, str], GPURequest]:
    """Return validated GPU mounts, environment, and identity for a requested GPU."""
    mounts, environment, gpu = _gpu_mounts_environment_and_request(gpu_index)
    return mounts, {name: value for _, name, value in environment}, gpu


def plan_data(plan: LaunchPlan) -> dict:
    """Return a data view of a launch plan without rendering argv."""
    data = {
        "runtime": {
            "rootfs": str(plan.runtime.rootfs),
            "lock": str(plan.runtime.lock_path) if plan.runtime.lock_path is not None else None,
            "lock_sha256": plan.runtime.lock_sha256,
            "form": plan.runtime.form,
        },
        "mounts": [_plan_mount_data(plan, mount, include_host=True) for mount in plan.mounts],
        "devices": [_mount_data(mount, include_host=True) for mount in plan.mounts if mount.kind == "dev-bind"],
        "environment": [list(item) for item in plan.environment],
        "working_directory": plan.working_directory,
        "command": list(plan.command),
        "unshare_flags": list(plan.unshare_flags),
        "clear_environment": plan.clear_environment,
    }
    if plan.gpu is not None:
        data["gpu"] = _gpu_request_data(plan.gpu, include_minor=False)
    return data


def render_plan(plan: LaunchPlan) -> list[str]:
    """Render a launch plan to bwrap argv at the execution boundary."""
    argv = ["bwrap", *plan.unshare_flags]
    for mount in plan.mounts:
        if mount.phase == "before_devices" and mount.role != "tmp" and not _mount_under_tmp(mount):
            argv.extend(_render_mount(mount))
    for mount in plan.mounts:
        if mount.role == "tmp":
            argv.extend(_render_mount(mount))
    for mount in plan.mounts:
        if mount.phase == "before_devices" and _mount_under_tmp(mount):
            argv.extend(_render_mount(mount))
    argv.extend(["--proc", "/proc", "--dev", "/dev"])
    for mount in plan.mounts:
        if mount.phase == "after_devices" and mount.role != "tmp":
            argv.extend(_render_mount(mount))
    if plan.clear_environment:
        argv.append("--clearenv")
    for item in plan.environment:
        argv.extend(item)
    argv.extend(["--chdir", plan.working_directory, "--", *plan.command])
    return [str(item) for item in argv]


def run_plan(plan: LaunchPlan, **kwargs) -> subprocess.CompletedProcess:
    """Run a rendered launch plan as a subprocess."""
    return subprocess.run(render_plan(plan), **kwargs)


def with_mounts(
    plan: LaunchPlan,
    *,
    before_devices: Iterable[Mount] = (),
    after_devices: Iterable[Mount] = (),
    command: Iterable[object] | None = None,
) -> LaunchPlan:
    """Return a plan with extra mounts, reusing launch-plan validation."""
    if not isinstance(plan, LaunchPlan):
        raise PlanError("launch plan required")
    before = [mount for mount in plan.mounts if mount.phase == "before_devices"]
    after = [mount for mount in plan.mounts if mount.phase != "before_devices"]
    return _assemble_plan(
        plan.runtime,
        mounts=[
            *before,
            *[replace(mount, phase="before_devices") for mount in before_devices],
            *after,
            *[replace(mount, phase="after_devices") for mount in after_devices],
        ],
        environment=plan.environment,
        command=plan.command if command is None else command,
        working_directory=plan.working_directory,
        unshare_flags=plan.unshare_flags,
        gpu=plan.gpu,
        source_snapshot_digest=plan.source_snapshot_digest,
        named_input_digests=dict(plan.named_input_digests),
        allow_readonly_inputs_cover_output=plan.allow_readonly_inputs_cover_output,
        clear_environment=plan.clear_environment,
    )


def record_plan(plan: LaunchPlan) -> dict:
    """Return the host-path-free receipt record for a launch plan."""
    record = {
        "runtime": {
            "lock_sha256": plan.runtime.lock_sha256,
            "form": plan.runtime.form,
        },
        "mounts": [_record_mount(plan, mount) for mount in plan.mounts if mount.kind != "dev-bind"],
        "devices": [_record_device(mount) for mount in plan.mounts if _record_device_mount(plan, mount)],
        "environment": {item[1]: item[2] for item in plan.environment if item[0] == "--setenv"},
        "working_directory": plan.working_directory,
        "command": list(plan.command),
        "unshare_flags": list(plan.unshare_flags),
        "clear_environment": plan.clear_environment,
    }
    if plan.gpu is not None:
        record["gpu"] = _gpu_request_data(plan.gpu, include_minor=True)
    return record


def gpu_driver_hashes_from_plan_record(record: Mapping[str, object]) -> dict[str, str]:
    """Return role-keyed GPU driver digests recorded in a launch plan."""
    plan_record = _extract_launch_plan_record(record)
    if plan_record is None:
        raise ValueError("launch plan record required")
    mounts = plan_record.get("mounts")
    if not isinstance(mounts, list):
        raise ValueError("launch plan mounts required")
    hashes: dict[str, str] = {}
    for mount in mounts:
        if not isinstance(mount, Mapping):
            raise ValueError("launch plan mount record required")
        role = mount.get("role")
        if not isinstance(role, str) or not role.startswith("gpu-driver:"):
            continue
        digest = mount.get("digest")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError(f"{role}: GPU driver digest required")
        if role in hashes:
            raise ValueError(f"{role}: duplicate GPU driver digest")
        hashes[role] = digest
    return hashes


def gpu_driver_paths_from_plan_record(record: Mapping[str, object]) -> dict[str, tuple[Path, str]]:
    """Return current host driver paths checked against a launch-plan record."""
    by_role = gpu_driver_hashes_from_plan_record(record)
    if not by_role:
        return {}
    paths = {path.name: path for path in _gpu_driver_paths()}
    result: dict[str, tuple[Path, str]] = {}
    for role, digest in by_role.items():
        name = role.split(":", 1)[1]
        path = paths.get(name)
        if path is None:
            raise ValueError(f"{role}: GPU driver library not found")
        actual = _mounted_file_sha256(path, role)
        if actual != digest:
            raise ValueError(f"{role}: GPU driver digest differs")
        result[name] = (path, digest)
    return result


def verify_gpu_driver_hashes_from_plan_record(record: Mapping[str, object]) -> dict[str, str]:
    """Verify recorded GPU driver digests and return the role-keyed pins."""
    gpu_driver_paths_from_plan_record(record)
    return gpu_driver_hashes_from_plan_record(record)


def read_receipt_mounts(
    receipt: Mapping[str, object],
    *,
    include_digests: bool = False,
    require_cleared_environment: bool = False,
    require_python_worker: bool = False,
) -> dict[str, dict[str, object]]:
    """Return launch mounts by inside path from a plan record or old command receipt."""
    plan_record = _extract_launch_plan_record(receipt)
    if plan_record is not None:
        _validate_plan_record_requirements(
            plan_record,
            require_cleared_environment=require_cleared_environment,
            require_python_worker=require_python_worker,
        )
        return _read_plan_record_mounts(plan_record)
    command = _extract_legacy_receipt_command(receipt)
    parsed = _parse_legacy_receipt_command(
        command,
        require_cleared_environment=require_cleared_environment,
        require_python_worker=require_python_worker,
    )
    return _legacy_receipt_mounts(command, parsed["options"], include_digests=include_digests)


def read_receipt_mount_sequence(
    receipt: Mapping[str, object],
    *,
    include_digests: bool = False,
    require_cleared_environment: bool = False,
    require_python_worker: bool = False,
) -> list[dict[str, object]]:
    """Return receipt mounts in recorded/rendered order, preserving legacy duplicates."""
    plan_record = _extract_launch_plan_record(receipt)
    if plan_record is not None:
        _validate_plan_record_requirements(
            plan_record,
            require_cleared_environment=require_cleared_environment,
            require_python_worker=require_python_worker,
        )
        mounts = plan_record.get("mounts")
        if not isinstance(mounts, list):
            raise ValueError("launch plan mounts required")
        return list(_read_plan_record_mounts({"mounts": mounts}).values())
    command = _extract_legacy_receipt_command(receipt)
    parsed = _parse_legacy_receipt_command(
        command,
        require_cleared_environment=require_cleared_environment,
        require_python_worker=require_python_worker,
    )
    return _legacy_receipt_mount_sequence(parsed["options"], include_digests=include_digests)


def legacy_receipt_command_argv(command: list[str]) -> list[str]:
    """Return the worker argv from an old rendered command receipt."""
    parsed = _parse_legacy_receipt_command(command, require_python_worker=True)
    return list(parsed["argv"])


def inspect_legacy_receipt_command(command: list[str]) -> tuple[int, list[str], list[tuple[str, tuple[str, ...]]]]:
    """Parse an old command receipt for legacy receipt readers."""
    parsed = _parse_legacy_receipt_command(command, require_python_worker=True)
    return parsed["separator"], list(parsed["argv"]), list(parsed["options"])


def _assemble_plan(
    runtime: RuntimeLock,
    *,
    mounts: Iterable[Mount],
    environment: Iterable[tuple[object, object, object]],
    command: Iterable[object],
    working_directory: str,
    unshare_flags: Iterable[object],
    gpu: GPURequest | None = None,
    allow_readonly_inputs_cover_output: bool = False,
    source_snapshot_digest: str | None = None,
    named_input_digests: Mapping[str, str] | None = None,
    clear_environment: bool = True,
) -> LaunchPlan:
    mount_tuple = tuple(mounts)
    _validate_mounts(
        mount_tuple,
        allow_readonly_inputs_cover_output=allow_readonly_inputs_cover_output,
    )
    return LaunchPlan(
        runtime=runtime,
        mounts=mount_tuple,
        environment=tuple((str(a), str(b), str(c)) for a, b, c in environment),
        working_directory=str(working_directory),
        command=tuple(str(item) for item in command),
        unshare_flags=tuple(str(flag) for flag in unshare_flags),
        gpu=gpu,
        source_snapshot_digest=source_snapshot_digest,
        named_input_digests=_normalise_named_input_digests(mount_tuple, named_input_digests),
        allow_readonly_inputs_cover_output=allow_readonly_inputs_cover_output,
        clear_environment=clear_environment,
    )


def _extract_launch_plan_record(receipt: Mapping[str, object]) -> Mapping[str, object] | None:
    if not isinstance(receipt, Mapping):
        raise ValueError("receipt record required")
    launch_plan = receipt.get("launch_plan")
    if isinstance(launch_plan, Mapping):
        return launch_plan
    if {"runtime", "mounts", "environment", "command"} <= set(receipt):
        return receipt
    return None


def _read_plan_record_mounts(record: Mapping[str, object]) -> dict[str, dict[str, object]]:
    mounts = record.get("mounts")
    if not isinstance(mounts, list):
        raise ValueError("launch plan mounts required")
    by_inside: dict[str, dict[str, object]] = {}
    for mount in mounts:
        if not isinstance(mount, Mapping):
            raise ValueError("launch plan mount record required")
        inside = mount.get("inside_path")
        mode = mount.get("mode")
        if not isinstance(inside, str) or not inside.startswith("/") or not isinstance(mode, str):
            raise ValueError("launch plan mount inside path and mode required")
        if inside in by_inside:
            raise ValueError(f"duplicate receipt mount {inside}")
        data = {
            "inside_path": inside,
            "mode": mode,
        }
        for field in ("role", "kind", "digest"):
            if field in mount:
                value = mount[field]
                if not isinstance(value, str):
                    raise ValueError(f"launch plan mount {field} must be a string")
                data[field] = value
        by_inside[inside] = data
    return by_inside


def _validate_plan_record_requirements(
    record: Mapping[str, object],
    *,
    require_cleared_environment: bool,
    require_python_worker: bool,
) -> None:
    if require_cleared_environment:
        environment = record.get("environment")
        unshare_flags = record.get("unshare_flags")
        if (
            not isinstance(environment, Mapping)
            or environment.get("PYTHONPATH") != "/experiment"
            or record.get("clear_environment") is not True
            or not isinstance(unshare_flags, list)
            or "--unshare-all" not in unshare_flags
            or "--die-with-parent" not in unshare_flags
        ):
            raise ValueError("launch plan record cleared environment required")
    if require_python_worker:
        command = record.get("command")
        if (
            not isinstance(command, list)
            or len(command) < 2
            or command[0] not in {"python", "/opt/waymo/bin/python"}
            or not isinstance(command[1], str)
            or not Path(command[1]).is_absolute()
            or not command[1].endswith(".py")
        ):
            raise ValueError("launch plan record Python worker required")


def _extract_legacy_receipt_command(receipt: Mapping[str, object]) -> list[str]:
    command = receipt.get("command")
    if isinstance(command, list):
        return command
    checks = receipt.get("checks")
    if isinstance(checks, list) and len(checks) == 1 and isinstance(checks[0], Mapping):
        command = checks[0].get("command")
        if isinstance(command, list):
            return command
    raise ValueError("receipt command or launch plan required")


def _parse_legacy_receipt_command(
    command: list[str],
    *,
    require_cleared_environment: bool = False,
    require_python_worker: bool = False,
) -> dict[str, object]:
    if (
        not isinstance(command, list)
        or not command
        or command[0] != "bwrap"
        or any(not isinstance(item, str) or not item for item in command)
        or command.count("--") != 1
    ):
        raise ValueError("literal legacy bwrap command required")
    separator = command.index("--")
    flags = set()
    options = []
    index = 1
    while index < separator:
        option = command[index]
        arity = _LEGACY_COMMAND_ARITY.get(option)
        if arity is None or index + arity >= separator:
            raise ValueError("declared legacy bwrap options required")
        values = tuple(command[index + 1 : index + 1 + arity])
        options.append((option, values))
        flags.add(option)
        index += arity + 1
    argv = command[separator + 1 :]
    if require_cleared_environment and not {"--unshare-all", "--clearenv"} <= flags:
        raise ValueError("legacy receipt cleared namespace required")
    if require_python_worker and (
        not {"--unshare-all", "--die-with-parent"} <= flags
        or len(argv) < 2
        or argv[0] not in {"python", "/opt/waymo/bin/python"}
        or not Path(argv[1]).is_absolute()
        or not argv[1].endswith(".py")
    ):
        raise ValueError("isolated namespace and declared original Python worker required")
    return {"separator": separator, "argv": argv, "options": options, "flags": flags}


def _legacy_receipt_mounts(
    command: list[str],
    options: Iterable[tuple[str, tuple[str, ...]]],
    *,
    include_digests: bool,
) -> dict[str, dict[str, object]]:
    by_inside: dict[str, dict[str, object]] = {}
    for mount in _legacy_receipt_mount_sequence(options, include_digests=include_digests):
        inside = mount["inside_path"]
        if not isinstance(inside, str):
            raise ValueError("legacy receipt mount inside path required")
        by_inside[inside] = mount
    if not by_inside:
        raise ValueError("legacy receipt mounts required")
    return by_inside


def _legacy_receipt_mount_sequence(
    options: Iterable[tuple[str, tuple[str, ...]]],
    *,
    include_digests: bool,
) -> list[dict[str, object]]:
    mounts = []
    for option, values in options:
        mount = _legacy_mount_from_option(option, values, include_digests=include_digests)
        if mount is not None:
            mounts.append(mount)
    return mounts


def _legacy_mount_from_option(
    option: str,
    values: tuple[str, ...],
    *,
    include_digests: bool,
) -> dict[str, object] | None:
    if option in {"--proc", "--dev", "--setenv", "--chdir"}:
        return None
    if option == "--tmpfs":
        inside = values[0]
        return {"inside_path": inside, "mode": "writable", "kind": "tmpfs", "role": _legacy_role(inside)}
    if option not in {"--ro-bind", "--bind", "--dev-bind"}:
        return None
    host, inside = values
    mode = "read_only" if option == "--ro-bind" else "writable"
    kind = "dev-bind" if option == "--dev-bind" else "bind"
    mount: dict[str, object] = {
        "inside_path": inside,
        "mode": mode,
        "kind": kind,
        "role": _legacy_role(inside),
        "host_path": host,
    }
    if include_digests and mode == "read_only" and kind == "bind" and inside != "/":
        host_path = Path(host)
        if host_path.exists():
            mount["digest"] = _content_digest(host_path)
    return mount


def _legacy_role(inside_path: str) -> str:
    roles = {
        "/": "runtime",
        "/experiment": "code",
        "/source": "source",
        "/outputs": "output",
        "/tmp": "tmp",
    }
    if inside_path in roles:
        return roles[inside_path]
    return f"input:{inside_path}"


def _plan_tmp_mounts_index(command: list[str], devices_at: int) -> int:
    index = 1
    while index < devices_at:
        option = command[index]
        arity = _LEGACY_COMMAND_ARITY.get(option)
        if arity is None:
            raise PlanError("rendered launch plan option required")
        target = command[index + arity] if arity else None
        if option in {"--ro-bind", "--bind", "--dev-bind", "--tmpfs", "--symlink"} and (
            target == "/tmp" or str(target).startswith("/tmp/")
        ):
            return index
        index += 1 + arity
    return devices_at


def _plan_device_insertion_index(command: list[str], separator: int) -> int:
    for index in range(1, separator - 1):
        if command[index : index + 2] == ["--proc", "/proc"]:
            return index
    raise PlanError("rendered launch plan device mounts required")


def _render_ordered_record_mounts(mounts: Iterable[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Recorded mounts in render_plan order."""

    def group(mount: Mapping[str, object]) -> int:
        if mount.get("phase") == "after_devices" and mount.get("role") != "tmp":
            return 3
        if mount.get("role") == "tmp":
            return 1
        if str(mount.get("inside_path", "")).startswith("/tmp/"):
            return 2
        return 0

    return sorted(mounts, key=group)


def _runtime_mounts(runtime: RuntimeLock, split_runtime_root: bool) -> list[Mount]:
    if type(split_runtime_root) is not bool:
        raise PlanError("split_runtime_root: boolean required")
    if not split_runtime_root:
        return [Mount("runtime", "bind", "/", "read_only", runtime.rootfs)]
    mounts = []
    for entry in sorted(runtime.rootfs.iterdir(), key=lambda path: path.name):
        if entry.name in _SPLIT_RUNTIME_MASKED_ENTRIES:
            continue
        inside_path = "/" + _safe_rootfs_entry_name(entry.name)
        if entry.is_symlink():
            mounts.append(
                Mount(
                    f"runtime-entry:{entry.name}",
                    "symlink",
                    inside_path,
                    "read_only",
                    symlink_target=_safe_symlink_target(os.readlink(entry)),
                )
            )
        else:
            mounts.append(Mount(f"runtime-entry:{entry.name}", "bind", inside_path, "read_only", entry))
    if not mounts:
        raise PlanError("split_runtime_root: runtime rootfs has no mountable entries")
    return mounts


def _safe_rootfs_entry_name(name: str) -> str:
    if not name or name in {".", ".."} or "/" in name or "\x00" in name:
        raise PlanError(f"{name!r}: runtime rootfs entry name must be a safe path component")
    return name


def _safe_symlink_target(target: str) -> str:
    if not isinstance(target, str) or not target or "\x00" in target:
        raise PlanError("symlink target must be non-empty text")
    return target


def _check_recipe_lock(rootfs: Path, data: Mapping[str, object]) -> None:
    spec = _recipe_spec_for(rootfs)
    for field, path in spec.fields.items():
        _require_field(data, field)
        expected = file_sha256(path)
        if data[field] != expected:
            raise RuntimeLockError(f"{field}: expected {expected}, found {data[field]!r}")
    if spec.bazel:
        _require_field(data, "bazel_version")
        if data["bazel_version"] != BAZEL_VERSION:
            raise RuntimeLockError(
                f"bazel_version: expected {BAZEL_VERSION}, found {data['bazel_version']!r}"
            )
        _require_field(data, "bazel_linux_x86_64_sha256")
        if data["bazel_linux_x86_64_sha256"] != BAZEL_LINUX_X86_64_SHA256:
            raise RuntimeLockError(
                "bazel_linux_x86_64_sha256: "
                f"expected {BAZEL_LINUX_X86_64_SHA256}, "
                f"found {data['bazel_linux_x86_64_sha256']!r}"
            )


def _check_image_lock(rootfs: Path, data: Mapping[str, object]) -> None:
    spec = _image_spec_for(rootfs)
    _require_field(data, "image_id")
    if not isinstance(data["image_id"], str) or not data["image_id"]:
        raise RuntimeLockError("image_id: non-empty image id required")
    _require_field(data, "recipe_hashes")
    expected = {name: file_sha256(path) for name, path in spec.fields.items()}
    if data["recipe_hashes"] != expected:
        raise RuntimeLockError(
            f"recipe_hashes: expected {expected}, found {data['recipe_hashes']!r}"
        )
    if spec.parent_image_id is not None:
        _require_field(data, "parent_image_id")
        if data["parent_image_id"] != spec.parent_image_id:
            raise RuntimeLockError(
                f"parent_image_id: expected {spec.parent_image_id}, "
                f"found {data['parent_image_id']!r}"
            )


def _check_rootfs_content(rootfs: Path, data: Mapping[str, object], lock_sha256: str) -> None:
    _require_field(data, "rootfs_sha256")
    key = (str(rootfs), lock_sha256)
    if key in _ROOTFS_CONTENT_CACHE:
        return
    try:
        actual = rootfs_identity(rootfs)
    except ValueError as exc:
        raise RuntimeLockError(f"rootfs_sha256: {exc}") from exc
    expected = data["rootfs_sha256"]
    if actual != expected:
        raise RuntimeLockError(
            f"rootfs_sha256: rootfs content does not match rootfs lock: "
            f"expected {expected}, found {actual}"
        )
    _ROOTFS_CONTENT_CACHE.add(key)


def _require_field(data: Mapping[str, object], field: str) -> None:
    if field not in data:
        raise RuntimeLockError(f"{field}: missing from runtime lock")


def _recipe_spec_for(rootfs: Path) -> _RecipeSpec:
    path = rootfs.as_posix()
    if rootfs.name == CURRENT_GPU_ROOTFS_NAME:
        return _RecipeSpec(
            fields={
                "dockerfile_sha256": AUTONOMY / "insula/Dockerfile.gpu-bazel-rootfs-v6",
                "requirements_sha256": AUTONOMY / "insula/gpu-requirements.lock",
            },
            bazel=True,
        )
    if rootfs.name == CURRENT_CURRICULUM_ROOTFS_NAME and "/3d-pathway/insula/" in path:
        return _RecipeSpec(
            fields={
                "dockerfile_sha256": REPO / "parallax/insulas/bazel-rootfs.Dockerfile",
                "requirements_sha256": REPO / "parallax/insulas/bazel-requirements.lock",
            },
            bazel=True,
        )
    return _RecipeSpec(
        fields={
            "dockerfile_sha256": AUTONOMY / "insula/Dockerfile",
            "requirements_sha256": AUTONOMY / "requirements-tracer.lock",
            "test_tools_requirements_sha256": AUTONOMY
            / "insula/cpu-test-tools-requirements.lock",
        },
        bazel=True,
    )


def _image_spec_for(rootfs: Path) -> _ImageSpec:
    if rootfs.name == CURRENT_METRICS_ROOTFS_NAME:
        return _ImageSpec(
            fields={
                "Dockerfile": AUTONOMY / "evaluation/Dockerfile",
                "CMakeLists.txt": AUTONOMY / "evaluation/CMakeLists.txt",
            }
        )
    if rootfs.name == CURRENT_MOTION_METRICS_ROOTFS_NAME:
        return _ImageSpec(
            fields={
                "Dockerfile": AUTONOMY / "motion/ingestion/native_metric.Dockerfile",
                "CMakeLists.txt": AUTONOMY / "motion/CMakeLists.txt",
            },
            parent_image_id="sha256:c0018cf57e482c6a9e6623ea32f29c6039f22f5dafb0f3311bad6d411a7bb135",
        )
    if rootfs.name == CURRENT_MOTION_CLI_ROOTFS_NAME:
        return _ImageSpec(
            fields={
                "Dockerfile": AUTONOMY / "motion/cli/motion_cli.Dockerfile",
                "CMakeLists.txt": AUTONOMY / "motion/cli/CMakeLists.txt",
                "motion_metrics_main.cc": AUTONOMY / "motion/cli/motion_metrics_main.cc",
            },
            parent_image_id="sha256:84fb83dd874d0cfff8e9ee3df0759d89f9ad85e9538c0071c9eb606a13d8c233",
        )
    raise RuntimeLockError(f"recipe_hashes: no image-form recipe is known for {rootfs.name}")


def _merge_environment(
    base_environment: Iterable[tuple[str, str, str]],
    extra_environment: Mapping[str, object] | None,
) -> list[tuple[str, str, str]]:
    environment = list(base_environment)
    if not extra_environment:
        return environment
    owned = {item[1] for item in environment if item[0] == "--setenv"} | _MODULE_ENVIRONMENT
    for name in sorted(extra_environment):
        if name in owned:
            raise PlanError(f"{name}: extra environment collides with module-owned variable")
        environment.append(("--setenv", str(name), str(extra_environment[name])))
    return environment


def _environment_from_mapping(environment: Mapping[str, object]) -> list[tuple[str, str, str]]:
    if not isinstance(environment, Mapping):
        raise PlanError("environment mapping required")
    items = []
    for name, value in environment.items():
        name = str(name)
        if not name or "=" in name or "\x00" in name:
            raise PlanError(f"{name!r}: invalid environment variable name")
        value = str(value)
        if "\x00" in value:
            raise PlanError(f"{name}: environment value contains NUL")
        items.append(("--setenv", name, value))
    return items


def _validate_named_input_path(path: str) -> None:
    inside = PurePosixPath(path)
    if not inside.is_absolute() or ".." in inside.parts:
        raise PlanError(f"{path}: named input path must be absolute and normalized")
    if str(inside) not in _NAMED_INPUT_PREFIXES and not any(
        str(inside).startswith(prefix + "/") for prefix in _NAMED_INPUT_PREFIXES
    ):
        raise PlanError(f"{path}: named input must be under /tmp, /opt, /srv or /mnt")


def _normalise_named_input_digests(
    mounts: tuple[Mount, ...],
    named_input_digests: Mapping[str, str] | None,
) -> tuple[tuple[str, str], ...]:
    if not named_input_digests:
        return ()
    named_mounts = {
        mount.inside_path
        for mount in mounts
        if mount.kind == "bind" and mount.role == f"input:{mount.inside_path}"
    }
    normalised = []
    for inside, digest in named_input_digests.items():
        inside_path = str(PurePosixPath(inside))
        _validate_named_input_path(inside_path)
        if inside_path not in named_mounts:
            raise PlanError(f"{inside_path}: declared digest requires a named input mount")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise PlanError(f"{inside_path}: declared named input digest required")
        normalised.append((inside_path, digest))
    return tuple(sorted(normalised))


def _validate_mounts(
    mounts: tuple[Mount, ...],
    *,
    allow_readonly_inputs_cover_output: bool = False,
) -> None:
    host_mounts = []
    inside_roles: dict[str, str] = {}
    for mount in mounts:
        if mount.kind not in {"bind", "dev-bind", "tmpfs", "symlink"}:
            raise PlanError(f"{mount.role}: unsupported mount kind {mount.kind}")
        if mount.mode not in {"read_only", "writable"}:
            raise PlanError(f"{mount.role}: unsupported mount mode {mount.mode}")
        if mount.kind == "symlink":
            if mount.mode != "read_only" or mount.host_path is not None:
                raise PlanError(f"{mount.role}: symlink mount must be read-only without host path")
            _safe_symlink_target(mount.symlink_target)
        elif mount.symlink_target is not None:
            raise PlanError(f"{mount.role}: symlink target only valid for symlink mounts")
        previous = inside_roles.get(mount.inside_path)
        if previous is not None:
            raise PlanError(f"{previous} and {mount.role}: duplicate inside mount {mount.inside_path}")
        inside_roles[mount.inside_path] = mount.role
        if mount.host_path is not None:
            host_mounts.append((mount, Path(mount.host_path).resolve()))
    for index, (left, left_path) in enumerate(host_mounts):
        for right, right_path in host_mounts[index + 1 :]:
            if left_path == right_path:
                if left.mode == right.mode == "read_only" and left_path.is_file():
                    continue
                raise PlanError(f"{left.role} and {right.role}: host path mounted twice")
            overlaps = left_path in right_path.parents or right_path in left_path.parents
            if (
                allow_readonly_inputs_cover_output
                and overlaps
                and _readonly_input_covers_output(left, right, left_path, right_path)
            ):
                continue
            if overlaps and ("writable" in (left.mode, right.mode)):
                raise PlanError(f"{left.role} and {right.role}: writable mount overlaps another mount")

def _readonly_input_covers_output(left: Mount, right: Mount, left_path: Path, right_path: Path) -> bool:
    pairs = ((left, right, left_path, right_path), (right, left, right_path, left_path))
    for input_mount, output_mount, input_path, output_path in pairs:
        if (
            input_mount.role.startswith("input:")
            and input_mount.mode == "read_only"
            and output_mount.role == "output"
            and output_mount.mode == "writable"
            and input_path in output_path.parents
        ):
            return True
    return False


def _render_mount(mount: Mount) -> list[str]:
    if mount.kind == "symlink":
        if mount.symlink_target is None:
            raise PlanError(f"{mount.role}: symlink target required")
        return ["--symlink", mount.symlink_target, mount.inside_path]
    if mount.kind == "tmpfs":
        return ["--tmpfs", mount.inside_path]
    if mount.host_path is None:
        raise PlanError(f"{mount.role}: host path required")
    if mount.digest is not None and _mounted_file_sha256(mount.host_path, mount.role) != mount.digest:
        raise PlanError(f"{mount.role}: mounted file changed")
    if mount.kind == "dev-bind":
        return ["--dev-bind", str(mount.host_path), mount.inside_path]
    if mount.kind != "bind":
        raise PlanError(f"{mount.role}: unsupported mount kind {mount.kind}")
    flag = "--bind" if mount.mode == "writable" else "--ro-bind"
    return [flag, str(mount.host_path), mount.inside_path]


def _mount_under_tmp(mount: Mount) -> bool:
    return mount.inside_path.startswith("/tmp/")


def _mount_data(mount: Mount, *, include_host: bool) -> dict:
    data = {
        "role": mount.role,
        "inside_path": mount.inside_path,
        "mode": mount.mode,
        "kind": mount.kind,
    }
    if mount.digest is not None:
        data["digest"] = mount.digest
    if include_host and mount.host_path is not None:
        data["host_path"] = str(Path(mount.host_path).resolve())
    if mount.kind == "symlink":
        data["symlink_target"] = mount.symlink_target
    return data


def _declared_named_input_digest(plan: LaunchPlan, mount: Mount) -> str | None:
    if mount.role != f"input:{mount.inside_path}":
        return None
    return dict(plan.named_input_digests).get(mount.inside_path)


def _plan_mount_data(plan: LaunchPlan, mount: Mount, *, include_host: bool) -> dict:
    data = _mount_data(mount, include_host=include_host)
    digest = _declared_named_input_digest(plan, mount)
    if digest is not None:
        data["digest"] = digest
    return data


def _record_mount(plan: LaunchPlan, mount: Mount) -> dict:
    data = _mount_data(mount, include_host=False)
    declared_input_digest = _declared_named_input_digest(plan, mount)
    if mount.digest is not None:
        data["digest"] = mount.digest
    elif mount.role == "runtime":
        data["digest"] = plan.runtime.data.get("rootfs_sha256", "")
    elif mount.role.startswith("runtime-entry:"):
        data["digest"] = plan.runtime.data.get("rootfs_sha256", "")
    elif mount.role == "code" and plan.source_snapshot_digest is not None:
        data["digest"] = plan.source_snapshot_digest
    elif declared_input_digest is not None:
        data["digest"] = declared_input_digest
    elif mount.host_path is not None and mount.mode == "read_only":
        data["digest"] = _content_digest(Path(mount.host_path))
    if mount.phase != "before_devices":
        data["phase"] = mount.phase
    return data


def _record_device(mount: Mount) -> dict:
    return {"role": mount.role, "inside_path": mount.inside_path}


def _record_device_mount(plan: LaunchPlan, mount: Mount) -> bool:
    if mount.kind != "dev-bind":
        return False
    return not (plan.gpu is not None and mount.role.startswith("gpu-device:"))


def _content_digest(path: Path) -> str:
    path = Path(path)
    if path.is_file():
        return file_sha256(path)
    if not path.is_dir() or path.is_symlink():
        raise PlanError(f"{path}: mounted digest input must be a regular file or directory")
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        info = item.lstat()
        kind = stat.S_IFMT(info.st_mode)
        record = [item.relative_to(path).as_posix(), kind, stat.S_IMODE(info.st_mode)]
        if stat.S_ISLNK(info.st_mode):
            record.append(str(item.readlink()))
        elif stat.S_ISREG(info.st_mode):
            record.extend([info.st_size, file_sha256(item)])
        elif not stat.S_ISDIR(info.st_mode):
            record.append(info.st_rdev)
        digest.update((json.dumps(record, separators=(",", ":")) + "\n").encode())
    return digest.hexdigest()


def _gpu_mounts_environment_and_request(gpu_index: int):
    if type(gpu_index) is not int or gpu_index < 0:
        raise PlanError("gpu_index: non-negative integer required")
    device_minor = gpu_index
    mounts = [Mount("gpu-driver-root", "tmpfs", "/driver", "writable", None)]
    for path in _gpu_driver_paths():
        mounts.append(
            Mount(
                f"gpu-driver:{path.name}",
                "bind",
                "/driver/" + path.name,
                "read_only",
                path,
                digest=_mounted_file_sha256(path, f"gpu-driver:{path.name}"),
            )
        )
    device_pairs = _gpu_device_pairs(gpu_index)
    if not any(guest == f"/dev/nvidia{device_minor}" for _, guest in device_pairs):
        raise PlanError(f"GPU override omits requested /dev/nvidia{device_minor}")
    for host, guest in device_pairs:
        mounts.append(Mount(f"gpu-device:{guest}", "dev-bind", guest, "writable", host, "after_devices"))
    return mounts, [
        ("--setenv", "PATH", _GPU_PATH),
        ("--setenv", "LD_LIBRARY_PATH", "/driver:/usr/local/cuda/lib64"),
        ("--setenv", "CUDA_VISIBLE_DEVICES", "0"),
    ], GPURequest(gpu_index, device_minor, _gpu_device_uuid(device_minor))


def _gpu_request_data(gpu: GPURequest, *, include_minor: bool) -> dict:
    data = {
        "requested_index": gpu.requested_index,
        "device_uuid": gpu.device_uuid,
    }
    if include_minor:
        data["device_minor"] = gpu.device_minor
    return data


def _gpu_device_pairs(gpu_index: int) -> list[tuple[Path, str]]:
    configured = os.environ.get("SUREAL_BAZEL_GPU_DEVICES")
    if configured:
        pairs = []
        for item in configured.split(","):
            if not item:
                continue
            if "=" in item:
                host, guest = item.split("=", 1)
            else:
                host = guest = item
            _validate_gpu_device_override_path(item, host, gpu_index, side="host")
            _validate_gpu_device_override_path(item, guest, gpu_index, side="guest")
            pairs.append((Path(host), guest))
    else:
        pairs = [
            (Path(f"/dev/nvidia{gpu_index}"), f"/dev/nvidia{gpu_index}"),
            (Path("/dev/nvidiactl"), "/dev/nvidiactl"),
            (Path("/dev/nvidia-uvm"), "/dev/nvidia-uvm"),
        ]
    for host, _ in pairs:
        if not host.exists():
            raise PlanError(f"GPU device not found: {host}")
    return pairs


def _validate_gpu_device_override_path(
    entry: str,
    path: str,
    gpu_index: int,
    *,
    side: str,
) -> None:
    requested_gpu = f"/dev/nvidia{gpu_index}"
    if path == requested_gpu or path in _GPU_CONTROL_DEVICES:
        return
    if re.fullmatch(r"/dev/nvidia\d+", path):
        raise PlanError(
            f"{entry}: GPU override {side} path {path} does not match requested {requested_gpu}"
        )
    if side == "guest" or path.startswith("/dev/nvidia"):
        allowed = ", ".join(sorted([requested_gpu, *_GPU_CONTROL_DEVICES]))
        raise PlanError(f"{entry}: GPU override {side} path {path} is not allowed; expected {allowed}")


def _gpu_device_uuid(gpu_index: int) -> str:
    configured = os.environ.get("SUREAL_BAZEL_GPU_DEVICE_UUIDS")
    if configured:
        mapping = {}
        for item in configured.split(","):
            if not item:
                continue
            index, uuid = item.split("=", 1)
            mapping[int(index)] = uuid
        try:
            return mapping[gpu_index]
        except KeyError as exc:
            raise PlanError(f"gpu_index {gpu_index}: device UUID override missing") from exc
    for info in sorted(_GPU_DRIVER_INFO_ROOT.glob("*/information")):
        try:
            fields = _parse_gpu_driver_information(info.read_text())
        except OSError:
            continue
        if fields.get("Device Minor") != str(gpu_index):
            continue
        uuid = fields.get("GPU UUID")
        if uuid:
            return uuid
    raise PlanError(f"gpu_index {gpu_index}: device UUID lookup failed")


def _parse_gpu_driver_information(text: str) -> dict[str, str]:
    fields = {}
    for line in text.splitlines():
        name, separator, value = line.partition(":")
        if separator:
            fields[name.strip()] = value.strip()
    return fields


def _gpu_driver_paths() -> list[Path]:
    configured = os.environ.get("SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS")
    directories = (
        tuple(Path(item) for item in configured.split(os.pathsep) if item)
        if configured
        else _DEFAULT_GPU_DRIVER_LIBRARY_DIRS
    )
    found_paths = []
    for prefix in _GPU_DRIVER_PREFIXES:
        found = []
        for directory in directories:
            found.extend(sorted(path for path in directory.glob(prefix + "*") if path.is_file()))
        if not found:
            searched = ", ".join(str(directory) for directory in directories)
            raise PlanError(f"GPU driver library {prefix} not found in {searched}")
        found_paths.extend(found)
    return found_paths


def _mounted_file_sha256(path: Path, role: str) -> str:
    try:
        resolved = Path(path).resolve(strict=True)
    except FileNotFoundError as exc:
        raise PlanError(f"{role}: mounted file missing: {path}") from exc
    if not resolved.is_file():
        raise PlanError(f"{role}: mounted file required: {path}")
    return file_sha256(resolved)


__all__ = [
    "RuntimeLockError",
    "PlanError",
    "load_runtime_lock",
    "load_default_runtime_lock",
    "build_plan",
    "build_custom_plan",
    "gpu_mounts_environment_and_request",
    "gpu_driver_hashes_from_plan_record",
    "gpu_driver_paths_from_plan_record",
    "verify_gpu_driver_hashes_from_plan_record",
    "plan_data",
    "render_plan",
    "legacy_receipt_command_argv",
    "inspect_legacy_receipt_command",
    "run_plan",
    "with_mounts",
    "record_plan",
    "read_receipt_mounts",
    "read_receipt_mount_sequence",
]
