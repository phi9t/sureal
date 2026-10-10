"""Tests for the machine-identifier boundary check."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import check_identifiers


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1]


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def init_tracked_repo(root: Path, files: dict[str, str]) -> None:
    run("git", "init", "-q", cwd=root)
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    run("git", "add", ".", cwd=root)


class CheckIdentifiersTests(unittest.TestCase):
    def test_scanner_reports_tracked_machine_identifier_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_tracked_repo(
                root,
                {
                    "notes.txt": "\n".join(
                        [
                            "host " + "n" + "116-077-207",
                            "data " + "/data" + "02/project/cache",
                            "home " + "/home/" + "runner/work",
                            "mail " + "operator" + "@" + "internal.invalid",
                        ]
                    )
                    + "\n"
                },
            )

            result = check_identifiers.scan(root)

        self.assertEqual(
            [(hit.path, hit.line, hit.kind) for hit in result.hits],
            [
                ("notes.txt", 1, "host name"),
                ("notes.txt", 2, "host data path"),
                ("notes.txt", 3, "user home path"),
                ("notes.txt", 4, "email address"),
            ],
        )

    def test_scanner_does_not_apply_repo_gate_git_env_to_other_repos(self) -> None:
        with tempfile.TemporaryDirectory() as gate, tempfile.TemporaryDirectory() as temporary:
            gate_root = Path(gate)
            root = Path(temporary)
            init_tracked_repo(gate_root, {"clean.txt": "clean\n"})
            init_tracked_repo(
                root,
                {"notes.txt": "host " + "n" + "116-077-207\n"},
            )

            with mock.patch.dict(
                os.environ,
                {
                    "SUREAL_REPO_GATE_GIT_DIR": str(gate_root / ".git"),
                    "SUREAL_REPO_GATE_GIT_WORK_TREE": str(gate_root),
                    "SUREAL_REPO_GATE_GIT_COMMON_DIR": str(gate_root / ".git"),
                },
            ):
                result = check_identifiers.scan(root)

        self.assertEqual(
            [(hit.path, hit.line, hit.kind) for hit in result.hits],
            [("notes.txt", 1, "host name")],
        )

    def test_scanner_ignores_allowed_fixture_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_tracked_repo(
                root,
                {
                    "fixture.py": (
                        "MATRIX = 'left @ right is prose, not mail'\n"
                        "SSH = 'git" + "@" + "github.com:phi9t/sureal.git'\n"
                        "EXAMPLE = 'person" + "@" + "example.invalid'\n"
                        "ATTRIBUTION = 'noreply" + "@" + "bytedance.com'\n"
                        "HOME = '/home/u/example'\n"
                    )
                },
            )

            result = check_identifiers.scan(root)

        self.assertEqual(result.hits, ())

    def test_retained_records_are_exempt_but_siblings_are_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_tracked_repo(
                root,
                {
                    "autonomy/research/receipt.json": "/home/" + "runner/value\n",
                    "autonomy/studies/balanced16/procedure_records/old.py": (
                        "path = '" + "/data" + "02/old'\n"
                    ),
                    "autonomy/studies/balanced16/current.py": (
                        "path = '" + "/data" + "02/current'\n"
                    ),
                },
            )

            result = check_identifiers.scan(root)

        self.assertEqual(
            [(hit.path, hit.kind) for hit in result.hits],
            [("autonomy/studies/balanced16/current.py", "host data path")],
        )
        self.assertEqual(result.skipped_retained_files, 2)

    def test_baseline_allows_existing_hits_and_fails_when_it_can_shrink(self) -> None:
        result = check_identifiers.ScanResult(
            hits=(
                check_identifiers.IdentifierHit("docs/report.md", 3, 5, "host data path"),
            ),
            scanned_files=1,
            skipped_binary_files=0,
            skipped_retained_files=0,
        )
        baseline = [
            check_identifiers.BaselineEntry(
                "docs/report.md", "host data path", 1, "legacy report"
            )
        ]

        check = check_identifiers.check_against_baseline(result, baseline)
        shrunk = check_identifiers.check_against_baseline(
            check_identifiers.ScanResult((), 1, 0, 0),
            baseline,
        )

        self.assertTrue(check.passed())
        self.assertFalse(shrunk.passed())
        self.assertEqual(shrunk.stale_entries[0][1], 0)

    def test_baseline_rejects_entries_without_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary) / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "allowed": [
                            {
                                "path": "docs/report.md",
                                "kind": "host data path",
                                "count": 1,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "reason"):
                check_identifiers.load_baseline(baseline)

    def test_real_repository_matches_identifier_baseline(self) -> None:
        root = repository_root()
        result = check_identifiers.scan(root)
        baseline = check_identifiers.load_baseline(
            root / "scripts" / "check_identifiers_baseline.json"
        )
        check = check_identifiers.check_against_baseline(result, baseline)

        self.assertEqual(check.unexpected_hits, ())
        self.assertEqual(check.stale_entries, ())


if __name__ == "__main__":
    unittest.main()
