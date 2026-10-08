import unittest

import torch
from torch import nn

from detection.norm_variants import PointChannelLayerNorm, configure_norm


class NormVariantTests(unittest.TestCase):
    def test_point_channel_layer_norm_uses_per_point_channels(self):
        values = torch.randn(3, 64, 5)
        norm = PointChannelLayerNorm(64)
        expected = (values - values.mean(1, keepdim=True)) / torch.sqrt(
            values.var(1, unbiased=False, keepdim=True) + 1e-3
        )

        torch.testing.assert_close(norm(values), expected, atol=2e-6, rtol=2e-6)

    def test_configure_norm_replaces_backbone_and_pillar_norms(self):
        toy = nn.Sequential(nn.BatchNorm2d(8, eps=1e-3), nn.BatchNorm1d(4, eps=1e-4))

        configured = configure_norm(toy, "gn_backbone_ln_pillar")

        self.assertIsInstance(configured[0], nn.GroupNorm)
        self.assertEqual(configured[0].num_groups, 8)
        self.assertIsInstance(configured[1], PointChannelLayerNorm)


if __name__ == "__main__":
    unittest.main()
