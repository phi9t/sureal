"""Legacy command-only receipt inspection for resource stages.

New receipts carry launch-plan records and are checked in
``insula.launch_plan``. This module is kept as a small compatibility face for
old receipts whose only launch description is a rendered command line.
"""
from pathlib import Path

from insula.launch_plan import (
    inspect_legacy_receipt_command as _inspect_legacy_receipt_command,
    validate_resource_wrapper_inputs,
    wrap_legacy_receipt_command,
)


def inspect_legacy_receipt_command(command):
    """Parse a legacy command-only receipt for old resource evidence readers."""
    return _inspect_legacy_receipt_command(command)


inspect_command = inspect_legacy_receipt_command


def wrapped_command(command, code, output):
    """Return the resource wrapper for a legacy rendered receipt command."""
    return wrap_legacy_receipt_command(command, Path(code), Path(output))


def wrap_command(command, code, output):
    """Mutate a legacy command-only receipt command for resource-stage execution."""
    actual, worker_argv = wrapped_command(command, code, output)
    validate_resource_wrapper_inputs(Path(code), Path(output))
    command[:] = actual
    return worker_argv


def __getattr__(name):
    compatibility_exports = {
        "wrap_rendered_plan_command",
        "wrap_resource_plan",
    }
    if name in compatibility_exports:
        from insula import launch_plan

        return getattr(launch_plan, name)
    raise AttributeError(name)
