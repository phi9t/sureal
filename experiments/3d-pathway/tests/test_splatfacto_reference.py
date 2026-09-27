from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
NERFSTUDIO_COMMIT = "50e0e3c70c775e89333256213363badbf074f29d"
GSPLAT_COMMIT = "4d3a3b69db4de0326f983ccf7b7b255271a17b01"
FIXTURE_IMAGE_ID = next(
    item["baseline_environment"]["container_image_id"]
    for item in json.loads((ROOT / "reference-adapters.json").read_text())["adapters"]
    if item["id"] == "nerfstudio-splatfacto-reference"
)


def fake_splatfacto_engine(path: Path, fail: bool = False) -> Path:
    engine = path / ("fake-splatfacto-failing-engine" if fail else "fake-splatfacto-engine")
    failure = "exit 29" if fail else ""
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
            [[ " $* " == *" -e USER=surflo "* ]]
            [[ " $* " == *" -e TORCH_EXTENSIONS_DIR=/cuda-cache/torch-extensions "* ]]
            [[ " $* " == *" -e TRITON_CACHE_DIR=/cuda-cache/triton "* ]]
            [[ " $* " == *":/input:ro "* ]]
            {failure}
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
            python3 - "$input" "$output" <<'PY'
            import csv
            import json
            import math
            from pathlib import Path
            import shutil
            import sys
            import numpy as np

            input_root = Path(sys.argv[1])
            output = Path(sys.argv[2])
            repository = Path("{ROOT}")
            manifest = json.loads((input_root / "manifest.json").read_text())
            output.mkdir(exist_ok=True)

            means = np.array([
                [0.72, 0.0, 0.0], [-0.72, 0.0, 0.0],
                [0.0, 0.72, 0.0], [0.0, 0.0, 0.72],
            ], dtype=np.float32)
            log_scales = np.log(np.full((4, 3), 0.03, dtype=np.float32))
            quaternions = np.zeros((4, 4), dtype=np.float32)
            quaternions[:, 0] = 1.0
            opacity_logits = np.full((4, 1), 3.0, dtype=np.float32)
            features_dc = np.zeros((4, 3), dtype=np.float32)
            np.savez_compressed(
                output / "gaussians.npz", means=means, log_scales=log_scales,
                quaternions=quaternions, opacity_logits=opacity_logits,
                features_dc=features_dc,
            )
            ply_names = (
                "x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2",
                "opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3",
            )
            ply_dtype = np.dtype([(name, "<f4") for name in ply_names])
            vertices = np.zeros(4, dtype=ply_dtype)
            for index, name in enumerate(("x", "y", "z")):
                vertices[name] = means[:, index]
            for index, name in enumerate(("f_dc_0", "f_dc_1", "f_dc_2")):
                vertices[name] = features_dc[:, index]
            vertices["opacity"] = opacity_logits[:, 0]
            for index, name in enumerate(("scale_0", "scale_1", "scale_2")):
                vertices[name] = log_scales[:, index]
            for index, name in enumerate(("rot_0", "rot_1", "rot_2", "rot_3")):
                vertices[name] = quaternions[:, index]
            header_lines = [
                "ply", "format binary_little_endian 1.0",
                "comment renderable_primitives_not_mesh", "element vertex 4",
            ]
            header_lines.extend(f"property float {{name}}" for name in ply_names)
            header_lines.append("end_header")
            header = ("\\n".join(header_lines) + "\\n").encode("ascii")
            (output / "gaussians.ply").write_bytes(header + vertices.tobytes())

            target_dir = output / "target-renders"
            context_dir = output / "context-renders"
            target_dir.mkdir()
            context_dir.mkdir()
            target_metrics = []
            for frame in manifest["target_frames"]:
                truth = np.load(input_root / frame["rgb_truth_path"], allow_pickle=False)
                depth = np.load(input_root / frame["depth_path"], allow_pickle=False)
                foreground = depth > 0.0
                predicted = np.clip(truth.astype(np.float32) / 255.0 + 0.01, 0.0, 1.0)
                accumulation = np.where(foreground, 0.9, 0.1).astype(np.float32)
                expected = np.where(foreground, depth + 0.025, 6.0).astype(np.float32)
                np.save(target_dir / f"{{frame['id']}}.rgb.float32.npy", predicted, allow_pickle=False)
                np.save(target_dir / f"{{frame['id']}}.rgb.npy", np.rint(predicted * 255).astype(np.uint8), allow_pickle=False)
                np.save(target_dir / f"{{frame['id']}}.accumulation.npy", accumulation, allow_pickle=False)
                np.save(target_dir / f"{{frame['id']}}.expected-camera-depth.npy", expected, allow_pickle=False)
                target_metrics.append({{"id": frame["id"], "lpips": 0.02, "crop_lpips": 0.03}})
            (output / "target-image-metrics.json").write_text(json.dumps(target_metrics, sort_keys=True) + "\\n")

            frame_by_id = {{frame["id"]: frame for frame in manifest["context_frames"]}}
            context_metrics = []
            for frame_id in manifest["primary_context_frame_ids"]:
                frame = frame_by_id[frame_id]
                truth = np.load(input_root / frame["rgb_truth_path"], allow_pickle=False)
                predicted = np.clip(truth.astype(np.float32) / 255.0 + 0.005, 0.0, 1.0)
                np.save(context_dir / f"{{frame_id}}.rgb.float32.npy", predicted, allow_pickle=False)
                np.save(context_dir / f"{{frame_id}}.rgb.npy", np.rint(predicted * 255).astype(np.uint8), allow_pickle=False)
                context_metrics.append({{"id": frame_id, "lpips": 0.01, "crop_lpips": 0.015}})
            (output / "context-image-metrics.json").write_text(json.dumps(context_metrics, sort_keys=True) + "\\n")

            rows = []
            for count, color_error, depth_error, primitives in (
                (3, 0.03, 0.12, 3000), (5, 0.02, 0.08, 5000), (9, 0.01, 0.04, 9000)
            ):
                sweep = output / "view-sweep" / f"views-{{count}}"
                sweep.mkdir(parents=True)
                psnrs = []
                residuals = []
                for frame in manifest["target_frames"]:
                    truth = np.load(input_root / frame["rgb_truth_path"], allow_pickle=False)
                    depth = np.load(input_root / frame["depth_path"], allow_pickle=False)
                    common = np.load(input_root / frame["common_visible_mask_path"], allow_pickle=False).astype(bool)
                    foreground = depth > 0.0
                    predicted = np.clip(truth.astype(np.float32) / 255.0 + color_error, 0.0, 1.0)
                    accumulation = np.where(foreground, 0.9, 0.1).astype(np.float32)
                    expected = np.where(foreground, depth + depth_error, 6.0).astype(np.float32)
                    np.save(sweep / f"{{frame['id']}}.rgb.float32.npy", predicted, allow_pickle=False)
                    np.save(sweep / f"{{frame['id']}}.accumulation.npy", accumulation, allow_pickle=False)
                    np.save(sweep / f"{{frame['id']}}.expected-camera-depth.npy", expected, allow_pickle=False)
                    mse = float(np.mean((predicted.astype(np.float64) - truth.astype(np.float64) / 255.0) ** 2))
                    psnrs.append(-10.0 * math.log10(mse))
                    valid = foreground & common & (accumulation >= 0.5) & (expected > 0.0)
                    residuals.append(expected[valid] - depth[valid])
                (sweep / "primitive-count.txt").write_text(f"{{primitives}}\\n")
                residual = np.concatenate(residuals).astype(np.float64)
                values = {{
                    "target_psnr_db": float(np.mean(psnrs)),
                    "expected_depth_rmse_m": float(np.sqrt(np.mean(residual * residual))),
                    "realized_primitive_count": primitives,
                }}
                for metric, measurement in values.items():
                    rows.append({{
                        "factor": "context_view_count", "value": count,
                        "metric": metric, "measurement": measurement,
                        "interpretation": "fixture trained view sweep",
                    }})
            with (output / "failure_sweep.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["factor", "value", "metric", "measurement", "interpretation"])
                writer.writeheader()
                writer.writerows(rows)

            (output / "unsupported.json").write_text(json.dumps({{
                "triangle_mesh": "unsupported", "mesh_f_score": "unsupported",
                "canonical_surface": "unsupported", "hidden_surface_completion": "unsupported",
                "surface_regularization_sweep": "unsupported_until_separate_sugar_or_2dgs_adapter",
            }}, sort_keys=True) + "\\n")
            locked = output / "nerfstudio"
            locked.mkdir()
            (locked / "checkpoint.ckpt").write_bytes(b"fixture splat checkpoint")
            (locked / "config.yml").write_text("method: splatfacto\\n")
            (output / "source-commit.txt").write_text("{NERFSTUDIO_COMMIT}\\n")
            (output / "gsplat-commit.txt").write_text("{GSPLAT_COMMIT}\\n")
            (output / "insula-manifest.txt").write_text(
                "schema_version=1\\nkind=gaussian-splatting\\ncuda=12.8.1\\npython=3.12\\n"
                "torch=2.7.1+cu128\\ntorchvision=0.22.1+cu128\\npillow=11.1.0\\n"
                "nerfstudio_commit={NERFSTUDIO_COMMIT}\\ngsplat_commit={GSPLAT_COMMIT}\\n"
                "gsplat_version=1.4.0\\ntorch_cuda_arch_list=10.0\\n"
                "requirements_lock_sha256=02c623f2a636dd774dda048f1a08c8d936d0701f74d3f50b3a7916d2280ed65a\\n"
                "resolved_requirements_sha256=587350cc8d7a65840facd27ebcf6fabc43f1e09d4f82541efa851ae914631076\\n"
                "network_policy=build-and-fetch-only\\n"
            )
            shutil.copy2(repository / "insulas/radiance-field/requirements.lock.txt", output / "requirements.lock.txt")
            resolved_text = (repository / "insulas/radiance-field/resolved-requirements.lock.txt").read_text()
            (output / "resolved-requirements.txt").write_text(
                resolved_text.replace("gsplat==1.4.0\\n", "gsplat @ file:///opt/src/gsplat\\n")
            )
            resolved_sha = "587350cc8d7a65840facd27ebcf6fabc43f1e09d4f82541efa851ae914631076"
            (output / "runtime-versions.json").write_text(json.dumps({{
                "nerfstudio_commit": "{NERFSTUDIO_COMMIT}", "gsplat_commit": "{GSPLAT_COMMIT}",
                "gsplat": "1.4.0", "gsplat_direct_url": "file:///opt/src/gsplat",
                "requirements_lock_sha256": "02c623f2a636dd774dda048f1a08c8d936d0701f74d3f50b3a7916d2280ed65a",
                "resolved_requirements_sha256": resolved_sha, "torch": "2.7.1+cu128",
                "torchvision": "0.22.1+cu128", "pillow": "11.1.0", "python": "3.12.3",
                "numpy": "2.5.2", "cuda_runtime": "12.8",
                "cuda_compiler": "Cuda compilation tools, release 12.8, V12.8.93",
                "compute_capability": [10, 0], "torch_cuda_arch_list": "10.0",
                "device": "fixture NVIDIA B200",
            }}, sort_keys=True) + "\\n")
            (output / "environment-gates.json").write_text(json.dumps({{
                "compute_capability_10_0": True, "gsplat_forward_backward": True,
                "splatfacto_forward_backward": True, "camera_round_trip": True,
            }}, sort_keys=True) + "\\n")
            iterations = 1000 if manifest["profile"] == "smoke" else 30000
            (output / "training-summary.json").write_text(json.dumps({{
                "method": "splatfacto", "iterations": iterations,
                "training_seconds": 4.0, "training_steps_per_second": iterations / 4.0,
                "random_init": True, "num_random": 50000, "random_scale": 2.0,
                "camera_optimizer": "off", "background_color": "black",
                "scale_regularization": False, "rasterization_mode": "classic",
                "seed": 260925, "tf32": False, "final_primitive_count": 4,
                "trained_view_sweep": {{"context_views": [3, 5, 9], "iterations": 1000}},
                "view_sweep_training_seconds": {{"3": 1.0, "5": 1.0, "9": 1.0}},
                "render_benchmark": {{"warmup_frames": 20, "measured_frames": 100, "median_fps": 123.0, "p95_latency_ms": 9.0}},
            }}, sort_keys=True) + "\\n")
            (output / "resource-usage.txt").write_text("Maximum resident set size (kbytes): 65432\\n")
            print("fixture Splatfacto completed")
            PY
            """
        ),
        encoding="utf-8",
    )
    engine.chmod(0o755)
    return engine


def run_fake_splatfacto_reference(root: Path, run_id: str = "splatfacto-smoke") -> Path:
    import sys

    sys.path.insert(0, str(ROOT / "pipeline"))
    import splatfacto_reference_runner

    checkpoint = root / "fixture-alexnet.pth"
    checkpoint.write_bytes(b"fixture")
    with mock.patch.dict(
        os.environ,
        {"SURFLO_PATHWAY_CONTAINER_ENGINE": str(fake_splatfacto_engine(root))},
    ), mock.patch.object(
        splatfacto_reference_runner,
        "_lpips_checkpoint_path",
        return_value=checkpoint,
    ):
        return splatfacto_reference_runner.run_splatfacto_reference(
            root / "cache", "smoke", run_id
        )


class SplatfactoReferenceFoundationTest(unittest.TestCase):
    def test_primary_implementation_sources_are_registered_for_module_11(self) -> None:
        sources = {
            item["id"]: item
            for item in json.loads((ROOT / "sources.json").read_text())["sources"]
        }
        self.assertEqual(
            sources["nerfstudio-splatfacto-2025"]["primary_url"],
            f"https://github.com/nerfstudio-project/nerfstudio/tree/{NERFSTUDIO_COMMIT}",
        )
        self.assertEqual(
            sources["gsplat-1.4.0"]["primary_url"],
            f"https://github.com/nerfstudio-project/gsplat/tree/{GSPLAT_COMMIT}",
        )
        curriculum = {
            item["id"]: item
            for item in json.loads((ROOT / "curriculum.json").read_text())["modules"]
        }
        self.assertEqual(curriculum["11"]["insula"], "gaussian-splatting")
        self.assertIn("nerfstudio-splatfacto-2025", curriculum["11"]["sources"])
        self.assertIn("gsplat-1.4.0", curriculum["11"]["sources"])

    def test_adapter_declares_rendering_scope_and_unsupported_surface_claims(self) -> None:
        adapters = {
            item["id"]: item
            for item in json.loads((ROOT / "reference-adapters.json").read_text())[
                "adapters"
            ]
        }
        adapter = adapters["nerfstudio-splatfacto-reference"]
        self.assertEqual(adapter["status"], "landed")
        self.assertEqual(adapter["modules"], ["11"])
        self.assertEqual(
            adapter["command"],
            "run.sh reference --adapter splatfacto --profile smoke --run-id ID",
        )
        self.assertEqual(adapter["model_contract"]["method"], "splatfacto")
        self.assertEqual(
            adapter["model_contract"]["inference"], "per-scene-optimization"
        )
        self.assertEqual(adapter["model_contract"]["initialization"], "random")
        self.assertFalse(adapter["model_contract"]["completion_claim"])
        self.assertFalse(adapter["model_contract"]["posterior_sampling_claim"])
        unsupported = set(adapter["evaluation_contract"]["unsupported_claims"])
        self.assertEqual(
            unsupported,
            {
                "triangle_mesh",
                "mesh_f_score",
                "canonical_surface",
                "hidden_surface_completion",
            },
        )
        self.assertEqual(
            adapter["evaluation_contract"]["geometry"],
            "view-conditioned expected-depth diagnostics on common-visible truth",
        )
        self.assertEqual(
            set(adapter["acceptance"]["smoke"]),
            {
                "target_psnr_db_min",
                "target_ssim_min",
                "common_visible_accumulation_coverage_min",
                "expected_depth_rmse_m_max",
                "point_fscore_10cm_min",
            },
        )
        self.assertEqual(
            set(adapter["acceptance"]["full"]),
            {
                "target_psnr_db_min",
                "target_ssim_min",
                "common_visible_accumulation_coverage_min",
                "expected_depth_rmse_m_max",
                "point_fscore_10cm_min",
            },
        )
        self.assertEqual(
            adapter["acceptance"]["full"],
            {
                "target_psnr_db_min": 18.0,
                "target_ssim_min": 0.6,
                "common_visible_accumulation_coverage_min": 0.95,
                "expected_depth_rmse_m_max": 1.0,
                "point_fscore_10cm_min": 0.01,
            },
        )
        self.assertIn("stochastic B200", adapter["measurement_note"])
        self.assertEqual(adapter["baseline_environment"]["gpu_model"], "NVIDIA B200")
        self.assertEqual(adapter["last_verified_smoke"]["date"], "2026-09-26")
        self.assertEqual(adapter["last_verified_full"]["date"], "2026-09-26")

    def test_gaussian_splatting_environment_is_blackwell_pinned(self) -> None:
        locks = json.loads((ROOT / "insulas/locks.json").read_text())["insulas"]
        gaussian = locks["gaussian-splatting"]
        self.assertEqual(gaussian["nerfstudio_source_commit"], NERFSTUDIO_COMMIT)
        self.assertEqual(gaussian["gsplat_source_commit"], GSPLAT_COMMIT)
        self.assertEqual(gaussian["torch_cuda_arch_list"], "10.0")
        self.assertEqual(gaussian["pytorch"], "2.7.1+cu128")
        requirements = ROOT / "insulas/radiance-field/requirements.lock.txt"
        resolved = ROOT / "insulas/radiance-field/resolved-requirements.lock.txt"
        self.assertEqual(
            gaussian["requirements_lock_sha256"],
            hashlib.sha256(requirements.read_bytes()).hexdigest(),
        )
        expected_resolved = resolved.read_text().replace(
            "gsplat==1.4.0\n", "gsplat @ file:///opt/src/gsplat\n"
        ).encode()
        self.assertEqual(
            gaussian["resolved_requirements_sha256"],
            hashlib.sha256(expected_resolved).hexdigest(),
        )
        dockerfile = (ROOT / "insulas/gaussian-splatting/Dockerfile").read_text()
        self.assertIn("git -C /opt/src/gsplat submodule update --init --recursive", dockerfile)
        self.assertIn("--force-reinstall /opt/src/gsplat", dockerfile)
        self.assertIn("direct_url.json", dockerfile)

    def test_public_reference_plan_is_offline(self) -> None:
        completed = subprocess.run(
            [
                str(ROOT / "run.sh"),
                "--emit-plan",
                "reference",
                "--adapter",
                "splatfacto",
                "--profile",
                "smoke",
                "--run-id",
                "splat-plan",
            ],
            cwd=ROOT.parent.parent,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "adapter": "splatfacto",
                "command": "reference",
                "network_mode": "offline",
                "profile": "smoke",
                "run_id": "splat-plan",
                "schema_version": 1,
            },
        )

    def test_scene_transform_contains_no_target_training_frames(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "pipeline"))
        from contracts import load_json
        from reference_scene import generate_radiance_field_scene

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "scene"
            manifest = generate_radiance_field_scene(
                destination, load_json(ROOT / "shared-scene.json"), "smoke"
            )
            transforms = json.loads((destination / "transforms.json").read_text())
            paths = [frame["file_path"] for frame in transforms["frames"]]
            self.assertEqual(len(paths), len(manifest["primary_context_frame_ids"]))
            self.assertTrue(all("context-" in path for path in paths))
            self.assertTrue(all("target-" not in path for path in paths))

    def test_reference_schema_requires_gaussian_metric_families(self) -> None:
        schema = json.loads((ROOT / "reference-result.schema.json").read_text())
        self.assertIn("splatfacto", schema["properties"]["adapter"]["enum"])
        branch = next(
            item
            for item in schema["allOf"]
            if item.get("if", {}).get("properties", {}).get("adapter", {}).get("const")
            == "splatfacto"
        )
        self.assertEqual(
            set(branch["then"]["properties"]["metrics"]["required"]),
            {"rendering", "geometry", "representation", "failure_sweep", "unsupported"},
        )
        metric_properties = branch["then"]["properties"]["metrics"]["properties"]
        self.assertIn("target_psnr_db", metric_properties["rendering"]["required"])
        self.assertIn("expected_depth_rmse_m", metric_properties["geometry"]["required"])
        self.assertIn("primitive_count", metric_properties["representation"]["required"])
        self.assertIn("triangle_mesh", metric_properties["unsupported"]["required"])

    def test_entrypoint_runs_iteration_zero_preflight_on_the_primary_trainer(self) -> None:
        text = (ROOT / "insulas/gaussian-splatting/run-splatfacto.py").read_text()
        self.assertIn("TrainingCallbackLocation.BEFORE_TRAIN_ITERATION", text)
        self.assertIn("TrainingCallbackLocation.AFTER_TRAIN_ITERATION", text)
        self.assertNotIn("gate_trainer", text)
        self.assertIn("trainer._start_step = 1", text)
        self.assertLess(text.index("trainer.setup"), text.index("gates = _environment_gates"))
        self.assertLess(text.index("gates = _environment_gates"), text.index("trainer._start_step = 1"))
        self.assertLess(text.index("trainer._start_step = 1"), text.index("trainer.train()"))
        self.assertIn("def _finite_value", text)
        self.assertIn("_finite_value(value) for value in metrics_dict.values()", text)


class SplatfactoOutputContractTest(unittest.TestCase):
    def test_fake_smoke_run_is_offline_recomputed_and_atomically_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_splatfacto_reference(Path(temporary))
            result = json.loads((run_dir / "result.json").read_text())
            self.assertEqual(result["adapter"], "splatfacto")
            self.assertEqual(result["module_ids"], ["11"])
            self.assertEqual(result["network_mode"], "offline")
            self.assertEqual(result["support"]["triangle_mesh"], "unsupported")
            self.assertEqual(result["support"]["completion_claim"], "none")
            self.assertEqual(
                result["provenance"]["config"]["container_user_environment"],
                {
                    "USER": "surflo",
                    "PYTHONHASHSEED": "260925",
                    "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
                    "NVIDIA_TF32_OVERRIDE": "0",
                },
            )
            self.assertGreater(result["metrics"]["rendering"]["target_psnr_db"], 0.0)
            self.assertAlmostEqual(
                result["metrics"]["geometry"]["expected_depth_rmse_m"],
                0.025,
                places=5,
            )
            self.assertEqual(result["metrics"]["representation"]["primitive_count"], 4)
            self.assertEqual(
                set(result["metrics"]["failure_sweep"]), {"3", "5", "9"}
            )
            self.assertEqual(
                result["metrics"]["unsupported"]["mesh_f_score"], "unsupported"
            )
            self.assertTrue((run_dir / "artifacts/metric-summary.svg").is_file())
            self.assertTrue((run_dir / "output/gaussians.npz").is_file())
            self.assertTrue((run_dir / "output/gaussians.ply").is_file())
            self.assertEqual(
                list((Path(temporary) / "cache/reference-staging").iterdir()), []
            )

    def test_real_profiles_are_explicit_b200_gates(self) -> None:
        for profile, variable in (
            ("smoke", "SURFLO_REQUIRE_SPLATFACTO_REFERENCE"),
            ("full", "SURFLO_REQUIRE_SPLATFACTO_FULL"),
        ):
            with self.subTest(profile=profile):
                if os.environ.get(variable) != "1":
                    continue
                docker = shutil.which("docker")
                self.assertIsNotNone(docker, "required Docker engine is unavailable")
                inspected = subprocess.run(
                    [docker, "image", "inspect", "surflo-pathway-gaussian-splatting:1"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(inspected.returncode, 0, inspected.stderr)
                import sys

                sys.path.insert(0, str(ROOT / "pipeline"))
                from splatfacto_reference_runner import run_splatfacto_reference

                cache = Path(
                    os.environ.get(
                        "SURFLO_PATHWAY_CACHE_ROOT",
                        Path.home() / ".cache/surflo/3d-pathway",
                    )
                )
                run_dir = run_splatfacto_reference(
                    cache, profile, f"splatfacto-real-{profile}-test-{os.getpid()}"
                )
                result = json.loads((run_dir / "result.json").read_text())
                self.assertEqual(result["profile"], profile)
                self.assertEqual(result["resources"]["gpu_measurement_status"], "measured")
                self.assertEqual(result["support"]["triangle_mesh"], "unsupported")

    def test_failed_container_is_not_promoted(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "pipeline"))
        import splatfacto_reference_runner

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint = root / "fixture-alexnet.pth"
            checkpoint.write_bytes(b"fixture")
            with mock.patch.dict(
                os.environ,
                {
                    "SURFLO_PATHWAY_CONTAINER_ENGINE": str(
                        fake_splatfacto_engine(root, fail=True)
                    )
                },
            ), mock.patch.object(
                splatfacto_reference_runner,
                "_lpips_checkpoint_path",
                return_value=checkpoint,
            ):
                with self.assertRaisesRegex(ValueError, "adapter failed"):
                    splatfacto_reference_runner.run_splatfacto_reference(
                        root / "cache", "smoke", "failed-splat"
                    )
            self.assertFalse((root / "cache/reference-runs/failed-splat").exists())
            self.assertEqual(list((root / "cache/reference-staging").iterdir()), [])

    def test_tampered_gaussian_archive_is_rejected(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "pipeline"))
        from splatfacto_reference_runner import validate_splatfacto_reference_result

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_splatfacto_reference(Path(temporary), "tamper-splat")
            with np.load(run_dir / "output/gaussians.npz", allow_pickle=False) as archive:
                arrays = {name: archive[name] for name in archive.files}
            arrays["quaternions"][0] = 2.0
            np.savez_compressed(run_dir / "output/gaussians.npz", **arrays)
            with self.assertRaisesRegex(ValueError, "unit quaternion"):
                validate_splatfacto_reference_result(run_dir)

    def test_truncated_or_nonfinite_gaussian_ply_is_rejected(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "pipeline"))
        from splatfacto_reference_runner import validate_splatfacto_reference_result

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_splatfacto_reference(Path(temporary), "truncated-ply")
            ply = run_dir / "output/gaussians.ply"
            ply.write_bytes(ply.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError, "PLY payload length"):
                validate_splatfacto_reference_result(run_dir)

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_splatfacto_reference(Path(temporary), "nonfinite-ply")
            ply = run_dir / "output/gaussians.ply"
            payload = bytearray(ply.read_bytes())
            offset = payload.index(b"end_header\n") + len(b"end_header\n")
            payload[offset : offset + 4] = np.asarray(np.nan, dtype="<f4").tobytes()
            ply.write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "PLY payload is non-finite"):
                validate_splatfacto_reference_result(run_dir)

    def test_tampered_resources_or_unapproved_image_are_rejected(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "pipeline"))
        import splatfacto_reference_runner

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_splatfacto_reference(Path(temporary), "resource-tamper")
            result_path = run_dir / "result.json"
            result = json.loads(result_path.read_text())
            result["resources"]["runtime_seconds"] = 999999.0
            result_path.write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, "resource summary mismatch"):
                splatfacto_reference_runner.validate_splatfacto_reference_result(run_dir)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(
                splatfacto_reference_runner,
                "_inspect_image",
                return_value="sha256:" + "c" * 64,
            ), mock.patch.dict(
                os.environ,
                {"SURFLO_PATHWAY_CONTAINER_ENGINE": str(fake_splatfacto_engine(root))},
            ):
                with self.assertRaisesRegex(ValueError, "approved calibration image"):
                    splatfacto_reference_runner.run_splatfacto_reference(
                        root / "cache", "smoke", "unapproved-image"
                    )

    def test_gaussian_parameter_validator_rejects_non_unit_quaternions(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "pipeline"))
        from splatfacto_reference_runner import validate_gaussian_archive

        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "gaussians.npz"
            np.savez_compressed(
                archive,
                means=np.zeros((2, 3), dtype=np.float32),
                log_scales=np.zeros((2, 3), dtype=np.float32),
                quaternions=np.ones((2, 4), dtype=np.float32),
                opacity_logits=np.zeros((2, 1), dtype=np.float32),
                features_dc=np.zeros((2, 3), dtype=np.float32),
            )
            with self.assertRaisesRegex(ValueError, "unit quaternion"):
                validate_gaussian_archive(archive)

    def test_gaussian_parameter_validator_recomputes_representation_metrics(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "pipeline"))
        from splatfacto_reference_runner import validate_gaussian_archive

        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "gaussians.npz"
            means = np.array([[0.72, 0.0, 0.0], [0.0, 0.0, 1.2]], dtype=np.float32)
            log_scales = np.log(
                np.array([[0.02, 0.04, 0.08], [0.01, 0.01, 0.01]], dtype=np.float32)
            )
            quaternions = np.zeros((2, 4), dtype=np.float32)
            quaternions[:, 0] = 1.0
            opacity_logits = np.array([[3.0], [-3.0]], dtype=np.float32)
            np.savez_compressed(
                archive,
                means=means,
                log_scales=log_scales,
                quaternions=quaternions,
                opacity_logits=opacity_logits,
                features_dc=np.zeros((2, 3), dtype=np.float32),
            )
            metrics = validate_gaussian_archive(archive)
            self.assertEqual(metrics["primitive_count"], 2)
            self.assertEqual(metrics["parameter_bytes"], 2 * (3 + 3 + 4 + 1 + 3) * 4)
            self.assertAlmostEqual(metrics["scale_anisotropy_p95"], 3.85, places=5)
            self.assertEqual(metrics["opacity_ge_0_5_count"], 1)


if __name__ == "__main__":
    unittest.main()
