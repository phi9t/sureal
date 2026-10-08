import unittest

import torch

from detection.architecture_variants import configure_architecture
from detection.architecture_weight_contract import verify_shared_weights
from detection.pillar_detector import PillarDetector


def small_detector():
    torch.manual_seed(17)
    return PillarDetector(
        nx=8,
        ny=8,
        classes=4,
        anchors_per_cell=8,
        cell_size=(0.25, 0.25),
        origin=(-1.0, -1.0),
    )


class ArchitectureVariantTests(unittest.TestCase):
    def test_residual_variant_preserves_all_shared_weights(self):
        reference = small_detector()
        candidate = configure_architecture(small_detector(), "residual_bev")

        self.assertEqual(verify_shared_weights(reference, candidate), len(reference.state_dict()))

        corrupt = configure_architecture(small_detector(), "residual_bev")
        with torch.no_grad():
            corrupt.blocks[0][4].unit[0].weight.add_(1)
        with self.assertRaises(AssertionError):
            verify_shared_weights(reference, corrupt)


if __name__ == "__main__":
    unittest.main()
