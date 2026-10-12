#!/usr/bin/env python3
"""Check shell files against docs/guides/shell-engineering.md mechanical rules."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re

from lint import pinned_sources


SHELL_STYLE_PATTERNS = (
    "autonomy/*.sh",
    "autonomy/**/*.sh",
    "parallax/*.sh",
    "parallax/**/*.sh",
    "harness/*.sh",
    "harness/**/*.sh",
    "scripts/*.sh",
    "scripts/**/*.sh",
)
SCRIPT_SHEBANG = "#!/usr/bin/env bash"
MAX_COLUMNS = 120
DEFAULT_MAX_LINES = 150
FUNCTION_RE = re.compile(
    r"^\s*(?:function\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\(\))?\s*\{"
)


@dataclass(frozen=True)
class ShellStyleBaseline:
    max_lines: int
    grandfathered_long_scripts: dict[str, int]


@dataclass(frozen=True)
class ShellStyleFinding:
    path: str
    line: int
    code: str
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.code}: {self.message}"


@dataclass(frozen=True)
class ShellStyleTargets:
    tracked_shell_files: tuple[str, ...]
    archive_files: tuple[str, ...]
    submodule_files: tuple[str, ...]
    checked_files: tuple[str, ...]

    @property
    def excluded_files(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.archive_files) | set(self.submodule_files)))


@dataclass(frozen=True)
class ShellStyleResult:
    targets: ShellStyleTargets
    baseline: ShellStyleBaseline
    findings: tuple[ShellStyleFinding, ...]

    @property
    def returncode(self) -> int:
        return 1 if self.findings else 0

    @property
    def finding_counts(self) -> Counter[str]:
        return Counter(finding.code for finding in self.findings)

    def format_findings(self) -> str:
        return "\n".join(finding.format() for finding in self.findings)


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2]


def shell_style_targets(root: Path) -> ShellStyleTargets:
    targets = pinned_sources.source_targets(root, SHELL_STYLE_PATTERNS)
    return ShellStyleTargets(
        tracked_shell_files=targets.tracked_files,
        archive_files=targets.archive_files,
        submodule_files=targets.submodule_files,
        checked_files=targets.checked_files,
    )


def load_baseline(path: Path) -> ShellStyleBaseline:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ShellStyleBaseline(DEFAULT_MAX_LINES, {})
    max_lines = data.get("max_lines", DEFAULT_MAX_LINES)
    if not isinstance(max_lines, int) or max_lines < 1:
        raise ValueError("shell style baseline max_lines must be a positive integer")
    raw_entries = data.get("grandfathered_long_scripts", {})
    if not isinstance(raw_entries, dict):
        raise ValueError("shell style baseline grandfathered_long_scripts must be an object")
    entries: dict[str, int] = {}
    for path_key, entry in raw_entries.items():
        if not isinstance(path_key, str):
            raise ValueError("shell style baseline paths must be strings")
        if not isinstance(entry, dict):
            raise ValueError(f"shell style baseline entry for {path_key} must be an object")
        lines = entry.get("lines")
        reason = entry.get("reason")
        if not isinstance(lines, int) or lines < max_lines + 1:
            raise ValueError(f"shell style baseline entry for {path_key} has invalid lines")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"shell style baseline entry for {path_key} needs a reason")
        entries[path_key] = lines
    return ShellStyleBaseline(max_lines=max_lines, grandfathered_long_scripts=entries)


def _has_header_comment(lines: Sequence[str]) -> bool:
    for raw in lines[1:5]:
        stripped = raw.strip()
        if not stripped:
            continue
        if not stripped.startswith("#"):
            return False
        if stripped != "#":
            return True
    return False


def _previous_meaningful_line_is_comment(lines: Sequence[str], index: int) -> bool:
    cursor = index - 1
    while cursor >= 0 and not lines[cursor].strip():
        cursor -= 1
    return cursor >= 0 and lines[cursor].lstrip().startswith("#")


def _line_count_findings(
    path: str,
    line_count: int,
    baseline: ShellStyleBaseline,
) -> Iterable[ShellStyleFinding]:
    grandfathered = baseline.grandfathered_long_scripts.get(path)
    if line_count <= baseline.max_lines:
        if grandfathered is not None:
            yield ShellStyleFinding(
                path,
                line_count,
                "stale-length-baseline",
                "script is no longer over the shell length limit; remove it from the baseline",
            )
        return

    if grandfathered is None:
        yield ShellStyleFinding(
            path,
            line_count,
            "line-count",
            f"script has {line_count} lines, above the {baseline.max_lines}-line limit",
        )
    elif line_count < grandfathered:
        yield ShellStyleFinding(
            path,
            line_count,
            "stale-length-baseline",
            f"script shrank from {grandfathered} to {line_count} lines; shrink the baseline",
        )
    elif line_count > grandfathered:
        yield ShellStyleFinding(
            path,
            line_count,
            "line-count",
            f"script grew from grandfathered {grandfathered} to {line_count} lines",
        )


def _check_file(path: str, root: Path, baseline: ShellStyleBaseline) -> tuple[ShellStyleFinding, ...]:
    full_path = root / path
    lines = full_path.read_text(encoding="utf-8").splitlines()
    findings: list[ShellStyleFinding] = []
    shebang = lines[0] if lines else ""
    if shebang != SCRIPT_SHEBANG:
        findings.append(
            ShellStyleFinding(path, 1, "shebang", f"expected {SCRIPT_SHEBANG!r}")
        )
    if not _has_header_comment(lines):
        findings.append(
            ShellStyleFinding(path, 2, "header-comment", "expected a non-empty file header comment after shebang")
        )
    for index, line in enumerate(lines, start=1):
        if len(line) > MAX_COLUMNS:
            findings.append(
                ShellStyleFinding(path, index, "line-length", f"line has {len(line)} columns, above {MAX_COLUMNS}")
            )
        if "`" in line:
            findings.append(ShellStyleFinding(path, index, "backticks", "use $(...) instead of backticks"))
        match = FUNCTION_RE.match(line)
        if match and not _previous_meaningful_line_is_comment(lines, index - 1):
            findings.append(
                ShellStyleFinding(
                    path,
                    index,
                    "function-comment",
                    f"function {match.group('name')} needs a preceding comment",
                )
            )
    findings.extend(_line_count_findings(path, len(lines), baseline))
    return tuple(findings)


def check_repository(root: Path, *, baseline_path: Path | None = None) -> ShellStyleResult:
    root = Path(root).resolve()
    baseline = load_baseline(baseline_path or root / "harness" / "lint" / "shell_style_baseline.json")
    targets = shell_style_targets(root)
    findings = []
    checked_set = set(targets.checked_files)
    for path in targets.checked_files:
        findings.extend(_check_file(path, root, baseline))
    for path in sorted(set(baseline.grandfathered_long_scripts) - checked_set):
        findings.append(
            ShellStyleFinding(
                path,
                1,
                "stale-length-baseline",
                "baseline entry no longer belongs to the checked shell-style scope",
            )
        )
    return ShellStyleResult(targets=targets, baseline=baseline, findings=tuple(findings))


def _print_summary(result: ShellStyleResult) -> None:
    targets = result.targets
    print(f"tracked_shell_style={len(targets.tracked_shell_files)}")
    print(f"archive_shell_style={len(targets.archive_files)}")
    print(f"submodule_shell_style={len(targets.submodule_files)}")
    print(f"shell_style_scope={len(targets.checked_files)}")
    print(f"grandfathered_long_scripts={len(result.baseline.grandfathered_long_scripts)}")
    if targets.excluded_files:
        print("excluded:")
        for path in targets.excluded_files:
            print(f"  {path}")
    if result.finding_counts:
        print("finding_counts:")
        for code, count in sorted(result.finding_counts.items()):
            print(f"  {code} {count}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--list", action="store_true", help="print checked shell files and exit")
    parser.add_argument("--list-excluded", action="store_true", help="print shell files excluded by archive policy")
    parser.add_argument("--summary-json", action="store_true", help="print a machine-readable summary")
    args = parser.parse_args(argv)

    result = check_repository(args.root, baseline_path=args.baseline)
    if args.list:
        print("\n".join(result.targets.checked_files))
        return 0
    if args.list_excluded:
        print("\n".join(result.targets.excluded_files))
        return 0
    if args.summary_json:
        print(
            json.dumps(
                {
                    "tracked_shell_style": len(result.targets.tracked_shell_files),
                    "archive_shell_style": len(result.targets.archive_files),
                    "submodule_shell_style": len(result.targets.submodule_files),
                    "shell_style_scope": len(result.targets.checked_files),
                    "grandfathered_long_scripts": len(result.baseline.grandfathered_long_scripts),
                    "finding_counts": dict(sorted(result.finding_counts.items())),
                    "finding_count": len(result.findings),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        _print_summary(result)
        if result.findings:
            print(result.format_findings())
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
