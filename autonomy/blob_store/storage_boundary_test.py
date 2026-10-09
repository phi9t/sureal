"""Static storage-boundary checks for active autonomy code."""

import os
import re
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path


AUTONOMY_ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".bzl", ".py", ".sh"}
TEXT_NAMES = {"BUILD", "BUILD.bazel"}


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    kind: str


FORBIDDEN_PATTERNS = (
    ("hard-coded Waystone storage root", re.compile(r"hdfs://harunava|/user/tiger/waystone")),
    ("Waystone storage-prefix CLI", re.compile(r"\bstorage-prefix\b")),
    ("copied Waystone tool-pin path", re.compile(r"rust/target/debug/waystone|libhdfs_client\.so|hdfs\.bin")),
    ("direct Waystone CLI path", re.compile(r"workspace/waystone/scripts/waystone|scripts/waystone")),
    ("Waystone command constant", re.compile(r"\bWAYSTONE\s*=")),
)

ALLOWED_EXACT = {
    "resources/hdfs_auth_keepalive.py",
    "resources/install-hdfs-auth-keepalive.py",
    "resources/refresh-hdfs-auth.sh",
}

ALLOWED_PREFIXES = (
    "blob_store/",
    "evidence/testdata/",
    "research/journal-evidence/",
    "research/parking/",
    "studies/balanced16/procedure_records/",
    "studies/expanded_batch/procedure_records/",
    "studies/fixed_batch/procedure_records/",
    "studies/normalization/procedure_records/",
)

# Ticket 07 owns the native-cache and sustained-pilot publication migration on a
# sibling branch. Keep these path-based so the coordinator can remove the
# exclusions when that branch merges.
BS07_OWNED = {
    "retention/cache_retention_audit.py",
    "retention/pilot_retention_audit.py",
    "retention/pilot_retention_sources.py",
    "retention/publish_native_cache.py",
    "retention/publish_sustained_pilot.py",
    "retention/retention_sources.py",
}


def _is_scanned_file(path: Path) -> bool:
    return path.name in TEXT_NAMES or path.suffix in TEXT_SUFFIXES


def _is_active_path(relative: str) -> bool:
    if relative in ALLOWED_EXACT or relative in BS07_OWNED:
        return False
    if relative.endswith("_test.py"):
        return False
    return not any(relative.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def scan_storage_boundary(root: Path = AUTONOMY_ROOT) -> list[Violation]:
    violations = []
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or not _is_scanned_file(path):
            continue
        relative = path.relative_to(root).as_posix()
        if not _is_active_path(relative):
            continue
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for kind, pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    violations.append(Violation(relative, line_number, kind))
    return violations


class StorageBoundaryTests(unittest.TestCase):
    def test_active_code_has_no_legacy_waystone_storage_surface(self):
        violations = scan_storage_boundary()
        if os.environ.get("SUREAL_BLOB_STORE_PLANT_VIOLATION") == "1":
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                planted = root / "dataset" / "planted.py"
                planted.parent.mkdir(parents=True)
                planted.write_text("WAYSTONE = 'workspace/waystone/scripts/waystone'\n")
                violations = scan_storage_boundary(root)
        self.assertEqual(
            violations,
            [],
            "active code outside blob_store and HDFS auth keepalive must not "
            "invoke Waystone or name its storage root",
        )

    def test_scanner_reports_a_planted_active_violation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            planted = root / "dataset" / "planted.py"
            planted.parent.mkdir(parents=True)
            planted.write_text("WAYSTONE = 'workspace/waystone/scripts/waystone'\n")

            violations = scan_storage_boundary(root)

        self.assertEqual(
            violations,
            [
                Violation("dataset/planted.py", 1, "direct Waystone CLI path"),
                Violation("dataset/planted.py", 1, "Waystone command constant"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
