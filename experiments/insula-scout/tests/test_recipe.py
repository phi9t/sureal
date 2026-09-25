from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCOUT_ROOT = Path(__file__).resolve().parents[1]


class RecipeTest(unittest.TestCase):
    def test_tracked_recipe_validates_without_cached_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCOUT_ROOT / "verify_recipe.py"),
                    "--recipe",
                    str(SCOUT_ROOT / "recipe.json"),
                    "--cache-root",
                    temp_dir,
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(
            [stage["id"] for stage in payload["stages"]],
            ["verify", "sample", "public-eval", "train-smoke", "synthetic-ambiguity"],
        )
        self.assertFalse(payload["artifacts"]["checkpoint"]["present"])
        self.assertFalse(payload["artifacts"]["synthetic_episode_manifest"]["present"])
        self.assertFalse(payload["artifacts"]["synthetic_probe_raw"]["present"])
        synthetic = payload["evidence"]["synthetic_probe"]
        self.assertEqual(
            synthetic["baseline_behavior"],
            "at_least_one_hybrid_completion",
        )
        self.assertEqual(synthetic["labels"], ["hybrid", "scene_a", "hybrid", "hybrid"])
        self.assertEqual(synthetic["paired_context_pixel_mismatches"], 0)

    def test_recipe_rejects_an_unknown_driver_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_recipe = Path(temp_dir) / "recipe.json"
            payload = json.loads((SCOUT_ROOT / "recipe.json").read_text())
            payload["stages"][0]["driver_mode"] = "not-a-mode"
            invalid_recipe.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCOUT_ROOT / "verify_recipe.py"),
                    "--recipe",
                    str(invalid_recipe),
                    "--cache-root",
                    temp_dir,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown driver_mode", result.stderr)


if __name__ == "__main__":
    unittest.main()
