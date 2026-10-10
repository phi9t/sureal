"""Runs the import rule checker against the mounted repository."""

from __future__ import annotations

import os
from pathlib import Path
import unittest

from scripts import check_imports


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1]


class RepoGateImportRuleTests(unittest.TestCase):
    def test_import_rule_passes_on_real_repository(self) -> None:
        report = check_imports.check(repository_root())

        self.assertEqual(report["unexpected"], [])
        self.assertEqual(report["stale_baseline"], [])


if __name__ == "__main__":
    unittest.main()
