from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

from tests.test_colmap_reference import ROOT, fake_engine, run_cli


SOURCE_COMMIT = "a561b849ebae10a6f5ef49e26c83cbbcd36c71bf"
CHECKPOINT_REVISION = "3bc65d4e14a6786a61acec16453c50e12bf5f338"
CHECKPOINT_SHA256 = "b782898d8a3e8be1f639de33837ed85e9b4b73e40f8f5e5cd99067588d722545"
CHECKPOINT_BYTES = 99_222_290


class DepthAnythingReferenceFoundationTest(unittest.TestCase):
    def test_public_reference_plan_is_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            completed = run_cli(
                "--emit-plan",
                "reference",
                "--adapter",
                "depth-anything-v2",
                "--profile",
                "smoke",
                "--run-id",
                "depth-plan",
                cache=Path(temporary) / "cache",
                engine=fake_engine(Path(temporary)),
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "adapter": "depth-anything-v2",
                "command": "reference",
                "network_mode": "offline",
                "profile": "smoke",
                "run_id": "depth-plan",
                "schema_version": 1,
            },
        )

    def test_official_source_checkpoint_and_adapter_are_locked(self) -> None:
        assets = {
            item["id"]: item for item in json.loads((ROOT / "assets.lock.json").read_text())["assets"]
        }
        checkpoint = assets["depth-anything-v2-metric-hypersim-small"]
        self.assertEqual(checkpoint["sha256"], CHECKPOINT_SHA256)
        self.assertEqual(checkpoint["byte_size"], CHECKPOINT_BYTES)
        self.assertEqual(checkpoint["license"], "Apache-2.0")
        self.assertIn(CHECKPOINT_REVISION, checkpoint["source"])
        self.assertEqual(checkpoint["consumers"], ["depth-anything-v2-reference"])

        adapters = {
            item["id"]: item
            for item in json.loads((ROOT / "reference-adapters.json").read_text())["adapters"]
        }
        adapter = adapters["depth-anything-v2-reference"]
        self.assertEqual(adapter["status"], "landed")
        self.assertEqual(adapter["modules"], ["08"])
        self.assertIn("raw_rmse_m_max", adapter["acceptance"]["smoke"])
        self.assertIn("affine_aligned_rmse_m_max", adapter["acceptance"]["full"])

        locks = json.loads((ROOT / "insulas/locks.json").read_text())["insulas"]
        self.assertEqual(locks["neural-rendering"]["depth_anything_v2_source_commit"], SOURCE_COMMIT)
        dockerfile = (ROOT / "insulas/neural-rendering/Dockerfile").read_text(encoding="utf-8")
        self.assertIn(f"ARG DEPTH_ANYTHING_V2_COMMIT={SOURCE_COMMIT}", dockerfile)
        self.assertIn("torch==2.10.0", dockerfile)
        self.assertIn("torchvision==0.25.0", dockerfile)

    def test_depth_metrics_keep_raw_metric_error_separate_from_alignment(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from depth_reference_runner import _depth_metrics

        truth = np.linspace(2.0, 6.0, 80, dtype=np.float32).reshape(8, 10)
        prediction = ((truth - 0.7) / 1.4).astype(np.float32)
        metrics = _depth_metrics(prediction, truth)

        self.assertGreater(metrics["raw_rmse_m"], 0.5)
        self.assertGreater(metrics["raw_abs_rel"], 0.1)
        self.assertLess(metrics["affine_aligned_rmse_m"], 1e-6)
        self.assertAlmostEqual(metrics["affine_scale"], 1.4, places=5)
        self.assertAlmostEqual(metrics["affine_shift_m"], 0.7, places=5)
        self.assertEqual(metrics["valid_pixels"], truth.size)

    def test_controlled_inputs_are_deterministic_visible_depth_not_completion(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from contracts import load_json, sha256_file
        from reference_scene import generate_learned_depth_scene

        scene = load_json(ROOT / "shared-scene.json")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = generate_learned_depth_scene(root / "first", scene, "smoke")
            second = generate_learned_depth_scene(root / "second", scene, "smoke")

            self.assertEqual(first, second)
            self.assertEqual(first["profile"], "smoke")
            self.assertEqual(first["prediction_domain"], "input-visible-pixels")
            self.assertEqual(first["hidden_scene_truth"], "not-defined")
            self.assertEqual(first["case_families"], ["shared-scene", "focal-crop", "ood-concavity"])
            self.assertEqual(len(first["cases"]), 3)
            self.assertEqual([case["family"] for case in first["cases"]], first["case_families"])

            for case in first["cases"]:
                image_path = root / "first" / case["image_path"]
                depth_path = root / "first" / case["depth_path"]
                depth = np.load(depth_path, allow_pickle=False)
                self.assertEqual(case["image_sha256"], sha256_file(image_path))
                self.assertEqual(case["depth_sha256"], sha256_file(depth_path))
                self.assertEqual(depth.shape, (480, 640))
                self.assertEqual(depth.dtype, np.float32)
                self.assertTrue(np.isfinite(depth).all())
                self.assertGreater(float(depth.min()), 0.0)

            focal = np.load(root / "first" / first["cases"][1]["depth_path"], allow_pickle=False)
            baseline = np.load(root / "first" / first["cases"][0]["depth_path"], allow_pickle=False)
            self.assertFalse(np.array_equal(focal, baseline))
            self.assertAlmostEqual(first["cases"][1]["effective_focal_scale"], 1.25)

            ood = first["cases"][2]
            self.assertEqual(ood["geometry"], "concave-open-box")
            self.assertLess(float(np.load(root / "first" / ood["depth_path"])[240, 320]), 6.0)

            full = generate_learned_depth_scene(root / "full", scene, "full")
            self.assertEqual(len(full["cases"]), 11)
            self.assertEqual(sum(case["family"] == "shared-scene" for case in full["cases"]), 9)


if __name__ == "__main__":
    unittest.main()
