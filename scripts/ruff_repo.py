#!/usr/bin/env python3
"""Run Ruff over unpinned Python sources owned by the repo gate."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Literal, Sequence

try:
    from scripts import pinned_sources
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import pinned_sources  # type: ignore[no-redef]


PYTHON_LINT_PATTERNS = (
    "autonomy/**/*.py",
    "parallax/**/*.py",
    "scripts/**/*.py",
    "scripts/*.py",
)
FORMAT_BATCH_DIRS = (
    "autonomy/association/",
    "autonomy/blob_store/",
)


@dataclass(frozen=True)
class RuffResult:
    mode: str
    returncode: int
    stdout: str
    stderr: str
    tracked_python_files: tuple[str, ...]
    excluded_files: tuple[str, ...]
    checked_files: tuple[str, ...]

    @property
    def finding_counts(self) -> Counter[str]:
        if self.mode != "check":
            return Counter()
        try:
            findings = json.loads(self.stdout or "[]")
        except json.JSONDecodeError:
            return Counter(re.findall(r"\b[A-Z][0-9]{3}\b", self.stdout + self.stderr))
        return Counter(item.get("code") or "syntax" for item in findings)


def repository_root() -> Path:
    return pinned_sources.repository_root()


def _resolved_executable(path: str) -> str:
    executable = Path(path)
    if executable.is_absolute():
        return str(executable)
    return str((Path.cwd() / executable).resolve())


def _format_batch_files(root: Path, targets: pinned_sources.SourceTargets) -> tuple[str, ...]:
    protected = set(targets.excluded_files)
    return tuple(
        path
        for path in targets.tracked_files
        if path not in protected and any(path.startswith(prefix) for prefix in FORMAT_BATCH_DIRS)
    )


def ruff_target_files(root: Path, *, mode: Literal["check", "format"]) -> pinned_sources.SourceTargets:
    targets = pinned_sources.source_targets(root, PYTHON_LINT_PATTERNS)
    if mode == "check":
        return targets
    checked = _format_batch_files(root, targets)
    return pinned_sources.SourceTargets(
        tracked_files=targets.tracked_files,
        receipt_pinned_files=targets.receipt_pinned_files,
        digest_pinned_files=targets.digest_pinned_files,
        current_candidate_files=targets.current_candidate_files,
        frozen_files=targets.frozen_files,
        checked_files=checked,
    )


def _ruff_command(ruff: str, mode: Literal["check", "format"], files: Sequence[str]) -> list[str]:
    if mode == "check":
        return [_resolved_executable(ruff), "check", "--no-cache", "--output-format=json", *files]
    return [_resolved_executable(ruff), "format", "--no-cache", "--check", *files]


def run_ruff(ruff: str, root: Path, *, mode: Literal["check", "format"]) -> RuffResult:
    root = Path(root).resolve()
    targets = ruff_target_files(root, mode=mode)
    if not targets.checked_files:
        return RuffResult(mode, 0, "", "", targets.tracked_files, targets.excluded_files, ())
    result = subprocess.run(
        _ruff_command(ruff, mode, targets.checked_files),
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return RuffResult(
        mode=mode,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        tracked_python_files=targets.tracked_files,
        excluded_files=targets.excluded_files,
        checked_files=targets.checked_files,
    )


def _print_summary(result: RuffResult) -> None:
    print(f"tracked_python={len(result.tracked_python_files)}")
    print(f"excluded_python={len(result.excluded_files)}")
    print(f"ruff_{result.mode}_scope={len(result.checked_files)}")
    counts = result.finding_counts
    if counts:
        print("finding_counts:", file=sys.stderr)
        for rule, count in sorted(counts.items()):
            print(f"  {rule} {count}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    parser.add_argument("--ruff", required=True)
    parser.add_argument("--mode", choices=("check", "format"), default="check")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--list-excluded", action="store_true")
    args = parser.parse_args(argv)

    targets = ruff_target_files(args.root, mode=args.mode)
    if args.list:
        print("\n".join(targets.checked_files))
        return 0
    if args.list_excluded:
        print("\n".join(targets.excluded_files))
        return 0

    result = run_ruff(args.ruff, args.root, mode=args.mode)
    _print_summary(result)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
