from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
VGGT_REVISION = "860abec7937da0a4c03c41d3c269c366e82abdf9"
VGGT_MODEL_SHA256 = "f164acf60724910d8fe1578bb499d800850c7bb0948db7555c413f9fbe60467e"
DA3_SOURCE_COMMIT = "3d835ec1a5802d64a8b8b15f817a1ab54809bfe4"
DA3_REVISION = "f4a6c9b3c95e41c82048423d3493a81ec3fa810e"
DA3_MODEL_SHA256 = "e01067dc1659613083d9145a9a2547ccdbe6ccbbf83c4fe7b3e8a4e2bdae78b5"
FIXTURE_IMAGE_ID = "sha256:" + "f" * 64


def fake_foundation_engine(path: Path) -> Path:
    engine = path / "fake-foundation-engine"
    engine.write_text(
        textwrap.dedent(
            rf'''
            #!/usr/bin/env bash
            set -euo pipefail
            if [[ "${{1:-}}" == image && "${{2:-}}" == inspect ]]; then
                printf '{FIXTURE_IMAGE_ID}\n'
                exit 0
            fi
            [[ "${{1:-}}" == run ]]
            [[ " $* " == *" --network none "* ]]
            [[ " $* " == *" --pull=never "* ]]
            [[ " $* " == *" --gpus device="* ]]
            evidence=''
            output=''
            repo=''
            cidfile=''
            previous=''
            for argument in "$@"; do
                if [[ "$previous" == -v && "$argument" == *:/input:ro ]]; then evidence="${{argument%:/input:ro}}"; fi
                if [[ "$previous" == -v && "$argument" == *:/output ]]; then output="${{argument%:/output}}"; fi
                if [[ "$previous" == -v && "$argument" == *:/workspace/surflo:ro ]]; then repo="${{argument%:/workspace/surflo:ro}}"; fi
                if [[ "$previous" == --cidfile ]]; then cidfile="$argument"; fi
                previous="$argument"
            done
            [[ -n "$evidence" && -n "$output" && -n "$repo" && -n "$cidfile" ]]
            [[ ! -e "$(dirname "$evidence")/evaluation/manifest.json" || "$evidence" != *evaluation* ]]
            printf 'fixture-container\n' >"$cidfile"
            python3 - "$evidence" "$output" "$repo" <<'PY'
            import hashlib
            import json
            from pathlib import Path
            import sys
            import numpy as np

            evidence_root, output_root, repo = map(Path, sys.argv[1:])
            sys.path.insert(0, str(repo / "parallax"))
            from pipeline.reference_scene import _render_implicit_sphere

            evidence = json.loads((evidence_root / "manifest.json").read_text())
            evaluation_root = evidence_root.parent / "evaluation"
            evaluation = json.loads((evaluation_root / "manifest.json").read_text())
            lock = json.loads((repo / "parallax/foundation-models.lock.json").read_text())
            environment_path = evidence_root.parent / "config/environment-manifest.json"
            environment = json.loads(environment_path.read_text())
            output_root.mkdir(parents=True, exist_ok=True)
            frames = {{frame["id"]: frame for frame in evaluation["context_frames"]}}
            angle = np.deg2rad(27.0)
            rotation = np.array([[np.cos(angle), -np.sin(angle), 0.0], [np.sin(angle), np.cos(angle), 0.0], [0.0, 0.0, 1.0]])
            scale = 1.8
            translation = np.array([0.35, -0.2, 0.15])
            methods = {{}}
            for method_id, source_commit, direct in (
                ("vggt/direct", "a288dd0f14786c93483e45524328726ab7b1b4ce", True),
                ("da3-base/camera-head", "{DA3_SOURCE_COMMIT}", False),
            ):
                cases = {{}}
                for case in evidence["cases"]:
                    height, width = 64, 84
                    base = evaluation["intrinsics"]
                    intrinsics = np.array([[base["fx"] * width / base["width"], 0.0, (width - 1) / 2], [0.0, base["fy"] * height / base["height"], (height - 1) / 2], [0.0, 0.0, 1.0]])
                    depths, points, extrinsics = [], [], []
                    for frame_id in case["frame_ids"]:
                        frame = frames[frame_id]
                        c2w_truth = np.asarray(frame["camera_to_world_model"], dtype=np.float64)
                        _, mask, depth_truth, normals = _render_implicit_sphere(
                            {{"width": width, "height": height, "fx": intrinsics[0, 0], "fy": intrinsics[1, 1], "cx": intrinsics[0, 2], "cy": intrinsics[1, 2]}},
                            c2w_truth,
                            float(evaluation["sphere_radius_m"]),
                        )
                        truth_points = normals.astype(np.float64) * float(evaluation["sphere_radius_m"])
                        foreground = mask > 0
                        truth_points[~foreground] = c2w_truth[:3, 3]
                        predicted_points = ((truth_points - translation) @ rotation) / scale
                        predicted_center = ((c2w_truth[:3, 3] - translation) @ rotation) / scale
                        predicted_c2w = np.eye(4)
                        predicted_c2w[:3, :3] = rotation.T @ c2w_truth[:3, :3]
                        predicted_c2w[:3, 3] = predicted_center
                        extrinsics.append(np.linalg.inv(predicted_c2w))
                        depths.append(np.where(foreground, depth_truth / scale, 1.0))
                        points.append(predicted_points)
                    depths = np.asarray(depths, dtype=np.float32)
                    points = np.asarray(points, dtype=np.float32)
                    extrinsics = np.asarray(extrinsics, dtype=np.float32)
                    intrinsics_batch = np.repeat(intrinsics[None], len(depths), axis=0).astype(np.float32)
                    archive = f"{{method_id.replace('/', '-')}}-{{case['id']}}.npz"
                    arrays = dict(
                        depth=depths,
                        pointmap_depth=points,
                        extrinsics_w2c=extrinsics,
                        intrinsics_px=intrinsics_batch,
                        confidence=np.ones_like(depths),
                    )
                    if direct:
                        arrays.update(
                            pointmap_direct=points + np.float32(0.001),
                            track_queries=np.zeros((16, 2), dtype=np.float32),
                            tracks=np.zeros((len(depths), 16, 2), dtype=np.float32),
                            track_visibility=np.ones((len(depths), 16), dtype=np.float32),
                            track_confidence=np.ones((len(depths), 16), dtype=np.float32),
                        )
                    np.savez_compressed(output_root / archive, **arrays)
                    checks = {{"depth_point_z_max_error": 1e-6, "depth_point_reprojection_max_px": 1e-6}}
                    if direct:
                        checks.update({{
                            "direct_point_positive_depth_count": int(np.prod(depths.shape)),
                            "direct_point_reprojection_mean_px": 0.1,
                            "direct_point_reprojection_max_px": 0.2,
                        }})
                    cases[case["id"]] = {{
                        "archive": archive,
                        "frame_ids": case["frame_ids"],
                        "original_size_hw": evidence["original_size_hw"],
                        "processed_size_hw": [height, width],
                        "preprocessing": "fixture resize",
                        "inputs": {{
                            "ordered_image_sha256": case["image_sha256"],
                            "ordered_frame_ids": case["frame_ids"],
                            "original_size_hw": evidence["original_size_hw"],
                            "processed_size_hw": [height, width],
                            "exif_orientation_action": "none; repository-generated RGB PNG",
                            "reference_view_index_before_reorder": 0,
                            "reference_view_index_after_reorder": 0,
                            "final_order": "exactly the declared input order",
                            "geometric_transform": "fixture resize",
                            "normalization": "fixture normalization",
                        }},
                        "reference_view_index": 0,
                        "optimization": "none",
                        "camera_convention": "OpenCV world-to-camera",
                        "depth_semantics": "camera-z relative scale",
                        "canonical_pointmap": "depth unprojection",
                        "pixel_coordinate_origin": "integer pixel centers (0,0) through (W-1,H-1)",
                        "direct_pointmap_present": direct,
                        "tracks_present": direct,
                        "tracks": (
                            {{
                                "status": "measured",
                                "query_frame": {{"index": 0, "frame_id": case["frame_ids"][0]}},
                                "coordinate_convention": {{
                                    "order": "xy",
                                    "space": "processed input image pixels",
                                    "origin": "(0,0) is the center of the upper-left pixel",
                                    "pixel_center_lattice": "integer centers 0..W-1 and 0..H-1",
                                }},
                                "resolution_hw": [height, width],
                                "arrays": {{
                                    "track_queries": {{
                                        "archive_member": "track_queries",
                                        "shape": [16, 2],
                                        "dtype": "float32",
                                        "semantics": "reference-frame query xy coordinates",
                                    }},
                                    "tracks": {{
                                        "archive_member": "tracks",
                                        "shape": [len(depths), 16, 2],
                                        "dtype": "float32",
                                        "semantics": "predicted xy coordinates for every frame and query",
                                    }},
                                    "track_visibility": {{
                                        "archive_member": "track_visibility",
                                        "shape": [len(depths), 16],
                                        "dtype": "float32",
                                        "semantics": "per-frame visibility scores",
                                    }},
                                    "track_confidence": {{
                                        "archive_member": "track_confidence",
                                        "shape": [len(depths), 16],
                                        "dtype": "float32",
                                        "semantics": "per-frame track confidence scores",
                                    }},
                                }},
                                "visibility": {{
                                    "domain": "sigmoid score in [0,1]",
                                    "threshold": None,
                                    "semantics": "model estimate that the query is visible in each frame",
                                }},
                                "confidence": {{
                                    "domain": "sigmoid score in [0,1]",
                                    "threshold": None,
                                    "semantics": "model confidence in each predicted track coordinate",
                                }},
                            }}
                            if direct
                            else {{"status": "unsupported"}}
                        ),
                        "confidence": {{
                            "raw_head": "fixture_confidence",
                            "shape": list(depths.shape),
                            "domain": "fixture",
                            "threshold": None,
                        }},
                        "validity": {{
                            "total_pixels": int(depths.size),
                            "finite_depth": int(depths.size),
                            "positive_depth": int(depths.size),
                            "finite_points": int(np.prod(points.shape[:-1])),
                            "in_frame_points": int(depths.size),
                            "finite_confidence": int(depths.size),
                            "confidence_threshold": None,
                            "confidence_selected": int(depths.size),
                            "sky_mask_status": "unsupported",
                            "background_mask_status": "unsupported-model-side",
                            "evaluation_mask_status": "evaluator-only; not mounted into inference container",
                        }},
                        "gauge": {{
                            "reference": "fixture learned frame",
                            "metric_scale": False,
                            "alignment_applied": "none",
                            "optimization": "none",
                        }},
                        "checks": checks,
                        "runtime_seconds": {{
                            "preprocessing": 0.001,
                            "network": 0.01,
                            "decoding_unprojection": 0.001,
                            "export": 0.001,
                            "total": 0.013,
                        }},
                    }}
                model_lock = lock["models"]["vggt" if method_id == "vggt/direct" else "depth-anything-3"]
                source_tree = (
                    model_lock["source_archive"]["tree_sha256"]
                    if method_id == "vggt/direct"
                    else model_lock["source_tree_sha256"]
                )
                methods[method_id] = {{
                    "source_commit": source_commit,
                    "source": {{
                        "repository": model_lock["source_repository"],
                        "commit": model_lock["source_commit"],
                        "license": model_lock["source_license"],
                        "tree_sha256": source_tree,
                        "nested_gitlinks": model_lock["nested_gitlinks"],
                    }},
                    "checkpoint": {{
                        "repository": model_lock["repository"],
                        "revision": model_lock["revision"],
                        "license": model_lock["license"],
                        "files": model_lock["files"],
                    }},
                    "checkpoint_path": "/locked/model",
                    "upstream_unprojection_parity": {{
                        "helper": (
                            "vggt.utils.geometry.unproject_depth_map_to_point_map"
                            if direct
                            else "depth_anything_3.utils.geometry.unproject_depth"
                        ),
                        "pixel_coordinate_origin": "integer pixel centers (0,0) through (W-1,H-1)",
                        "max_abs_error": 0.0,
                    }},
                    "load_seconds": 0.01,
                    "peak_gpu_memory_bytes": 123456,
                    "cases": cases,
                }}
            result = {{
                "schema_version": 2,
                "network_mode": "offline",
                "methods": methods,
                "runtime": {{
                    "python": "3.10.20", "torch": "2.9.1+cu130", "torchvision": "0.24.1+cu130",
                    "cuda_runtime": "13.0", "device": "fixture B200", "compute_capability": [10, 0],
                    "deterministic_seed": 260925, "cudnn_benchmark": False, "tf32": False,
                    "dtype": "bfloat16", "total_seconds": 0.1,
                }},
                "environment": {{
                    "build_lock": lock["environment"]["build_lock"],
                    "tree_sha256": environment["tree_sha256"],
                    "file_count": environment["file_count"],
                    "byte_size": environment["byte_size"],
                    "manifest_sha256": hashlib.sha256(environment_path.read_bytes()).hexdigest(),
                    "distributions": environment["distributions"],
                    "native_binaries": environment["native_binaries"],
                    "python_executable": {{"path": "/fixture/python", "sha256": "fixture"}},
                    "loaded_module_files": [{{"path": "/fixture/module.py", "byte_size": 1, "sha256": "fixture"}}],
                }},
            }}
            (output_root / "inference-manifest.json").write_text(json.dumps(result, sort_keys=True) + "\n")
            (output_root / "resource-usage.txt").write_text("Maximum resident set size (kbytes): 12345\n")
            PY
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    engine.chmod(0o755)
    return engine


def run_fake_foundation_reference(root: Path, run_id: str = "foundation-smoke") -> Path:
    sys.path.insert(0, str(ROOT / "pipeline"))
    import pipeline.foundation_geometry_reference_runner as runner

    scout_cache = root / "scout-cache"
    model_root = scout_cache / "models"
    (model_root / "vggt").mkdir(parents=True)
    (model_root / "da3").mkdir()
    source_root = root / "sources"
    (source_root / "vggt").mkdir(parents=True)
    (source_root / "da3").mkdir()
    environment_root = scout_cache / "venv"
    environment_root.mkdir()
    environment_lock = json.loads((ROOT / "foundation-models.lock.json").read_text())[
        "environment"
    ]
    environment_manifest = {
        "schema_version": 1,
        "root_kind": "resolved-python-environment",
        "tree_sha256": environment_lock["tree_sha256"],
        "file_count": environment_lock["file_count"],
        "byte_size": environment_lock["byte_size"],
        "files": [{"path": "fixture", "size": 1, "sha256": "fixture"}],
        "exclusions": ["__pycache__", "*.pyc"],
        "distributions": [{"name": "fixture", "version": "1"}],
        "native_binaries": [{"path": "fixture.so", "size": 1, "sha256": "fixture"}],
    }
    with (
        mock.patch.object(
            runner,
            "_verify_model_cache",
            return_value={
                "models": {
                    "vggt": model_root / "vggt",
                    "depth-anything-3": model_root / "da3",
                },
                "sources": {
                    "vggt": source_root / "vggt",
                    "depth-anything-3": source_root / "da3",
                },
                "source_manifests": {
                    "vggt": {"tree_sha256": "fixture-vggt"},
                    "depth-anything-3": {"tree_sha256": "fixture-da3"},
                },
                "environment": {
                    "root": environment_root,
                    "manifest": environment_manifest,
                },
            },
        ),
        mock.patch.object(runner, "_gpu_hardware", return_value=[]),
        mock.patch.dict(
            os.environ,
            {
                "SURFLO_PATHWAY_CONTAINER_ENGINE": str(fake_foundation_engine(root)),
                "SURFLO_INSULA_CACHE_ROOT": str(scout_cache),
            },
        ),
    ):
        return runner.run_foundation_geometry_reference(
            root / "cache", "smoke", run_id
        )


class FoundationGeometryReferenceContractTest(unittest.TestCase):
    def test_canonical_unprojection_matches_upstream_integer_pixel_lattice(self) -> None:
        script = ROOT / "insulas/surflo-foundation/run-foundation-models.py"
        spec = importlib.util.spec_from_file_location("foundation_models_runner", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        depth = np.full((1, 2, 3), 2.0, dtype=np.float32)
        intrinsics = np.array(
            [[[2.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 1.0]]],
            dtype=np.float32,
        )
        extrinsics = np.eye(4, dtype=np.float32)[None]

        points = module._unproject_depth(depth, intrinsics, extrinsics)

        expected = np.array(
            [
                [
                    [[0.0, 0.0, 2.0], [1.0, 0.0, 2.0], [2.0, 0.0, 2.0]],
                    [[0.0, 0.5, 2.0], [1.0, 0.5, 2.0], [2.0, 0.5, 2.0]],
                ]
            ],
            dtype=np.float32,
        )
        np.testing.assert_allclose(points, expected, atol=0.0, rtol=0.0)

    @unittest.skipUnless(
        os.environ.get("SURFLO_REQUIRE_FOUNDATION_GEOMETRY_REFERENCE") == "1",
        "set SURFLO_REQUIRE_FOUNDATION_GEOMETRY_REFERENCE=1 for the real B200 smoke gate",
    )
    def test_real_smoke_reference_runs_when_required(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.foundation_geometry_reference_runner import (
            run_foundation_geometry_reference,
            validate_foundation_geometry_reference_result,
        )

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_foundation_geometry_reference(
                Path(temporary), "smoke", f"foundation-real-smoke-{os.getpid()}"
            )
            result = validate_foundation_geometry_reference_result(run_dir)
            self.assertEqual(result["profile"], "smoke")

    @unittest.skipUnless(
        os.environ.get("SURFLO_REQUIRE_FOUNDATION_GEOMETRY_FULL") == "1",
        "set SURFLO_REQUIRE_FOUNDATION_GEOMETRY_FULL=1 for the real B200 full gate",
    )
    def test_real_full_reference_runs_when_required(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.foundation_geometry_reference_runner import (
            run_foundation_geometry_reference,
            validate_foundation_geometry_reference_result,
        )

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_foundation_geometry_reference(
                Path(temporary), "full", f"foundation-real-full-{os.getpid()}"
            )
            result = validate_foundation_geometry_reference_result(run_dir)
            self.assertEqual(result["profile"], "full")

    def test_container_command_uses_only_tools_in_the_surflo_insula(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.foundation_geometry_reference_runner import _container_command

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "scout-cache"
            staging = root / "staging"
            cuda_cache = root / "cuda-cache"
            vggt = cache / "vggt"
            da3 = cache / "da3"
            vggt_source = root / "vggt-source"
            da3_source = root / "da3-source"
            for directory in (
                staging / "evidence",
                staging / "output",
                staging / "config",
                cuda_cache,
                vggt,
                da3,
                vggt_source,
                da3_source,
            ):
                directory.mkdir(parents=True)
            with mock.patch.dict(os.environ, {"SURFLO_INSULA_CACHE_ROOT": str(cache)}):
                command = _container_command(
                    "docker",
                    FIXTURE_IMAGE_ID,
                    staging,
                    cuda_cache,
                    {
                        "models": {"vggt": vggt, "depth-anything-3": da3},
                        "sources": {
                            "vggt": vggt_source,
                            "depth-anything-3": da3_source,
                        },
                    },
                    "1",
                )
        shell = command[-1]
        self.assertNotIn("/usr/bin/time", shell)
        self.assertIn("PYTHONPATH=/workspace/surflo/parallax:/opt/vggt", shell)
        self.assertIn("run-foundation-models.py", shell)

    def test_fake_reference_is_scored_sealed_and_atomically_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = run_fake_foundation_reference(Path(temporary))
            result = json.loads((run_dir / "result.json").read_text())

            self.assertEqual(result["adapter"], "foundation-geometry")
            self.assertEqual(result["module_ids"], ["12"])
            self.assertEqual(result["network_mode"], "offline")
            self.assertEqual(
                set(result["metrics"]["methods"]),
                {"vggt/direct", "da3-base/camera-head"},
            )
            for method in result["metrics"]["methods"].values():
                geometry = method["primary_case"]["pointmap_depth"]
                self.assertGreater(geometry["raw_point_rmse_m"], 0.1)
                self.assertGreater(geometry["se3_point_rmse_m"], 0.05)
                self.assertLess(geometry["sim3_point_rmse_m"], 1e-4)
                self.assertLess(
                    method["primary_case"]["camera"]["sim3_center_rmse_m"],
                    1e-5,
                )
                self.assertIn(
                    "first_camera_translation_residual", method["primary_case"]["camera"]
                )
                self.assertIn(
                    "focal_relative_error_mean", method["primary_case"]["camera"]
                )
                self.assertNotIn("sim3_point_fscore", geometry)
                self.assertIn("sim3_correspondence_within_threshold", geometry)
                self.assertIn("fscore", geometry["surface_observed_metric"])
                self.assertIn("recall", geometry["surface_unseen_metric"])
                self.assertEqual(
                    method["cases"]["views-1-monocular"]["camera"][
                        "relative_pose_auc_30_status"
                    ],
                    "unsupported-single-view",
                )
                self.assertIn("case_total_seconds", method["runtime"])
                self.assertIn("network_seconds", method["runtime"])
            vggt_tracks = result["metrics"]["methods"]["vggt/direct"][
                "primary_case"
            ]["tracks"]
            self.assertEqual(vggt_tracks["status"], "measured")
            self.assertEqual(vggt_tracks["query_frame"]["index"], 0)
            self.assertEqual(
                vggt_tracks["query_frame"]["frame_id"],
                "context-000",
            )
            self.assertEqual(vggt_tracks["resolution_hw"], [64, 84])
            self.assertEqual(vggt_tracks["arrays"]["track_queries"]["shape"], [16, 2])
            self.assertEqual(
                vggt_tracks["arrays"]["tracks"]["shape"], [5, 16, 2]
            )
            self.assertEqual(
                vggt_tracks["visibility"]["domain"], "sigmoid score in [0,1]"
            )
            self.assertEqual(vggt_tracks["visibility"]["threshold"], None)
            sweep = result["metrics"]["failure_sweep"]
            self.assertEqual(sweep["views-1-monocular"]["sweep"]["view_count"], 1)
            self.assertEqual(sweep["views-5-permuted"]["sweep"]["order"], "permuted")
            self.assertEqual(result["support"]["hidden_scene_prediction_count"], 0)
            self.assertEqual(result["support"]["completion_claim"], "none")
            self.assertTrue((run_dir / "report.md").is_file())
            self.assertTrue((run_dir / "output/foundation-geometry-sweep.svg").is_file())
            self.assertFalse(
                list((run_dir.parent.parent.parent / "reference-staging").glob("*"))
            )

            inference = json.loads(
                (run_dir / "output/inference-manifest.json").read_text()
            )
            for method_id, method in inference["methods"].items():
                self.assertEqual(
                    set(method["source"]),
                    {
                        "repository",
                        "commit",
                        "license",
                        "tree_sha256",
                        "nested_gitlinks",
                    },
                )
                self.assertEqual(
                    set(method["checkpoint"]),
                    {"repository", "revision", "license", "files"},
                )
                parity = method["upstream_unprojection_parity"]
                self.assertEqual(
                    parity["pixel_coordinate_origin"],
                    "integer pixel centers (0,0) through (W-1,H-1)",
                )
                self.assertLessEqual(parity["max_abs_error"], 1e-6)
                self.assertIn(
                    "vggt.utils.geometry"
                    if method_id == "vggt/direct"
                    else "depth_anything_3.utils.geometry",
                    parity["helper"],
                )
                for case in method["cases"].values():
                    self.assertIn("ordered_image_sha256", case["inputs"])
                    self.assertIn("raw_head", case["confidence"])
                    self.assertIn("finite_points", case["validity"])
                    self.assertEqual(case["gauge"]["alignment_applied"], "none")
                    self.assertIn("total", case["runtime_seconds"])
                    if method_id == "vggt/direct":
                        self.assertEqual(case["tracks"]["query_frame"]["index"], 0)
                        self.assertEqual(
                            case["tracks"]["coordinate_convention"]["order"], "xy"
                        )
                        self.assertEqual(
                            case["tracks"]["arrays"]["track_confidence"]["shape"],
                            [len(case["frame_ids"]), 16],
                        )
                    else:
                        self.assertEqual(case["tracks"], {"status": "unsupported"})
            self.assertIn("tree_sha256", inference["environment"])
            self.assertEqual(
                inference["environment"]["build_lock"],
                json.loads((ROOT / "foundation-models.lock.json").read_text())[
                    "environment"
                ]["build_lock"],
            )
            self.assertIn("distributions", inference["environment"])
            self.assertIn("native_binaries", inference["environment"])

            sys.path.insert(0, str(ROOT / "pipeline"))
            from pipeline.foundation_geometry_reference_runner import validate_foundation_geometry_reference_result

            validate_foundation_geometry_reference_result(run_dir)
            archive = next((run_dir / "output").glob("*.npz"))
            archive.write_bytes(archive.read_bytes() + b"tamper")
            with self.assertRaisesRegex(ValueError, "artifact|hash"):
                validate_foundation_geometry_reference_result(run_dir)

    def test_in_insula_runner_exposes_explicit_local_model_inputs(self) -> None:
        script = ROOT / "insulas/surflo-foundation/run-foundation-models.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=ROOT.parent,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--vggt-model", completed.stdout)
        self.assertIn("--da3-model", completed.stdout)
        self.assertIn("--input", completed.stdout)
        self.assertIn("--output", completed.stdout)

    def test_controlled_scene_hides_evaluator_truth_from_model_inputs(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.contracts import load_json
        from pipeline.foundation_geometry_reference_runner import _prepare_reference_scene

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evaluation, evidence = _prepare_reference_scene(
                root, load_json(ROOT / "shared-scene.json"), "smoke"
            )

            self.assertEqual(evaluation["profile"], "smoke")
            self.assertEqual(
                [case["id"] for case in evidence["cases"]],
                [
                    "views-1-monocular",
                    "views-2-high-overlap",
                    "views-2-low-overlap",
                    "views-3",
                    "views-5",
                    "views-5-permuted",
                ],
            )
            self.assertEqual(evidence["primary_case_id"], "views-5")
            self.assertEqual(evidence["prediction_input"], "ordered unposed RGB only")
            evidence_text = (root / "evidence/manifest.json").read_text()
            for forbidden in (
                "camera_to_world",
                "depth_path",
                "mask_path",
                "surface_truth",
                "intrinsics",
            ):
                self.assertNotIn(forbidden, evidence_text)
            self.assertTrue((root / "evaluation/manifest.json").is_file())
            self.assertFalse((root / "evidence/depth").exists())
            self.assertFalse((root / "evidence/masks").exists())
            for case in evidence["cases"]:
                self.assertEqual(len(case["frame_ids"]), len(case["image_paths"]))
                for image_path in case["image_paths"]:
                    self.assertTrue((root / "evidence" / image_path).is_file())

    def test_full_scene_declares_complete_factorial_failure_sweep(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.contracts import load_json
        from pipeline.foundation_geometry_reference_runner import _prepare_reference_scene

        with tempfile.TemporaryDirectory() as temporary:
            _, evidence = _prepare_reference_scene(
                Path(temporary), load_json(ROOT / "shared-scene.json"), "full"
            )

        cases = {case["id"]: case for case in evidence["cases"]}
        self.assertEqual(evidence["primary_case_id"], "views-16")
        self.assertEqual(
            {case["sweep"]["view_count"] for case in cases.values()},
            {1, 2, 4, 8, 16},
        )
        self.assertEqual(
            {
                case["sweep"]["overlap"]
                for case in cases.values()
                if case["sweep"]["family"] == "overlap"
            },
            {"high", "medium", "low", "disconnected"},
        )
        self.assertEqual(cases["views-8-permuted"]["sweep"]["order"], "permuted")
        nested_ids = ["views-1-monocular", "views-2", "views-4", "views-8", "views-16"]
        nested_sets = [set(cases[case_id]["frame_ids"]) for case_id in nested_ids]
        for smaller, larger in zip(nested_sets, nested_sets[1:]):
            self.assertLess(smaller, larger)
        self.assertTrue(all(case["sweep"]["surface_slices"] == ["observed", "unseen"] for case in cases.values()))

    def test_public_reference_plan_is_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(Path(temporary) / "cache")
            completed = subprocess.run(
                [
                    str(ROOT / "run.sh"),
                    "--emit-plan",
                    "reference",
                    "--adapter",
                    "foundation-geometry",
                    "--profile",
                    "smoke",
                    "--run-id",
                    "foundation-plan",
                ],
                cwd=ROOT.parent,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "adapter": "foundation-geometry",
                "command": "reference",
                "network_mode": "offline",
                "profile": "smoke",
                "run_id": "foundation-plan",
                "schema_version": 1,
            },
        )

    def test_checkpoint_source_and_license_locks_are_exact(self) -> None:
        lock = json.loads((ROOT / "foundation-models.lock.json").read_text())
        self.assertEqual(lock["schema_version"], 2)
        models = lock["models"]
        self.assertEqual(models["vggt"]["revision"], VGGT_REVISION)
        self.assertEqual(
            models["vggt"]["files"]["model.safetensors"]["sha256"],
            VGGT_MODEL_SHA256,
        )
        self.assertEqual(models["vggt"]["license"], "CC-BY-NC-4.0")
        self.assertEqual(
            models["vggt"]["source_commit"],
            "a288dd0f14786c93483e45524328726ab7b1b4ce",
        )
        self.assertEqual(
            models["vggt"]["source_archive"]["sha256"],
            "df4e7de1184bcb28ad6b4a83ead828f34ba42fb18be03c034801ffeb3a058f91",
        )
        self.assertNotIn("vendored_source_files", models["vggt"])
        self.assertEqual(models["vggt"]["nested_gitlinks"], [])
        self.assertEqual(models["depth-anything-3"]["source_commit"], DA3_SOURCE_COMMIT)
        self.assertEqual(
            models["depth-anything-3"]["nested_gitlinks"],
            [
                {
                    "path": "da3_streaming/loop_utils/salad",
                    "mode": "160000",
                    "commit": "6aede13a3f6c25750bf7fde10209c06cb73060bb",
                }
            ],
        )
        self.assertEqual(models["depth-anything-3"]["revision"], DA3_REVISION)
        self.assertEqual(
            models["depth-anything-3"]["files"]["model.safetensors"]["sha256"],
            DA3_MODEL_SHA256,
        )
        self.assertEqual(models["depth-anything-3"]["license"], "Apache-2.0")
        self.assertRegex(lock["environment"]["tree_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            lock["environment"]["build_lock"],
            {
                "path": "experiments/insula-scout/foundation-environment.lock.json",
                "sha256": "4e2f2abc0ab1a620efbd45ff25786c710cb175cf05d7711e3b94423f42c917e3",
            },
        )

    def test_dirty_source_checkout_is_rejected_before_execution(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.foundation_geometry_reference_runner import _tracked_source_manifest

        with tempfile.TemporaryDirectory() as temporary:
            checkout = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
            source = checkout / "source.py"
            source.write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "source.py"], cwd=checkout, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                cwd=checkout,
                check=True,
            )
            self.assertEqual(_tracked_source_manifest(checkout)["file_count"], 1)
            source.write_text("VALUE = 2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "dirty"):
                _tracked_source_manifest(checkout)

    def test_tracked_source_manifest_includes_nested_gitlink_commit(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.foundation_geometry_reference_runner import _tracked_source_manifest

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dependency = root / "dependency"
            dependency.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=dependency, check=True)
            (dependency / "nested.py").write_text("VALUE = 7\n", encoding="utf-8")
            subprocess.run(["git", "add", "nested.py"], cwd=dependency, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "nested",
                ],
                cwd=dependency,
                check=True,
            )
            nested_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=dependency,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(
                [
                    "git",
                    "-c",
                    "advice.addEmbeddedRepo=false",
                    "add",
                    "source.py",
                    "dependency",
                ],
                cwd=root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "root",
                ],
                cwd=root,
                check=True,
            )

            manifest = _tracked_source_manifest(root)

        self.assertEqual(manifest["file_count"], 2)
        self.assertEqual(
            manifest["gitlinks"],
            [{"path": "dependency", "mode": "160000", "commit": nested_commit}],
        )
        self.assertIn(manifest["gitlinks"][0], manifest["files"])

    def test_similarity_alignment_recovers_scale_rotation_and_translation(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.foundation_geometry_reference_runner import _fit_similarity

        source = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 2.0, 0.0],
                [0.0, 0.0, 3.0],
            ],
            dtype=np.float64,
        )
        rotation = np.array(
            [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        target = 2.5 * (source @ rotation.T) + np.array([4.0, -3.0, 1.5])

        fitted = _fit_similarity(source, target)

        np.testing.assert_allclose(fitted["aligned"], target, atol=1e-12, rtol=0.0)
        np.testing.assert_allclose(fitted["rotation"], rotation, atol=1e-12, rtol=0.0)
        np.testing.assert_allclose(fitted["translation"], [4.0, -3.0, 1.5], atol=1e-12, rtol=0.0)
        self.assertAlmostEqual(fitted["scale"], 2.5, places=12)
        self.assertLess(fitted["rmse"], 1e-12)

    def test_geometry_scores_do_not_hide_scale_error_in_rigid_alignment(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.foundation_geometry_reference_runner import _score_aligned_geometry

        truth_centers = np.array(
            [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 4.0]],
            dtype=np.float64,
        )
        truth_points = np.array(
            [[0.5, 0.0, 0.0], [0.0, 0.75, 0.0], [0.0, 0.0, 1.0], [-0.5, 0.0, 0.0]],
            dtype=np.float64,
        )
        rotation = np.array(
            [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        scale = 2.0
        translation = np.array([1.0, -2.0, 0.5])
        predicted_centers = ((truth_centers - translation) @ rotation) / scale
        predicted_points = ((truth_points - translation) @ rotation) / scale

        scores = _score_aligned_geometry(
            predicted_centers,
            predicted_points,
            truth_centers,
            truth_points,
        )

        self.assertGreater(scores["raw"]["camera_center_rmse_m"], 0.5)
        self.assertGreater(scores["se3"]["camera_center_rmse_m"], 0.25)
        self.assertGreater(scores["se3"]["point_rmse_m"], 0.1)
        self.assertLess(scores["sim3"]["camera_center_rmse_m"], 1e-12)
        self.assertLess(scores["sim3"]["point_rmse_m"], 1e-12)
        self.assertAlmostEqual(scores["sim3"]["scale"], scale, places=12)

    def test_pose_constrained_alignment_is_defined_for_two_views(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.foundation_geometry_reference_runner import _fit_pose_alignment

        truth_centers = np.array([[-1.0, 0.0, 0.25], [1.0, 0.0, 0.25]])
        truth_rotations = np.repeat(np.eye(3)[None], 2, axis=0)
        angle = np.deg2rad(71.0)
        gauge_rotation = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, np.cos(angle), -np.sin(angle)],
                [0.0, np.sin(angle), np.cos(angle)],
            ]
        )
        scale = 2.4
        translation = np.array([0.4, -0.7, 1.1])
        predicted_centers = ((truth_centers - translation) @ gauge_rotation) / scale
        predicted_rotations = np.einsum(
            "ij,njk->nik", gauge_rotation.T, truth_rotations
        )

        fitted = _fit_pose_alignment(
            predicted_centers,
            predicted_rotations,
            truth_centers,
            truth_rotations,
            allow_scale=True,
        )

        np.testing.assert_allclose(fitted["aligned"], truth_centers, atol=1e-12)
        np.testing.assert_allclose(fitted["rotation"], gauge_rotation, atol=1e-12)
        self.assertAlmostEqual(fitted["scale"], scale, places=12)

    def test_bidirectional_point_metrics_report_real_precision_recall_and_fscore(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.foundation_geometry_reference_runner import _bidirectional_cloud_metrics

        predicted = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]])
        truth = np.array([[0.0, 0.0, 0.0], [0.05, 0.0, 0.0]])

        metrics = _bidirectional_cloud_metrics(predicted, truth, threshold_m=0.1)

        self.assertAlmostEqual(metrics["precision"], 0.5)
        self.assertAlmostEqual(metrics["recall"], 1.0)
        self.assertAlmostEqual(metrics["fscore"], 2.0 / 3.0)
        self.assertGreater(metrics["accuracy_mean_m"], metrics["completeness_mean_m"])

    def test_pathway_build_prepares_reused_surflo_insula(self) -> None:
        build = (ROOT / "insulas/build.sh").read_text(encoding="utf-8")
        self.assertIn("insula-scout/build.sh", build)
        self.assertIn("selected_gpu_device", build)
        self.assertIn("CUDA_VISIBLE_DEVICES", build)

    def test_relative_pose_auc_is_invariant_to_global_similarity_gauge(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from pipeline.foundation_geometry_reference_runner import _pair_pose_auc

        truth_centers = np.array(
            [[-2.0, 0.0, 1.0], [0.0, 0.0, 3.0], [2.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        truth_rotations = np.repeat(np.eye(3)[None], 3, axis=0)
        angle = np.deg2rad(67.0)
        gauge_rotation = np.array(
            [[np.cos(angle), -np.sin(angle), 0.0], [np.sin(angle), np.cos(angle), 0.0], [0.0, 0.0, 1.0]]
        )
        translation = np.array([0.4, -0.7, 1.1])
        predicted_centers = ((truth_centers - translation) @ gauge_rotation) / 2.3
        predicted_rotations = np.einsum(
            "ij,njk->nik", gauge_rotation.T, truth_rotations
        )

        auc = _pair_pose_auc(
            predicted_centers,
            predicted_rotations,
            truth_centers,
            truth_rotations,
            30.0,
        )

        self.assertAlmostEqual(auc, 1.0, places=7)


if __name__ == "__main__":
    unittest.main()
