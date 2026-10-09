"""Resource-stage command wrapping and legacy receipt inspection."""
from pathlib import Path
from typing import Iterable, Mapping

from evidence.source_snapshot import is_regular_file
from insula.launch_plan import (
    LaunchPlan,
    Mount,
    PlanError,
    _parse_legacy_receipt_command,
    _plan_device_insertion_index,
    _plan_tmp_mounts_index,
    _render_mount,
    _render_ordered_record_mounts,
    inspect_legacy_receipt_command as _inspect_legacy_receipt_command,
    legacy_receipt_command_argv,
    with_mounts,
)


_RESOURCE_WRAPPER_ALIASES = {
    "/tmp/resource-layer",
    "/tmp/resource-output",
    "/experiment/resources",
    "/experiment/evidence",
}


def inspect_legacy_receipt_command(command):
    """Parse old command receipts as values, never as isolation flags or mounts."""
    return _inspect_legacy_receipt_command(command)


inspect_command=inspect_legacy_receipt_command


def wrapped_command(command,code,output):
    """Construct the recorded wrapper around an old rendered receipt command."""
    return wrap_legacy_receipt_command(command,code,output)


def wrapped_rendered_plan_command(command,code,output):
    """Construct the resource wrapper in launch-plan render order for old receipts."""
    return wrap_rendered_plan_command(command,code,output)


def wrapped_plan(plan,code,output):
    """Construct the resource wrapper as launch-plan data."""
    return wrap_resource_plan(plan,code,output)


def wrap_command(command,code,output):
    """Mutate an old rendered command receipt for legacy resource-stage execution."""
    code=Path(code);output=Path(output)
    actual,worker_argv=wrapped_command(command,code,output)
    _validate_resource_wrapper_inputs(code,output)
    command[:]=actual
    return worker_argv


def wrap_plan(plan,code,output):
    """Return the wrapped launch plan for new resource-stage execution."""
    code=Path(code);output=Path(output)
    wrapped,worker_argv=wrapped_plan(plan,code,output)
    _validate_resource_wrapper_inputs(code,output)
    return wrapped,worker_argv


def wrap_legacy_receipt_command(command: list[str], code: Path, output: Path) -> tuple[list[str], list[str]]:
    """Render a resource wrapper around an old command receipt."""
    parsed = _parse_legacy_receipt_command(command, require_python_worker=True)
    _require_resource_aliases_unused(parsed["options"])
    separator = parsed["separator"]
    argv = list(parsed["argv"])
    wrapper_mounts = _resource_wrapper_mounts(Path(code), Path(output))
    bindings = [item for mount in wrapper_mounts for item in _render_mount(mount)]
    return (
        [
            *command[:separator],
            *bindings,
            "--",
            argv[0],
            "/tmp/resource-layer/resources/execute_worker.py",
            "/tmp/resource-output",
            *argv[1:],
        ],
        argv[1:],
    )


def wrap_rendered_plan_command(command: list[str], code: Path, output: Path) -> tuple[list[str], list[str]]:
    """Render a resource wrapper into an already-rendered launch plan command."""
    parsed = _parse_legacy_receipt_command(command, require_python_worker=True)
    _require_resource_aliases_unused(parsed["options"])
    separator = parsed["separator"]
    argv = list(parsed["argv"])
    devices_at = _plan_device_insertion_index(command, separator)
    tmp_at = _plan_tmp_mounts_index(command, devices_at)
    resource_mounts = _resource_wrapper_mounts(Path(code), Path(output))
    experiment = [
        item
        for mount in resource_mounts
        if not _mount_under_tmp(mount)
        for item in _render_mount(mount)
    ]
    under_tmp = [
        item
        for mount in resource_mounts
        if _mount_under_tmp(mount)
        for item in _render_mount(mount)
    ]
    return (
        [
            *command[:tmp_at],
            *experiment,
            *command[tmp_at:devices_at],
            *under_tmp,
            *command[devices_at:separator],
            "--",
            argv[0],
            "/tmp/resource-layer/resources/execute_worker.py",
            "/tmp/resource-output",
            *argv[1:],
        ],
        argv[1:],
    )


def wrap_resource_plan(plan: LaunchPlan, code: Path, output: Path) -> tuple[LaunchPlan, list[str]]:
    """Return a launch plan wrapped with the resource layer."""
    if not isinstance(plan,LaunchPlan):
        raise PlanError("launch plan required")
    argv = list(plan.command)
    if (
        len(argv) < 2
        or argv[0] not in {"python", "/opt/waymo/bin/python"}
        or not Path(argv[1]).is_absolute()
        or not argv[1].endswith(".py")
    ):
        raise PlanError("declared original Python worker required")
    if any(mount.kind in {"bind", "dev-bind", "tmpfs", "symlink"} and mount.inside_path in _RESOURCE_WRAPPER_ALIASES for mount in plan.mounts):
        raise PlanError("resource mount aliases must be unused")
    wrapped = with_mounts(
        plan,
        before_devices=_resource_wrapper_mounts(Path(code), Path(output)),
        command=[
            argv[0],
            "/tmp/resource-layer/resources/execute_worker.py",
            "/tmp/resource-output",
            *argv[1:],
        ],
    )
    return wrapped, argv[1:]


