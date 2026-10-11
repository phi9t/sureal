"""Runtime guard for the requested CUDA test tier."""
import os


REQUIRE_GPU_ENV = "SUREAL_REQUIRE_GPU"


def require_requested_gpu_visible(*, available=None, device_count=None) -> None:
    if os.environ.get(REQUIRE_GPU_ENV) != "1":
        return
    if available is None or device_count is None:
        try:
            import torch
        except Exception as exc:  # pragma: no cover - exercised only in broken rootfses.
            raise AssertionError(
                f"{REQUIRE_GPU_ENV}=1 requires a CUDA visibility probe; importing torch failed: {exc}"
            ) from exc
        available = torch.cuda.is_available()
        device_count = torch.cuda.device_count()
    if not available or device_count != 1:
        raise AssertionError(
            f"{REQUIRE_GPU_ENV}=1 requires one visible CUDA device; found {device_count}"
        )
