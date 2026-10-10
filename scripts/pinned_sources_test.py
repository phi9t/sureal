"""Tests for retained-receipt pinned source discovery."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import pinned_sources


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class PinnedSourcesTests(unittest.TestCase):
    def test_receipt_pin_fields_are_derived_from_retained_sweep(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write(
                root,
                "autonomy/retained_receipt_sweep.py",
                "RETAINED_SOURCE_PIN_FIELDS = ('source_pins', 'candidate_hashes')\n",
            )

            self.assertEqual(
                pinned_sources.retained_source_pin_fields(root),
                ("source_pins", "candidate_hashes"),
            )

    def test_receipt_pins_are_normalized_to_tracked_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            write(
                root,
                "autonomy/retained_receipt_sweep.py",
                "RETAINED_SOURCE_PIN_FIELDS = ('source_pins', 'candidate_hashes')\n",
            )
            write(root, "autonomy/pinned.py", "from .sibling import VALUE\n")
            write(root, "autonomy/current_candidate.py", "VALUE = 1\n")
            write(root, "autonomy/free.py", "VALUE = 2\n")
            write(
                root,
                "autonomy/research/receipt.json",
                json.dumps(
                    {
                        "source_pins": {"pinned.py": "a" * 64},
                        "candidate_hashes": {
                            "/source/autonomy/current_candidate.py": "b" * 64,
                        },
                    }
                ),
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True)

            self.assertEqual(pinned_sources.pinned_source_paths(root), ("autonomy/pinned.py",))
            self.assertEqual(
                pinned_sources.protected_source_paths(root),
                ("autonomy/current_candidate.py", "autonomy/pinned.py"),
            )

    def test_real_repository_pinned_count_matches_retained_sweep_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]

        pinned = pinned_sources.pinned_source_paths(root)

        self.assertEqual(len(pinned), 267)
        self.assertIn("autonomy/resources/checkpoint.py", pinned)


if __name__ == "__main__":
    unittest.main()
