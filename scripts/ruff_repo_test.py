"""Unit tests for the Ruff repo-policy wrapper."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import ruff_repo


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

    def test_pinned_sources_are_excluded_from_lint_and_format_scope(self) -> None:
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

        self.assertIn("autonomy/association/pinned.py", targets.excluded_files)
        self.assertNotIn("autonomy/association/pinned.py", targets.checked_files)
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_format_check_does_not_touch_receipt_pinned_file_bytes(self) -> None:
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
        protected = self.root / "autonomy/association/pinned.py"
        before = hashlib.sha256(protected.read_bytes()).hexdigest()

        result = ruff_repo.run_ruff(RUFF, self.root, mode="format")
        after = hashlib.sha256(protected.read_bytes()).hexdigest()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