def rendered_command_matches_record(command: list[str], record: Mapping[str, object]) -> bool:
    """Return whether a rendered command matches a recorded launch plan."""
    try:
        parsed = _parse_legacy_receipt_command(command, require_cleared_environment=True, require_python_worker=True)
        mounts = []
        devices = []
        environment = {}
        working_directory = None
        for option, values in parsed["options"]:
            if option == "--ro-bind":
                mounts.append({"kind": "bind", "inside_path": values[1], "mode": "read_only"})
            elif option == "--bind":
                mounts.append({"kind": "bind", "inside_path": values[1], "mode": "writable"})
            elif option == "--dev-bind":
                devices.append({"inside_path": values[1]})
            elif option == "--tmpfs":
                mounts.append({"kind": "tmpfs", "inside_path": values[0], "mode": "writable"})
            elif option == "--symlink":
                mounts.append(
                    {
                        "kind": "symlink",
                        "inside_path": values[1],
                        "mode": "read_only",
                        "symlink_target": values[0],
                    }
                )
            elif option == "--setenv":
                environment[values[0]] = values[1]
            elif option == "--chdir":
                working_directory = values[0]
        flag_options = [option for option, values in parsed["options"] if not values]
        proc_options = [values for option, values in parsed["options"] if option == "--proc"]
        dev_options = [values for option, values in parsed["options"] if option == "--dev"]
        recorded_mounts = [
            {key: mount[key] for key in ("kind", "inside_path", "mode", "symlink_target") if key in mount}
            for mount in _render_ordered_record_mounts(record["mounts"])
        ]
        recorded_devices = _recorded_device_bindings(record)
        return (
            flag_options == ["--unshare-all", "--die-with-parent", "--clearenv"]
            and proc_options == [("/proc",)]
            and dev_options == [("/dev",)]
            and mounts == recorded_mounts
            and devices == recorded_devices
            and environment == record["environment"]
            and working_directory == record["working_directory"]
            and list(parsed["argv"]) == record["command"]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("actual wrapper, original worker, native output and resource mounts required") from error


def _recorded_device_bindings(record: Mapping[str, object]) -> list[dict[str, str]]:
    devices = [{"inside_path": device["inside_path"]} for device in record.get("devices", [])]
    gpu = record.get("gpu")
    if isinstance(gpu, Mapping) and type(gpu.get("requested_index")) is int:
        index = gpu["requested_index"]
        devices.extend(
            [
                {"inside_path": f"/dev/nvidia{index}"},
                {"inside_path": "/dev/nvidiactl"},
                {"inside_path": "/dev/nvidia-uvm"},
            ]
        )
    return devices


def recorded_resource_mounts_match(mounts: Iterable[Mapping[str, object]]) -> bool:
    """Return whether a launch-plan record contains the resource wrapper mounts."""
    expected = [
        {"role": "resource-layer", "kind": "bind", "inside_path": "/tmp/resource-layer", "mode": "read_only"},
        {
            "role": "resource-experiment-resources",
            "kind": "bind",
            "inside_path": "/experiment/resources",
            "mode": "read_only",
        },
        {
            "role": "resource-experiment-evidence",
            "kind": "bind",
            "inside_path": "/experiment/evidence",
            "mode": "read_only",
        },
        {"role": "resource-output", "kind": "bind", "inside_path": "/tmp/resource-output", "mode": "writable"},
    ]
    return all(
        sum(1 for mount in mounts if all(mount.get(key) == value for key, value in required.items())) == 1
        for required in expected
    )


def _validate_resource_wrapper_inputs(code,output):
    if (any(not p.is_absolute() or not p.is_dir() or any(q.is_symlink() for q in [p,*p.parents]) for p in [code,output]) or
        not (code/'resources').is_dir() or not (code/'evidence').is_dir() or
        not is_regular_file(code/'resources/execute_worker.py') or
        not is_regular_file(code/'evidence/source_snapshot.py') or
        any(output.iterdir())):
        raise ValueError('regular code and empty resource output required')


def _require_resource_aliases_unused(options: Iterable[tuple[str, tuple[str, ...]]]) -> None:
    for option, values in options:
        if option in {"--ro-bind", "--bind", "--dev-bind", "--proc", "--dev", "--tmpfs", "--symlink"} and values[-1] in _RESOURCE_WRAPPER_ALIASES:
            raise PlanError("resource mount aliases must be unused")


def _resource_wrapper_mounts(code: Path, output: Path) -> list[Mount]:
    return [
        Mount("resource-layer", "bind", "/tmp/resource-layer", "read_only", code),
        Mount("resource-experiment-resources", "bind", "/experiment/resources", "read_only", code / "resources"),
        Mount("resource-experiment-evidence", "bind", "/experiment/evidence", "read_only", code / "evidence"),
        Mount("resource-output", "bind", "/tmp/resource-output", "writable", output),
    ]


def _mount_under_tmp(mount: Mount) -> bool:
    return mount.inside_path.startswith("/tmp/")
