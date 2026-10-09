"""Current Insula root filesystem names and default locations."""
from pathlib import Path


WAYMO_CACHE_RELATIVE = ".cache/waystone/waymo-perception"
PATHWAY_CACHE_RELATIVE = ".cache/waystone/3d-pathway"

CURRENT_CPU_ROOTFS_NAME = "rootfs-v5-t29-20261008T230657Z"
CURRENT_GPU_ROOTFS_NAME = "gpu-rootfs-v6"
CURRENT_METRICS_ROOTFS_NAME = "metrics-rootfs"
CURRENT_MOTION_METRICS_ROOTFS_NAME = "motion-metrics-rootfs"
CURRENT_MOTION_CLI_ROOTFS_NAME = "motion-cli-rootfs-v2"
CURRENT_CURRICULUM_ROOTFS_NAME = "rootfs-v2"


def waymo_cache() -> Path:
    return Path.home() / WAYMO_CACHE_RELATIVE


def pathway_cache() -> Path:
    return Path.home() / PATHWAY_CACHE_RELATIVE


def current_cpu_rootfs(cache: Path | None = None) -> Path:
    root = Path(cache) if cache is not None else waymo_cache()
    return root / "insula" / CURRENT_CPU_ROOTFS_NAME


def current_gpu_rootfs(cache: Path | None = None) -> Path:
    root = Path(cache) if cache is not None else waymo_cache()
    return root / CURRENT_GPU_ROOTFS_NAME


def current_metrics_rootfs(cache: Path | None = None) -> Path:
    root = Path(cache) if cache is not None else waymo_cache()
    return root / CURRENT_METRICS_ROOTFS_NAME


def current_motion_metrics_rootfs(cache: Path | None = None) -> Path:
    root = Path(cache) if cache is not None else waymo_cache()
    return root / CURRENT_MOTION_METRICS_ROOTFS_NAME


def current_motion_cli_rootfs(cache: Path | None = None) -> Path:
    root = Path(cache) if cache is not None else waymo_cache()
    return root / CURRENT_MOTION_CLI_ROOTFS_NAME


def current_curriculum_rootfs(cache: Path | None = None) -> Path:
    root = Path(cache) if cache is not None else pathway_cache()
    return root / "insula" / CURRENT_CURRICULUM_ROOTFS_NAME


def default_lock(rootfs: Path) -> Path:
    return Path(str(Path(rootfs)) + ".lock.json")
