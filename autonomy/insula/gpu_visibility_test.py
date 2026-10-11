import tempfile
import unittest
from pathlib import Path

from insula import gpu_visibility


class GPUVisibilityTests(unittest.TestCase):
    def test_requested_gpu_tier_fails_when_no_device_was_mounted(self):
        with self.assertRaisesRegex(
            AssertionError,
            "SUREAL_REQUIRE_GPU=1 requires one visible CUDA device; found 0",
        ):
            gpu_visibility.require_requested_gpu_visible(environ={"SUREAL_REQUIRE_GPU": "1"})

    def test_requested_gpu_tier_fails_when_device_node_is_missing(self):
        with tempfile.TemporaryDirectory() as dev:
            with self.assertRaisesRegex(AssertionError, "nvidia1; it is not mounted"):
                gpu_visibility.require_requested_gpu_visible(
                    environ={"SUREAL_REQUIRE_GPU": "1", "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-abc"},
                    dev_root=Path(dev),
                )

    def test_requested_gpu_tier_passes_with_one_mounted_device(self):
        with tempfile.TemporaryDirectory() as dev:
            (Path(dev) / "nvidia1").touch()
            gpu_visibility.require_requested_gpu_visible(
                environ={"SUREAL_REQUIRE_GPU": "1", "SUREAL_BAZEL_GPU_DEVICE_UUIDS": "1=GPU-abc"},
                dev_root=Path(dev),
            )

    def test_default_cpu_tier_does_not_require_cuda(self):
        gpu_visibility.require_requested_gpu_visible(environ={})


if __name__ == "__main__":
    unittest.main()
