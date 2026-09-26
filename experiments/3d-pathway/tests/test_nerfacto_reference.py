from __future__ import annotations

import json
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

from tests.test_colmap_reference import fake_engine, run_cli


ROOT = Path(__file__).resolve().parents[1]
NERFSTUDIO_COMMIT = "50e0e3c70c775e89333256213363badbf074f29d"
TCNN_COMMIT = "0109538c37ac0bf613f2bac8de6cda48352feca7"
NERF_SYNTHETIC_SHA256 = "ce4e94e031c099a19ef04cfb6c71f1e47225d97d365be610b476e379a386c25f"
LPIPS_SHA256 = "7be5be791159472b1fbf3c69796f7cb30dca7ad8466c2df70058c37116cdee02"
FIXTURE_IMAGE_ID = "sha256:" + "a" * 64


def fake_nerfacto_engine(path: Path, fail: bool = False) -> Path:
    engine = path / ("fake-nerfacto-failing-engine" if fail else "fake-nerfacto-engine")
    failure = "exit 23" if fail else ""
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
            [[ " $* " == *" --gpus all "* ]]
            [[ " $* " == *" -e USER=surflo "* ]]
            [[ " $* " == *" -e TORCH_HOME=/model "* ]]
            [[ " $* " == *":/model/hub/checkpoints/alexnet-owt-7be5be79.pth:ro "* ]]
            [[ " $* " == *" {FIXTURE_IMAGE_ID} "* ]]
            input=''
            output=''
            previous=''
            for argument in "$@"; do
                if [[ "$previous" == -v && "$argument" == *:/input:ro ]]; then
                    input="${{argument%:/input:ro}}"
                elif [[ "$previous" == -v && "$argument" == *:/output ]]; then
                    output="${{argument%:/output}}"
                fi
                previous="$argument"
            done
            [[ -n "$input" && -n "$output" ]]
            [[ " $* " != *":/work "* ]]
            {failure}
            python3 - "$input" "$output" <<'PY'
            import json
            import math
            import csv
            from pathlib import Path
            import shutil
            import sys
            import numpy as np

            input_root = Path(sys.argv[1])
            output = Path(sys.argv[2])
            repository = Path("{ROOT}")
            sys.path.insert(0, str(repository / "pipeline"))
            from nerfacto_reference_runner import _component_count
            manifest = json.loads((input_root / "manifest.json").read_text())
            resolution = 128 if manifest["profile"] == "smoke" else 256
            axis = np.linspace(-1.0, 1.0, resolution, dtype=np.float32)
            xx, yy, zz = np.meshgrid(axis, axis, axis, indexing="ij")
            density = (25.0 * np.exp(-((np.sqrt(xx * xx + yy * yy + zz * zz) - 0.72) / 0.08) ** 2)).astype(np.float32)
            np.save(output / "field.density_grid.float32.npy", density, allow_pickle=False)

            render_dir = output / "target-renders"
            render_dir.mkdir()
            metric_rows = []
            for frame in manifest["target_frames"]:
                truth_rgb = np.load(input_root / frame["rgb_truth_path"], allow_pickle=False)
                truth_depth = np.load(input_root / frame["depth_path"], allow_pickle=False)
                predicted_rgb = np.clip(truth_rgb.astype(np.float32) / 255.0 + 0.01, 0.0, 1.0).astype(np.float32)
                foreground = truth_depth > 0.0
                accumulation = np.where(foreground, 0.9, 0.1).astype(np.float32)
                median = np.where(foreground, truth_depth + 0.05, 6.0).astype(np.float32)
                expected = np.where(foreground, truth_depth + 0.025, 6.0).astype(np.float32)
                np.save(render_dir / f"{{frame['id']}}.rgb.float32.npy", predicted_rgb, allow_pickle=False)
                np.save(render_dir / f"{{frame['id']}}.rgb.npy", np.rint(predicted_rgb * 255.0).astype(np.uint8), allow_pickle=False)
                np.save(render_dir / f"{{frame['id']}}.accumulation.npy", accumulation, allow_pickle=False)
                np.save(render_dir / f"{{frame['id']}}.median-camera-depth.npy", median, allow_pickle=False)
                np.save(render_dir / f"{{frame['id']}}.expected-camera-depth.npy", expected, allow_pickle=False)
                mse = float(np.mean((predicted_rgb.astype(np.float64) - truth_rgb.astype(np.float64) / 255.0) ** 2))
                metric_rows.append({{
                    "id": frame["id"],
                    "psnr_db": -10.0 * math.log10(mse),
                    "ssim": 0.99,
                    "lpips": 0.02,
                    "crop_lpips": 0.03,
                }})
            (output / "target-image-metrics.json").write_text(json.dumps(metric_rows, sort_keys=True) + "\\n")

            context_dir = output / "context-renders"
            context_dir.mkdir()
            context_rows = []
            frames = {{frame["id"]: frame for frame in manifest["context_frames"]}}
            for frame_id in manifest["primary_context_frame_ids"]:
                frame = frames[frame_id]
                truth_rgb = np.load(input_root / frame["rgb_truth_path"], allow_pickle=False)
                predicted_rgb = np.clip(truth_rgb.astype(np.float32) / 255.0 + 0.005, 0.0, 1.0).astype(np.float32)
                np.save(context_dir / f"{{frame_id}}.rgb.float32.npy", predicted_rgb, allow_pickle=False)
                np.save(context_dir / f"{{frame_id}}.rgb.npy", np.rint(predicted_rgb * 255.0).astype(np.uint8), allow_pickle=False)
                context_rows.append({{"id": frame_id, "lpips": 0.01, "crop_lpips": 0.015}})
            (output / "context-image-metrics.json").write_text(json.dumps(context_rows, sort_keys=True) + "\\n")

            sweep_metrics = {{}}
            for view_count, color_error, depth_error in ((3, 0.03, 0.12), (5, 0.02, 0.08), (9, 0.01, 0.04)):
                sweep_dir = output / "view-sweep" / f"views-{{view_count}}"
                sweep_dir.mkdir(parents=True)
                psnrs = []
                residuals = []
                for frame in manifest["target_frames"]:
                    truth_rgb = np.load(input_root / frame["rgb_truth_path"], allow_pickle=False)
                    truth_depth = np.load(input_root / frame["depth_path"], allow_pickle=False)
                    foreground = truth_depth > 0.0
                    predicted = np.clip(truth_rgb.astype(np.float32) / 255.0 + color_error, 0.0, 1.0).astype(np.float32)
                    accumulation = np.where(foreground, 0.9, 0.1).astype(np.float32)
                    expected = np.where(foreground, truth_depth + depth_error, 6.0).astype(np.float32)
                    common = np.load(input_root / frame["common_visible_mask_path"], allow_pickle=False).astype(bool)
                    psnrs.append(-10.0 * math.log10(float(np.mean((predicted.astype(np.float64) - truth_rgb.astype(np.float64) / 255.0) ** 2))))
                    valid = foreground & common & (accumulation >= 0.5) & (expected > 0.0)
                    residuals.append(expected[valid] - truth_depth[valid])
                    np.save(sweep_dir / f"{{frame['id']}}.rgb.float32.npy", predicted, allow_pickle=False)
                    np.save(sweep_dir / f"{{frame['id']}}.accumulation.npy", accumulation, allow_pickle=False)
                    np.save(sweep_dir / f"{{frame['id']}}.expected-camera-depth.npy", expected, allow_pickle=False)
                residual = np.concatenate(residuals).astype(np.float64)
                sweep_metrics[str(view_count)] = {{
                    "target_psnr_db": float(np.mean(psnrs)),
                    "expected_depth_rmse_m": float(np.sqrt(np.mean(residual * residual))),
                }}

            locked = output / "nerfstudio"
            locked.mkdir()
            (locked / "checkpoint.ckpt").write_bytes(b"fixture nerfacto checkpoint")
            (locked / "config.yml").write_text("method: nerfacto\\n")
            (output / "source-commit.txt").write_text("{NERFSTUDIO_COMMIT}\\n")
            (output / "tcnn-commit.txt").write_text("{TCNN_COMMIT}\\n")
            (output / "insula-manifest.txt").write_text(
                "schema_version=1\\nkind=radiance-field\\ncuda=12.8.1\\npython=3.12\\n"
                "torch=2.7.1+cu128\\ntorchvision=0.22.1+cu128\\npillow=11.1.0\\n"
                "nerfstudio_commit={NERFSTUDIO_COMMIT}\\ntiny_cuda_nn_commit={TCNN_COMMIT}\\n"
                "tcnn_cuda_architectures=100\\n"
                "requirements_lock_sha256=02c623f2a636dd774dda048f1a08c8d936d0701f74d3f50b3a7916d2280ed65a\\n"
                "network_policy=build-and-fetch-only\\n"
            )
            shutil.copy2(repository / "insulas/radiance-field/requirements.lock.txt", output / "requirements.lock.txt")
            shutil.copy2(repository / "insulas/radiance-field/resolved-requirements.lock.txt", output / "resolved-requirements.txt")
            (output / "runtime-versions.json").write_text(json.dumps({{
                "nerfstudio_commit": "{NERFSTUDIO_COMMIT}",
                "tiny_cuda_nn_commit": "{TCNN_COMMIT}",
                "requirements_lock_sha256": "02c623f2a636dd774dda048f1a08c8d936d0701f74d3f50b3a7916d2280ed65a",
                "resolved_requirements_sha256": "75324c79132de2fcf25b60444c7e9820baeebbc3a6db2002eb601ac2b5c33e4c",
                "torch": "2.7.1+cu128", "torchvision": "0.22.1+cu128",
                "pillow": "11.1.0", "python": "3.12.3", "numpy": "2.5.2",
                "cuda_runtime": "12.8", "cuda_compiler": "Cuda compilation tools, release 12.8, V12.8.93",
                "compute_capability": [10, 0], "tcnn_cuda_architectures": "100",
                "device": "fixture NVIDIA B200"
            }}, sort_keys=True) + "\\n")
            (output / "environment-gates.json").write_text(json.dumps({{
                "compute_capability_10_0": True, "tcnn_forward_backward": True,
                "nerfacto_forward_backward": True, "density_query_32": True
            }}, sort_keys=True) + "\\n")
            iterations = 1000 if manifest["profile"] == "smoke" else 20001
            rays = 1024 if manifest["profile"] == "smoke" else 2048
            (output / "training-summary.json").write_text(json.dumps({{
                "method": "nerfacto", "iterations": iterations, "rays_per_batch": rays,
                "density_resolution": resolution, "training_seconds": 4.0,
                "training_steps_per_second": iterations / 4.0, "density_query_seconds": 0.25,
                "camera_optimizer": "off", "appearance_embedding": False,
                "scene_contraction": False, "near_plane_m": 0.1, "far_plane_m": 6.0,
                "proposal_initial_sampler": "uniform", "tf32": False,
                "context_split_mode": "all-context-frames-train-and-eval",
                "dataloader_num_workers": 1,
                "seed": manifest["scene_seed"],
                "trained_view_sweep": {{"context_views": [3, 5, 9], "iterations": 1000, "rays_per_batch": 1024}},
                "view_sweep_training_seconds": {{"3": 1.0, "5": 1.0, "9": 1.0}}
            }}, sort_keys=True) + "\\n")
            sweep_rows = []
            for count, values in sweep_metrics.items():
                for metric, measurement in values.items():
                    sweep_rows.append({{
                        "factor": "context_view_count", "value": count,
                        "metric": metric, "measurement": measurement,
                        "interpretation": "fixture trained sweep",
                    }})
            indices = np.linspace(0, resolution - 1, 32, dtype=np.int64)
            component_grid = density[np.ix_(indices, indices, indices)]
            for threshold, label in ((0.1, "0_1"), (1.0, "1"), (10.0, "10"), (100.0, "100")):
                sweep_rows.extend([
                    {{"factor": "density_threshold", "value": threshold, "metric": "occupied_fraction", "measurement": float(np.mean(density >= threshold)), "interpretation": "fixture threshold"}},
                    {{"factor": "density_threshold", "value": threshold, "metric": "component_count_32cube", "measurement": _component_count(component_grid >= threshold), "interpretation": "fixture components"}},
                ])
            with (output / "failure_sweep.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["factor", "value", "metric", "measurement", "interpretation"])
                writer.writeheader()
                writer.writerows(sweep_rows)
            (output / "resource-usage.txt").write_text("Maximum resident set size (kbytes): 65432\\n")
            print("fixture Nerfacto completed")
            PY
            """
        ),
        encoding="utf-8",
    )
    engine.chmod(0o755)
    return engine


def run_fake_nerfacto_reference(root: Path, run_id: str = "nerfacto-smoke") -> Path:
    sys.path.insert(0, str(ROOT / "pipeline"))
    import nerfacto_reference_runner

    checkpoint = root / "fixture-alexnet-weights.pth"
    checkpoint.write_bytes(b"fixture weights")
    with mock.patch.dict(
        os.environ, {"SURFLO_PATHWAY_CONTAINER_ENGINE": str(fake_nerfacto_engine(root))}
    ), mock.patch.object(
        nerfacto_reference_runner, "_lpips_checkpoint_path", return_value=checkpoint
    ):
        return nerfacto_reference_runner.run_nerfacto_reference(
            root / "cache", "smoke", run_id
        )


class NerfactoReferenceFoundationTest(unittest.TestCase):
    def test_primary_source_is_registered_for_module_10(self) -> None:
        sources = {
            item["id"]: item
            for item in json.loads((ROOT / "sources.json").read_text())["sources"]
        }
        self.assertIn("nerfstudio-nerfacto-2025", sources)
        implementation = sources["nerfstudio-nerfacto-2025"]
        self.assertEqual(
            implementation["primary_url"],
            f"https://github.com/nerfstudio-project/nerfstudio/tree/{NERFSTUDIO_COMMIT}",
        )
        self.assertIn("per-scene radiance field", implementation["claims"][0])

        curriculum = {
            item["id"]: item
            for item in json.loads((ROOT / "curriculum.json").read_text())["modules"]
        }
        self.assertIn("nerfstudio-nerfacto-2025", curriculum["10"]["sources"])

    def test_adapter_keeps_rendering_and_geometry_contracts_separate(self) -> None:
        adapters = {
            item["id"]: item
            for item in json.loads((ROOT / "reference-adapters.json").read_text())["adapters"]
        }
        self.assertIn("nerfstudio-nerfacto-reference", adapters)
        adapter = adapters["nerfstudio-nerfacto-reference"]
        self.assertEqual(adapter["status"], "landed")
        self.assertEqual(
            adapter["command"],
            "run.sh reference --adapter nerfacto --profile smoke --run-id ID",
        )
        self.assertEqual(adapter["modules"], ["10"])
        self.assertEqual(adapter["model_contract"]["method"], "nerfacto")
        self.assertEqual(adapter["model_contract"]["inference"], "per-scene-optimization")
        self.assertFalse(adapter["model_contract"]["completion_claim"])
        self.assertFalse(adapter["model_contract"]["posterior_sampling_claim"])
        self.assertEqual(
            adapter["evaluation_contract"]["rendering"],
            "held-out target RGB; separate from geometry",
        )
        self.assertEqual(
            adapter["evaluation_contract"]["geometry"],
            "held-out depth restricted to common-visible analytic truth",
        )
        self.assertEqual(
            adapter["evaluation_contract"]["comparison_guardrail"],
            "do not compare heterogeneous retained Module 09 registry scalars",
        )
        self.assertEqual(adapter["evaluation_contract"]["trained_view_sweep"], [3, 5, 9])
        self.assertEqual(adapter["acceptance"]["smoke"]["target_psnr_db_min"], 20.0)
        self.assertEqual(adapter["acceptance"]["full"]["expected_depth_rmse_m_max"], 0.7)
        self.assertEqual(
            adapter["baseline_environment"]["container_image_id"],
            "sha256:49e4cbea691768dc3085796f5619266e156bc800ff8b92d88563498b872c12dc",
        )
        self.assertEqual(adapter["baseline_environment"]["gpu_model"], "NVIDIA B200")
        for profile, key in (
            ("smoke", "last_verified_smoke"),
            ("full", "last_verified_full"),
        ):
            self.assertEqual(adapter[key]["date"], "2026-09-26")
            self.assertGreater(adapter[key]["training_steps_per_second"], 0.0)
            self.assertGreater(adapter[key]["peak_gpu_compute_memory_bytes"], 0)
            self.assertNotAlmostEqual(
                adapter[key]["target_lpips"], adapter[key]["target_crop_lpips"]
            )
            self.assertGreaterEqual(
                adapter[key]["target_psnr_db"],
                adapter["acceptance"][profile]["target_psnr_db_min"],
            )
            self.assertLessEqual(
                adapter[key]["expected_depth_rmse_m"],
                adapter["acceptance"][profile]["expected_depth_rmse_m_max"],
            )
        self.assertLess(
            adapter["last_verified_full"]["expected_depth_rmse_m"],
            adapter["last_verified_smoke"]["expected_depth_rmse_m"],
        )
        self.assertIn("failure evidence", adapter["measurement_note"])

    def test_nerf_synthetic_archive_has_a_verified_lock(self) -> None:
        assets = {
            item["id"]: item
            for item in json.loads((ROOT / "assets.lock.json").read_text())["assets"]
        }
        archive = assets["nerf-synthetic"]
        self.assertEqual(archive["sha256"], NERF_SYNTHETIC_SHA256)
        self.assertEqual(archive["byte_size"], 370385516)
        self.assertEqual(archive["digest_status"], "verified_2026-09-26")
        self.assertEqual(
            archive["extraction"],
            {"mode": "zip", "roots": ["nerf_llff_data", "nerf_synthetic"]},
        )
        self.assertEqual(archive["consumers"], ["future-nerf-synthetic-extension"])

    def test_radiance_field_environment_is_blackwell_pinned(self) -> None:
        locks = json.loads((ROOT / "insulas/locks.json").read_text())["insulas"]
        self.assertIn("radiance-field", locks)
        radiance = locks["radiance-field"]
        self.assertEqual(radiance["nerfstudio_source_commit"], NERFSTUDIO_COMMIT)
        self.assertEqual(radiance["tiny_cuda_nn_source_commit"], TCNN_COMMIT)
        self.assertEqual(radiance["tcnn_cuda_architectures"], "100")
        self.assertEqual(radiance["pytorch"], "2.7.1+cu128")
        dependency_lock = ROOT / "insulas/radiance-field/requirements.lock.txt"
        self.assertTrue(dependency_lock.is_file())
        self.assertEqual(
            radiance["requirements_lock_sha256"],
            __import__("hashlib").sha256(dependency_lock.read_bytes()).hexdigest(),
        )
        resolved_lock = ROOT / "insulas/radiance-field/resolved-requirements.lock.txt"
        self.assertEqual(
            radiance["resolved_requirements_sha256"],
            __import__("hashlib").sha256(resolved_lock.read_bytes()).hexdigest(),
        )


class NerfactoReferenceExecutionContractTest(unittest.TestCase):
    def test_fake_smoke_run_is_offline_scored_and_atomically_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_nerfacto_reference(Path(temporary))
            result = json.loads((run_dir / "result.json").read_text())

            self.assertEqual(result["adapter"], "nerfacto")
            self.assertEqual(result["module_ids"], ["10"])
            self.assertEqual(result["network_mode"], "offline")
            self.assertEqual(result["support"]["completion_claim"], "none")
            self.assertEqual(result["support"]["posterior_sampling_claim"], "none")
            rendering = result["metrics"]["rendering"]
            geometry = result["metrics"]["geometry"]
            field = result["metrics"]["field"]
            self.assertGreater(rendering["target_psnr_db"], 35.0)
            self.assertNotAlmostEqual(rendering["target_ssim"], 0.99)
            self.assertAlmostEqual(rendering["target_lpips"], 0.02)
            self.assertGreater(rendering["target_crop_ssim"], 0.0)
            self.assertEqual(rendering["context_fit_views"], 5)
            self.assertAlmostEqual(geometry["expected_depth_rmse_m"], 0.025, places=5)
            self.assertAlmostEqual(geometry["median_depth_rmse_m"], 0.05, places=5)
            self.assertEqual(geometry["common_visible_accumulation_coverage"], 1.0)
            self.assertGreater(field["density_max"], 1.0)
            self.assertEqual(set(result["metrics"]["failure_sweep"]), {"3", "5", "9"})
            self.assertNotIn("comparison", result["metrics"])
            self.assertEqual(result["tool"]["container_image_id"], FIXTURE_IMAGE_ID)
            self.assertEqual(result["acceptance"]["target_psnr_db_min"], 20.0)
            self.assertIn("output/field.density_grid.float32.npy", result["provenance"]["artifacts_sha256"])
            self.assertIn("output/resolved-requirements.txt", result["provenance"]["artifacts_sha256"])
            self.assertIn("## Rendering", (run_dir / "report.md").read_text())

            sys.path.insert(0, str(ROOT / "pipeline"))
            from nerfacto_reference_runner import validate_nerfacto_reference_result

            validate_nerfacto_reference_result(run_dir)

    def test_failed_container_is_not_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sys.path.insert(0, str(ROOT / "pipeline"))
            import nerfacto_reference_runner

            checkpoint = root / "fixture-alexnet-weights.pth"
            checkpoint.write_bytes(b"fixture weights")
            with mock.patch.dict(
                os.environ,
                {"SURFLO_PATHWAY_CONTAINER_ENGINE": str(fake_nerfacto_engine(root, fail=True))},
            ), mock.patch.object(
                nerfacto_reference_runner, "_lpips_checkpoint_path", return_value=checkpoint
            ):
                with self.assertRaisesRegex(ValueError, "failed"):
                    nerfacto_reference_runner.run_nerfacto_reference(
                        root / "cache", "smoke", "failed-nerfacto"
                    )
            self.assertFalse((root / "cache/reference-runs/failed-nerfacto").exists())

    def test_tampered_metric_or_density_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_nerfacto_reference(Path(temporary))
            result_path = run_dir / "result.json"
            result = json.loads(result_path.read_text())
            result["metrics"]["rendering"]["target_psnr_db"] = 0.0
            result_path.write_text(json.dumps(result))
            sys.path.insert(0, str(ROOT / "pipeline"))
            from nerfacto_reference_runner import validate_nerfacto_reference_result

            with self.assertRaisesRegex(ValueError, "metric recomputation"):
                validate_nerfacto_reference_result(run_dir)

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_nerfacto_reference(Path(temporary))
            density = run_dir / "output/field.density_grid.float32.npy"
            values = np.load(density, allow_pickle=False)
            values.reshape(-1)[0] += 1.0
            np.save(density, values, allow_pickle=False)
            with self.assertRaisesRegex(
                ValueError, "metric recomputation|artifact|failure-sweep metric mismatch"
            ):
                validate_nerfacto_reference_result(run_dir)

    def test_real_profiles_are_explicit_b200_gates(self) -> None:
        for profile, variable in (
            ("smoke", "SURFLO_REQUIRE_NERFACTO_REFERENCE"),
            ("full", "SURFLO_REQUIRE_NERFACTO_FULL"),
        ):
            with self.subTest(profile=profile):
                if os.environ.get(variable) != "1":
                    continue
                docker = shutil.which("docker")
                self.assertIsNotNone(docker, "required Docker engine is unavailable")
                inspected = subprocess.run(
                    [docker, "image", "inspect", "surflo-pathway-radiance-field:1"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(inspected.returncode, 0, inspected.stderr)
                sys.path.insert(0, str(ROOT / "pipeline"))
                from nerfacto_reference_runner import run_nerfacto_reference

                cache = Path(
                    os.environ.get(
                        "SURFLO_PATHWAY_CACHE_ROOT",
                        Path.home() / ".cache/surflo/3d-pathway",
                    )
                )
                run_dir = run_nerfacto_reference(
                    cache, profile, f"nerfacto-real-{profile}-test-{os.getpid()}"
                )
                result = json.loads((run_dir / "result.json").read_text())
                self.assertEqual(result["profile"], profile)
                self.assertEqual(result["resources"]["gpu_measurement_status"], "measured")

    def test_public_reference_plan_is_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            completed = run_cli(
                "--emit-plan",
                "reference",
                "--adapter",
                "nerfacto",
                "--profile",
                "smoke",
                "--run-id",
                "nerfacto-plan",
                cache=Path(temporary) / "cache",
                engine=fake_engine(Path(temporary)),
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "adapter": "nerfacto",
                "command": "reference",
                "network_mode": "offline",
                "profile": "smoke",
                "run_id": "nerfacto-plan",
                "schema_version": 1,
            },
        )

    def test_scene_transform_contains_context_only_and_converts_opencv_axes(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from contracts import load_json, sha256_file
        from reference_scene import generate_radiance_field_scene

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "scene"
            manifest = generate_radiance_field_scene(
                destination,
                load_json(ROOT / "shared-scene.json"),
                "smoke",
            )
            transforms_path = destination / manifest["nerfstudio_transforms_path"]
            transforms = json.loads(transforms_path.read_text())
            self.assertEqual(manifest["nerfstudio_transforms_sha256"], sha256_file(transforms_path))
            self.assertEqual(len(transforms["frames"]), 5)
            self.assertEqual(len(manifest["context_frames"]), 9)
            self.assertEqual(len(manifest["primary_context_frame_ids"]), 5)
            self.assertEqual(set(manifest["view_sweep_context_frame_ids"]), {"3", "5", "9"})
            self.assertTrue(all("context-" in frame["file_path"] for frame in transforms["frames"]))
            self.assertFalse(any("target-" in frame["file_path"] for frame in transforms["frames"]))
            self.assertEqual(transforms["orientation_override"], "none")
            self.assertEqual(transforms["center_override"], "none")
            self.assertFalse(transforms["auto_scale_poses"])
            self.assertEqual(transforms["scale_factor"], 1.0)

            opencv = np.asarray(manifest["context_frames"][0]["camera_to_world_model"])
            opengl = np.asarray(transforms["frames"][0]["transform_matrix"])
            expected = opencv.copy()
            expected[:3, 1:3] *= -1.0
            self.assertTrue(np.allclose(opengl, expected, atol=0.0, rtol=0.0))
            self.assertTrue(all(
                frame["image_sha256"] != target["image_sha256"]
                for frame in manifest["context_frames"]
                for target in manifest["target_frames"]
            ))

    def test_entrypoint_declares_controlled_nerfacto_overrides(self) -> None:
        entrypoint = ROOT / "insulas/radiance-field/run-nerfacto.py"
        self.assertTrue(entrypoint.is_file())
        text = entrypoint.read_text()
        self.assertIn('method_configs["nerfacto"]', text)
        self.assertIn('camera_optimizer.mode = "off"', text)
        self.assertIn("use_appearance_embedding = False", text)
        self.assertIn("disable_scene_contraction = True", text)
        self.assertIn("orientation_method = \"none\"", text)
        self.assertIn("auto_scale_poses = False", text)
        self.assertIn('eval_mode = "all"', text)
        self.assertIn("dataloader_num_workers = 1", text)
        self.assertIn("get_outputs_for_camera", text)
        self.assertIn('outputs["accumulation"]', text)
        self.assertIn('outputs["expected_depth"]', text)
        self.assertIn("to(ray_bundle.directions.device)", text)
        self.assertIn("model.lpips", text)
        self.assertIn("truth_tensor", text)
        self.assertIn('Image.open(input_root / str(frame["mask_path"]))', text)
        self.assertIn("foreground_mask", text)
        self.assertNotIn("np.any(truth != 0", text)
        self.assertIn("context-renders", text)
        self.assertIn("view-sweep", text)
        self.assertLess(text.index("trainer.train()"), text.index('manifest["target_frames"]'))

    def test_lpips_crop_uses_truth_mask_not_nonzero_rgb(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from contracts import load_json
        from reference_scene import generate_radiance_field_scene

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "scene"
            manifest = generate_radiance_field_scene(
                destination,
                load_json(ROOT / "shared-scene.json"),
                "smoke",
            )
            frame = manifest["target_frames"][0]
            truth = np.load(destination / frame["rgb_truth_path"], allow_pickle=False)
            foreground = (
                np.load(destination / frame["depth_path"], allow_pickle=False) > 0
            )
            rgb_nonzero = np.any(truth != 0, axis=-1)

            self.assertTrue(rgb_nonzero.all())
            self.assertGreater(np.count_nonzero(foreground), 0)
            self.assertLess(np.count_nonzero(foreground), foreground.size)
            self.assertFalse(np.array_equal(foreground, rgb_nonzero))

if __name__ == "__main__":
    unittest.main()
