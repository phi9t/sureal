"""Runs shfmt over tracked shell files in active source roots."""

from __future__ import annotations

import argparse
import sys
import unittest

from scripts import shfmt_repo


def _parse_shfmt_arg() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--shfmt", required=True)
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    return args.shfmt


SHFMT = _parse_shfmt_arg()


class RepoGateShfmtTests(unittest.TestCase):
    def test_real_repository_shell_formatting_matches_shfmt(self) -> None:
        root = shfmt_repo.repository_root()
        result = shfmt_repo.run_shfmt(SHFMT, root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
