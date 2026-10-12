#!/usr/bin/env python3
"""Check active C++ and CUDA files against Sureal's mechanical rules."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from lint import pinned_sources


ALLOWED_SUFFIXES = (".cc", ".hh", ".cu", ".cuh")
FORBIDDEN_SUFFIXES = (".cpp", ".h", ".hpp", ".hxx")
HEADER_SUFFIXES = (".hh", ".cuh")
CXX_PATTERNS = tuple(
    pattern
    for root in ("autonomy", "parallax")
    for suffix in (*ALLOWED_SUFFIXES, *FORBIDDEN_SUFFIXES)
    for pattern in (f"{root}/*{suffix}", f"{root}/**/*{suffix}")
)
BASELINE_PATH = Path("harness/lint/cxx_lint_baseline.json")
OWNERSHIP_WORDS = ("owns", "ownership")
MAX_COLUMNS = 120
ProblemKey = tuple[str, int, str]

CV_QUALIFIERS = r"(?:(?:const|volatile)\s+)*"
SCALAR_TYPES = (
    r"bool",
    r"char",
    r"signed\s+char",
    r"unsigned\s+char",
    r"short",
    r"signed\s+short",
    r"unsigned\s+short",
    r"int",
    r"signed\s+int",
    r"unsigned\s+int",
    r"long",
    r"signed\s+long",
    r"unsigned\s+long",
    r"long\s+long",
    r"signed\s+long\s+long",
    r"unsigned\s+long\s+long",
    r"float",
    r"double",
    r"long\s+double",
    r"size_t",
    r"std::size_t",
    r"ssize_t",
    r"ptrdiff_t",
    r"std::ptrdiff_t",
    r"int8_t",
    r"uint8_t",
    r"int16_t",
    r"uint16_t",
    r"int32_t",
    r"uint32_t",
    r"int64_t",
    r"uint64_t",
    r"std::int8_t",
    r"std::uint8_t",
    r"std::int16_t",
    r"std::uint16_t",
    r"std::int32_t",
    r"std::uint32_t",
    r"std::int64_t",
    r"std::uint64_t",
)
SCALAR_TYPE_RE = rf"{CV_QUALIFIERS}(?:{'|'.join(SCALAR_TYPES)})(?:\s*(?:\*|&)\s*)*"
VOID_POINTER_TYPE_RE = rf"{CV_QUALIFIERS}void(?:\s*\*)+"
CAST_TYPE_RE = rf"(?:{SCALAR_TYPE_RE}|{VOID_POINTER_TYPE_RE})"
CAST_RE = re.compile(rf"\(\s*{CAST_TYPE_RE}\s*\)\s*[A-Za-z_(]")
USING_NAMESPACE_RE = re.compile(r"\busing\s+namespace\b")
NULL_RE = re.compile(r"\bNULL\b")
PLAIN_ENUM_RE = re.compile(r"\benum\s+(?!class\b)")
RAW_NEW_RE = re.compile(r"\bnew\s+")
RAW_DELETE_RE = re.compile(r"\bdelete(?![A-Za-z0-9_])\s*(?:\[\]\s*)?")
NAMESPACE_PREFIX_RE = re.compile(r"(?:^|[;{}]\s*)(?:inline\s+)?namespace(?:\s+[A-Za-z_][A-Za-z0-9_:]*)?\s*$")
NAMESPACE_LINE_RE = re.compile(r"^(?:inline\s+)?namespace(?:\s+[A-Za-z_][A-Za-z0-9_:]*)?\s*$")
EXTERN_PREFIX_RE = re.compile(r'(?:^|[;{}]\s*)extern\s+"C(?:\+\+)?"\s*$')
EXTERN_LINE_RE = re.compile(r'^extern\s+"C(?:\+\+)?"\s*$')


@dataclass(frozen=True)
class CxxFinding:
    path: str
    line: int
    code: str
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.code}: {self.message}"


@dataclass(frozen=True)
class CxxTargets:
    tracked_cxx_files: tuple[str, ...]
    archive_files: tuple[str, ...]
    submodule_files: tuple[str, ...]
    checked_files: tuple[str, ...]

    @property
    def excluded_files(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.archive_files) | set(self.submodule_files)))


@dataclass(frozen=True)
class CxxResult:
    targets: CxxTargets
    findings: tuple[CxxFinding, ...]
    baseline: dict[ProblemKey, str]
    unexpected: tuple[CxxFinding, ...]
    stale_baseline: tuple[ProblemKey, ...]

    @property
    def returncode(self) -> int:
        return 1 if self.unexpected or self.stale_baseline else 0

    @property
    def finding_counts(self) -> Counter[str]:
        return Counter(finding.code for finding in self.findings)

    def format_findings(self) -> str:
        lines = [finding.format() for finding in self.unexpected]
        lines.extend(f"stale C++ lint baseline entry: {_format_key(key)}" for key in self.stale_baseline)
        return "\n".join(lines)


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2]


def cxx_targets(root: Path) -> CxxTargets:
    targets = pinned_sources.source_targets(root, CXX_PATTERNS)
    return CxxTargets(
        tracked_cxx_files=targets.tracked_files,
        archive_files=targets.archive_files,
        submodule_files=targets.submodule_files,
        checked_files=targets.checked_files,
    )


def _scan_lines(source: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    code_lines: list[str] = []
    comment_lines: list[str] = []
    code: list[str] = []
    comment: list[str] = []
    state = "code"
    raw_end = ""
    index = 0

    while index < len(source):
        char = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""

        if char == "\n":
            code_lines.append("".join(code))
            comment_lines.append("".join(comment))
            code = []
            comment = []
            if state == "line_comment":
                state = "code"
            index += 1
            continue

        if state == "code":
            if char == "/" and nxt == "/":
                code.extend("  ")
                comment.extend("//")
                state = "line_comment"
                index += 2
            elif char == "/" and nxt == "*":
                code.extend("  ")
                comment.extend("/*")
                state = "block_comment"
                index += 2
            elif char == "R" and nxt == '"':
                delimiter_end = source.find("(", index + 2, index + 18)
                if delimiter_end != -1:
                    delimiter = source[index + 2 : delimiter_end]
                    raw_end = ")" + delimiter + '"'
                    code.extend(" " * (delimiter_end - index + 1))
                    state = "raw_string"
                    index = delimiter_end + 1
                else:
                    code.append(char)
                    index += 1
            elif char == '"':
                code.append(" ")
                state = "string"
                index += 1
            elif char == "'":
                code.append(" ")
                state = "char"
                index += 1
            else:
                code.append(char)
                index += 1
        elif state == "line_comment":
            code.append(" ")
            comment.append(char)
            index += 1
        elif state == "block_comment":
            if char == "*" and nxt == "/":
                code.extend("  ")
                comment.extend("*/")
                state = "code"
                index += 2
            else:
                code.append(" ")
                comment.append(char)
                index += 1
        elif state == "string":
            if char == "\\" and nxt:
                code.extend("  ")
                index += 2
            elif char == '"':
                code.append(" ")
                state = "code"
                index += 1
            else:
                code.append(" ")
                index += 1
        elif state == "char":
            if char == "\\" and nxt:
                code.extend("  ")
                index += 2
            elif char == "'":
                code.append(" ")
                state = "code"
                index += 1
            else:
                code.append(" ")
                index += 1
        elif state == "raw_string":
            if raw_end and source.startswith(raw_end, index):
                code.extend(" " * len(raw_end))
                index += len(raw_end)
                raw_end = ""
                state = "code"
            else:
                code.append(" ")
                index += 1

    if code or comment or (source and not source.endswith("\n")):
        code_lines.append("".join(code))
        comment_lines.append("".join(comment))
    return tuple(code_lines), tuple(comment_lines)


def _has_ownership_comment(comment_lines: Sequence[str], line_index: int) -> bool:
    first = max(0, line_index - 2)
    text = "\n".join(comment_lines[first : line_index + 1]).lower()
    return any(word in text for word in OWNERSHIP_WORDS)


def _classify_open_brace(prefix: str, pending: str | None) -> tuple[str, str | None]:
    if pending is not None:
        return pending, None
    stripped = prefix.strip()
    if NAMESPACE_PREFIX_RE.search(stripped) or EXTERN_PREFIX_RE.search(stripped):
        return "namespace", None
    return "block", None


def _pending_scope_kind(code: str) -> str | None:
    stripped = code.strip()
    if not stripped or "{" in stripped:
        return None
    if NAMESPACE_LINE_RE.match(stripped) or EXTERN_LINE_RE.match(stripped):
        return "namespace"
    return None


def _advance_scope(code: str, stack: list[str], pending: str | None) -> str | None:
    for index, char in enumerate(code):
        if char == "{":
            kind, pending = _classify_open_brace(code[:index], pending)
            stack.append(kind)
        elif char == "}":
            if stack:
                stack.pop()
            pending = None
    return _pending_scope_kind(code) or pending


def _using_namespace_findings(path: str, suffix: str, code_lines: Sequence[str]) -> Iterable[CxxFinding]:
    stack: list[str] = []
    pending: str | None = None
    header = suffix in HEADER_SUFFIXES

    for line_number, code in enumerate(code_lines, start=1):
        cursor = 0
        for match in USING_NAMESPACE_RE.finditer(code):
            pending = _advance_scope(code[cursor : match.start()], stack, pending)
            cursor = match.start()
            in_block_scope = any(kind != "namespace" for kind in stack)
            if header or not in_block_scope:
                message = "do not use using namespace in headers or at file scope"
                yield CxxFinding(path, line_number, "using-namespace", message)
        pending = _advance_scope(code[cursor:], stack, pending)


def _check_file(path: str, root: Path) -> tuple[CxxFinding, ...]:
    suffix = Path(path).suffix
    findings: list[CxxFinding] = []
    if suffix in FORBIDDEN_SUFFIXES:
        findings.append(
            CxxFinding(path, 1, "forbidden-suffix", "use .cc, .hh, .cu or .cuh for C++ and CUDA")
        )
        return tuple(findings)

    source = (root / path).read_text(encoding="utf-8")
    code_lines, comment_lines = _scan_lines(source)
    if suffix in HEADER_SUFFIXES and not any(line.strip() == "#pragma once" for line in code_lines):
        findings.append(CxxFinding(path, 1, "pragma-once", "headers must start with #pragma once"))

    for number, raw_line in enumerate(source.splitlines(), start=1):
        if len(raw_line) > MAX_COLUMNS:
            findings.append(
                CxxFinding(path, number, "line-length", f"line has {len(raw_line)} columns, above {MAX_COLUMNS}")
            )

    findings.extend(_using_namespace_findings(path, suffix, code_lines))

    for number, code in enumerate(code_lines, start=1):
        if NULL_RE.search(code):
            findings.append(CxxFinding(path, number, "null", "use nullptr instead of NULL"))
        if PLAIN_ENUM_RE.search(code):
            findings.append(CxxFinding(path, number, "plain-enum", "use enum class instead of plain enum"))
        if CAST_RE.search(code):
            findings.append(CxxFinding(path, number, "c-style-cast", "use an explicit C++ cast"))
        if RAW_NEW_RE.search(code) and "operator new" not in code and not _has_ownership_comment(comment_lines, number - 1):
            message = "raw new requires a nearby owns/ownership comment"
            findings.append(CxxFinding(path, number, "raw-new", message))
        if (
            RAW_DELETE_RE.search(code)
            and "= delete" not in code
            and "operator delete" not in code
            and not _has_ownership_comment(comment_lines, number - 1)
        ):
            message = "raw delete requires a nearby owns/ownership comment"
            findings.append(CxxFinding(path, number, "raw-delete", message))

    return tuple(findings)


def _digest_files(root: Path, paths: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        full_path = root / path
        digest.update(path.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        if full_path.is_file():
            digest.update(hashlib.sha256(full_path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def problem_key(finding: CxxFinding) -> ProblemKey:
    return (finding.path, finding.line, finding.code)


def _format_key(key: ProblemKey) -> str:
    path, line, code = key
    return f"{path}:{line}: {code}"


def read_baseline(path: Path) -> dict[ProblemKey, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"{path}: C++ lint baseline must have version 1")
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: C++ lint baseline entries must be a list")
    baseline: dict[ProblemKey, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: baseline entry {index} must be an object")
        relative = entry.get("path")
        line = entry.get("line")
        code = entry.get("kind")
        reason = entry.get("reason")
        message = entry.get("message")
        if (
            not isinstance(relative, str)
            or not isinstance(line, int)
            or line < 1
            or not isinstance(code, str)
            or not isinstance(reason, str)
            or not reason.strip()
            or not isinstance(message, str)
            or not message.strip()
        ):
            raise ValueError(f"{path}: invalid C++ lint baseline entry {index}")
        key = (relative, line, code)
        if key in baseline:
            raise ValueError(f"{path}: duplicate C++ lint baseline entry {_format_key(key)}")
        baseline[key] = message
    return baseline


def check_repository(root: Path, *, baseline_path: Path | None = None) -> CxxResult:
    root = Path(root).resolve()
    targets = cxx_targets(root)
    findings: list[CxxFinding] = []
    for path in targets.checked_files:
        findings.extend(_check_file(path, root))
    baseline = read_baseline(root / BASELINE_PATH if baseline_path is None else baseline_path)
    finding_keys = {problem_key(finding) for finding in findings}
    unexpected = tuple(
        finding for finding in findings if baseline.get(problem_key(finding)) != finding.message
    )
    stale = tuple(sorted(set(baseline) - finding_keys))
    return CxxResult(
        targets=targets,
        findings=tuple(findings),
        baseline=baseline,
        unexpected=unexpected,
        stale_baseline=stale,
    )


def _summary(result: CxxResult, root: Path) -> dict[str, object]:
    return {
        "tracked_cxx": len(result.targets.tracked_cxx_files),
        "archive_cxx": len(result.targets.archive_files),
        "submodule_cxx": len(result.targets.submodule_files),
        "cxx_lint_scope": len(result.targets.checked_files),
        "finding_count": len(result.findings),
        "unexpected_count": len(result.unexpected),
        "baseline_count": len(result.findings) - len(result.unexpected),
        "stale_baseline_count": len(result.stale_baseline),
        "finding_counts": dict(sorted(result.finding_counts.items())),
        "checked_digest": _digest_files(root, result.targets.checked_files),
        "excluded_digest": _digest_files(root, result.targets.excluded_files),
    }


def _print_summary(result: CxxResult, root: Path) -> None:
    summary = _summary(result, root)
    for key in (
        "tracked_cxx",
        "archive_cxx",
        "submodule_cxx",
        "cxx_lint_scope",
        "finding_count",
        "unexpected_count",
        "baseline_count",
        "stale_baseline_count",
        "checked_digest",
        "excluded_digest",
    ):
        print(f"{key}={summary[key]}")
    if result.targets.excluded_files:
        print("excluded:")
        for path in result.targets.excluded_files:
            print(f"  {path}")
    if result.finding_counts:
        print("finding_counts:")
        for code, count in sorted(result.finding_counts.items()):
            print(f"  {code} {count}")


def render_baseline(findings: Sequence[CxxFinding]) -> str:
    entries = [
        {
            "path": finding.path,
            "line": finding.line,
            "kind": finding.code,
            "message": finding.message,
            "reason": "existing source-frozen C++ issue exposed when lint-side source freeze was retired",
        }
        for finding in findings
    ]
    return json.dumps({"version": 1, "entries": entries}, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--list", action="store_true", help="print checked C++ files and exit")
    parser.add_argument("--list-excluded", action="store_true", help="print C++ files excluded by policy")
    parser.add_argument("--print-baseline", action="store_true", help="print a baseline for current findings")
    parser.add_argument("--summary-json", action="store_true", help="print a machine-readable summary")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    baseline_path = args.baseline
    if args.print_baseline and baseline_path is None:
        baseline_path = root / "harness" / "lint" / ".missing-cxx-lint-baseline.json"
    result = check_repository(root, baseline_path=baseline_path)
    if args.list:
        print("\n".join(result.targets.checked_files))
        return 0
    if args.list_excluded:
        print("\n".join(result.targets.excluded_files))
        return 0
    if args.print_baseline:
        print(render_baseline(result.findings), end="")
        return 0
    if args.summary_json:
        print(json.dumps(_summary(result, root), indent=2, sort_keys=True))
    else:
        _print_summary(result, root)
        if result.findings:
            print(result.format_findings())
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
