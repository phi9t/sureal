"""Unit tests for the repository import rule checker."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import check_imports


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ImportRuleBehaviorTests(unittest.TestCase):
    def test_absolute_imports_from_declared_roots_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write(root, "autonomy/evidence/source_snapshot.py", "VALUE = 1\n")
            write(
                root,
                "autonomy/geometry/worker.py",
                "from evidence.source_snapshot import VALUE\n",
            )
            write(root, "parallax/pipeline/contracts.py", "ROOT = 'ok'\n")
            write(
                root,
                "parallax/pipeline/runner.py",
                "from pipeline.contracts import ROOT\n",
            )

            self.assertEqual(check_imports.scan(root), [])

    def test_relative_import_sys_path_edit_and_unrooted_local_import_are_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write(root, "autonomy/geometry/sibling.py", "VALUE = 1\n")
            write(root, "autonomy/geometry/relative.py", "from .sibling import VALUE\n")
            write(root, "autonomy/geometry/path_edit.py", "import sys\nsys.path.insert(0, 'x')\n")
            write(root, "parallax/pipeline/contracts.py", "ROOT = 'ok'\n")
            write(root, "parallax/pipeline/runner.py", "from contracts import ROOT\n")

            problems = check_imports.scan(root)

            self.assertEqual(
                [check_imports.problem_key(problem) for problem in problems],
                [
                    ("autonomy/geometry/path_edit.py", 2, "sys-path-edit"),
                    ("autonomy/geometry/relative.py", 1, "relative-import"),
                    ("parallax/pipeline/runner.py", 1, "unrooted-local-import"),
                ],
            )

    def test_pinned_sources_are_exempted_from_the_active_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write(
                root,
                "autonomy/retained_receipt_sweep.py",
                "RETAINED_SOURCE_PIN_FIELDS = ('source_pins',)\n",
            )
            write(root, "autonomy/pinned.py", "from .sibling import VALUE\n")
            write(root, "autonomy/sibling.py", "VALUE = 1\n")
            write(
                root,
                "autonomy/research/receipt.json",
                json.dumps({"source_pins": {"autonomy/pinned.py": "a" * 64}}),
            )

            self.assertEqual(check_imports.pinned_source_paths(root), {"autonomy/pinned.py"})
            self.assertEqual(check_imports.scan(root), [])

    def test_baseline_allows_current_hits_but_rejects_stale_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write(root, "autonomy/geometry/path_edit.py", "import sys\nsys.path.append('x')\n")
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": [
                            {
                                "path": "autonomy/geometry/path_edit.py",
                                "kind": "sys-path-edit",
                                "line": 2,
                                "reason": "fixture exercises shrink-only baseline behavior",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = check_imports.check(root, baseline)

            self.assertEqual(report["unexpected"], [])
            self.assertEqual(report["stale_baseline"], [])

            write(root, "autonomy/geometry/path_edit.py", "import sys\n")
            stale = check_imports.check(root, baseline)

            self.assertEqual(stale["unexpected"], [])
            self.assertEqual(
                stale["stale_baseline"],
                [("autonomy/geometry/path_edit.py", 2, "sys-path-edit")],
            )

    def test_frozen_receipt_paths_are_exempted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in (
                "autonomy/research/legacy.py",
                "autonomy/studies/example/procedure_records/legacy.py",
                "autonomy/studies/architecture/harness/legacy.py",
            ):
                write(root, relative, "from .sibling import VALUE\n")

            self.assertEqual(check_imports.scan(root), [])


if __name__ == "__main__":
    unittest.main()
