#!/usr/bin/env python3
"""Run shfmt over unpinned tracked shell scripts in active source roots."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
from collections.abc import Sequence

try:
    from scripts import pinned_sources
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import pinned_sources  # type: ignore[no-redef]


SHFMT_PATTERNS = (
    "autonomy/*.sh",
    "autonomy/**/*.sh",
    "parallax/*.sh",
    "parallax/**/*.sh",
    "scripts/*.sh",
    "scripts/**/*.sh",
)
SHFMT_FLAGS = ("-i", "2", "-ci", "-bn")


@dataclass(frozen=True)
class ShfmtTargets:
    tracked_shell_files: tuple[str, ...]
    receipt_pinned_files: tuple[str, ...]
    digest_pinned_files: tuple[str, ...]
    current_candidate_files: tuple[str, ...]
    frozen_files: tuple[str, ...]
    checked_files: tuple[str, ...]

    @property
    def protected_files(self) -> tuple[str, ...]:
        return tuple(
            sorted(set(self.receipt_pinned_files) | set(self.digest_pinned_files) | set(self.current_candidate_files))
        )

    @property
    def excluded_files(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.protected_files) | set(self.frozen_files)))


@dataclass(frozen=True)
class ShfmtResult:
    returncode: int
    stdout: str
    stderr: str
    targets: ShfmtTargets

    @property
    def tracked_shell_files(self) -> tuple[str, ...]:
        return self.targets.tracked_shell_files

    @property
    def excluded_files(self) -> tuple[str, ...]:
        return self.targets.excluded_files

    @property
    def checked_files(self) -> tuple[str, ...]:
        return self.targets.checked_files

    @property
    def format_violation_count(self) -> int:
        return len([line for line in self.stdout.splitlines() if line.strip()])


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1]


def _resolved_executable(path: str) -> str:
    executable = Path(path)
    if executable.is_absolute():
        return str(executable)
    return str((Path.cwd() / executable).resolve())


def shfmt_targets(root: Path) -> ShfmtTargets:
    targets = pinned_sources.source_targets(root, SHFMT_PATTERNS)
    return ShfmtTargets(
        tracked_shell_files=targets.tracked_files,
        receipt_pinned_files=targets.receipt_pinned_files,
        digest_pinned_files=targets.digest_pinned_files,
        current_candidate_files=targets.current_candidate_files,
        frozen_files=targets.frozen_files,
        checked_files=targets.checked_files,
    )


def _shfmt_command(shfmt: str, files: Sequence[str], *, fix: bool) -> list[str]:
    command = [_resolved_executable(shfmt), *SHFMT_FLAGS]
    command.append("-w" if fix else "-l")
    command.extend(files)
    return command


def run_shfmt(shfmt: str, root: Path, *, fix: bool = False) -> ShfmtResult:
    root = Path(root).resolve()
    targets = shfmt_targets(root)
    if not targets.checked_files:
        return ShfmtResult(0, "", "", targets)
    result = subprocess.run(
        _shfmt_command(shfmt, targets.checked_files, fix=fix),
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    returncode = result.returncode
    if not fix and result.returncode == 0 and result.stdout.strip():
        returncode = 1
    return ShfmtResult(returncode, result.stdout, result.stderr, targets)


def _print_summary(result: ShfmtResult) -> None:
    targets = result.targets
    print(f"tracked_shfmt_shell={len(targets.tracked_shell_files)}")
    print(f"protected_shfmt_shell={len(targets.protected_files)}")
    print(f"frozen_shfmt_shell={len(targets.frozen_files)}")
    print(f"shfmt_scope={len(targets.checked_files)}")
    if targets.excluded_files:
        print("excluded:")
        for path in targets.excluded_files:
            print(f"  {path}")
    if result.format_violation_count:
        print(f"format_violations={result.format_violation_count}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    parser.add_argument("--shfmt", required=True)
    parser.add_argument("--fix", action="store_true", help="rewrite checked shell files in place")
    parser.add_argument("--list", action="store_true", help="print checked shell files and exit")
    parser.add_argument("--list-excluded", action="store_true", help="print source-pin excluded shell files")
    args = parser.parse_args(argv)

    targets = shfmt_targets(args.root)
    if args.list:
        print("\n".join(targets.checked_files))
        return 0
    if args.list_excluded:
        print("\n".join(targets.excluded_files))
        return 0

    result = run_shfmt(args.shfmt, args.root, fix=args.fix)
    _print_summary(result)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
