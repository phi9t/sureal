#!/usr/bin/env python3
"""Run ShellCheck over tracked shell entry points."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys

from lint import pinned_sources


@dataclass(frozen=True)
class ShellCheckResult:
    returncode: int
    stdout: str
    stderr: str
    tracked_shell_files: tuple[str, ...]
    excluded_files: tuple[str, ...]
    checked_files: tuple[str, ...]

    @property
    def finding_counts(self) -> Counter[str]:
        return Counter(re.findall(r"SC[0-9]{4}", self.stdout + self.stderr))


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2]


def shellcheck_target_files(root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    targets = pinned_sources.source_targets(root, ("*.sh", ".githooks"))
    tracked = tuple(
        path
        for path in targets.tracked_files
        if path.endswith(".sh") or (path.startswith(".githooks/") and "." not in Path(path).name)
    )
    excluded = tuple(path for path in targets.excluded_files if path in set(tracked))
    return tuple(path for path in tracked if path not in set(excluded)), excluded


def _resolved_executable(path: str) -> str:
    executable = Path(path)
    if executable.is_absolute():
        return str(executable)
    return str((Path.cwd() / executable).resolve())


def run_shellcheck(shellcheck: str, root: Path) -> ShellCheckResult:
    root = root.resolve()
    checked, excluded = shellcheck_target_files(root)
    tracked = tuple(sorted(set(checked) | set(excluded)))
    if not checked:
        return ShellCheckResult(0, "", "", tracked, excluded, checked)

    command = [
        _resolved_executable(shellcheck),
        "-x",
        "-P",
        "SCRIPTDIR",
        "-P",
        ".",
        *checked,
    ]
    result = subprocess.run(
        command,
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return ShellCheckResult(
        result.returncode,
        result.stdout,
        result.stderr,
        tracked,
        excluded,
        checked,
    )


def _print_summary(result: ShellCheckResult) -> None:
    print(f"tracked_shell={len(result.tracked_shell_files)}")
    print(f"excluded_shell={len(result.excluded_files)}")
    print(f"shellcheck_scope={len(result.checked_files)}")
    if result.excluded_files:
        print("excluded:")
        for path in result.excluded_files:
            print(f"  {path}")
    if result.finding_counts:
        print("finding_counts:", file=sys.stderr)
        for rule, count in sorted(result.finding_counts.items()):
            print(f"  {rule} {count}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    parser.add_argument("--shellcheck", required=True)
    parser.add_argument("--list", action="store_true", help="print checked files and exit")
    parser.add_argument("--list-excluded", action="store_true", help="print shell files excluded by archive policy")
    args = parser.parse_args(argv)

    checked, excluded = shellcheck_target_files(args.root)
    if args.list:
        print("\n".join(checked))
        return 0
    if args.list_excluded:
        print("\n".join(excluded))
        return 0

    result = run_shellcheck(args.shellcheck, args.root)
    _print_summary(result)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
