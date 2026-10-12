"""Tests for active-lint source target discovery."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from lint import pinned_sources


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class PinnedSourcesTests(unittest.TestCase):
    def test_archive_and_submodule_paths_are_excluded(self) -> None:
        cases = {
            "autonomy/research/receipt.py": True,
            "parallax/research/receipt.py": True,
            "autonomy/studies/balanced16/procedure_records/run.py": True,
            "parallax/studies/example/procedure_records/run.py": True,
            "autonomy/studies/architecture/harness/build.py": True,
            "parallax/studies/architecture/harness/build.py": True,
            "parallax/submodules/vendor/source.py": True,
            "autonomy/active/source.py": False,
            "parallax/studies/architecture/active.py": False,
        }

        for relative, excluded in cases.items():
            with self.subTest(relative=relative):
                self.assertEqual(pinned_sources.is_excluded_path(relative), excluded)

    def test_source_targets_do_not_exclude_receipt_pinned_active_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            write(root, "autonomy/package/active.py", "VALUE = 1\n")
            write(root, "autonomy/research/legacy.py", "from .sibling import VALUE\n")
            write(
                root,
                "autonomy/research/receipt.json",
                '{"source_pins": {"autonomy/package/active.py": "' + "a" * 64 + '"}}\n',
            )
            write(root, "parallax/submodules/vendor/source.py", "VALUE = 2\n")
            subprocess.run(["git", "add", "."], cwd=root, check=True)

            targets = pinned_sources.source_targets(root, ("autonomy/**/*.py", "parallax/**/*.py"))

            self.assertIn("autonomy/package/active.py", targets.checked_files)
            self.assertIn("autonomy/research/legacy.py", targets.archive_files)
            self.assertIn("parallax/submodules/vendor/source.py", targets.submodule_files)
            self.assertNotIn("autonomy/research/legacy.py", targets.checked_files)
            self.assertNotIn("parallax/submodules/vendor/source.py", targets.checked_files)

    def test_real_repository_excludes_archives_but_not_active_sources(self) -> None:
        root = Path(__file__).resolve().parents[2]

        targets = pinned_sources.source_targets(root, ("autonomy/**/*.py", "parallax/**/*.py"))

        self.assertIn("autonomy/resources/checkpoint.py", targets.checked_files)
        self.assertTrue(all(pinned_sources.is_excluded_path(path) for path in targets.excluded_files))


if __name__ == "__main__":
    unittest.main()
