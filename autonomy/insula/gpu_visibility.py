"""Runtime guard for the requested CUDA test tier."""
import os
from pathlib import Path


REQUIRE_GPU_ENV = "SUREAL_REQUIRE_GPU"
DEVICE_UUIDS_ENV = "SUREAL_BAZEL_GPU_DEVICE_UUIDS"


def require_requested_gpu_visible(*, environ=None, dev_root=Path("/dev")) -> None:
    """Fail when the CUDA tier was requested but the launcher mounted no GPU.

    The launcher sets DEVICE_UUIDS_ENV to `<minor>=<uuid>` only after it finds and
    mounts the requested device, so that record and the device node are the probe.
    A torch probe in the test process is wrong here: the sandbox exposes only the
    requested node, so CUDA_VISIBLE_DEVICES indices do not match what torch sees.
    """
    environ = os.environ if environ is None else environ
    if environ.get(REQUIRE_GPU_ENV) != "1":
        return
    entries = [item for item in environ.get(DEVICE_UUIDS_ENV, "").split(",") if item]
    if len(entries) != 1:
        raise AssertionError(
            f"{REQUIRE_GPU_ENV}=1 requires one visible CUDA device; found {len(entries)}"
        )
    minor, _, uuid = entries[0].partition("=")
    if not minor.isdigit() or not uuid:
        raise AssertionError(f"{DEVICE_UUIDS_ENV} is malformed: {entries[0]!r}")
    node = Path(dev_root) / f"nvidia{minor}"
    if not node.exists():
        raise AssertionError(f"{REQUIRE_GPU_ENV}=1 requires {node}; it is not mounted")
