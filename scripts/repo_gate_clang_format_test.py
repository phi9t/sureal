"""Runs clang-format over tracked active C++ files in the real repository."""

from __future__ import annotations

import argparse
import sys
import unittest

from scripts import clang_format_repo

def _parse_clang_format_arg() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--clang-format", required=True)
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    return args.clang_format


CLANG_FORMAT = _parse_clang_format_arg()


class RepoGateClangFormatTests(unittest.TestCase):
    def test_real_repository_cpp_passes_clang_format(self) -> None:
        root = clang_format_repo.repository_root()
        result = clang_format_repo.run_clang_format(CLANG_FORMAT, root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
