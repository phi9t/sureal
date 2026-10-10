"""Tests for the standalone storage-boundary check."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check_storage_boundary


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1]


class CheckStorageBoundaryTests(unittest.TestCase):
    def test_scanner_accepts_clean_active_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clean = root / "dataset" / "reader.py"
            clean.parent.mkdir(parents=True)
            clean.write_text("from blob_store import default_blob_store\n", encoding="utf-8")

            result = check_storage_boundary.scan(root)

        self.assertTrue(result.passed())
        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(result.violations, ())

    def test_scanner_reports_planted_active_violation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            planted = root / "dataset" / "planted.py"
            planted.parent.mkdir(parents=True)
            planted.write_text(
                "\n".join(
                    [
                        "WAYSTONE = 'workspace/waystone/scripts/waystone'",
                        "args = ['layout-profile', '--project', 'sureal']",
                        "env = {'SUREAL_WAYSTONE': WAYSTONE}",
                        "command = 'hdfs dfs -ls /tmp'",
                        "fs = HadoopFileSystem()",
                        "subprocess.Popen(['waystone', 'ls'])",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = check_storage_boundary.scan(root)

        self.assertEqual(
            result.violations,
            (
                check_storage_boundary.Violation(
                    "dataset/planted.py", 1, "Waystone command constant"
                ),
                check_storage_boundary.Violation(
                    "dataset/planted.py", 1, "direct Waystone CLI path"
                ),
                check_storage_boundary.Violation(
                    "dataset/planted.py", 2, "Waystone layout-profile CLI"
                ),
                check_storage_boundary.Violation(
                    "dataset/planted.py", 3, "SUREAL_WAYSTONE environment lookup"
                ),
                check_storage_boundary.Violation(
                    "dataset/planted.py", 4, "direct hdfs dfs invocation"
                ),
                check_storage_boundary.Violation(
                    "dataset/planted.py", 5, "direct HadoopFileSystem client"
                ),
                check_storage_boundary.Violation(
                    "dataset/planted.py",
                    6,
                    "Waystone process start outside blob_store",
                ),
            ),
        )

    def test_cli_fails_on_planted_violation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            planted = root / "dataset" / "planted.py"
            planted.parent.mkdir(parents=True)
            planted.write_text("WAYSTONE = 'workspace/waystone/scripts/waystone'\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(repository_root() / "scripts" / "check_storage_boundary.py"),
                    "--root",
                    str(root),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("storage boundary scan: fail", result.stderr)
        self.assertIn("dataset/planted.py:1: direct Waystone CLI path", result.stderr)

    def test_real_repository_scans_clean(self) -> None:
        result = check_storage_boundary.scan(repository_root() / "autonomy")

        self.assertEqual(result.violations, ())


if __name__ == "__main__":
    unittest.main()
