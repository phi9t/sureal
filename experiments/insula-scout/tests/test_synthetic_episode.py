from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


SYNTHETIC_ROOT = Path(__file__).resolve().parents[1] / "synthetic_ambiguity"
sys.path.insert(0, str(SYNTHETIC_ROOT))

from episode import generate_episode  # noqa: E402


class SyntheticAmbiguityEpisodeTest(unittest.TestCase):
    def test_episode_has_identical_context_and_distinct_hidden_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "episode"
            manifest = generate_episode(
                output_dir,
                width=64,
                height=48,
                n_context=4,
                n_target=3,
                surface_points_per_box=128,
                seed=7,
            )
            on_disk = json.loads((output_dir / "manifest.json").read_text())

            self.assertEqual(manifest, on_disk)
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["task"], "paired_hidden-scene_ambiguity")
            self.assertEqual(manifest["paired_context"]["pixel_mismatches"], 0)
            self.assertEqual(
                manifest["paired_context"]["sha256_a"],
                manifest["paired_context"]["sha256_b"],
            )
            self.assertNotEqual(
                manifest["paired_targets"]["sha256_a"],
                manifest["paired_targets"]["sha256_b"],
            )

            for scene_name in ("scene_a", "scene_b"):
                visibility = manifest["scenes"][scene_name]["visibility"]
                self.assertEqual(visibility["hidden_object_context_fraction"], 0.0)
                self.assertGreater(visibility["hidden_object_target_fraction"], 0.25)
                self.assertGreater(visibility["target_new_surface_fraction"], 0.25)
                self.assertTrue((output_dir / scene_name / "surface.npz").is_file())
                self.assertEqual(
                    len(list((output_dir / scene_name / "context" / "rgb").glob("*.png"))),
                    4,
                )
                self.assertEqual(
                    len(list((output_dir / scene_name / "target" / "rgb").glob("*.png"))),
                    3,
                )

            self.assertLess(manifest["camera_checks"]["max_center_error"], 1e-6)


if __name__ == "__main__":
    unittest.main()
