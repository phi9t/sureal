"""Unit tests for the Ruff repo-policy wrapper."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lint import ruff_repo


def _parse_ruff_arg() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--ruff", required=True)
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    return args.ruff


RUFF = _parse_ruff_arg()


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class RuffRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        write(
            self.root,
            "pyproject.toml",
            "\n".join(
                [
                    "[tool.ruff]",
                    "line-length = 120",
                    'target-version = "py310"',
                    "[tool.ruff.lint]",
                    'select = ["E9", "F821"]',
                    "",
                ]
            ),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def track(self, relative: str, text: str) -> None:
        write(self.root, relative, text)
        subprocess.run(["git", "add", relative], cwd=self.root, check=True)

    def test_clean_python_passes_lint_and_format(self) -> None:
        self.track("autonomy/association/contract.py", "VALUE = 1\n")

        lint = ruff_repo.run_ruff(RUFF, self.root, mode="check")
        formatting = ruff_repo.run_ruff(RUFF, self.root, mode="format")

        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)
        self.assertEqual(formatting.returncode, 0, formatting.stdout + formatting.stderr)

    def test_syntax_error_fails_lint_with_rule_summary(self) -> None:
        self.track("autonomy/association/bad.py", "def nope(:\n    pass\n")

        result = ruff_repo.run_ruff(RUFF, self.root, mode="check")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("syntax", result.finding_counts)

    def test_receipt_pinned_active_sources_are_linted(self) -> None:
        self.track(
            "autonomy/retained_receipt_sweep.py",
            "RETAINED_SOURCE_PIN_FIELDS = ('source_pins',)\n",
        )
        self.track("autonomy/association/pinned.py", "def broken(:\n    pass\n")
        self.track("autonomy/association/free.py", "VALUE = 1\n")
        self.track(
            "autonomy/research/receipt.json",
            json.dumps({"source_pins": {"autonomy/association/pinned.py": "a" * 64}}),
        )

        targets = ruff_repo.ruff_target_files(self.root, mode="check")
        lint = ruff_repo.run_ruff(RUFF, self.root, mode="check")

        self.assertIn("autonomy/association/pinned.py", targets.checked_files)
        self.assertNotIn("autonomy/association/pinned.py", targets.excluded_files)
        self.assertNotEqual(lint.returncode, 0)
        self.assertIn("syntax", lint.finding_counts)

    def test_deleted_tracked_python_files_are_not_linted_before_commit(self) -> None:
        self.track("parallax/pipeline/removed.py", "not python syntax :\n")
        (self.root / "parallax/pipeline/removed.py").unlink()

        result = ruff_repo.run_ruff(RUFF, self.root, mode="check")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("parallax/pipeline/removed.py", result.checked_files)

    def test_format_check_includes_receipt_pinned_batch_files(self) -> None:
        self.track(
            "autonomy/retained_receipt_sweep.py",
            "RETAINED_SOURCE_PIN_FIELDS = ('source_pins',)\n",
        )
        self.track("autonomy/association/pinned.py", "VALUE={  'kept': 1}\n")
        self.track("autonomy/association/free.py", "VALUE = 1\n")
        self.track(
            "autonomy/research/receipt.json",
            json.dumps({"source_pins": {"autonomy/association/pinned.py": "a" * 64}}),
        )

        result = ruff_repo.run_ruff(RUFF, self.root, mode="format")

        self.assertIn("autonomy/association/pinned.py", result.checked_files)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
