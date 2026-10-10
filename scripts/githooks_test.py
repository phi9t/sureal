"""Tests for versioned git hook contracts."""

from __future__ import annotations

import os
import stat
import unittest
from pathlib import Path


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1]


class GitHooksTests(unittest.TestCase):
    def test_versioned_hooks_are_executable_bash_scripts(self) -> None:
        root = repository_root()
        hooks = sorted((root / ".githooks").iterdir())

        self.assertTrue(hooks)
        for hook in hooks:
            mode = hook.stat().st_mode
            first_line = hook.read_text(encoding="utf-8").splitlines()[0]
            self.assertTrue(
                mode & stat.S_IXUSR,
                f"{hook.relative_to(root)} must be executable",
            )
            self.assertEqual(first_line, "#!/bin/bash")

    def test_pre_commit_runs_only_static_standalone_checks(self) -> None:
        root = repository_root()
        hook = root / ".githooks" / "pre-commit"
        text = hook.read_text(encoding="utf-8")

        self.assertIn("git diff --cached --check", text)
        self.assertIn("python3 scripts/check_identifiers.py", text)
        self.assertIn("python3 scripts/check_storage_boundary.py", text)
        self.assertNotIn("./bazelw", text)
        self.assertNotIn("python3 -m", text)


if __name__ == "__main__":
    unittest.main()
