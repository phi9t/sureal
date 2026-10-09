"""Record the actual bwrap command; never pretend an unwrapped argv executed."""
from pathlib import Path
from evidence.source_snapshot import is_regular_file
from insula.launch_plan import (
    LaunchPlan,
    inspect_legacy_receipt_command as _inspect_legacy_receipt_command,
    wrap_legacy_receipt_command,
    wrap_rendered_plan_command,
    wrap_resource_plan,
)


def inspect_legacy_receipt_command(command):
    """Parse old command receipts as values, never as isolation flags or mounts."""
    return _inspect_legacy_receipt_command(command)


inspect_command=inspect_legacy_receipt_command


def wrapped_command(command,code,output):
    """Construct the recorded wrapper without changing or executing anything."""
    return wrap_legacy_receipt_command(command,code,output)


def wrapped_rendered_plan_command(command,code,output):
    """Construct the resource wrapper in launch-plan render order."""
    return wrap_rendered_plan_command(command,code,output)


def wrapped_plan(plan,code,output):
    """Construct the resource wrapper as launch-plan data."""
    if not isinstance(plan,LaunchPlan):
        raise ValueError('launch plan required')
    return wrap_resource_plan(plan,code,output)


def wrap_command(command,code,output):
    code=Path(code);output=Path(output)
    actual,worker_argv=wrapped_command(command,code,output)
    _validate_resource_wrapper_inputs(code,output)
    command[:]=actual
    return worker_argv


def wrap_plan(plan,code,output):
    code=Path(code);output=Path(output)
    wrapped,worker_argv=wrapped_plan(plan,code,output)
    _validate_resource_wrapper_inputs(code,output)
    return wrapped,worker_argv


def _validate_resource_wrapper_inputs(code,output):
    if (any(not p.is_absolute() or not p.is_dir() or any(q.is_symlink() for q in [p,*p.parents]) for p in [code,output]) or
        not (code/'resources').is_dir() or not (code/'evidence').is_dir() or
        not is_regular_file(code/'resources/execute_worker.py') or
        not is_regular_file(code/'evidence/source_snapshot.py') or
        any(output.iterdir())):
        raise ValueError('regular code and empty resource output required')
