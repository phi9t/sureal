"""Runs the shell-style policy checker over the real repository."""

from __future__ import annotations

import unittest

from lint import check_shell_style


class RepoGateShellStyleTests(unittest.TestCase):
    def test_real_repository_shell_style_matches_policy(self) -> None:
        root = check_shell_style.repository_root()
        result = check_shell_style.check_repository(root)

        self.assertEqual(result.findings, (), result.format_findings())


if __name__ == "__main__":
    unittest.main()
