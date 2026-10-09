import json
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence.source_snapshot import file_sha256
from insula.launch_plan import RuntimeLockError, plan_data
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import current_metrics_rootfs

from evaluation.launches import build_evaluation_plan, load_current_metrics_runtime, plan_receipt


AUTONOMY = Path(__file__).resolve().parents[1]


def write_rootfs(root: Path):
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/python").write_text("#!/bin/sh\n")
    (root / "bin/python").chmod(0o755)
    (root / "etc").mkdir()
    (root / "etc/issue").write_text("fixture metrics rootfs\n")


def write_metrics_lock(path: Path, rootfs: Path):
    lock = {
        "schema_version": 1,
        "rootfs_sha256": rootfs_identity(rootfs),
        "image_id": "sha256:" + "1" * 64,
        "recipe_hashes": {
            "Dockerfile": file_sha256(AUTONOMY / "evaluation/Dockerfile"),
            "CMakeLists.txt": file_sha256(AUTONOMY / "evaluation/CMakeLists.txt"),
        },
    }
    path.write_text(json.dumps(lock, indent=2) + "\n")
    return lock


class EvaluationLaunchTests(unittest.TestCase):
    def test_missing_metrics_lock_is_not_materialized_by_verifier(self):
        script = AUTONOMY / "evaluation/verify-native-metrics.py"
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            out = home / "out"
            cache = home / ".cache/waystone/waymo-perception"
            root = current_metrics_rootfs(cache)
            with patch.dict(os.environ, {"HOME": str(home)}):
                module = runpy.run_path(str(script))
            with patch.object(sys, "argv", [str(script), str(out)]), patch(
                "subprocess.check_output",
                side_effect=AssertionError("missing metrics lock was materialized"),
            ):
                with self.assertRaises(RuntimeLockError):
                    module["main"]()

            self.assertFalse(root.exists())
            self.assertFalse(Path(str(root) + ".lock.json").exists())

    def test_metrics_verifier_plan_is_checked_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            rootfs = current_metrics_rootfs(cache)
            write_rootfs(rootfs)
            write_metrics_lock(Path(str(rootfs) + ".lock.json"), rootfs)
            code = cache / "code"
            source = cache / "source"
            output = cache / "output"
            for path in (code, source, output):
                path.mkdir()

            runtime = load_current_metrics_runtime(cache)
            plan = build_evaluation_plan(
                runtime,
                code=code,
                source=source,
                output=output,
                command=["/metrics-build/compute_detection_metrics", "/source/p.bin", "/source/g.bin"],
            )
            data = plan_data(plan)

            self.assertEqual(data["runtime"]["form"], "image")
            self.assertEqual(data["command"], ["/metrics-build/compute_detection_metrics", "/source/p.bin", "/source/g.bin"])
            self.assertIn(["--setenv", "PYTHONPATH", "/experiment"], data["environment"])
            self.assertEqual(
                {
                    mount["role"]: (mount["inside_path"], mount["mode"])
                    for mount in data["mounts"]
                    if mount["role"] in {"code", "source", "output"}
                },
                {
                    "code": ("/experiment", "read_only"),
                    "source": ("/source", "read_only"),
                    "output": ("/outputs", "writable"),
                },
            )

            receipt = plan_receipt(plan)
            self.assertEqual(receipt["runtime"]["form"], "image")
            self.assertEqual(receipt["command"], data["command"])
            self.assertNotIn(str(cache), json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
