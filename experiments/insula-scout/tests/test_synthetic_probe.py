from __future__ import annotations

from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

import numpy as np


SYNTHETIC_ROOT = Path(__file__).resolve().parents[1] / "synthetic_ambiguity"
sys.path.insert(0, str(SYNTHETIC_ROOT))

from probe import classify_hypothesis, resolve_episode, target_new_mask  # noqa: E402


class SyntheticAmbiguityProbeTest(unittest.TestCase):
    def test_photoreal_probe_summary_imports_on_surflo_python(self) -> None:
        path = SYNTHETIC_ROOT.parents[1] / "photoreal-scenes" / "pipeline" / "probe_summary.py"
        spec = importlib.util.spec_from_file_location("photoreal_probe_summary_py310", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.build_summary))

    def test_photoreal_fetch_pins_vggt_and_probe_forces_hub_offline(self) -> None:
        script = (SYNTHETIC_ROOT.parent / "run_scout.sh").read_text(encoding="utf-8")
        self.assertIn('MODEL_LOCK="experiments/photoreal-scenes/model.lock.json"', script)
        self.assertIn('python "${MODEL_LOCK_TOOL}" verify', script)
        self.assertIn('hf download "${VGGT_REPOSITORY}" --revision "${VGGT_REVISION}"', script)
        self.assertIn("HF_HUB_OFFLINE=1", script)
        self.assertIn("--source-recipe", script)
        self.assertIn("--model-lock", script)
        self.assertNotIn("VGGT_CONFIG_SHA256=", script)

    def test_resolves_v1_and_v2_episode_directories_without_changing_layout(self) -> None:
        for schema_version in (1, 2):
            with self.subTest(schema_version=schema_version), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                (root / "scene_a" / "context" / "rgb").mkdir(parents=True)
                (root / "scene_a" / "surface.npz").touch()
                (root / "scene_b").mkdir()
                (root / "scene_b" / "surface.npz").touch()
                (root / "cameras.npz").touch()
                (root / "manifest.json").write_text(
                    json.dumps({"schema_version": schema_version}), encoding="utf-8"
                )
                paths = resolve_episode(root)
                self.assertEqual(paths.schema_version, schema_version)
                self.assertEqual(paths.context_rgb, root / "scene_a" / "context" / "rgb")
                self.assertEqual(paths.surface_b, root / "scene_b" / "surface.npz")

    def test_v2_target_only_visibility_falls_back_without_changing_v1_alias(self) -> None:
        v1 = {"new_in_target": np.asarray([True, False])}
        v2 = {"target_only_visible": np.asarray([False, True])}
        np.testing.assert_array_equal(target_new_mask(v1), [True, False])
        np.testing.assert_array_equal(target_new_mask(v2), [False, True])

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
