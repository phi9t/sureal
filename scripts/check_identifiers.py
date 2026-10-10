#!/usr/bin/env python3
"""Fail when tracked content names a machine, user home, host path or e-mail.

The scanner reports locations and kinds, but not the matched text. That keeps
the check useful in logs without copying the identifier into more artifacts.
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


REPO = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = REPO / "scripts" / "check_identifiers_baseline.json"

# Patterns are assembled from parts so this file does not match itself.
PATTERNS = {
    "host name": re.compile(r"\bn" + r"\d{3}-\d{3}-\d{3}\b"),
    "host data path": re.compile("/data" + r"\d{2}/"),
    "user home path": re.compile("/home/" + r"(?!u/)[A-Za-z][\w.-]*/"),
    "email address": re.compile(
        r"(?<![\w.+-])[\w.+-]+"
        + r"@"
        + r"[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b"
    ),
}

ALLOWED_EMAILS = {
    "git" + "@" + "github.com",
    "noreply" + "@" + "bytedance.com",
}
ALLOWED_EMAIL_DOMAINS = {
    "example.com",
    "example.invalid",
}
SKIPPED_DIRS = {
    ".bazel-cache",
    ".git",
    "__pycache__",
    "bazel-bin",
    "bazel-out",
    "bazel-sureal",
    "bazel-testlogs",
}

# These are retained records or frozen procedure sources. They preserve old
# machine-specific bytes as evidence and are exempted rather than rewritten.
RETAINED_PREFIXES = (
    "autonomy/evidence/testdata/retained_source_snapshots/",
    "autonomy/research/",
    "autonomy/segmentation/testdata/semantic_receipts/",
    "autonomy/studies/architecture/harness/",
    "autonomy/studies/balanced16/procedure_records/",
    "autonomy/studies/expanded_batch/procedure_records/",
    "autonomy/studies/fixed_batch/procedure_records/",
    "autonomy/studies/normalization/procedure_records/",
    "docs/collaboration/checks/",
    "docs/research/parking/",
    "docs/research/reviews/",
)
RETAINED_SUFFIXES = (".source",)


@dataclass(frozen=True, order=True)
class IdentifierHit:
    path: str
    line: int
    column: int
    kind: str

    def location(self) -> str:
        return f"{self.path}:{self.line}:{self.column}: {self.kind}"


@dataclass(frozen=True)
class BaselineEntry:
    path: str
    kind: str
    count: int
    reason: str


@dataclass(frozen=True)
class ScanResult:
    hits: tuple[IdentifierHit, ...]
    scanned_files: int
    skipped_binary_files: int
    skipped_retained_files: int

    def counts_by_kind(self) -> dict[str, int]:
        return dict(sorted(collections.Counter(hit.kind for hit in self.hits).items()))

    def counts_by_top_directory(self) -> dict[str, int]:
        counts = collections.Counter(hit.path.split("/", 1)[0] for hit in self.hits)
        return dict(sorted(counts.items()))


@dataclass(frozen=True)
class BaselineCheck:
    result: ScanResult
    unexpected_hits: tuple[IdentifierHit, ...]
    stale_entries: tuple[tuple[BaselineEntry, int], ...]

    def passed(self) -> bool:
        return not self.unexpected_hits and not self.stale_entries

    def as_jsonable(self) -> dict[str, object]:
        return {
            "status": "pass" if self.passed() else "fail",
            "scanned_text_files": self.result.scanned_files,
            "skipped_binary_files": self.result.skipped_binary_files,
            "skipped_retained_files": self.result.skipped_retained_files,
            "total_hits": len(self.result.hits),
            "hit_counts_by_kind": self.result.counts_by_kind(),
            "hit_counts_by_top_directory": self.result.counts_by_top_directory(),
            "unexpected_hits": [hit.__dict__ for hit in self.unexpected_hits],
            "stale_baseline_entries": [
                {
                    "path": entry.path,
                    "kind": entry.kind,
                    "expected_count": entry.count,
                    "actual_count": actual,
                    "reason": entry.reason,
                }
                for entry, actual in self.stale_entries
            ],
        }


def apply_repo_gate_git_environment(env: dict[str, str]) -> None:
    for source, destination in (
        ("SUREAL_REPO_GATE_GIT_DIR", "GIT_DIR"),
        ("SUREAL_REPO_GATE_GIT_WORK_TREE", "GIT_WORK_TREE"),
        ("SUREAL_REPO_GATE_GIT_COMMON_DIR", "GIT_COMMON_DIR"),
    ):
        value = env.get(source)
        if value:
            env[destination] = value
    alternate = env.get("SUREAL_REPO_GATE_GIT_ALTERNATE_OBJECT_DIRECTORIES")
    if alternate:
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = alternate
    primary = env.get("SUREAL_REPO_GATE_GIT_OBJECT_DIRECTORY")
    if primary:
        env["GIT_OBJECT_DIRECTORY"] = primary


def tracked_paths(root: Path) -> list[str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    gate_work_tree = env.get("SUREAL_REPO_GATE_GIT_WORK_TREE") or env.get("SUREAL_REPO_ROOT")
    if gate_work_tree and root.resolve() == Path(gate_work_tree).resolve():
        apply_repo_gate_git_environment(env)
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        env=env,
        check=True,
        stdout=subprocess.PIPE,
    )
    return sorted(
        raw.decode("utf-8", errors="surrogateescape")
        for raw in result.stdout.split(b"\0")
        if raw
    )


def is_retained_record(path: str) -> bool:
    return path.startswith(RETAINED_PREFIXES) or path.endswith(RETAINED_SUFFIXES)


def should_scan_path(path: str) -> bool:
    if set(Path(path).parts) & SKIPPED_DIRS:
        return False
    return not is_retained_record(path)


def allowed_email(value: str) -> bool:
    domain = value.rsplit("@", 1)[-1]
    return value in ALLOWED_EMAILS or domain in ALLOWED_EMAIL_DOMAINS


def _python_text_lines_for_email(text: str) -> set[int]:
    lines = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                lines.update(range(token.start[0], token.end[0] + 1))
    except tokenize.TokenError:
        return set(range(1, len(text.splitlines()) + 1))
    return lines


def scan_text(path: str, text: str) -> list[IdentifierHit]:
    email_lines = _python_text_lines_for_email(text) if path.endswith(".py") else None
    hits = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in PATTERNS.items():
            if (
                kind == "email address"
                and email_lines is not None
                and line_number not in email_lines
            ):
                continue
            for match in pattern.finditer(line):
                if kind == "email address" and allowed_email(match.group(0)):
                    continue
                hits.append(IdentifierHit(path, line_number, match.start() + 1, kind))
    return hits


def scan(root: Path = REPO, paths: Iterable[str] | None = None) -> ScanResult:
    root = Path(root)
    scanned_files = 0
    skipped_binary_files = 0
    skipped_retained_files = 0
    hits: list[IdentifierHit] = []
    for relative in paths if paths is not None else tracked_paths(root):
        if not should_scan_path(relative):
            if is_retained_record(relative):
                skipped_retained_files += 1
            continue
        path = root / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped_binary_files += 1
            continue
        except OSError:
            continue
        scanned_files += 1
        hits.extend(scan_text(relative, text))
    return ScanResult(
        hits=tuple(sorted(hits)),
        scanned_files=scanned_files,
        skipped_binary_files=skipped_binary_files,
        skipped_retained_files=skipped_retained_files,
    )


def load_baseline(path: Path = DEFAULT_BASELINE) -> list[BaselineEntry]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_entries = data.get("allowed") if isinstance(data, Mapping) else None
    if not isinstance(raw_entries, list):
        raise ValueError("baseline must contain an allowed list")
    entries = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_entries:
        if not isinstance(raw, Mapping):
            raise ValueError("baseline entries must be objects")
        path_value = raw.get("path")
        kind = raw.get("kind")
        count = raw.get("count")
        reason = raw.get("reason")
        if not isinstance(path_value, str) or not path_value:
            raise ValueError("baseline entry path must be a non-empty string")
        if kind not in PATTERNS:
            raise ValueError(f"baseline entry has unknown kind: {kind!r}")
        if not isinstance(count, int) or count < 1:
            raise ValueError("baseline entry count must be a positive integer")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("baseline entry reason must be a non-empty string")
        key = (path_value, kind)
        if key in seen:
            raise ValueError(f"duplicate baseline entry: {path_value} {kind}")
        seen.add(key)
        entries.append(BaselineEntry(path_value, kind, count, reason.strip()))
    return entries


def check_against_baseline(
    result: ScanResult, baseline: Iterable[BaselineEntry]
) -> BaselineCheck:
    allowed = {(entry.path, entry.kind): entry for entry in baseline}
    actual_counts = collections.Counter((hit.path, hit.kind) for hit in result.hits)
    stale = []
    for key, entry in sorted(allowed.items()):
        actual = actual_counts.get(key, 0)
        if actual < entry.count:
            stale.append((entry, actual))
    remaining = collections.Counter(actual_counts)
    for key, entry in allowed.items():
        remaining[key] -= entry.count
        if remaining[key] <= 0:
            del remaining[key]
    unexpected = []
    used: collections.Counter[tuple[str, str]] = collections.Counter()
    for hit in result.hits:
        key = (hit.path, hit.kind)
        if used[key] < remaining.get(key, 0):
            unexpected.append(hit)
            used[key] += 1
    return BaselineCheck(
        result=result,
        unexpected_hits=tuple(unexpected),
        stale_entries=tuple(stale),
    )


def format_text_report(check: BaselineCheck) -> str:
    lines = [f"machine identifier scan: {'pass' if check.passed() else 'fail'}"]
    lines.append(f"scanned_text_files: {check.result.scanned_files}")
    lines.append(f"skipped_binary_files: {check.result.skipped_binary_files}")
    lines.append(f"skipped_retained_files: {check.result.skipped_retained_files}")
    lines.append("hit_counts_by_kind:")
    for kind, count in check.result.counts_by_kind().items():
        lines.append(f"  {kind}: {count}")
    lines.append("hit_counts_by_top_directory:")
    for directory, count in check.result.counts_by_top_directory().items():
        lines.append(f"  {directory}: {count}")
    if check.unexpected_hits:
        lines.append("unexpected_hits:")
        lines.extend(f"  {hit.location()}" for hit in check.unexpected_hits[:50])
    if check.stale_entries:
        lines.append("stale_baseline_entries:")
        for entry, actual in check.stale_entries[:50]:
            lines.append(
                f"  {entry.path}: {entry.kind}: expected {entry.count}, actual {actual}"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--no-baseline", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = scan(args.root)
    baseline_path = args.baseline or args.root / DEFAULT_BASELINE.relative_to(REPO)
    baseline = [] if args.no_baseline else load_baseline(baseline_path)
    check = check_against_baseline(result, baseline)
    if args.json:
        print(json.dumps(check.as_jsonable(), indent=2, sort_keys=True))
    else:
        stream = sys.stdout if check.passed() else sys.stderr
        stream.write(format_text_report(check))
    return 0 if check.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
