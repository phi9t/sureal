import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence.source_snapshot import file_sha256
from studies import scientific_cohort


class ScientificCohortWorkflowTests(unittest.TestCase):
    def write_receipt(self, path, **extra):
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "checks": [{"exit_code": 0}],
            "candidate_hashes": {},
            "artifacts": {},
            **extra,
        }
        path.write_text(json.dumps(payload) + "\n")
        return path

    def test_point_and_camera_lifecycle_dispatches_under_study_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "autonomy"
            dataset = package / "dataset"
            dataset.mkdir(parents=True)
            manifest = {
                "components": ["lidar"],
                "scenes": {
                    "scene-a": {
                        "official_split": "training",
                        "research_splits": ["train"],
                    }
                },
            }
            (dataset / "scientific-acquisition.candidate.json").write_text(json.dumps(manifest))
            (dataset / "scientific-cohort.candidate.json").write_text(
                json.dumps({"excluded_engineering_segments": []})
            )
            cache = root / "cache"
            source_record = cache / "scientific-source-audit" / "training-lidar-scene-a.json"
            source_record.parent.mkdir(parents=True)
            source_record.write_text(json.dumps({"component": "lidar"}))
            rootfs = cache / "insula" / "rootfs-v2"
            rootfs.mkdir(parents=True)
            lock = {"rootfs_sha256": "r" * 64}
            rootfs.with_name(rootfs.name + ".lock.json").write_text(json.dumps(lock))
            working = cache / "scientific-processing"
            output = working / "queue"
            calls = []

            def fake_run(command, capture_output, text, cwd, **_kwargs):
                calls.append(command)
                stage = None
                for candidate in (
                    "point-preprocess",
                    "point-publication",
                    "point-replay",
                    "point-evict",
                    "sidecar-publication",
                    "sidecar-evict",
                    "camera-preprocess",
                    "camera-publication",
                    "camera-replay",
                    "camera-evict",
                ):
                    if any(candidate in str(part) for part in command):
                        stage = candidate
                        break
                scene_base = output / "scene-a"
                if command[:3] == ["python3", "-m", "dataset.scientific-preprocess"]:
                    stage = "point-preprocess"
                    processing = Path(command[command.index("--output") + 1])
                    (processing / "sidecars").mkdir(parents=True)
                    for component in scientific_cohort.POINT_COMPONENTS:
                        self.write_receipt(processing / "evidence" / component / "receipt.json")
                elif command[:3] == ["python3", "-m", "dataset.publish-scientific-scene"]:
                    stage = "point-publication"
                    self.write_receipt(
                        Path(command[4]) / "receipt.json",
                        archive_hdfs_uri="hdfs://fixture/points",
                    )
                elif command[:3] == ["python3", "-m", "dataset.verify-scientific-replay"]:
                    stage = "point-replay"
                    publication = Path(command[4])
                    self.write_receipt(
                        Path(command[5]) / "receipt.json",
                        checks=[{"exit_code": 0}, {"exit_code": 0}],
                        publication_receipt_sha256=file_sha256(publication / "receipt.json"),
                        validation={"kind": "points"},
                    )
                elif command[:3] == ["python3", "-m", "dataset.publish-scientific-sidecars"]:
                    stage = "sidecar-publication"
                    self.write_receipt(Path(command[4]) / "receipt.json")
                elif command[:3] == ["python3", "-m", "camera.scientific-camera-preprocess"]:
                    stage = "camera-preprocess"
                    camera = Path(command[command.index("--output") + 1])
                    for component in scientific_cohort.CAMERA_COMPONENTS:
                        self.write_receipt(camera / "evidence" / component / "receipt.json")
                elif command[:3] == ["python3", "-m", "camera.publish-scientific-camera"]:
                    stage = "camera-publication"
                    self.write_receipt(
                        Path(command[command.index("--output") + 1]) / "receipt.json",
                        archive_hdfs_uri="hdfs://fixture/camera",
                    )
                elif command[:3] == ["python3", "-m", "camera.verify-camera-replay"]:
                    stage = "camera-replay"
                    publication = Path(command[4])
                    self.write_receipt(
                        Path(command[5]) / "receipt.json",
                        checks=[{"exit_code": 0}, {"exit_code": 0}],
                        publication_receipt_sha256=file_sha256(publication / "receipt.json"),
                        validation={"kind": "camera"},
                    )
                elif any("dataset.verified_eviction" in str(part) for part in command):
                    stage = "point-evict"
                    (scene_base / "points" / "point-eviction.json").write_text(
                        json.dumps({"status": "point eviction completed", "files": []})
                    )
                elif any("dataset.sidecar_eviction" in str(part) for part in command):
                    stage = "sidecar-evict"
                    (scene_base / "points" / "sidecar-eviction.json").write_text(
                        json.dumps({"status": "sidecar eviction completed", "files": []})
                    )
                elif any("camera.camera_eviction" in str(part) for part in command):
                    stage = "camera-evict"
                    (scene_base / "camera" / "camera-eviction.json").write_text(
                        json.dumps({"status": "camera eviction completed", "files": []})
                    )
                if stage is None:
                    raise AssertionError(command)
                return subprocess.CompletedProcess(command, 0, stage + "\n", "")

            def fake_launch_plan(_root, _experiment, _source, output_directory, command):
                return ["bwrap", "--bind", str(output_directory), "/outputs", "--", *command]

            with (
                patch.object(scientific_cohort, "HERE", package),
                patch.object(scientific_cohort, "CACHE", cache),
                patch.object(scientific_cohort, "WORKING", working),
                patch.object(scientific_cohort, "verify_rootfs"),
                patch.object(scientific_cohort, "admit_scene"),
                patch.object(scientific_cohort, "launch_plan", side_effect=fake_launch_plan),
                patch.object(scientific_cohort.subprocess, "run", side_effect=fake_run),
                patch.object(sys, "argv", [
                    "scientific_cohort.py",
                    "--scene",
                    "scene-a",
                    "--output",
                    str(output),
                ]),
            ):
                scientific_cohort.main()

            receipt = json.loads((output / "scene-a" / "receipt.json").read_text())
            self.assertEqual(receipt["scene"], "scene-a")
            self.assertEqual(receipt["point_validation"], {"kind": "points"})
            self.assertEqual(receipt["camera_validation"], {"kind": "camera"})
            flattened = [" ".join(map(str, call)) for call in calls]
            self.assertTrue(any("camera.scientific-camera-preprocess" in call for call in flattened))
            self.assertTrue(any("camera.publish-scientific-camera" in call for call in flattened))
            self.assertTrue(any("camera.verify-camera-replay" in call for call in flattened))
            self.assertTrue(any("camera.camera_eviction" in call for call in flattened))


if __name__ == "__main__":
    unittest.main()
