from __future__ import annotations

import copy
import io
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent


def run_cli(*args: str, cache: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["SURFLO_PATHWAY_CACHE_ROOT"] = str(cache)
    return subprocess.run(
        [str(ROOT / "run.sh"), *args],
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def link_tum_asset(cache: Path) -> None:
    source = Path.home() / ".cache" / "surflo" / "3d-pathway" / "assets"
    destination = cache / "assets"
    destination.mkdir(parents=True)
    os.link(source / "tum-rgbd.archive", destination / "tum-rgbd.archive")
    shutil.copytree(source / "tum-rgbd", destination / "tum-rgbd", copy_function=os.link)
    shutil.copy2(source / "tum-rgbd.extraction.json", destination / "tum-rgbd.extraction.json")


def real_test_temporary_directory() -> tempfile.TemporaryDirectory[str]:
    root = Path.home() / ".cache" / "surflo" / "3d-pathway" / "test-tmp"
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)


class OrbSlamReferenceContractTest(unittest.TestCase):
    def test_tum_asset_lock_uses_the_verified_archive_and_safe_extraction(self) -> None:
        registry = json.loads((ROOT / "assets.lock.json").read_text())
        asset = next(item for item in registry["assets"] if item["id"] == "tum-rgbd")
        self.assertEqual(asset["sha256"], "a0236d97b8c30cd93b653656d2b6c293ff7c982a4130ef2a1a8beecdb124ef98")
        self.assertEqual(asset["digest_status"], "verified_2026-09-26")
        self.assertEqual(
            asset["extraction"],
            {"mode": "tar", "root": "rgbd_dataset_freiburg1_xyz"},
        )

    def test_orb_slam_insula_is_source_pinned_and_registered(self) -> None:
        locks = json.loads((ROOT / "insulas/locks.json").read_text())
        lock = locks["insulas"]["orb-slam"]
        self.assertEqual(lock["base_image"], "ubuntu:22.04")
        self.assertEqual(lock["base_image_digest"], "b8b6ee6aa931ecd9d0d952abc34dc0e5f7c6a30c6bb71b079fe399fde0329c02")
        self.assertEqual(lock["orb_slam3_source_commit"], "4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4")
        self.assertEqual(lock["pangolin_source_commit"], "dd801d244db3a8e27b7fe8020cd751404aa818fd")
        dockerfile = (ROOT / "insulas/orb-slam/Dockerfile").read_text()
        self.assertIn("ubuntu:22.04@sha256:b8b6ee6aa931ecd9d0d952abc34dc0e5f7c6a30c6bb71b079fe399fde0329c02", dockerfile)
        self.assertIn(lock["orb_slam3_source_commit"], dockerfile)
        self.assertIn(lock["pangolin_source_commit"], dockerfile)
        build = (ROOT / "insulas/build.sh").read_text()
        self.assertIn("surflo-pathway-orb-slam:1", build)

    def test_reference_plan_is_explicitly_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            completed = run_cli(
                "--emit-plan",
                "reference",
                "--adapter",
                "orb-slam",
                "--profile",
                "smoke",
                "--run-id",
                "slam-plan",
                cache=Path(temporary),
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "adapter": "orb-slam",
                "command": "reference",
                "network_mode": "offline",
                "profile": "smoke",
                "run_id": "slam-plan",
                "schema_version": 1,
            },
        )

    def test_tum_trajectory_metrics_recover_known_rigid_frame_change(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from slam_reference_runner import GROUND_TRUTH_MAX_DELTA_SECONDS, evaluate_trajectory

        self.assertEqual(GROUND_TRUTH_MAX_DELTA_SECONDS, 0.05)

        truth = [
            (0.0, np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0])),
            (1.0, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0])),
            (2.0, np.array([2.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0])),
            (3.0, np.array([3.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0])),
        ]
        rotation = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
        offset = np.array([4.0, -2.0, 0.5])
        estimated = [
            (timestamp + 0.002, rotation @ position + offset, np.array([0.0, 0.0, 2**-0.5, 2**-0.5]))
            for timestamp, position, _ in truth
        ]

        metrics, transform = evaluate_trajectory(estimated, truth, max_delta_seconds=0.01)

        self.assertEqual(metrics["trajectory_matches"], 4)
        self.assertLess(metrics["ate_rmse_m"], 1e-12)
        self.assertLess(metrics["rpe_translation_rmse_m"], 1e-12)
        self.assertLess(metrics["rpe_rotation_rmse_deg"], 1e-8)
        self.assertTrue(np.allclose(transform["rotation"], rotation.T, atol=1e-12))
        self.assertTrue(np.allclose(transform["translation"], -rotation.T @ offset, atol=1e-12))

    def test_tum_parser_rejects_duplicate_or_non_unit_records(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from slam_reference_runner import parse_tum_trajectory

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trajectory.txt"
            path.write_text(
                "0.0 0 0 0 0 0 0 1\n"
                "0.0 1 0 0 0 0 0 1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                parse_tum_trajectory(path)
            path.write_text("0.0 0 0 0 0 0 0 2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unit quaternion"):
                parse_tum_trajectory(path)

    def test_rpe_translation_is_measured_in_the_origin_camera_frame(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from slam_reference_runner import evaluate_trajectory

        truth = [
            (float(index), np.array([float(index), 0.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0]))
            for index in range(4)
        ]
        wrong_orientation = np.array([0.0, 0.0, 2**-0.5, 2**-0.5])
        estimated = [(timestamp, position.copy(), wrong_orientation) for timestamp, position, _ in truth]
        metrics, _ = evaluate_trajectory(estimated, truth)
        self.assertAlmostEqual(metrics["ate_rmse_m"], 0.0)
        self.assertAlmostEqual(metrics["rpe_translation_rmse_m"], 2**0.5)

    def test_endpoint_drift_is_first_pose_relative_not_final_aligned_residual(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from slam_reference_runner import evaluate_trajectory

        identity = np.array([0.0, 0.0, 0.0, 1.0])
        truth = [
            (float(index), np.array([float(index), 0.0, 0.0]), identity)
            for index in range(4)
        ]
        estimated = [
            (0.0, np.array([0.0, 0.0, 0.0]), identity),
            (1.0, np.array([1.0, 0.0, 0.0]), identity),
            (2.0, np.array([2.0, 0.0, 0.0]), identity),
            (3.0, np.array([4.0, 0.0, 0.0]), identity),
        ]

        metrics, _ = evaluate_trajectory(estimated, truth)

        self.assertNotIn("end_drift_m", metrics)
        self.assertAlmostEqual(metrics["endpoint_drift_m"], 1.0)
        self.assertAlmostEqual(metrics["endpoint_rotation_drift_deg"], 0.0)

    def test_cpp_runner_exports_final_points_and_evaluable_failure_trajectories(self) -> None:
        source = (ROOT / "insulas/orb-slam/surflo_rgbd.cc").read_text(encoding="utf-8")
        self.assertIn("std::map<unsigned long, ORB_SLAM3::MapPoint*> landmarks", source)
        self.assertLess(source.index("slam.Shutdown();"), source.rindex("point->GetWorldPos()"))
        self.assertIn("point->GetReplaced()", source)
        self.assertIn("same_map_relocalized", source)
        self.assertIn("CameraTrajectory-dynamic-object.txt", source)

    def test_safe_tum_extraction_is_atomic_and_rejects_traversal(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from fetch import extract_locked_asset

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "tum-rgbd.archive"
            with tarfile.open(archive, "w:gz") as bundle:
                payload = b"0.0 rgb/0.png\n"
                member = tarfile.TarInfo("rgbd_dataset_freiburg1_xyz/rgb.txt")
                member.size = len(payload)
                bundle.addfile(member, io.BytesIO(payload))
            asset = {
                "id": "tum-rgbd",
                "archive_format": "tar.gz",
                "extraction": {"mode": "tar", "root": "rgbd_dataset_freiburg1_xyz"},
            }
            extracted = extract_locked_asset(asset, archive, root)
            self.assertEqual((extracted / "rgb.txt").read_bytes(), payload)
            manifest = json.loads((root / "tum-rgbd.extraction.json").read_text())
            self.assertEqual(manifest["file_count"], 1)
            self.assertEqual(manifest["root"], "rgbd_dataset_freiburg1_xyz")

            hostile = root / "hostile.archive"
            with tarfile.open(hostile, "w:gz") as bundle:
                payload = b"escape"
                member = tarfile.TarInfo("../escape")
                member.size = len(payload)
                bundle.addfile(member, io.BytesIO(payload))
            with self.assertRaisesRegex(ValueError, "unsafe archive member"):
                extract_locked_asset(asset, hostile, root / "other")
            self.assertFalse((root / "escape").exists())

    def test_point_cloud_metrics_keep_accuracy_and_completeness_directional(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        from slam_reference_runner import evaluate_point_clouds

        estimate = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        truth = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [4.0, 0.0, 0.0]])
        metrics = evaluate_point_clouds(estimate, truth, threshold_m=0.1)
        self.assertEqual(metrics["map_points"], 2)
        self.assertAlmostEqual(metrics["map_accuracy_mean_m"], 0.0)
        self.assertAlmostEqual(metrics["map_completeness_mean_m"], 1.0)
        self.assertAlmostEqual(metrics["map_precision_10cm"], 1.0)
        self.assertAlmostEqual(metrics["map_recall_10cm"], 2.0 / 3.0)
        self.assertAlmostEqual(metrics["map_fscore_10cm"], 0.8)

    def test_reference_run_is_offline_hash_bound_and_atomically_promoted(self) -> None:
        sys.path.insert(0, str(ROOT / "pipeline"))
        import slam_reference_runner as runner

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            dataset = root / "rgbd_dataset_freiburg1_xyz"
            (dataset / "rgb").mkdir(parents=True)
            (dataset / "depth").mkdir()
            records = []
            for index in range(300):
                timestamp = float(index)
                (dataset / f"rgb/{index}.png").write_bytes(b"rgb")
                (dataset / f"depth/{index}.png").write_bytes(b"depth")
                records.append(f"{timestamp:.1f} rgb/{index}.png")
            (dataset / "rgb.txt").write_text("\n".join(records) + "\n", encoding="utf-8")
            (dataset / "depth.txt").write_text(
                "\n".join(f"{float(index):.1f} depth/{index}.png" for index in range(300)) + "\n",
                encoding="utf-8",
            )
            (dataset / "groundtruth.txt").write_text(
                "\n".join(f"{float(index):.1f} {index * 0.1:.6f} 0 0 0 0 0 1" for index in range(300)) + "\n",
                encoding="utf-8",
            )
            engine = root / "fake-engine"
            engine.write_text(
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    if [[ "${{1:-}}" == image && "${{2:-}}" == inspect ]]; then
                      printf 'sha256:fixture-orb-slam-image\\n'
                      exit 0
                    fi
                    [[ "${{1:-}}" == run ]]
                    [[ " $* " == *" --network none "* ]]
                    [[ " $* " == *" --pull=never "* ]]
                    [[ " $* " == *" --user "* ]]
                    [[ " $* " == *":/dataset:ro "* ]]
                    [[ " $* " == *" sha256:fixture-orb-slam-image "* ]]
                    work=''
                    previous=''
                    for argument in "$@"; do
                      if [[ "$previous" == -v && "$argument" == *:/work ]]; then work="${{argument%:/work}}"; fi
                      previous="$argument"
                    done
                    mkdir -p "$work/output"
                    printf '{runner.PINNED_ORB_SLAM3_COMMIT}\\n' > "$work/output/source-commit.txt"
                    cp "$work/config/insula-manifest.expected" "$work/output/insula-manifest.txt"
                    cp "$work/config/groundtruth-prefix.txt" "$work/output/CameraTrajectory.txt"
                    cp "$work/config/groundtruth-prefix.txt" "$work/output/KeyFrameTrajectory.txt"
                    sed -n '1,180p' "$work/config/groundtruth-prefix.txt" > "$work/output/CameraTrajectory-occlusion.txt"
                    cp "$work/config/groundtruth-prefix.txt" "$work/output/CameraTrajectory-dynamic-object.txt"
                    {{
                      printf 'timestamp,state,tracked_map_points,runtime_seconds\\n'
                      for i in $(seq 0 299); do printf '%s.0,2,1200,0.01\\n' "$i"; done
                    }} > "$work/output/tracking.csv"
                    {{
                      printf 'ply\\nformat ascii 1.0\\nelement vertex 1200\\nproperty float x\\nproperty float y\\nproperty float z\\nend_header\\n'
                      for i in $(seq 0 1199); do printf '0 0 %s\\n' "$i"; done
                    }} > "$work/output/map.ply"
                    cp "$work/output/map.ply" "$work/output/ground-truth-map.ply"
                    printf '{{"variants":[{{"id":"occlusion","tracking_coverage":0.6,"lost_during_perturbation":true,"tracking_resumed":true,"same_map_relocalized":true,"map_id_before_perturbation":0,"map_id_after_resume":0}},{{"id":"dynamic-object","tracking_coverage":1.0,"lost_during_perturbation":false,"tracking_resumed":false,"same_map_relocalized":false,"map_id_before_perturbation":1,"map_id_after_resume":-1}}]}}\\n' > "$work/output/failure-sweep.json"
                    printf 'Maximum resident set size (kbytes): 12345\\n' > "$work/output/resource-summary.txt"
                    printf 'fixture complete\\n'
                    """
                ),
                encoding="utf-8",
            )
            engine.chmod(0o755)
            asset_manifest = {
                "schema_version": 1,
                "archive_sha256": "a0236d97b8c30cd93b653656d2b6c293ff7c982a4130ef2a1a8beecdb124ef98",
                "tree_sha256": "b" * 64,
                "file_count": 13,
                "root": dataset.name,
                "files": [],
            }
            with (
                mock.patch.dict(os.environ, {"SURFLO_PATHWAY_CONTAINER_ENGINE": str(engine)}),
                mock.patch.object(runner, "_verify_tum_asset", return_value=(dataset, asset_manifest)),
            ):
                run_dir = runner.run_slam_reference(cache, "smoke", "fixture-slam")

            self.assertEqual(run_dir, cache / "reference-runs/fixture-slam/orb-slam")
            result = json.loads((run_dir / "result.json").read_text())
            original_result = copy.deepcopy(result)
            self.assertEqual(result["adapter"], "orb-slam")
            self.assertEqual(result["module_ids"], ["07"])
            self.assertEqual(result["tool"]["source_commit"], runner.PINNED_ORB_SLAM3_COMMIT)
            self.assertEqual(
                result["provenance"]["asset_archive_sha256"],
                "a0236d97b8c30cd93b653656d2b6c293ff7c982a4130ef2a1a8beecdb124ef98",
            )
            self.assertEqual(result["metrics"]["tracked_frames"], 300)
            self.assertEqual(result["metrics"]["keyframes"], 300)
            self.assertAlmostEqual(result["metrics"]["tracking_coverage"], 1.0)
            self.assertLess(result["metrics"]["ate_rmse_m"], 1e-12)
            self.assertEqual(result["resources"]["peak_cpu_memory_bytes"], 12345 * 1024)
            runner.validate_slam_reference_result(run_dir)
            self.assertFalse((cache / "reference-staging").is_symlink())

            result["resources"]["runtime_seconds"] += 1.0
            (run_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "resource summary mismatch"):
                runner.validate_slam_reference_result(run_dir)
            result = copy.deepcopy(original_result)
            (run_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

            result["tool"]["source_commit"] = "c" * 40
            (run_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "tool source commit mismatch"):
                runner.validate_slam_reference_result(run_dir)
            result["tool"]["source_commit"] = runner.PINNED_ORB_SLAM3_COMMIT

            contract_path = run_dir / "input/dataset-contract.json"
            contract = json.loads(contract_path.read_text())
            contract["frame_count"] += 1
            contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
            result["provenance"]["artifacts_sha256"]["input/dataset-contract.json"] = hashlib.sha256(
                contract_path.read_bytes()
            ).hexdigest()
            (run_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "dataset contract binding mismatch"):
                runner.validate_slam_reference_result(run_dir)

    def test_real_orb_slam_smoke_tracks_tum_rgbd_and_exports_a_map(self) -> None:
        require_real = os.environ.get("SURFLO_REQUIRE_ORB_SLAM_REFERENCE") == "1"
        docker = shutil.which("docker")
        asset = Path.home() / ".cache/surflo/3d-pathway/assets/tum-rgbd.archive"
        if docker is None or not asset.is_file():
            if require_real:
                self.fail("real ORB-SLAM gate requires Docker and the fetched TUM RGB-D asset")
            self.skipTest("Docker or the fetched TUM RGB-D asset is unavailable")
        image = subprocess.run(
            [docker, "image", "inspect", "surflo-pathway-orb-slam:1"],
            text=True,
            capture_output=True,
            check=False,
        )
        if image.returncode != 0:
            if require_real:
                self.fail("SURFLO_REQUIRE_ORB_SLAM_REFERENCE=1 but the ORB-SLAM Insula is not built")
            self.skipTest("ORB-SLAM Insula is not built")
        with real_test_temporary_directory() as temporary:
            cache = Path(temporary) / "cache"
            link_tum_asset(cache)
            completed = run_cli(
                "reference", "--adapter", "orb-slam", "--profile", "smoke", "--run-id", "real-orb-slam",
                cache=cache,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads((cache / "reference-runs/real-orb-slam/orb-slam/result.json").read_text())
            self.assertEqual(result["metrics"]["input_frames"], 300)
            self.assertGreaterEqual(result["metrics"]["tracking_coverage"], 0.70)
            self.assertLessEqual(result["metrics"]["ate_rmse_m"], 0.15)
            self.assertGreaterEqual(result["metrics"]["map_points"], 50)
            self.assertGreaterEqual(result["metrics"]["map_fscore_10cm"], 0.10)

    def test_real_orb_slam_full_profile(self) -> None:
        if os.environ.get("SURFLO_REQUIRE_ORB_SLAM_FULL") != "1":
            self.skipTest("set SURFLO_REQUIRE_ORB_SLAM_FULL=1 for the full-profile gate")
        docker = shutil.which("docker")
        asset = Path.home() / ".cache/surflo/3d-pathway/assets/tum-rgbd.archive"
        if docker is None or not asset.is_file():
            self.fail("real ORB-SLAM full gate requires Docker and the fetched TUM RGB-D asset")
        with real_test_temporary_directory() as temporary:
            cache = Path(temporary) / "cache"
            link_tum_asset(cache)
            completed = run_cli(
                "reference", "--adapter", "orb-slam", "--profile", "full", "--run-id", "real-orb-slam-full",
                cache=cache,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads((cache / "reference-runs/real-orb-slam-full/orb-slam/result.json").read_text())
            self.assertEqual(result["metrics"]["input_frames"], 798)
            self.assertGreaterEqual(result["metrics"]["tracking_coverage"], 0.80)
            self.assertLessEqual(result["metrics"]["ate_rmse_m"], 0.10)
            self.assertGreaterEqual(result["metrics"]["map_points"], 200)
            self.assertGreaterEqual(result["metrics"]["map_fscore_10cm"], 0.15)


if __name__ == "__main__":
    unittest.main()
