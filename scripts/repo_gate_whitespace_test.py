"""Runs the repository whitespace check used by the repo gate."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1]


class RepoGateWhitespaceTests(unittest.TestCase):
    def test_tracked_changes_have_no_git_diff_check_findings(self) -> None:
        root = repository_root()
        env = os.environ.copy()
        env["GIT_OPTIONAL_LOCKS"] = "0"
        apply_repo_gate_git_environment(env)
        result = subprocess.run(
            ["git", "-C", str(root), "diff", "--check", "HEAD", "--"],
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def apply_repo_gate_git_environment(env: dict[str, str]) -> None:
    for source, destination in (
        ("SUREAL_REPO_GATE_GIT_DIR", "GIT_DIR"),
        ("SUREAL_REPO_GATE_GIT_WORK_TREE", "GIT_WORK_TREE"),
        ("SUREAL_REPO_GATE_GIT_COMMON_DIR", "GIT_COMMON_DIR"),
    ):
        value = env.get(source)
        if value:
            env[destination] = value
    alternate = env.get("SUREAL_REPO_GATE_GIT_ALTERNATE_OBJECT_DIRECTORIES")
    if alternate:
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = alternate
    primary = env.get("SUREAL_REPO_GATE_GIT_OBJECT_DIRECTORY")
    if primary:
        env["GIT_OBJECT_DIRECTORY"] = primary


if __name__ == "__main__":
    unittest.main()
