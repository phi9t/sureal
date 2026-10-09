import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence.source_snapshot import file_sha256
from insula.launch_plan import (
    BAZEL_LINUX_X86_64_SHA256,
    BAZEL_VERSION,
    load_runtime_lock,
    plan_data,
)
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME, default_lock
from studies import scientific_cohort


AUTONOMY = Path(__file__).resolve().parents[1]


class ScientificCohortWorkflowTests(unittest.TestCase):
    def write_rootfs(self, rootfs):
        rootfs.mkdir(parents=True)
        (rootfs / "bin").mkdir()
        (rootfs / "bin/python").write_text("#!/bin/sh\n")
        (rootfs / "bin/python").chmod(0o755)
        (rootfs / "etc").mkdir()
        (rootfs / "etc/issue").write_text("scientific cohort fixture\n")

    def write_cpu_runtime_lock(self, rootfs):
        payload = {
            "schema_version": 1,
            "rootfs_sha256": rootfs_identity(rootfs),
            "dockerfile_sha256": file_sha256(AUTONOMY / "insula/Dockerfile"),
            "requirements_sha256": file_sha256(AUTONOMY / "requirements-tracer.lock"),
            "test_tools_requirements_sha256": file_sha256(
                AUTONOMY / "insula/cpu-test-tools-requirements.lock"
            ),
            "bazel_version": BAZEL_VERSION,
            "bazel_linux_x86_64_sha256": BAZEL_LINUX_X86_64_SHA256,
        }
        default_lock(rootfs).write_text(json.dumps(payload, indent=2) + "\n")
        return payload

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

    def test_eviction_plan_uses_checked_runtime_and_declared_mount_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            runtime_rootfs = cache / "insula" / CURRENT_CPU_ROOTFS_NAME
            self.write_rootfs(runtime_rootfs)
            self.write_cpu_runtime_lock(runtime_rootfs)
            runtime = load_runtime_lock(runtime_rootfs, default_lock(runtime_rootfs))
            processing = root / "processing"
            publication = root / "publication"
            replay = root / "replay"
            for path in (processing, publication, replay):
                path.mkdir()

            plan = scientific_cohort.build_eviction_plan(
                runtime,
                processing=processing,
                publication=publication,
                replay=replay,
                command=["python", "-c", "print('evict')"],
            )
            data = plan_data(plan)
            mounts = {mount["role"]: mount for mount in data["mounts"]}

            self.assertEqual(data["runtime"]["form"], "recipe-digest")
            self.assertEqual(mounts["code"]["host_path"], str(scientific_cohort.HERE.resolve()))
            self.assertEqual(mounts["output"]["host_path"], str(processing.resolve()))
            self.assertEqual(mounts["input:/opt"]["mode"], "writable")
            self.assertEqual(mounts["input:/opt"]["host_path"], str(publication.resolve()))
            self.assertEqual(mounts["input:/srv"]["mode"], "read_only")
            self.assertEqual(mounts["input:/srv"]["host_path"], str(replay.resolve()))
            self.assertNotIn("source", mounts)

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
            runtime_rootfs = cache / "insula" / CURRENT_CPU_ROOTFS_NAME
            self.write_rootfs(runtime_rootfs)
            rootfs = cache / "insula" / "rootfs-v2"
            rootfs.mkdir(parents=True)
            lock = {"rootfs_sha256": rootfs_identity(rootfs)}
            rootfs.with_name(rootfs.name + ".lock.json").write_text(json.dumps(lock))
            self.write_cpu_runtime_lock(runtime_rootfs)
            working = cache / "scientific-processing"
            output = working / "queue"
            calls = []

            def fake_run(command, capture_output, text, cwd, **_kwargs):
                calls.append(command)
                inner = command[command.index("--") + 1 :] if command and command[0] == "bwrap" else command
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
                    if any(candidate in str(part) for part in inner):
                        stage = candidate
                        break
                scene_base = output / "scene-a"
                if inner[:3] == ["python3", "-m", "dataset.scientific-preprocess"]:
                    stage = "point-preprocess"
                    processing = Path(inner[inner.index("--output") + 1])
                    (processing / "sidecars").mkdir(parents=True)
                    for component in scientific_cohort.POINT_COMPONENTS:
                        self.write_receipt(processing / "evidence" / component / "receipt.json")
                elif inner[:3] == ["python3", "-m", "dataset.publish-scientific-scene"]:
                    stage = "point-publication"
                    self.write_receipt(
                        Path(inner[4]) / "receipt.json",
                        archive_hdfs_uri="hdfs://fixture/points",
                    )
                elif inner[:3] == ["python3", "-m", "dataset.verify-scientific-replay"]:
                    stage = "point-replay"
                    publication = Path(inner[4])
                    self.write_receipt(
                        Path(inner[5]) / "receipt.json",
                        checks=[{"exit_code": 0}, {"exit_code": 0}],
                        publication_receipt_sha256=file_sha256(publication / "receipt.json"),
                        validation={"kind": "points"},
                    )
                elif inner[:3] == ["python3", "-m", "dataset.publish-scientific-sidecars"]:
                    stage = "sidecar-publication"
                    self.write_receipt(Path(inner[4]) / "receipt.json")
                elif inner[:3] == ["python3", "-m", "camera.scientific-camera-preprocess"]:
                    stage = "camera-preprocess"
                    camera = Path(inner[inner.index("--output") + 1])
                    for component in scientific_cohort.CAMERA_COMPONENTS:
                        self.write_receipt(camera / "evidence" / component / "receipt.json")
                elif inner[:3] == ["python3", "-m", "camera.publish-scientific-camera"]:
                    stage = "camera-publication"
                    self.write_receipt(
                        Path(inner[inner.index("--output") + 1]) / "receipt.json",
                        archive_hdfs_uri="hdfs://fixture/camera",
                    )
                elif inner[:3] == ["python3", "-m", "camera.verify-camera-replay"]:
                    stage = "camera-replay"
                    publication = Path(inner[4])
                    self.write_receipt(
                        Path(inner[5]) / "receipt.json",
                        checks=[{"exit_code": 0}, {"exit_code": 0}],
                        publication_receipt_sha256=file_sha256(publication / "receipt.json"),
                        validation={"kind": "camera"},
                    )
                elif any("dataset.verified_eviction" in str(part) for part in inner):
                    stage = "point-evict"
                    (scene_base / "points" / "point-eviction.json").write_text(
                        json.dumps({"status": "point eviction completed", "files": []})
                    )
                elif any("dataset.sidecar_eviction" in str(part) for part in inner):
                    stage = "sidecar-evict"
                    (scene_base / "points" / "sidecar-eviction.json").write_text(
                        json.dumps({"status": "sidecar eviction completed", "files": []})
                    )
                elif any("camera.camera_eviction" in str(part) for part in inner):
                    stage = "camera-evict"
                    (scene_base / "camera" / "camera-eviction.json").write_text(
                        json.dumps({"status": "camera eviction completed", "files": []})
                    )
                if stage is None:
                    raise AssertionError(command)
                return subprocess.CompletedProcess(command, 0, stage + "\n", "")

            with (
                patch.object(scientific_cohort, "HERE", package),
                patch.object(scientific_cohort, "CACHE", cache),
                patch.object(scientific_cohort, "WORKING", working),
                patch.object(scientific_cohort, "admit_scene"),
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
