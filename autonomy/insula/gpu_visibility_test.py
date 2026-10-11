import os
import unittest
from unittest import mock

from insula import gpu_visibility


class GPUVisibilityTests(unittest.TestCase):
    def test_requested_gpu_tier_fails_when_cuda_is_masked(self):
        with mock.patch.dict(os.environ, {"SUREAL_REQUIRE_GPU": "1"}):
            with self.assertRaisesRegex(
                AssertionError,
                "SUREAL_REQUIRE_GPU=1 requires one visible CUDA device; found 0",
            ):
                gpu_visibility.require_requested_gpu_visible(
                    available=False,
                    device_count=0,
                )

    def test_default_cpu_tier_does_not_require_cuda(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            gpu_visibility.require_requested_gpu_visible(
                available=False,
                device_count=0,
            )


if __name__ == "__main__":
    unittest.main()
