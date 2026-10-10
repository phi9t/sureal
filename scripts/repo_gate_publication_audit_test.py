"""Runs the publication audit from Bazel against the mounted repository."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1]


class RepoGatePublicationAuditTests(unittest.TestCase):
    def test_publication_audit_passes_on_real_repository(self) -> None:
        root = repository_root()
        pycache = Path(os.environ.get("TEST_TMPDIR", "/tmp")) / "repo-gate-pycache"
        pycache.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["GIT_OPTIONAL_LOCKS"] = "0"
        env["PYTHONPYCACHEPREFIX"] = str(pycache)
        apply_repo_gate_git_environment(env)

        result = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "publication_audit.py"),
                "--root",
                str(root),
            ],
            cwd=root,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass", report["errors"])


def apply_repo_gate_git_environment(env: dict[str, str]) -> None:
    alternate = env.get("SUREAL_REPO_GATE_GIT_ALTERNATE_OBJECT_DIRECTORIES")
    if alternate:
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = alternate
    primary = env.get("SUREAL_REPO_GATE_GIT_OBJECT_DIRECTORY")
    if primary:
        env["GIT_OBJECT_DIRECTORY"] = primary


if __name__ == "__main__":
    unittest.main()
