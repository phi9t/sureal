import unittest

import torch

from detection.architecture_followups import CoarseMLP, WindowAttention


class ArchitectureFollowupTests(unittest.TestCase):
    def test_followup_blocks_are_residual_when_projection_is_zero(self):
        x = torch.randn(2, 256, 16, 16)
        window = WindowAttention()
        with torch.no_grad():
            window.output.weight.zero_()
        torch.testing.assert_close(window(x), x)
        torch.testing.assert_close(window.unpartition(window.partition(x), 2, 16, 16), x)

        control = CoarseMLP()
        with torch.no_grad():
            control.output.weight.zero_()
        torch.testing.assert_close(control(x), x)


if __name__ == "__main__":
    unittest.main()
