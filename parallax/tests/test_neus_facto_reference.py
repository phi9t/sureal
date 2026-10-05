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


NERFSTUDIO_COMMIT = "50e0e3c70c775e89333256213363badbf074f29d"
TCNN_COMMIT = "0109538c37ac0bf613f2bac8de6cda48352feca7"
LPIPS_SHA256 = "7be5be791159472b1fbf3c69796f7cb30dca7ad8466c2df70058c37116cdee02"
FIXTURE_IMAGE_ID = "sha256:" + "9" * 64


def fake_neus_engine(path: Path, fail: bool = False) -> Path:
    engine = path / ("fake-neus-failing-engine" if fail else "fake-neus-container-engine")
    failure = "exit 19" if fail else ""
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
            [[ " $* " == *" -e MPLCONFIGDIR=/cuda-cache/matplotlib "* ]]
            [[ " $* " == *" -e TORCH_HOME=/model "* ]]
            [[ " $* " == *":/model/hub/checkpoints/alexnet-owt-7be5be79.pth:ro "* ]]
            [[ " $* " == *" {FIXTURE_IMAGE_ID} "* ]]
            work=''
            previous=''
            for argument in "$@"; do
                if [[ "$previous" == -v && "$argument" == *:/work ]]; then
                    work="${{argument%:/work}}"
                fi
                previous="$argument"
            done
            [[ -n "$work" ]]
            {failure}
            python3 - "$work" <<'PY'
            import json
            from pathlib import Path
            import sys

            import numpy as np

            root = Path(sys.argv[1])
            manifest = json.loads((root / "input/manifest.json").read_text())
            output = root / "output"
            output.mkdir(exist_ok=True)
            truth = manifest["surface_truth"]
            points = np.load(root / "input" / truth["points_path"], allow_pickle=False)
            normals = np.load(root / "input" / truth["normals_path"], allow_pickle=False)
            face_count = len(points) // 3
            faces = np.arange(face_count * 3, dtype=np.int32).reshape(face_count, 3)
            np.savez(output / "mesh.npz", points=points, normals=normals, faces=faces)
            with (output / "mesh.ply").open("w", encoding="ascii") as stream:
                stream.write(
                    "ply\\nformat ascii 1.0\\n"
                    f"element vertex {{len(points)}}\\n"
                    "property float x\\nproperty float y\\nproperty float z\\n"
                    "property float nx\\nproperty float ny\\nproperty float nz\\n"
                    f"element face {{len(faces)}}\\n"
                    "property list uchar int vertex_indices\\nend_header\\n"
                )
                for point, normal in zip(points, normals):
                    stream.write(" ".join(str(float(v)) for v in np.r_[point, normal]) + "\\n")
                for face in faces:
                    stream.write(f"3 {{face[0]}} {{face[1]}} {{face[2]}}\\n")

            resolution = 128 if manifest["profile"] == "smoke" else 256
            axis = np.linspace(-1.0, 1.0, resolution, dtype=np.float32)
            xx, yy, zz = np.meshgrid(axis, axis, axis, indexing="ij")
            sdf = np.sqrt(xx * xx + yy * yy + zz * zz) - np.float32(manifest["sphere_radius_m"])
            np.save(output / "field.sdf_grid.float32.npy", sdf.astype(np.float32), allow_pickle=False)
            np.save(output / "field.gradient_norms.float32.npy", np.ones(4096, dtype=np.float32), allow_pickle=False)

            predictions = output / "target-renders"
            predictions.mkdir()
            for frame in manifest["target_frames"]:
                rgb = np.load(root / "input" / frame["rgb_truth_path"], allow_pickle=False)
                depth = np.load(root / "input" / frame["depth_path"], allow_pickle=False)
                normals_frame = np.load(root / "input" / frame["normal_path"], allow_pickle=False)
                np.save(predictions / f"{{frame['id']}}.rgb.npy", np.clip(rgb.astype(np.int16) + 1, 0, 255).astype(np.uint8), allow_pickle=False)
                predicted_depth = np.where(depth > 0, depth + np.float32(0.005), 0.0).astype(np.float32)
                np.save(predictions / f"{{frame['id']}}.depth.npy", predicted_depth, allow_pickle=False)
                np.save(predictions / f"{{frame['id']}}.normal.npy", normals_frame, allow_pickle=False)

            checkpoint = output / "nerfstudio/checkpoint.ckpt"
            checkpoint.parent.mkdir()
            checkpoint.write_bytes(b"fixture neus-facto checkpoint")
            (output / "source-commit.txt").write_text("{NERFSTUDIO_COMMIT}\\n")
            (output / "tcnn-commit.txt").write_text("{TCNN_COMMIT}\\n")
            (output / "insula-manifest.txt").write_text(
                "schema_version=1\\n"
                "kind=implicit-surface\\n"
                "cuda=12.8.1\\n"
                "python=3.12\\n"
                "torch=2.7.1+cu128\\n"
                "torchvision=0.22.1+cu128\\n"
                "pillow=11.1.0\\n"
                "nerfstudio_commit={NERFSTUDIO_COMMIT}\\n"
                "tiny_cuda_nn_commit={TCNN_COMMIT}\\n"
                "tcnn_cuda_architectures=100\\n"
                "network_policy=build-and-fetch-only\\n"
            )
            (output / "runtime-versions.json").write_text(json.dumps({{
                "nerfstudio_commit": "{NERFSTUDIO_COMMIT}",
                "tiny_cuda_nn_commit": "{TCNN_COMMIT}",
                "torch": "2.7.1+cu128",
                "torchvision": "0.22.1+cu128",
                "pillow": "11.1.0",
                "python": "3.12.3",
                "numpy": "2.5.2",
                "cuda_runtime": "12.8",
                "cuda_compiler": "Cuda compilation tools, release 12.8, V12.8.93",
                "compute_capability": [10, 0],
                "tcnn_cuda_architectures": "100",
                "device": "fixture NVIDIA B200",
            }}, sort_keys=True) + "\\n")
            (output / "environment-gates.json").write_text(json.dumps({{
                "compute_capability_10_0": True,
                "tcnn_forward_backward": True,
                "neus_facto_forward_backward": True,
                "sdf_extraction_32": True,
            }}, sort_keys=True) + "\\n")
            (output / "training-summary.json").write_text(json.dumps({{
                "method": "neus-facto",
                "iterations": 1000 if manifest["profile"] == "smoke" else 20001,
                "rays_per_batch": 1024 if manifest["profile"] == "smoke" else 2048,
                "extraction_resolution": resolution,
                "training_seconds": 4.0,
                "training_steps_per_second": (1000 if manifest["profile"] == "smoke" else 20001) / 4.0,
                "extraction_seconds": 0.25,
                "mesh_vertices": len(points),
                "mesh_faces": len(faces),
                "camera_optimizer": "off",
                "mono_prior": False,
                "inside_outside": True,
                "tf32": False,
                "seed": manifest["scene_seed"],
            }}, sort_keys=True) + "\\n")
            (output / "resource-usage.txt").write_text("Maximum resident set size (kbytes): 54321\\n")
            (output / "failure_sweep.csv").write_text(
                "factor,value,image_supported,interpretation\\n"
                "view_count,2,true,reduced observed support\\n"
                "texture,constant,true,photometric ambiguity\\n"
                "hidden_counterfactual,a_vs_b,false,identical context evidence\\n"
            )
            print("fixture NeuS-Facto completed")
            PY
            """
        ),
        encoding="utf-8",
    )
    engine.chmod(0o755)
    return engine


def run_fake_neus_reference(root: Path, profile: str = "smoke", run_id: str = "neus-smoke") -> Path:
    sys.path.insert(0, str(ROOT / "pipeline"))
    import neus_reference_runner

    checkpoint = root / "fixture-alexnet-weights.pth"
    checkpoint.write_bytes(b"fixture weights")
    with mock.patch.dict(
        os.environ, {"SURFLO_PATHWAY_CONTAINER_ENGINE": str(fake_neus_engine(root))}
    ), mock.patch.object(
        neus_reference_runner, "_lpips_checkpoint_path", return_value=checkpoint
    ):
        return neus_reference_runner.run_neus_reference(root / "cache", profile, run_id)


class NeuSFactoReferenceFoundationTest(unittest.TestCase):
    def test_public_reference_plan_is_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            completed = run_cli(
                "--emit-plan",
                "reference",
                "--adapter",
                "neus-facto",
                "--profile",
                "smoke",
                "--run-id",
                "neus-plan",
                cache=Path(temporary) / "cache",
                engine=fake_engine(Path(temporary)),
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "adapter": "neus-facto",
                "command": "reference",
                "network_mode": "offline",
                "profile": "smoke",
                "run_id": "neus-plan",
                "schema_version": 1,
            },
        )

    def test_sources_container_and_adapter_are_locked(self) -> None:
        adapters = {
            item["id"]: item
            for item in json.loads((ROOT / "reference-adapters.json").read_text())["adapters"]
        }
        adapter = adapters["nerfstudio-neus-facto-reference"]
        self.assertEqual(adapter["status"], "landed")
        self.assertEqual(adapter["modules"], ["09"])
        self.assertEqual(adapter["baseline_environment"]["gpu_model"], "NVIDIA B200")
        self.assertEqual(adapter["baseline_environment"]["compute_capability"], 10.0)
        self.assertRegex(
            adapter["baseline_environment"]["container_image_id"],
            r"^sha256:[0-9a-f]{64}$",
        )
        for profile in ("last_verified_smoke", "last_verified_full"):
            self.assertEqual(adapter[profile]["date"], "2026-09-26")
            self.assertGreater(adapter[profile]["mesh_vertices"], 100)
            self.assertGreater(adapter[profile]["training_steps_per_second"], 0.0)
            self.assertGreater(adapter[profile]["peak_gpu_compute_memory_bytes"], 0)
        self.assertIn("failure evidence", adapter["measurement_note"])
        self.assertIn("common_visible_fscore_10cm_min", adapter["acceptance"]["smoke"])
        self.assertIn("target_psnr_db_min", adapter["acceptance"]["full"])
        self.assertEqual(adapter["acceptance"]["smoke"]["common_visible_fscore_10cm_min"], 0.35)
        self.assertEqual(adapter["acceptance"]["full"]["common_visible_fscore_5cm_min"], 0.15)

        locks = json.loads((ROOT / "insulas/locks.json").read_text())["insulas"]
        implicit = locks["implicit-surface"]
        self.assertEqual(implicit["nerfstudio_source_commit"], NERFSTUDIO_COMMIT)
        self.assertEqual(implicit["tiny_cuda_nn_source_commit"], TCNN_COMMIT)
        self.assertEqual(implicit["tcnn_cuda_architectures"], "100")
        self.assertEqual(implicit["pillow"], "11.1.0")

        assets = {
            item["id"]: item
            for item in json.loads((ROOT / "assets.lock.json").read_text())["assets"]
        }
        lpips = assets["nerfstudio-lpips-alexnet"]
        self.assertEqual(lpips["sha256"], LPIPS_SHA256)
        self.assertEqual(lpips["byte_size"], 244408911)
        self.assertEqual(
            lpips["consumers"],
            [
                "nerfstudio-neus-facto-reference",
                "nerfstudio-nerfacto-reference",
                "nerfstudio-splatfacto-reference",
            ],
        )

        dockerfile = (ROOT / "insulas/implicit-surface/Dockerfile").read_text()
        self.assertIn(f"ARG NERFSTUDIO_COMMIT={NERFSTUDIO_COMMIT}", dockerfile)
        self.assertIn(f"ARG TCNN_COMMIT={TCNN_COMMIT}", dockerfile)
        self.assertIn("TCNN_CUDA_ARCHITECTURES=100", dockerfile)
        self.assertIn("torch==2.7.1", dockerfile)
        self.assertIn("torchvision==0.22.1", dockerfile)
        self.assertIn("Pillow==11.1.0", dockerfile)
        entrypoint = (ROOT / "insulas/implicit-surface/run-neus-facto.py").read_text()
        self.assertIn('method_configs["neus-facto"]', entrypoint)
        self.assertIn("forward_geonetwork", entrypoint)
        self.assertIn("measure.marching_cubes", entrypoint)
        self.assertIn("config.pipeline.model.sdf_field.inside_outside = True", entrypoint)
        self.assertIn("normals = (-gradients / lengths)", entrypoint)
        self.assertIn("get_outputs_for_camera", entrypoint)
        self.assertIn('f"safe.directory={path}"', entrypoint)
        self.assertNotIn("not built yet", entrypoint)

    def test_controlled_sphere_inputs_are_deterministic_and_support_labelled(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from contracts import load_json, sha256_file
        from reference_scene import generate_implicit_surface_scene

        scene = load_json(ROOT / "shared-scene.json")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = generate_implicit_surface_scene(root / "first", scene, "smoke")
            second = generate_implicit_surface_scene(root / "second", scene, "smoke")

            self.assertEqual(first, second)
            self.assertEqual(first["method_input"], "calibrated-multiview-rgb")
            self.assertEqual(first["inference"], "per-scene-optimization")
            self.assertEqual(first["completion_claim"], "none")
            self.assertEqual(first["model_from_world"][0][3], 0.65)
            self.assertEqual(first["model_from_world"][1][3], 0.25)
            self.assertEqual(first["model_from_world"][2][3], -0.1)
            self.assertEqual(len(first["context_frames"]), 5)
            self.assertEqual(len(first["target_frames"]), 3)
            self.assertEqual(
                [frame["azimuth_degrees"] for frame in first["context_frames"]],
                [-45.0, -25.0, -5.0, 15.0, 35.0],
            )
            self.assertEqual(
                [frame["azimuth_degrees"] for frame in first["target_frames"]],
                [120.0, 150.0, 180.0],
            )

            for frame in first["context_frames"] + first["target_frames"]:
                image = root / "first" / frame["image_path"]
                mask = root / "first" / frame["mask_path"]
                depth_path = root / "first" / frame["depth_path"]
                normal_path = root / "first" / frame["normal_path"]
                rgb_truth_path = root / "first" / frame["rgb_truth_path"]
                support_mask_path = root / "first" / frame["common_visible_mask_path"]
                self.assertEqual(frame["image_sha256"], sha256_file(image))
                self.assertEqual(frame["mask_sha256"], sha256_file(mask))
                self.assertEqual(frame["depth_sha256"], sha256_file(depth_path))
                self.assertEqual(frame["normal_sha256"], sha256_file(normal_path))
                self.assertEqual(frame["rgb_truth_sha256"], sha256_file(rgb_truth_path))
                self.assertEqual(frame["common_visible_mask_sha256"], sha256_file(support_mask_path))
                self.assertEqual(image.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
                depth = np.load(depth_path, allow_pickle=False)
                normals = np.load(normal_path, allow_pickle=False)
                rgb_truth = np.load(rgb_truth_path, allow_pickle=False)
                common_visible = np.load(support_mask_path, allow_pickle=False)
                self.assertEqual(depth.shape, (480, 640))
                self.assertEqual(depth.dtype, np.float32)
                self.assertEqual(normals.shape, (480, 640, 3))
                self.assertEqual(normals.dtype, np.float32)
                self.assertEqual(rgb_truth.shape, (480, 640, 3))
                self.assertEqual(rgb_truth.dtype, np.uint8)
                self.assertEqual(common_visible.shape, (480, 640))
                self.assertEqual(common_visible.dtype, np.uint8)
                self.assertTrue(np.isfinite(depth).all())
                self.assertTrue(np.isfinite(normals).all())
                self.assertTrue(np.isin(common_visible, [0, 1]).all())

                c2w = np.asarray(frame["camera_to_world_model"], dtype=np.float64)
                self.assertTrue(np.allclose(c2w[:3, :3].T @ c2w[:3, :3], np.eye(3), atol=1e-12))
                self.assertAlmostEqual(float(np.linalg.det(c2w[:3, :3])), 1.0, places=12)
                self.assertTrue(np.allclose(c2w[:3, 3] + np.asarray(scene["geometry"][1]["center"]), frame["camera_center_world_m"]))

            support = np.load(root / "first" / first["surface_truth"]["support_path"], allow_pickle=False)
            points = np.load(root / "first" / first["surface_truth"]["points_path"], allow_pickle=False)
            normals = np.load(root / "first" / first["surface_truth"]["normals_path"], allow_pickle=False)
            self.assertEqual(points.shape, (8192, 3))
            self.assertEqual(normals.shape, points.shape)
            self.assertEqual(support.shape, (8192,))
            self.assertGreater(np.count_nonzero(support >= 2), 0)
            self.assertGreater(np.count_nonzero(support == 0), 0)
            self.assertEqual(first["surface_truth"]["common_visible_rule"], "context-visibility-count>=2")
            self.assertEqual(first["surface_truth"]["unsupported_rule"], "context-visibility-count==0")
            target_support = np.load(
                root / "first" / first["target_frames"][0]["common_visible_mask_path"],
                allow_pickle=False,
            )
            target_foreground = np.load(
                root / "first" / first["target_frames"][0]["depth_path"],
                allow_pickle=False,
            ) > 0
            self.assertGreater(np.count_nonzero(target_support), 0)
            self.assertGreater(np.count_nonzero(target_foreground & ~target_support.astype(bool)), 0)

            metadata = json.loads((root / "first/meta_data.json").read_text())
            self.assertEqual(metadata["camera_model"], "OPENCV")
            self.assertFalse(metadata["has_mono_prior"])
            self.assertEqual(len(metadata["frames"]), 5)
            self.assertEqual(metadata["height"], 480)
            self.assertEqual(metadata["width"], 640)

            full = generate_implicit_surface_scene(root / "full", scene, "full")
            self.assertEqual(len(full["context_frames"]), 9)
            self.assertEqual(len(full["target_frames"]), 3)
            self.assertTrue(set([-45.0, -25.0, -5.0, 15.0, 35.0]).issubset(
                {frame["azimuth_degrees"] for frame in full["context_frames"]}
            ))


class NeuSFactoNumericalContractTest(unittest.TestCase):
    def test_persisted_metric_comparison_is_float_tolerant_but_structurally_strict(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from neus_reference_runner import _values_match

        expected = {"score": 1.0, "count": 7, "labels": ["visible", True]}
        self.assertTrue(
            _values_match(
                {"score": 1.0 + 5e-7, "count": 7, "labels": ["visible", True]},
                expected,
            )
        )
        self.assertFalse(_values_match({**expected, "count": 7.0}, expected))
        self.assertFalse(_values_match({"score": 1.0, "count": 7}, expected))

    def test_surface_metrics_exclude_unsupported_truth_from_geometry_score(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from neus_reference_runner import _surface_metrics

        truth_points = np.array(
            [[1, 0, 0], [0, 1, 0], [0, 0, 1], [-1, 0, 0], [0, -1, 0], [0, 0, -1]],
            dtype=np.float64,
        )
        truth_normals = truth_points.copy()
        support = np.array([3, 3, 2, 0, 0, 0], dtype=np.int16)
        predicted_points = np.concatenate(
            (truth_points[:3] + np.array([0.01, 0.0, 0.0]), [[-1.4, 0.0, 0.0]]), axis=0
        )
        predicted_normals = np.concatenate((truth_normals[:3], [[-1.0, 0.0, 0.0]]), axis=0)
        metrics = _surface_metrics(
            predicted_points, predicted_normals, truth_points, truth_normals, support
        )

        self.assertEqual(metrics["common_visible_truth_points"], 3)
        self.assertEqual(metrics["unsupported_truth_points"], 3)
        self.assertEqual(metrics["common_visible_predicted_points"], 3)
        self.assertEqual(metrics["unsupported_predicted_points"], 1)
        self.assertLess(metrics["common_visible_accuracy_rmse_m"], 0.011)
        self.assertLess(metrics["common_visible_completeness_rmse_m"], 0.011)
        self.assertEqual(metrics["common_visible_fscore_5cm"], 1.0)
        self.assertEqual(metrics["common_visible_fscore_10cm"], 1.0)
        self.assertLess(metrics["common_visible_normal_mean_deg"], 1e-8)
        self.assertGreater(metrics["unsupported_accuracy_mean_m"], 0.39)

    def test_render_and_field_residual_metrics_are_distinct(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from neus_reference_runner import _eikonal_metrics, _render_metrics

        truth_rgb = np.full((4, 5, 3), 100, dtype=np.uint8)
        predicted_rgb = np.full((4, 5, 3), 110, dtype=np.uint8)
        truth_depth = np.arange(20, dtype=np.float32).reshape(4, 5) + 1.0
        predicted_depth = truth_depth + 0.25
        common_visible = np.zeros((4, 5), dtype=bool)
        common_visible[:, :3] = True
        predicted_rgb[:, 3:] = 255
        rendering = _render_metrics(
            predicted_rgb, truth_rgb, predicted_depth, truth_depth, common_visible
        )
        self.assertAlmostEqual(rendering["target_psnr_db"], 28.130803608679106)
        self.assertEqual(rendering["target_rgb_score_domain"], "common-visible-truth-pixels")
        self.assertAlmostEqual(rendering["target_common_visible_depth_rmse_m"], 0.25)
        self.assertEqual(rendering["target_common_visible_pixels"], 12)

        eikonal = _eikonal_metrics(np.array([1.0, 0.9, 1.2, 1.0]))
        self.assertAlmostEqual(eikonal["eikonal_mean"], 0.075)
        self.assertAlmostEqual(eikonal["eikonal_p95"], 0.185)
        self.assertAlmostEqual(eikonal["eikonal_max"], 0.2)

        with self.assertRaisesRegex(ValueError, "finite positive"):
            _eikonal_metrics(np.array([1.0, np.nan]))


class NeuSFactoReferenceAdapterTest(unittest.TestCase):
    def test_fake_smoke_run_is_offline_scored_and_atomically_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_neus_reference(Path(temporary))
            result = json.loads((run_dir / "result.json").read_text())

            self.assertEqual(result["adapter"], "neus-facto")
            self.assertEqual(result["module_ids"], ["09"])
            self.assertEqual(result["network_mode"], "offline")
            self.assertEqual(result["support"]["completion_claim"], "none")
            self.assertEqual(result["support"]["posterior_sampling_claim"], "none")
            geometry = result["metrics"]["geometry"]
            rendering = result["metrics"]["rendering"]
            field = result["metrics"]["field"]
            unsupported = result["metrics"]["unsupported"]
            self.assertGreaterEqual(geometry["common_visible_fscore_10cm"], 0.99)
            self.assertLess(geometry["common_visible_accuracy_rmse_m"], 1e-5)
            self.assertGreater(rendering["target_psnr_db"], 40.0)
            self.assertAlmostEqual(field["eikonal_mean"], 0.0)
            self.assertGreater(unsupported["truth_points"], 0)
            self.assertGreater(unsupported["predicted_points"], 0)
            self.assertEqual(result["topology"]["mesh_vertices"], 8192)
            self.assertGreater(result["topology"]["mesh_faces"], 1000)

            config = result["provenance"]["config"]
            self.assertEqual(config["iterations"], 1000)
            self.assertEqual(config["rays_per_batch"], 1024)
            self.assertEqual(config["extraction_resolution"], 128)
            self.assertEqual(config["container_user_environment"], {"USER": "surflo"})
            self.assertEqual(config["cuda_cache"], "persistent-cache-root-mount")
            self.assertIs(config["inside_outside"], True)
            self.assertEqual(config["evaluation_software"]["numpy"], np.__version__)
            self.assertEqual(config["evaluation_software"]["python"], sys.version.split()[0])
            self.assertEqual(
                config["entrypoint_command"],
                [
                    "/usr/bin/time",
                    "-v",
                    "-o",
                    "/work/output/resource-usage.txt",
                    "python",
                    "/usr/local/bin/run-neus-facto.py",
                    "--input",
                    "/work/input",
                    "--output",
                    "/work/output",
                    "--iterations",
                    "1000",
                    "--rays-per-batch",
                    "1024",
                    "--extraction-resolution",
                    "128",
                ],
            )
            self.assertEqual(config["lpips_backbone"]["sha256"], LPIPS_SHA256)
            self.assertRegex(config["adapter_execution_contract_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(result["tool"]["container_image_id"], FIXTURE_IMAGE_ID)
            self.assertGreater(result["resources"]["training_seconds"], 0.0)
            self.assertGreater(result["resources"]["training_steps_per_second"], 0.0)
            versions = json.loads(
                (run_dir / "output/runtime-versions.json").read_text()
            )
            self.assertEqual(versions["python"], "3.12.3")
            self.assertEqual(versions["numpy"], "2.5.2")
            self.assertIn("release 12.8", versions["cuda_compiler"])
            self.assertIn("output/mesh.ply", result["provenance"]["artifacts_sha256"])
            self.assertIn(
                "output/field.sdf_grid.float32.npy",
                result["provenance"]["artifacts_sha256"],
            )
            self.assertIn("## Geometry", (run_dir / "report.md").read_text())
            self.assertIn("not a completion", (run_dir / "report.md").read_text())

            sys.path.insert(0, str(ROOT / "pipeline"))
            from neus_reference_runner import validate_neus_reference_result

            validate_neus_reference_result(run_dir)

    def test_failed_container_is_not_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sys.path.insert(0, str(ROOT / "pipeline"))
            import neus_reference_runner

            checkpoint = root / "fixture-alexnet-weights.pth"
            checkpoint.write_bytes(b"fixture weights")

            with mock.patch.dict(
                os.environ,
                {"SURFLO_PATHWAY_CONTAINER_ENGINE": str(fake_neus_engine(root, fail=True))},
            ), mock.patch.object(
                neus_reference_runner, "_lpips_checkpoint_path", return_value=checkpoint
            ):
                with self.assertRaisesRegex(ValueError, "failed"):
                    neus_reference_runner.run_neus_reference(
                        root / "cache", "smoke", "failed-neus"
                    )
            self.assertFalse((root / "cache/reference-runs/failed-neus").exists())

    def test_tampered_metric_or_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = run_fake_neus_reference(root)
            sys.path.insert(0, str(ROOT / "pipeline"))
            from neus_reference_runner import validate_neus_reference_result

            result_path = run_dir / "result.json"
            result = json.loads(result_path.read_text())
            result["metrics"]["geometry"]["common_visible_fscore_10cm"] = 0.123
            result_path.write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, "metric"):
                validate_neus_reference_result(run_dir)

            result_path.write_text(json.dumps(json.loads(
                (run_dir / "result.json").read_text()
            )))

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_neus_reference(Path(temporary))
            mesh = run_dir / "output/mesh.ply"
            mesh.write_text(mesh.read_text() + "\n")
            sys.path.insert(0, str(ROOT / "pipeline"))
            from neus_reference_runner import validate_neus_reference_result

            with self.assertRaisesRegex(ValueError, "artifact"):
                validate_neus_reference_result(run_dir)

    def test_tampered_resource_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_neus_reference(Path(temporary))
            result_path = run_dir / "result.json"
            result = json.loads(result_path.read_text())
            result["resources"]["runtime_seconds"] += 1.0
            result_path.write_text(json.dumps(result))

            sys.path.insert(0, str(ROOT / "pipeline"))
            from neus_reference_runner import validate_neus_reference_result

            with self.assertRaisesRegex(ValueError, "resource summary mismatch"):
                validate_neus_reference_result(run_dir)

    def test_tampered_sdfstudio_metadata_is_rejected_as_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_neus_reference(Path(temporary))
            metadata = run_dir / "input/meta_data.json"
            value = json.loads(metadata.read_text())
            value["camera_model"] = "PINHOLE"
            metadata.write_text(json.dumps(value))

            sys.path.insert(0, str(ROOT / "pipeline"))
            from neus_reference_runner import validate_neus_reference_result

            with self.assertRaisesRegex(ValueError, "input hash mismatch: meta_data.json"):
                validate_neus_reference_result(run_dir)

    def test_tampered_evaluation_or_compiler_provenance_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_neus_reference(Path(temporary))
            result_path = run_dir / "result.json"
            result = json.loads(result_path.read_text())
            config = result["provenance"]["config"]
            config["evaluation_software"]["numpy"] = "0.0.0"
            result["provenance"]["config_sha256"] = hashlib.sha256(
                json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            result_path.write_text(json.dumps(result))

            sys.path.insert(0, str(ROOT / "pipeline"))
            from neus_reference_runner import validate_neus_reference_result

            with self.assertRaisesRegex(ValueError, "config identity"):
                validate_neus_reference_result(run_dir)

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_neus_reference(Path(temporary))
            versions_path = run_dir / "output/runtime-versions.json"
            versions = json.loads(versions_path.read_text())
            versions["cuda_compiler"] = "unknown"
            versions_path.write_text(json.dumps(versions))

            with self.assertRaisesRegex(ValueError, "runtime identity"):
                validate_neus_reference_result(run_dir)

    def test_real_profiles_are_explicit_b200_gates(self) -> None:
        for profile, variable in (
            ("smoke", "SURFLO_REQUIRE_NEUS_FACTO_REFERENCE"),
            ("full", "SURFLO_REQUIRE_NEUS_FACTO_FULL"),
        ):
            with self.subTest(profile=profile):
                required = os.environ.get(variable) == "1"
                if not required:
                    continue
                docker = shutil.which("docker")
                self.assertIsNotNone(docker, "required Docker engine is unavailable")
                inspected = subprocess.run(
                    [docker, "image", "inspect", "surflo-pathway-implicit-surface:1"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(inspected.returncode, 0, inspected.stderr)
                sys.path.insert(0, str(ROOT / "pipeline"))
                from neus_reference_runner import run_neus_reference

                cache = Path(
                    os.environ.get(
                        "SURFLO_PATHWAY_CACHE_ROOT",
                        Path.home() / ".cache/surflo/3d-pathway",
                    )
                )
                run_dir = run_neus_reference(
                    cache, profile, f"neus-real-{profile}-test-{os.getpid()}"
                )
                result = json.loads((run_dir / "result.json").read_text())
                self.assertEqual(result["profile"], profile)
                self.assertEqual(result["resources"]["gpu_measurement_status"], "measured")


if __name__ == "__main__":
    unittest.main()
