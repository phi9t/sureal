import fcntl
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import file_sha256
from retention.sustained_controller_lock import acquire_experiment_lock


sha = file_sha256


class PublishSustainedCheckpointTests(unittest.TestCase):
    def fixture(self, root):
        work = root / "scientific-processing"
        case = work / "balanced16-sustained-baseline-run1"
        payload = case / "update-1000"
        heads = payload / "heads"
        heads.mkdir(parents=True)
        manifest = root / "manifest.json"
        manifest.write_text("{}\n")
        (payload / "checkpoint.pt").write_text("checkpoint\n")
        (payload / "live.log").write_text("producer\n")
        head_hashes = {}
        for index in range(16):
            head = heads / f"heads-{index:02d}.npz"
            head.write_text(f"head {index}\n")
            head_hashes[head.name] = sha(head)
        report = {
            "manifest_sha256": sha(manifest),
            "updates": 1000,
            "requested_updates": 1000,
            "stop_reason": "sample",
            "resource_gate_passed": True,
            "checkpoint_sha256": sha(payload / "checkpoint.pt"),
            "head_hashes": head_hashes,
        }
        (payload / "check.json").write_text(json.dumps(report, sort_keys=True))
        refs = {}
        for stage in ["train", "audit", "literal-loss", "export", "proposals", "score", "metrics-audit"]:
            if stage == "train":
                artifacts = {str(path): sha(path) for path in sorted(payload.rglob("*")) if path.is_file()}
            else:
                artifact = root / f"{stage}.log"
                artifact.write_text(stage + "\n")
                artifacts = {str(artifact): sha(artifact)}
            receipt = root / f"{stage}.json"
            receipt.write_text(
                json.dumps(
                    {
                        "stage": f"{stage}-1000",
                        "exit_code": 0,
                        "manifest_sha256": sha(manifest),
                        "artifacts": artifacts,
                    },
                    sort_keys=True,
                )
            )
            refs[stage] = {"path": str(receipt), "sha256": sha(receipt)}
        final = root / "final.json"
        final.write_text(
            json.dumps(
                {
                    "output_directory": str(payload),
                    "manifest_path": str(manifest),
                    "manifest_sha256": sha(manifest),
                    "step": 1000,
                    "stage_receipts": refs,
                },
                sort_keys=True,
            )
        )
        return work, payload, final

    def test_subprocess_entrypoint_without_release_keeps_payload_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work, payload, final = self.fixture(root)
            payload_files = sorted(path for path in payload.rglob("*") if path.is_file())
            self.assertTrue(payload_files)
            cache = root / "cache"
            (cache / "insula").mkdir(parents=True)
            blob_root = root / "blob-store"
            lock_path = root / "architecture-experiments.lock"
            command = [
                sys.executable,
                "-m",
                "retention.publish_sustained_checkpoint",
                "--receipt",
                str(final),
                "--receipt-sha256",
                sha(final),
                "--lock-path",
                str(lock_path),
                "--lock-fd",
                "{fd}",
                "--cache-root",
                str(cache),
                "--work-root",
                str(work),
                "--store-descriptor",
                json.dumps({"kind": "local", "root": str(blob_root)}),
                "--tool-digest",
                json.dumps({"waystone-cli": "a" * 64}),
            ]
            env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
            with acquire_experiment_lock(lock_path) as held:
                command[command.index("{fd}")] = str(held.fileno())
                result = subprocess.run(
                    command,
                    cwd=Path(__file__).resolve().parents[1],
                    env=env,
                    text=True,
                    capture_output=True,
                    pass_fds=(held.fileno(),),
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                with lock_path.open("a") as other:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

            publications = list((cache / "insula").glob("hdfs-retention-*"))
            self.assertEqual(len(publications), 1)
            publication_path = publications[0] / "verified-publication.json"
            release_path = publications[0] / "release-completed.json"
            publication = json.loads(publication_path.read_text())
            self.assertFalse(release_path.exists())
            self.assertEqual(publication["store_descriptor"], {"kind": "local", "root": str(blob_root)})
            self.assertEqual(publication["blobs"]["manifest"]["key"], "checkpoints/perception-sustained-checkpoints/balanced16-sustained-baseline-run1-step1000/checkpoint/manifest.json")
            self.assertTrue(all(path.is_file() for path in payload_files))

    def test_subprocess_entrypoint_uses_lock_fd_and_local_blob_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work, payload, final = self.fixture(root)
            cache = root / "cache"
            (cache / "insula").mkdir(parents=True)
            blob_root = root / "blob-store"
            lock_path = root / "architecture-experiments.lock"
            command = [
                sys.executable,
                "-m",
                "retention.publish_sustained_checkpoint",
                "--receipt",
                str(final),
                "--receipt-sha256",
                sha(final),
                "--release",
                "--lock-path",
                str(lock_path),
                "--lock-fd",
                "{fd}",
                "--cache-root",
                str(cache),
                "--work-root",
                str(work),
                "--store-descriptor",
                json.dumps({"kind": "local", "root": str(blob_root)}),
                "--tool-digest",
                json.dumps({"waystone-cli": "a" * 64}),
            ]
            env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
            with acquire_experiment_lock(lock_path) as held:
                command[command.index("{fd}")] = str(held.fileno())
                result = subprocess.run(
                    command,
                    cwd=Path(__file__).resolve().parents[1],
                    env=env,
                    text=True,
                    capture_output=True,
                    pass_fds=(held.fileno(),),
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                with lock_path.open("a") as other:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

            publications = list((cache / "insula").glob("hdfs-retention-*"))
            self.assertEqual(len(publications), 1)
            publication_path = publications[0] / "verified-publication.json"
            release_path = publications[0] / "release-completed.json"
            publication = json.loads(publication_path.read_text())
            release = json.loads(release_path.read_text())
            self.assertEqual(publication["store_descriptor"], {"kind": "local", "root": str(blob_root)})
            self.assertEqual(publication["blobs"]["manifest"]["key"], "checkpoints/perception-sustained-checkpoints/balanced16-sustained-baseline-run1-step1000/checkpoint/manifest.json")
            self.assertEqual(release["publication_receipt_sha256"], sha(publication_path))
            self.assertEqual(len(release["released"]), 19)
            self.assertFalse(any(path.is_file() for path in payload.rglob("*")))


if __name__ == "__main__":
    unittest.main()
