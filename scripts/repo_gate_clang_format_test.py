"""Runs clang-format over tracked, unpinned C++ files in the real repository."""

from __future__ import annotations

import argparse
import sys
import unittest

from scripts import clang_format_repo
from scripts import pinned_sources


def _parse_clang_format_arg() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--clang-format", required=True)
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    return args.clang_format


CLANG_FORMAT = _parse_clang_format_arg()


class RepoGateClangFormatTests(unittest.TestCase):
    def test_explicit_cpp_exclusions_match_pin_registry(self) -> None:
        root = clang_format_repo.repository_root()
        registry_targets = pinned_sources.source_targets(root, clang_format_repo.CPP_FORMAT_PATTERNS)

        self.assertEqual(
            registry_targets.protected_files,
            clang_format_repo.EXPLICIT_PINNED_CPP_EXCLUSIONS,
        )

    def test_real_repository_cpp_passes_clang_format(self) -> None:
        root = clang_format_repo.repository_root()
        result = clang_format_repo.run_clang_format(CLANG_FORMAT, root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
