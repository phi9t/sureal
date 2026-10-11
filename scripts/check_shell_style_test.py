"""Unit tests for the shell-style policy checker."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import check_shell_style


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class CheckShellStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.baseline = self.root / "scripts" / "shell_style_baseline.json"
        write(
            self.root,
            "scripts/shell_style_baseline.json",
            json.dumps({"version": 1, "max_lines": 150, "grandfathered_long_scripts": {}}, indent=2),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def track(self, relative: str, text: str) -> None:
        write(self.root, relative, text)
        subprocess.run(["git", "add", relative], cwd=self.root, check=True)

    def test_clean_active_script_passes(self) -> None:
        self.track(
            "autonomy/run.sh",
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "# Runs the example command.",
                    "set -euo pipefail",
                    "",
                    "# Prints the selected name.",
                    "main() {",
                    "  local name=\"${1:-world}\"",
                    "  printf '%s\\n' \"${name}\"",
                    "}",
                    "",
                    "main \"$@\"",
                    "",
                ]
            ),
        )
        self.track("experiments/legacy.sh", "#!/bin/bash\nset -euo pipefail\nlegacy() {\n  true\n}\n")

        result = check_shell_style.check_repository(self.root, baseline_path=self.baseline)

        self.assertEqual(result.findings, ())
        self.assertEqual(result.targets.checked_files, ("autonomy/run.sh",))

    def test_bad_active_script_reports_each_policy_family(self) -> None:
        self.track(
            "parallax/bad.sh",
            "\n".join(
                [
                    "#!/bin/bash",
                    "set -euo pipefail",
                    "bad() {",
                    "  echo `date`",
                    "  printf '%s\\n' 'this line is intentionally longer than one hundred and twenty columns so the style checker catches it and the fixture proves the rule'",
                    "}",
                    "",
                ]
            ),
        )

        result = check_shell_style.check_repository(self.root, baseline_path=self.baseline)

        codes = {finding.code for finding in result.findings}
        self.assertIn("shebang", codes)
        self.assertIn("header-comment", codes)
        self.assertIn("function-comment", codes)
        self.assertIn("line-length", codes)
        self.assertIn("backticks", codes)

    def test_long_script_baseline_allows_only_current_line_count(self) -> None:
        lines = ["#!/usr/bin/env bash", "# Runs a long legacy command.", "set -euo pipefail"]
        lines.extend(f"printf '%s\\n' {index}" for index in range(151))
        self.track("scripts/legacy.sh", "\n".join(lines) + "\n")
        self.baseline.write_text(
            json.dumps(
                {
                    "version": 1,
                    "max_lines": 150,
                    "grandfathered_long_scripts": {
                        "scripts/legacy.sh": {
                            "lines": 154,
                            "reason": "existing script awaiting Python extraction",
                        }
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_shell_style.check_repository(self.root, baseline_path=self.baseline)

        self.assertEqual(result.findings, ())

    def test_stale_long_script_baseline_fails(self) -> None:
        self.track(
            "scripts/short.sh",
            "#!/usr/bin/env bash\n# Runs a short command.\nset -euo pipefail\n",
        )
        self.baseline.write_text(
            json.dumps(
                {
                    "version": 1,
                    "max_lines": 150,
                    "grandfathered_long_scripts": {
                        "scripts/short.sh": {
                            "lines": 151,
                            "reason": "existing script awaiting Python extraction",
                        }
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        result = check_shell_style.check_repository(self.root, baseline_path=self.baseline)

        self.assertEqual([finding.code for finding in result.findings], ["stale-length-baseline"])


if __name__ == "__main__":
    unittest.main()
