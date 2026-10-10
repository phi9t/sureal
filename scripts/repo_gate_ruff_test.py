"""Runs Ruff over the real repository scope owned by repo quality."""

from __future__ import annotations

import argparse
import sys
import unittest

from scripts import ruff_repo


def _parse_ruff_arg() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--ruff", required=True)
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    return args.ruff


RUFF = _parse_ruff_arg()


class RepoGateRuffTests(unittest.TestCase):
    def test_real_repository_lint_scope_passes_ruff(self) -> None:
        root = ruff_repo.repository_root()
        result = ruff_repo.run_ruff(RUFF, root, mode="check")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_first_format_batch_passes_ruff_format_check(self) -> None:
        root = ruff_repo.repository_root()
        result = ruff_repo.run_ruff(RUFF, root, mode="format")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
