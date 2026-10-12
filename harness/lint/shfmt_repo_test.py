"""Unit tests for the shfmt repo-policy wrapper."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lint import shfmt_repo


def _parse_shfmt_arg() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--shfmt", required=True)
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    return args.shfmt


SHFMT = _parse_shfmt_arg()


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ShfmtRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def track(self, relative: str, text: str) -> None:
        write(self.root, relative, text)
        subprocess.run(["git", "add", relative], cwd=self.root, check=True)

    def test_clean_active_script_passes_format_check(self) -> None:
        self.track("autonomy/run.sh", "#!/usr/bin/env bash\n# Runs a command.\nset -euo pipefail\ntrue\n")
        self.track("experiments/legacy.sh", "#!/bin/bash\nif true; then echo ok; fi\n")

        result = shfmt_repo.run_shfmt(SHFMT, self.root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.checked_files, ("autonomy/run.sh",))

    def test_misformatted_active_script_fails_with_violation_count(self) -> None:
        self.track("parallax/bad.sh", "#!/usr/bin/env bash\n# Runs a command.\nif true; then\n    echo ok\nfi\n")

        result = shfmt_repo.run_shfmt(SHFMT, self.root)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.format_violation_count, 1)

    def test_receipt_pinned_active_script_is_checked(self) -> None:
        self.track(
            "autonomy/retained_receipt_sweep.py",
            "RETAINED_SOURCE_PIN_FIELDS = ('source_pins', 'candidate_hashes')\n",
        )
        self.track("autonomy/pinned.sh", "#!/usr/bin/env bash\nif true; then\n    echo pinned\nfi\n")
        self.track("autonomy/free.sh", "#!/usr/bin/env bash\n# Runs a command.\nset -euo pipefail\ntrue\n")
        receipt = self.root / "autonomy" / "research" / "live-audit.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps({"source_pins": {"autonomy/pinned.sh": "0" * 64}}),
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "autonomy/research/live-audit.json"], cwd=self.root, check=True)

        result = shfmt_repo.run_shfmt(SHFMT, self.root)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.excluded_files, ())
        self.assertEqual(result.checked_files, ("autonomy/free.sh", "autonomy/pinned.sh"))


if __name__ == "__main__":
    unittest.main()
