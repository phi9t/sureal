import unittest

import torch

from detection.checkpoint_values import same_tensor_values


class CheckpointValueTests(unittest.TestCase):
    def test_checkpoint_value_comparison_ignores_device_identity_only(self):
        left = torch.tensor([1.0, 2.0])

        self.assertTrue(same_tensor_values(left, left.clone()))
        self.assertFalse(same_tensor_values(left, left.to(torch.float64)))


if __name__ == "__main__":
    unittest.main()
