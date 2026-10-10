"""Focused tests for publication audit behavior owned by repo quality."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import publication_audit


class PublicationAuditBehaviorTests(unittest.TestCase):
    def test_testdata_fixtures_may_have_generated_suffixes(self) -> None:
        self.assertFalse(
            publication_audit._is_generated_path(
                "autonomy/segmentation/testdata/semantic_receipts/exact/source/live.log"
            )
        )
        self.assertTrue(publication_audit._is_generated_path("training/logs/run.log"))

    def test_portable_command_failure_includes_bounded_output(self) -> None:
        result = subprocess.CompletedProcess(
            ["python", "tool.py"],
            9,
            b"stdout details\n",
            b"stderr details\n",
        )

        message = publication_audit._portable_command_failure(["python", "tool.py"], result)

        self.assertIn("portable command failed (exit 9): python tool.py", message)
        self.assertIn("stdout details", message)
        self.assertIn("stderr details", message)

    def test_portable_command_environment_uses_parallax_import_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = publication_audit._portable_command_environment(root)

        self.assertEqual(env["PYTHONPATH"].split(":")[0], str(root / "parallax"))
        self.assertNotIn("PYTHONSAFEPATH", env)

    def test_publication_audit_cli_accepts_tracked_testdata_log(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path, content in {
                ".github/workflows/publication.yml": "name: publication\n",
                ".gitignore": "",
                ".gitmodules": "",
                "CONTRIBUTING.md": "contribute\n",
                "docs/coherent-scene-hypotheses.md": "hypotheses\n",
                "LICENSE.md": "Gaussian-Splatting License\n",
                "MISSION.md": "mission\n",
                "README.md": "\n".join(
                    [
                        "Sureal",
                        "surflo",
                        "fork of Surflo",
                        "non-commercial research and evaluation",
                        publication_audit.TARGET_URL,
                        publication_audit.UPSTREAM_URL,
                        "[LICENSE.md](LICENSE.md)",
                        "[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)",
                    ]
                ),
                "RELEASING.md": "release\n",
                "SECURITY.md": "security\n",
                "THIRD_PARTY_NOTICES.md": "Gaussian-Splatting License\n",
                "UPSTREAM.md": "upstream\n",
                "pyproject.toml": "\n".join(
                    [
                        "[project]",
                        'name = "surflo"',
                        "[project.urls]",
                        f'Homepage = "{publication_audit.TARGET_URL}"',
                        f'Repository = "{publication_audit.TARGET_URL}"',
                        f'Upstream = "{publication_audit.UPSTREAM_URL}"',
                    ]
                ),
                "autonomy/example/testdata/source/live.log": "fixture\n",
            }.items():
                file = root / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content, encoding="utf-8")

            subprocess.run(["git", "init", "-q"], cwd=root, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(
                ["git", "add", "."],
                cwd=root,
                check=True,
                stdout=subprocess.DEVNULL,
            )

            errors = publication_audit.static_errors(root)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
