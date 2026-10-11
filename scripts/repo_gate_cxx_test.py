"""Runs the mechanical C++ lint over the real repository scope."""

from __future__ import annotations

import unittest

from scripts import check_cxx


class RepoGateCxxTests(unittest.TestCase):
    def test_real_repository_cxx_passes_mechanical_lint(self) -> None:
        root = check_cxx.repository_root()
        result = check_cxx.check_repository(root)

        self.assertEqual(result.returncode, 0, result.format_findings())


if __name__ == "__main__":
    unittest.main()
