"""Shared runtime choices for live semantic-recovery readmission."""
from pathlib import Path


CURRENT_CPU_ROOTFS_NAME = "rootfs-v5-t29-20261008T230657Z"


def recovery_rootfs(cache: Path) -> Path:
    return Path(cache) / "insula" / CURRENT_CPU_ROOTFS_NAME


def validate_recovery_output(output: Path) -> None:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("new semantic recovery output required")
