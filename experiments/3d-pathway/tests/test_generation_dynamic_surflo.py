from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))


class AmbiguousSceneContractTest(unittest.TestCase):
    def test_shared_scene_latent_is_coherent_while_independent_points_hybridize(self) -> None:
        from generative import evaluate_ambiguity_fixture, generate_ambiguity_fixture

        fixture = generate_ambiguity_fixture(
            samples=128,
            hidden_points_per_sample=257,
            seed=13,
        )
        comparison = evaluate_ambiguity_fixture(fixture)
        independent = comparison["independent_points"]
        shared = comparison["shared_scene_latent"]
        self.assertLess(independent["within_sample_coherence"], 0.65)
        self.assertEqual(shared["within_sample_coherence"], 1.0)
        self.assertGreater(independent["hypothesis_coverage"], 0.9)
        self.assertGreater(shared["hypothesis_coverage"], 0.9)
        self.assertEqual(independent["coherent_hypothesis_coverage"], 0.0)
        self.assertEqual(shared["coherent_hypothesis_coverage"], 1.0)
        self.assertEqual(independent["evidence_consistency"], 1.0)
        self.assertEqual(shared["evidence_consistency"], 1.0)
        self.assertGreater(independent["best_hypothesis_rmse_m"], 0.5)
        self.assertEqual(shared["best_hypothesis_rmse_m"], 0.0)
        self.assertGreater(independent["repeat_query_consistency"], 0.4)
        self.assertLess(independent["repeat_query_consistency"], 0.6)
        self.assertEqual(shared["repeat_query_consistency"], 1.0)
        self.assertGreater(independent["marginal_mode_entropy_bits"], 0.95)
        self.assertEqual(independent["coherent_scene_entropy_bits"], 0.0)
        self.assertGreater(shared["coherent_scene_entropy_bits"], 0.9)

    def test_shared_scene_latent_is_resolution_persistent(self) -> None:
        from generative import generate_ambiguity_fixture

        coarse = generate_ambiguity_fixture(
            samples=64,
            hidden_points_per_sample=17,
            seed=260925,
        )
        dense = generate_ambiguity_fixture(
            samples=64,
            hidden_points_per_sample=4097,
            seed=260925,
        )
        np.testing.assert_array_equal(
            coarse["shared_scene_latents"],
            dense["shared_scene_latents"],
        )

    def test_ambiguity_fixture_is_seed_deterministic(self) -> None:
        from generative import generate_ambiguity_fixture

        first = generate_ambiguity_fixture(
            samples=16,
            hidden_points_per_sample=33,
            seed=7,
        )
        second = generate_ambiguity_fixture(
            samples=16,
            hidden_points_per_sample=33,
            seed=7,
        )
        self.assertEqual(set(first), set(second))
        for name in first:
            with self.subTest(array=name):
                np.testing.assert_array_equal(first[name], second[name])

    def test_evidence_consistency_is_recomputed_from_predicted_points(self) -> None:
        from generative import evaluate_ambiguity_fixture, generate_ambiguity_fixture

        fixture = generate_ambiguity_fixture(
            samples=32,
            hidden_points_per_sample=31,
            seed=13,
        )
        fixture["independent_observed_xyz"] = (
            fixture["independent_observed_xyz"] + np.array([0.2, 0.0, 0.0])
        )
        independent = evaluate_ambiguity_fixture(fixture)["independent_points"]
        self.assertGreater(independent["evidence_rmse_m"], 0.19)
        self.assertEqual(independent["evidence_consistency"], 0.0)

    def test_fixture_rejects_degenerate_experiments(self) -> None:
        from generative import generate_ambiguity_fixture

        for samples, points in ((1, 16), (8, 1)):
            with self.subTest(samples=samples, points=points):
                with self.assertRaisesRegex(ValueError, "at least two"):
                    generate_ambiguity_fixture(
                        samples=samples,
                        hidden_points_per_sample=points,
                        seed=13,
                    )

    def test_fixture_rejects_non_finite_observed_truth(self) -> None:
        from generative import evaluate_ambiguity_fixture, generate_ambiguity_fixture

        fixture = generate_ambiguity_fixture(
            samples=8,
            hidden_points_per_sample=17,
            seed=13,
        )
        fixture["observed_truth_xyz"][0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "observed truth contains non-finite"):
            evaluate_ambiguity_fixture(fixture)

    def test_module13_persists_recomputable_samples_and_visual_evidence(self) -> None:
        from generative import evaluate_ambiguity_fixture

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            completed = subprocess.run(
                [
                    str(ROOT / "run.sh"),
                    "run",
                    "--module",
                    "13",
                    "--profile",
                    "smoke",
                    "--run-id",
                    "ambiguity-contract",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "runs" / "ambiguity-contract" / "13"
            result = json.loads((run_dir / "result.json").read_text())
            self.assertTrue((run_dir / "artifacts/ambiguity_samples.npz").is_file())
            self.assertTrue((run_dir / "artifacts/ambiguity_samples.svg").is_file())
            with np.load(run_dir / "artifacts/ambiguity_samples.npz") as archive:
                recomputed = evaluate_ambiguity_fixture(
                    {name: archive[name] for name in archive.files}
                )
            metrics = result["metrics"]["generative"]
            self.assertAlmostEqual(
                recomputed["independent_points"]["within_sample_coherence"],
                metrics["independent_point_coherence"],
            )
            self.assertAlmostEqual(
                recomputed["shared_scene_latent"]["best_hypothesis_rmse_m"],
                metrics["shared_latent_best_hypothesis_rmse_m"],
            )
            result["profile"] = "full"
            (run_dir / "result.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n"
            )
            validation = subprocess.run(
                [
                    str(ROOT / "run.sh"),
                    "validate",
                    "--module",
                    "13",
                    "--run-id",
                    "ambiguity-contract",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("Module 13 fixture/profile mismatch", validation.stderr)
            result["profile"] = "smoke"
            expected_coherence = metrics["independent_point_coherence"]
            result["metrics"]["generative"]["independent_point_coherence"] = 1.0
            (run_dir / "result.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n"
            )
            validation = subprocess.run(
                [
                    str(ROOT / "run.sh"),
                    "validate",
                    "--module",
                    "13",
                    "--run-id",
                    "ambiguity-contract",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("Module 13 metric mismatch", validation.stderr)

            result["metrics"]["generative"][
                "independent_point_coherence"
            ] = expected_coherence
            expected_sweep_measurement = result["failure_sweep"][0]["measurement"]
            result["failure_sweep"][0]["measurement"] = 0.123
            (run_dir / "result.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n"
            )
            validation = subprocess.run(
                [
                    str(ROOT / "run.sh"),
                    "validate",
                    "--module",
                    "13",
                    "--run-id",
                    "ambiguity-contract",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("Module 13 failure sweep mismatch", validation.stderr)

            result["failure_sweep"][0]["measurement"] = expected_sweep_measurement
            sweep_path = run_dir / "artifacts/failure_sweep.csv"
            with sweep_path.open(newline="", encoding="utf-8") as stream:
                sweep_rows = list(csv.DictReader(stream))
            sweep_rows[0]["measurement"] = "0.123"
            with sweep_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=["parameter", "value", "metric", "measurement"],
                )
                writer.writeheader()
                writer.writerows(sweep_rows)
            result["provenance"]["artifacts_sha256"]["failure_sweep.csv"] = (
                hashlib.sha256(sweep_path.read_bytes()).hexdigest()
            )
            (run_dir / "result.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n"
            )
            validation = subprocess.run(
                [
                    str(ROOT / "run.sh"),
                    "validate",
                    "--module",
                    "13",
                    "--run-id",
                    "ambiguity-contract",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("Module 13 failure sweep mismatch", validation.stderr)


class DynamicSceneContractTest(unittest.TestCase):
    def test_occlusion_can_preserve_set_geometry_while_switching_identity(self) -> None:
        from dynamic import evaluate_dynamic_fixture, generate_dynamic_fixture

        fixture = generate_dynamic_fixture(frame_count=65, occlusion_frames=16)
        static = evaluate_dynamic_fixture(fixture)["static_camera"]
        self.assertLess(static["set_aligned_reappearance_rmse_m"], 0.08)
        self.assertGreater(static["identity_aware_post_occlusion_rmse_m"], 0.2)
        self.assertEqual(static["post_occlusion_identity_accuracy"], 0.0)

    def test_known_camera_motion_does_not_create_object_drift(self) -> None:
        from dynamic import evaluate_dynamic_fixture, generate_dynamic_fixture

        comparison = evaluate_dynamic_fixture(
            generate_dynamic_fixture(frame_count=65, occlusion_frames=16)
        )
        self.assertAlmostEqual(
            comparison["static_camera"]["identity_aware_post_occlusion_rmse_m"],
            comparison["moving_camera"]["identity_aware_post_occlusion_rmse_m"],
        )
        self.assertEqual(comparison["moving_camera"]["camera_ate_m"], 0.0)
        self.assertLess(
            comparison["moving_camera"]["temporal_displacement_rmse_m"],
            1e-12,
        )

    def test_dynamic_support_contaminates_camera_object_factorization(self) -> None:
        from dynamic import evaluate_dynamic_fixture, generate_dynamic_fixture

        comparison = evaluate_dynamic_fixture(
            generate_dynamic_fixture(frame_count=65, occlusion_frames=16)
        )
        moving = comparison["moving_camera"]
        joint = comparison["moving_camera_object"]
        self.assertGreater(joint["camera_ate_m"], moving["camera_ate_m"])
        self.assertGreater(
            joint["identity_aware_post_occlusion_rmse_m"],
            moving["identity_aware_post_occlusion_rmse_m"],
        )
        self.assertGreater(joint["temporal_displacement_rmse_m"], 0.0)

    def test_set_aligned_error_uses_world_truth_not_biased_detections(self) -> None:
        from dynamic import evaluate_dynamic_fixture, generate_dynamic_fixture

        joint = evaluate_dynamic_fixture(
            generate_dynamic_fixture(frame_count=33, occlusion_frames=0)
        )["moving_camera_object"]
        self.assertAlmostEqual(
            joint["set_aligned_reappearance_rmse_m"],
            joint["identity_aware_post_occlusion_rmse_m"],
        )

    def test_dynamic_fixture_rejects_invalid_frame_and_occlusion_contracts(self) -> None:
        from dynamic import generate_dynamic_fixture

        for frames, occlusion in ((8, 2), (33, -1), (33, 30)):
            with self.subTest(frames=frames, occlusion=occlusion):
                with self.assertRaises(ValueError):
                    generate_dynamic_fixture(
                        frame_count=frames,
                        occlusion_frames=occlusion,
                    )

    def test_dynamic_fixture_rejects_inconsistent_camera_and_visibility(self) -> None:
        from dynamic import evaluate_dynamic_fixture, generate_dynamic_fixture

        camera_tamper = generate_dynamic_fixture(33, 8)
        camera_tamper["estimated_camera_xyz"][0, 0, 0] += 0.1
        with self.assertRaisesRegex(ValueError, "visible world reconstruction"):
            evaluate_dynamic_fixture(camera_tamper)

        visibility_tamper = generate_dynamic_fixture(33, 8)
        visibility_tamper["observed_mask"][0, 0, 0] = False
        with self.assertRaisesRegex(ValueError, "observed mask"):
            evaluate_dynamic_fixture(visibility_tamper)

        prediction_tamper = generate_dynamic_fixture(33, 8)
        prediction_tamper["post_occlusion_prediction_xyz"][0, 0, 0] += 0.1
        with self.assertRaisesRegex(ValueError, "post-occlusion prediction"):
            evaluate_dynamic_fixture(prediction_tamper)

    def test_module14_persists_recomputable_dynamic_evidence(self) -> None:
        from dynamic import evaluate_dynamic_fixture

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            completed = subprocess.run(
                [
                    str(ROOT / "run.sh"),
                    "run",
                    "--module",
                    "14",
                    "--profile",
                    "smoke",
                    "--run-id",
                    "dynamic-contract",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_dir = cache / "runs" / "dynamic-contract" / "14"
            archive_path = run_dir / "artifacts/dynamic_sequence.npz"
            self.assertTrue(archive_path.is_file())
            self.assertTrue((run_dir / "artifacts/dynamic_trajectories.svg").is_file())
            with np.load(archive_path, allow_pickle=False) as archive:
                recomputed = evaluate_dynamic_fixture(
                    {name: archive[name] for name in archive.files}
                )
            result = json.loads((run_dir / "result.json").read_text())
            result_path = run_dir / "result.json"

            def validate() -> subprocess.CompletedProcess[str]:
                result_path.write_text(
                    json.dumps(result, indent=2, sort_keys=True) + "\n"
                )
                return subprocess.run(
                    [
                        str(ROOT / "run.sh"),
                        "validate",
                        "--module",
                        "14",
                        "--run-id",
                        "dynamic-contract",
                    ],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )

            self.assertAlmostEqual(
                recomputed["static_camera"][
                    "identity_aware_post_occlusion_rmse_m"
                ],
                result["metrics"]["geometry"][
                    "static_camera_post_occlusion_error_m"
                ],
            )
            expected_metric = result["metrics"]["geometry"][
                "static_camera_post_occlusion_error_m"
            ]
            result["metrics"]["geometry"][
                "static_camera_post_occlusion_error_m"
            ] = 0.0
            validation = validate()
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("Module 14 metric mismatch", validation.stderr)

            result["metrics"]["geometry"][
                "static_camera_post_occlusion_error_m"
            ] = expected_metric
            result["profile"] = "full"
            validation = validate()
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("Module 14 fixture/profile mismatch", validation.stderr)

            result["profile"] = "smoke"
            expected_sweep_measurement = result["failure_sweep"][0]["measurement"]
            result["failure_sweep"][0]["measurement"] = 0.123
            validation = validate()
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("Module 14 failure sweep mismatch", validation.stderr)

            result["failure_sweep"][0]["measurement"] = expected_sweep_measurement
            sweep_path = run_dir / "artifacts/failure_sweep.csv"
            with sweep_path.open(newline="", encoding="utf-8") as stream:
                sweep_rows = list(csv.DictReader(stream))
            sweep_rows[0]["measurement"] = "0.123"
            with sweep_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=["parameter", "value", "metric", "measurement"],
                )
                writer.writeheader()
                writer.writerows(sweep_rows)
            result["provenance"]["artifacts_sha256"]["failure_sweep.csv"] = (
                hashlib.sha256(sweep_path.read_bytes()).hexdigest()
            )
            validation = validate()
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("Module 14 failure sweep mismatch", validation.stderr)


class FrontierLabContractTest(unittest.TestCase):
    def test_modules_12_through_15_emit_foundation_generation_dynamic_and_surflo_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            results: dict[str, dict] = {}
            for module_id in ("12", "13", "14", "15"):
                completed = subprocess.run(
                    [str(ROOT / "run.sh"), "run", "--module", module_id, "--profile", "smoke", "--run-id", "frontier"],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, f"module {module_id}: {completed.stderr}")
                run_dir = cache / "runs" / "frontier" / module_id
                results[module_id] = json.loads((run_dir / "result.json").read_text())
                self.assertTrue(any((run_dir / "artifacts").glob("*.svg")))

            foundation = results["12"]["metrics"]["geometry"]
            self.assertLess(
                foundation["similarity_aligned_point_rmse_m"],
                foundation["raw_point_rmse_m"],
            )
            self.assertEqual(foundation["hidden_surface_recall"], 0.0)

            generation = results["13"]["metrics"]["generative"]
            self.assertGreater(generation["shared_latent_coherence"], generation["independent_point_coherence"])
            self.assertGreater(generation["shared_latent_hypothesis_coverage"], 0.9)

            dynamics = results["14"]["metrics"]["geometry"]
            self.assertGreater(dynamics["moving_camera_object_post_occlusion_error_m"], dynamics["static_camera_post_occlusion_error_m"])

            surflo = results["15"]
            photoreal = REPO_ROOT / "experiments" / "photoreal-scenes" / "results.json"
            expected_hash = hashlib.sha256(photoreal.read_bytes()).hexdigest()
            self.assertEqual(surflo["source_results_sha256"], expected_hash)
            self.assertEqual(surflo["metrics"]["generative"]["hidden_hypothesis_support"], 0.0)
            self.assertEqual(surflo["observations"][0], "Tracked paired-scene outcome: unsupported for all four seeds.")

    def test_all_smoke_runs_every_module_and_builds_cross_era_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
            completed = subprocess.run(
                [str(ROOT / "run.sh"), "all", "--profile", "smoke", "--run-id", "all-smoke"],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            run_root = cache / "runs" / "all-smoke"
            self.assertEqual(len(list(run_root.glob("[0-9][0-9]/result.json"))), 15)
            report = (run_root / "report.md").read_text()
            self.assertIn("01 Image formation and observability", report)
            self.assertIn("15 Surflo as the current case study", report)
            self.assertIn("Metrics from different task families", report)


if __name__ == "__main__":
    unittest.main()
