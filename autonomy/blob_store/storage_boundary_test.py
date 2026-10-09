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
    ("Waystone layout-profile CLI", re.compile(r"\blayout-profile\b")),
    ("copied Waystone tool-pin path", re.compile(r"rust/target/debug/waystone|libhdfs_client\.so|hdfs\.bin")),
    ("direct Waystone CLI path", re.compile(r"workspace/waystone/scripts/waystone|scripts/waystone")),
    ("SUREAL_WAYSTONE environment lookup", re.compile(r"\bSUREAL_WAYSTONE\b")),
    ("direct hdfs dfs invocation", re.compile(r"\bhdfs\s+dfs\b")),
    ("direct HadoopFileSystem client", re.compile(r"\bHadoopFileSystem\b")),
    ("Waystone process start outside blob_store", re.compile(r"\b(?:Popen|subprocess\.(?:run|Popen))\s*\(.*waystone")),
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
)

# ADR 0001 treats historical procedure records as retained evidence bytes. Keep
# these exact records readable, but do not exclude the whole procedure_records tree.
ALLOWED_PROCEDURE_RECORDS = {
    "studies/balanced16/procedure_records/legacy_cache_retention_audit.py",
    "studies/balanced16/procedure_records/legacy_checkpoint_retention_audit.py",
    "studies/balanced16/procedure_records/legacy_checkpoint_retention_sources.py",
    "studies/balanced16/procedure_records/legacy_checkpoint_retention_sources_test.py",
    "studies/balanced16/procedure_records/legacy_pilot_retention_audit.py",
    "studies/balanced16/procedure_records/legacy_pilot_retention_sources.py",
    "studies/balanced16/procedure_records/legacy_pilot_retention_sources_test.py",
    "studies/balanced16/procedure_records/legacy_publish_native_cache.py",
    "studies/balanced16/procedure_records/legacy_publish_sustained_pilot.py",
    "studies/balanced16/procedure_records/legacy_resource_retention.py",
    "studies/balanced16/procedure_records/legacy_resource_retention_audit.py",
    "studies/balanced16/procedure_records/legacy_resource_retention_test.py",
    "studies/balanced16/procedure_records/legacy_retention_sources.py",
    "studies/balanced16/procedure_records/legacy_retention_sources_test.py",
    "studies/balanced16/procedure_records/scan.py",
    "studies/expanded_batch/procedure_records/expanded_publish.py",
}

def _is_scanned_file(path: Path) -> bool:
    return path.name in TEXT_NAMES or path.suffix in TEXT_SUFFIXES


def _is_active_path(relative: str) -> bool:
    if relative in ALLOWED_EXACT:
        return False
    if relative.endswith("_test.py"):
        return False
    if relative in ALLOWED_PROCEDURE_RECORDS:
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
            planted.write_text(
                "\n".join(
                    [
                        "WAYSTONE = 'workspace/waystone/scripts/waystone'",
                        "args = ['layout-profile', '--project', 'sureal']",
                        "env = {'SUREAL_WAYSTONE': WAYSTONE}",
                        "command = 'hdfs dfs -ls /tmp'",
                        "fs = HadoopFileSystem()",
                        "subprocess.Popen(['waystone', 'ls'])",
                    ]
                )
                + "\n"
            )

            violations = scan_storage_boundary(root)

        self.assertEqual(
            violations,
            [
                Violation("dataset/planted.py", 1, "direct Waystone CLI path"),
                Violation("dataset/planted.py", 1, "Waystone command constant"),
                Violation("dataset/planted.py", 2, "Waystone layout-profile CLI"),
                Violation("dataset/planted.py", 3, "SUREAL_WAYSTONE environment lookup"),
                Violation("dataset/planted.py", 4, "direct hdfs dfs invocation"),
                Violation("dataset/planted.py", 5, "direct HadoopFileSystem client"),
                Violation("dataset/planted.py", 6, "Waystone process start outside blob_store"),
            ],
        )

    def test_runnable_procedure_records_are_not_broadly_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            planted = root / "studies" / "balanced16" / "procedure_records" / "new_publisher.py"
            planted.parent.mkdir(parents=True)
            planted.write_text(
                "if __name__ == '__main__':\n"
                "    command = 'hdfs dfs -ls /tmp'\n"
            )

            violations = scan_storage_boundary(root)

        self.assertEqual(
            violations,
            [
                Violation(
                    "studies/balanced16/procedure_records/new_publisher.py",
                    2,
                    "direct hdfs dfs invocation",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
