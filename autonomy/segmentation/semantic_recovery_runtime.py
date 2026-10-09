"""Shared runtime choices for live semantic-recovery readmission."""
from pathlib import Path

from insula.runtime_roots import current_cpu_rootfs


def recovery_rootfs(cache: Path) -> Path:
    return current_cpu_rootfs(Path(cache))


def validate_recovery_output(output: Path) -> None:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("new semantic recovery output required")
