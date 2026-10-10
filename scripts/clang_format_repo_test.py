"""Unit tests for the clang-format repo-policy wrapper."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import clang_format_repo


def _parse_clang_format_arg() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--clang-format", required=True)
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    return args.clang_format


CLANG_FORMAT = _parse_clang_format_arg()


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ClangFormatRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        write(
            self.root,
            ".clang-format",
            "\n".join(
                [
                    "BasedOnStyle: Google",
                    "ColumnLimit: 120",
                    "SortIncludes: Never",
                    "AllowShortBlocksOnASingleLine: Never",
                    "AllowShortEnumsOnASingleLine: false",
                    "AllowShortFunctionsOnASingleLine: Empty",
                    "AllowShortIfStatementsOnASingleLine: Never",
                    "AllowShortLoopsOnASingleLine: false",
                    "BreakStringLiterals: false",
                    "ReflowComments: false",
                    "SkipMacroDefinitionBody: true",
                    "",
                ]
            ),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def track(self, relative: str, text: str) -> None:
        write(self.root, relative, text)
        subprocess.run(["git", "add", relative], cwd=self.root, check=True)

    def test_clean_active_cpp_passes_format_check(self) -> None:
        self.track("autonomy/native/example.cc", "int main() {\n  return 0;\n}\n")
        self.track("parallax/native/example.hh", "#pragma once\n\nint Value();\n")
        self.track("submodules/vendor/ignored.cc", "int main(){return 0;}\n")

        result = clang_format_repo.run_clang_format(CLANG_FORMAT, self.root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            result.checked_files,
            (
                "autonomy/native/example.cc",
                "parallax/native/example.hh",
            ),
        )

    def test_misformatted_active_cpp_fails_with_violation_count(self) -> None:
        self.track("autonomy/native/bad.cc", "int main(){return 0;}\n")

        result = clang_format_repo.run_clang_format(CLANG_FORMAT, self.root)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.format_violation_count, 1)

    def test_explicit_pinned_sources_are_not_checked(self) -> None:
        self.track("autonomy/native/pinned.cc", "int main(){return 0;}\n")
        self.track("autonomy/native/free.cc", "int main() {\n  return 0;\n}\n")

        result = clang_format_repo.run_clang_format(
            CLANG_FORMAT,
            self.root,
            protected=("autonomy/native/pinned.cc",),
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.excluded_files, ("autonomy/native/pinned.cc",))
        self.assertEqual(result.checked_files, ("autonomy/native/free.cc",))


if __name__ == "__main__":
    unittest.main()
