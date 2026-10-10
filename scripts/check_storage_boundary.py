#!/usr/bin/env python3
"""Fail when active autonomy code bypasses the blob-store boundary."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO / "autonomy"
TEXT_SUFFIXES = {".bzl", ".py", ".sh"}
TEXT_NAMES = {"BUILD", "BUILD.bazel"}


@dataclass(frozen=True, order=True)
class Violation:
    path: str
    line: int
    kind: str

    def location(self) -> str:
        return f"{self.path}:{self.line}: {self.kind}"


@dataclass(frozen=True)
class ScanResult:
    violations: tuple[Violation, ...]
    scanned_files: int

    def passed(self) -> bool:
        return not self.violations

    def as_jsonable(self) -> dict[str, object]:
        return {
            "status": "pass" if self.passed() else "fail",
            "scanned_files": self.scanned_files,
            "violations": [violation.__dict__ for violation in self.violations],
        }


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


def scan(root: Path = DEFAULT_ROOT) -> ScanResult:
    violations: list[Violation] = []
    scanned_files = 0
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
        scanned_files += 1
        for line_number, line in enumerate(lines, start=1):
            for kind, pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    violations.append(Violation(relative, line_number, kind))
    return ScanResult(tuple(sorted(violations)), scanned_files)


def format_text_report(result: ScanResult) -> str:
    lines = [f"storage boundary scan: {'pass' if result.passed() else 'fail'}"]
    lines.append(f"scanned_files: {result.scanned_files}")
    if result.violations:
        lines.append("violations:")
        lines.extend(f"  {violation.location()}" for violation in result.violations[:50])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = scan(args.root)
    if args.json:
        print(json.dumps(result.as_jsonable(), indent=2, sort_keys=True))
    else:
        stream = sys.stdout if result.passed() else sys.stderr
        stream.write(format_text_report(result))
    return 0 if result.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
