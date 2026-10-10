"""Unit tests for the ShellCheck repo-policy wrapper."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import shellcheck_repo


def _parse_shellcheck_arg() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--shellcheck", required=True)
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    return args.shellcheck


SHELLCHECK = _parse_shellcheck_arg()


class ShellCheckRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_tracked(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", relative], cwd=self.root, check=True)

    def test_clean_script_passes(self) -> None:
        self.write_tracked(
            "scripts/clean.sh",
            "#!/bin/bash\nset -euo pipefail\nname=${1:-world}\nprintf '%s\\n' \"$name\"\n",
        )

        result = shellcheck_repo.run_shellcheck(SHELLCHECK, self.root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.checked_files, ("scripts/clean.sh",))

    def test_bad_script_fails_with_shellcheck_rule(self) -> None:
        self.write_tracked(
            "scripts/bad.sh",
            "#!/bin/bash\nset -euo pipefail\nname=${1:-world}\necho $name\n",
        )

        result = shellcheck_repo.run_shellcheck(SHELLCHECK, self.root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SC2086", result.stdout + result.stderr)

    def test_file_list_includes_extensionless_hooks_and_excludes_receipt_pins(self) -> None:
        self.write_tracked(
            "autonomy/retained_receipt_sweep.py",
            "RETAINED_SOURCE_PIN_FIELDS = ('source_pins', 'candidate_hashes')\n",
        )
        self.write_tracked(".githooks/pre-commit", "#!/bin/bash\nset -euo pipefail\ntrue\n")
        self.write_tracked("autonomy/tracer.sh", "#!/bin/bash\nset -euo pipefail\ntrue\n")
        self.write_tracked("autonomy/run.sh", "#!/bin/bash\nset -euo pipefail\ntrue\n")
        receipt = self.root / "autonomy/research/live-audit.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps({"source_pins": {"tracer.sh": "0" * 64}}),
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "autonomy/research/live-audit.json"], cwd=self.root, check=True)

        checked, excluded = shellcheck_repo.shellcheck_target_files(self.root)

        self.assertIn(".githooks/pre-commit", checked)
        self.assertIn("autonomy/run.sh", checked)
        self.assertIn("autonomy/tracer.sh", excluded)
        self.assertNotIn("autonomy/tracer.sh", checked)


if __name__ == "__main__":
    unittest.main()
