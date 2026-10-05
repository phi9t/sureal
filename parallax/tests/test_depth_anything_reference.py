from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

import numpy as np

from tests.test_colmap_reference import ROOT, fake_engine, run_cli


SOURCE_COMMIT = "a561b849ebae10a6f5ef49e26c83cbbcd36c71bf"
CHECKPOINT_REVISION = "3bc65d4e14a6786a61acec16453c50e12bf5f338"
CHECKPOINT_SHA256 = "b782898d8a3e8be1f639de33837ed85e9b4b73e40f8f5e5cd99067588d722545"
CHECKPOINT_BYTES = 99_222_290
FIXTURE_IMAGE_ID = "sha256:" + "d" * 64


def fake_depth_engine(path: Path) -> Path:
    engine = path / "fake-depth-container-engine"
    engine.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail
            if [[ "${{1:-}}" == image && "${{2:-}}" == inspect ]]; then
                printf '{FIXTURE_IMAGE_ID}\\n'
                exit 0
            fi
            [[ "${{1:-}}" == run ]]
            [[ " $* " == *" --network none "* ]]
            [[ " $* " == *" --pull=never "* ]]
            [[ " $* " == *" --gpus device="* ]]
            [[ " $* " == *" --cidfile "* ]]
            [[ " $* " == *" --user "* ]]
            [[ " $* " == *" -e USER=surflo "* ]]
            [[ " $* " == *" -e CUDA_CACHE_PATH=/cuda-cache "* ]]
            [[ " $* " == *" {FIXTURE_IMAGE_ID} "* ]]
            work=''
            checkpoint=''
            previous=''
            for argument in "$@"; do
                if [[ "$previous" == -v && "$argument" == *:/work ]]; then
                    work="${{argument%:/work}}"
                elif [[ "$previous" == -v && "$argument" == *:/model/checkpoint.pth:ro ]]; then
                    checkpoint="${{argument%:/model/checkpoint.pth:ro}}"
                fi
                previous="$argument"
            done
            [[ -n "$work" && -f "$checkpoint" ]]
            python3 - "$work" <<'PY'
            import json
            from pathlib import Path
            import sys

            import numpy as np

            root = Path(sys.argv[1])
            manifest = json.loads((root / "input/manifest.json").read_text())
            output = root / "output"
            predictions = output / "predictions"
            predictions.mkdir(parents=True)
            for case in manifest["cases"]:
                truth = np.load(root / "input" / case["depth_path"], allow_pickle=False)
                transforms = {{
                    "shared-scene": (1.15, 0.20),
                    "focal-crop": (0.80, 1.00),
                    "ood-concavity": (1.40, -0.30),
                }}
                scale, shift = transforms[case["family"]]
                prediction = (truth * scale + shift).astype(np.float32)
                valid = np.ones(truth.shape, dtype=np.uint8)
                np.save(predictions / f"{{case['id']}}.depth.npy", prediction, allow_pickle=False)
                np.save(predictions / f"{{case['id']}}.valid.npy", valid, allow_pickle=False)
            (output / "source-commit.txt").write_text("{SOURCE_COMMIT}\\n")
            (output / "insula-manifest.txt").write_text(
                "schema_version=1\\n"
                "kind=neural-rendering\\n"
                "cuda=13.2.1\\n"
                "uv=0.11.13\\n"
                "torch=2.13.0+cu132\\n"
                "torchvision=0.28.0+cu132\\n"
                "depth_anything_v2_commit={SOURCE_COMMIT}\\n"
                "network_policy=build-and-fetch-only\\n"
            )
            (output / "runtime-versions.json").write_text(json.dumps({{
                "source_commit": "{SOURCE_COMMIT}",
                "torch": "2.13.0+cu132",
                "torchvision": "0.28.0+cu132",
                "numpy": np.__version__,
                "opencv": "4.13.0",
                "cuda_runtime": "13.2",
                "device": "fixture-cuda",
            }}, sort_keys=True) + "\\n")
            (output / "resource-usage.txt").write_text(
                "Maximum resident set size (kbytes): 12345\\n"
            )
            print("fixture Depth Anything V2 completed")
            PY
            """
        ),
        encoding="utf-8",
    )
    engine.chmod(0o755)
    return engine


def run_fake_depth_reference(root: Path, profile: str = "smoke", run_id: str = "depth-smoke") -> Path:
    sys.path.insert(0, str(ROOT / "pipeline"))
    import depth_reference_runner

    cache = root / "cache"
    asset_dir = cache / "assets"
    asset_dir.mkdir(parents=True)
    checkpoint = asset_dir / "depth-anything-v2-metric-hypersim-small.archive"
    checkpoint.write_bytes(b"fixture depth checkpoint")
    fixture_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    official = {
        item["id"]: item for item in json.loads((ROOT / "assets.lock.json").read_text())["assets"]
    }["depth-anything-v2-metric-hypersim-small"]
    record = {**official, "sha256": fixture_sha, "byte_size": checkpoint.stat().st_size}
    engine = fake_depth_engine(root)
    with (
        mock.patch.object(depth_reference_runner, "_checkpoint_record", return_value=record),
        mock.patch.object(depth_reference_runner, "CHECKPOINT_SHA256", fixture_sha),
        mock.patch.object(depth_reference_runner, "CHECKPOINT_BYTES", checkpoint.stat().st_size),
        mock.patch.dict(os.environ, {"SURFLO_PATHWAY_CONTAINER_ENGINE": str(engine)}),
    ):
        return depth_reference_runner.run_depth_reference(cache, profile, run_id)


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
        self.assertIn("--index-url https://download.pytorch.org/whl/cu132", dockerfile)
        self.assertIn("torch==2.13.0", dockerfile)
        self.assertIn("torchvision==0.28.0", dockerfile)

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

        inverted = _depth_metrics(np.flip(truth.reshape(-1)).reshape(truth.shape).copy(), truth)
        self.assertEqual(inverted["affine_scale"], 0.0)
        self.assertTrue(inverted["alignment_scale_at_boundary"])
        self.assertGreater(inverted["affine_aligned_rmse_m"], 0.5)

        constant = _depth_metrics(np.full_like(truth, 4.0), truth)
        self.assertEqual(constant["affine_scale"], 0.0)
        self.assertAlmostEqual(constant["affine_shift_m"], float(truth.mean()), places=6)
        self.assertTrue(constant["alignment_scale_at_boundary"])
        self.assertGreater(constant["affine_aligned_rmse_m"], 1.0)

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


class DepthAnythingReferenceAdapterTest(unittest.TestCase):
    def test_checkpoint_asset_directory_cannot_escape_the_cache_root(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from depth_reference_runner import _checkpoint_path

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            outside = root / "outside-assets"
            cache.mkdir()
            outside.mkdir()
            checkpoint = outside / "depth-anything-v2-metric-hypersim-small.archive"
            checkpoint.write_bytes(b"fixture")
            (cache / "assets").symlink_to(outside, target_is_directory=True)
            record = {
                "sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "byte_size": checkpoint.stat().st_size,
            }
            with self.assertRaisesRegex(ValueError, "cache|escape|directory"):
                _checkpoint_path(cache.resolve(), record)

    def test_checkpoint_hash_mismatch_fails_before_execution(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from depth_reference_runner import run_depth_reference

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            asset_dir = cache / "assets"
            asset_dir.mkdir(parents=True)
            (asset_dir / "depth-anything-v2-metric-hypersim-small.archive").write_bytes(b"wrong")
            with mock.patch.dict(
                os.environ,
                {"SURFLO_PATHWAY_CONTAINER_ENGINE": str(fake_depth_engine(root))},
            ):
                with self.assertRaisesRegex(ValueError, "checkpoint.*(?:byte-size|hash)"):
                    run_depth_reference(cache, "smoke", "bad-checkpoint")
            self.assertFalse((cache / "reference-runs/bad-checkpoint").exists())

    def test_fake_smoke_run_is_offline_scored_and_atomically_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = run_fake_depth_reference(root)
            result = json.loads((run_dir / "result.json").read_text())

            self.assertEqual(result["adapter"], "depth-anything-v2")
            self.assertEqual(result["module_ids"], ["08"])
            self.assertEqual(result["network_mode"], "offline")
            self.assertEqual(result["metrics"]["evaluated_cases"], 3)
            self.assertEqual(result["metrics"]["valid_pixel_fraction"], 1.0)
            self.assertGreater(result["metrics"]["raw_rmse_m"], 0.5)
            self.assertGreater(result["metrics"]["affine_aligned_rmse_m"], 0.05)
            self.assertIn("affine_scale", result["metrics"])
            self.assertTrue(
                all(
                    record["affine_aligned_rmse_m"] < 1e-5
                    for record in result["case_metrics"].values()
                )
            )
            self.assertEqual(set(result["case_metrics"]), {"shared-000", "focal-crop", "ood-concavity"})
            self.assertEqual(
                result["support"],
                {
                    "prediction_domain": "input-visible-pixels",
                    "model_output": "deterministic-per-view-camera-axis-depth",
                    "hidden_scene_prediction_count": 0,
                    "complete_scene_samples": 0,
                    "completion_claim": "none",
                    "posterior_sampling_claim": "none",
                },
            )
            for relative in (
                "input/manifest.json",
                "output/predictions/shared-000.depth.npy",
                "output/predictions/focal-crop.depth.npy",
                "output/predictions/ood-concavity.depth.npy",
                "output/visualizations/shared-000-comparison.ppm",
                "output/visualizations/focal-crop-comparison.ppm",
                "output/visualizations/ood-concavity-comparison.ppm",
                "output/checkpoint.json",
                "output/runtime-versions.json",
                "output/resource-summary.json",
                "adapter.log",
                "report.md",
            ):
                self.assertTrue((run_dir / relative).is_file(), relative)
            self.assertFalse(any((root / "cache/reference-staging").glob("*")))

            sys.path.insert(0, str(ROOT / "pipeline"))
            import depth_reference_runner

            checkpoint_record = json.loads((run_dir / "output/checkpoint.json").read_text())
            with (
                mock.patch.object(
                    depth_reference_runner, "_checkpoint_record", return_value=checkpoint_record
                ),
                mock.patch.object(
                    depth_reference_runner,
                    "CHECKPOINT_SHA256",
                    checkpoint_record["sha256"],
                ),
                mock.patch.object(
                    depth_reference_runner,
                    "CHECKPOINT_BYTES",
                    checkpoint_record["byte_size"],
                ),
            ):
                depth_reference_runner.validate_depth_reference_result(run_dir)

                result["metrics"]["raw_rmse_m"] += 1.0
                (run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "metric mismatch"):
                    depth_reference_runner.validate_depth_reference_result(run_dir)

    def test_validator_binds_tool_and_evaluator_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_depth_reference(Path(temporary), run_id="depth-provenance")
            original = json.loads((run_dir / "result.json").read_text())
            checkpoint_record = json.loads((run_dir / "output/checkpoint.json").read_text())
            sys.path.insert(0, str(ROOT / "pipeline"))
            import depth_reference_runner

            mutations = (
                ("tool-version", lambda result: result["tool"].__setitem__("version", "forged")),
                (
                    "package-version",
                    lambda result: result["tool"].__setitem__("package_version", "forged"),
                ),
                (
                    "image-id",
                    lambda result: result["tool"].__setitem__("container_image_id", "forged"),
                ),
                (
                    "evaluator-version",
                    lambda result: result["provenance"]["config"].__setitem__(
                        "evaluation_software", {"numpy": "forged"}
                    ),
                ),
                (
                    "cuda-cache-policy",
                    lambda result: result["provenance"]["config"].__setitem__(
                        "cuda_cache", "forged"
                    ),
                ),
            )
            with (
                mock.patch.object(
                    depth_reference_runner, "_checkpoint_record", return_value=checkpoint_record
                ),
                mock.patch.object(
                    depth_reference_runner,
                    "CHECKPOINT_SHA256",
                    checkpoint_record["sha256"],
                ),
                mock.patch.object(
                    depth_reference_runner,
                    "CHECKPOINT_BYTES",
                    checkpoint_record["byte_size"],
                ),
            ):
                for name, mutate in mutations:
                    with self.subTest(mutation=name):
                        forged = json.loads(json.dumps(original))
                        mutate(forged)
                        config = forged["provenance"]["config"]
                        forged["provenance"]["config_sha256"] = hashlib.sha256(
                            depth_reference_runner.canonical_json(config)
                        ).hexdigest()
                        (run_dir / "result.json").write_text(json.dumps(forged))
                        with self.assertRaisesRegex(ValueError, "identity|binding"):
                            depth_reference_runner.validate_depth_reference_result(run_dir)

    def test_full_profile_evaluates_all_shared_views_and_failure_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_depth_reference(Path(temporary), "full", "depth-full")
            result = json.loads((run_dir / "result.json").read_text())
            self.assertEqual(result["metrics"]["evaluated_cases"], 11)
            self.assertEqual(sum(key.startswith("shared-") for key in result["case_metrics"]), 9)
            self.assertEqual(result["acceptance"]["evaluated_cases_min"], 11)

    def test_real_smoke_reference_runs_when_required(self) -> None:
        required = os.environ.get("SURFLO_REQUIRE_DEPTH_ANYTHING_REFERENCE") == "1"
        docker = shutil.which("docker")
        cache = Path(os.environ.get("SURFLO_PATHWAY_CACHE_ROOT", Path.home() / ".cache/surflo/3d-pathway"))
        checkpoint = cache / "assets/depth-anything-v2-metric-hypersim-small.archive"
        image = None if docker is None else subprocess.run(
            [docker, "image", "inspect", "surflo-pathway-neural-rendering:1"],
            text=True,
            capture_output=True,
            check=False,
        )
        if docker is None or image is None or image.returncode != 0 or not checkpoint.is_file():
            if required:
                self.fail("required real Depth Anything V2 image/checkpoint is unavailable")
            self.skipTest("real Depth Anything V2 image/checkpoint is unavailable")
        sys.path.insert(0, str(ROOT / "pipeline"))
        from depth_reference_runner import run_depth_reference

        run_id = f"depth-real-smoke-test-{os.getpid()}"
        run_dir = run_depth_reference(cache, "smoke", run_id)
        result = json.loads((run_dir / "result.json").read_text())
        self.assertEqual(result["metrics"]["evaluated_cases"], 3)
        self.assertEqual(result["resources"]["gpu_measurement_status"], "measured")

    def test_real_full_reference_runs_when_required(self) -> None:
        required = os.environ.get("SURFLO_REQUIRE_DEPTH_ANYTHING_FULL") == "1"
        if not required:
            self.skipTest("full B200 profile is opt-in")
        docker = shutil.which("docker")
        cache = Path(
            os.environ.get(
                "SURFLO_PATHWAY_CACHE_ROOT", Path.home() / ".cache/surflo/3d-pathway"
            )
        )
        checkpoint = cache / "assets/depth-anything-v2-metric-hypersim-small.archive"
        image = None if docker is None else subprocess.run(
            [docker, "image", "inspect", "surflo-pathway-neural-rendering:1"],
            text=True,
            capture_output=True,
            check=False,
        )
        if docker is None or image is None or image.returncode != 0 or not checkpoint.is_file():
            self.fail("required full Depth Anything V2 image/checkpoint is unavailable")
        sys.path.insert(0, str(ROOT / "pipeline"))
        from depth_reference_runner import run_depth_reference

        run_id = f"depth-real-full-test-{os.getpid()}"
        run_dir = run_depth_reference(cache, "full", run_id)
        result = json.loads((run_dir / "result.json").read_text())
        self.assertEqual(result["metrics"]["evaluated_cases"], 11)
        self.assertEqual(result["metrics"]["valid_pixel_fraction"], 1.0)
        self.assertEqual(result["resources"]["gpu_measurement_status"], "measured")


if __name__ == "__main__":
    unittest.main()
