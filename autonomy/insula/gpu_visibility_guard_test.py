import unittest

from insula import gpu_visibility


class GPUVisibilityGuardTests(unittest.TestCase):
    def test_requested_gpu_tier_has_visible_cuda_device(self):
        gpu_visibility.require_requested_gpu_visible()


if __name__ == "__main__":
    unittest.main()
