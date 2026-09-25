from __future__ import annotations

from pathlib import Path
import sys
import unittest


SYNTHETIC_ROOT = Path(__file__).resolve().parents[1] / "synthetic_ambiguity"
sys.path.insert(0, str(SYNTHETIC_ROOT))

from probe import classify_hypothesis  # noqa: E402


class SyntheticAmbiguityProbeTest(unittest.TestCase):
    def test_classifies_unsupported_completion(self) -> None:
        result = classify_hypothesis(0.02, 0.01)
        self.assertEqual(result["label"], "unsupported")

    def test_classifies_hybrid_completion(self) -> None:
        result = classify_hypothesis(0.72, 0.68)
        self.assertEqual(result["label"], "hybrid")
        self.assertLess(result["coherence"], 0.1)

    def test_classifies_each_coherent_hypothesis(self) -> None:
        self.assertEqual(classify_hypothesis(0.72, 0.08)["label"], "scene_a")
        self.assertEqual(classify_hypothesis(0.08, 0.72)["label"], "scene_b")


if __name__ == "__main__":
    unittest.main()
