#!/usr/bin/env python3
"""Run ShellCheck over unpinned tracked shell entry points."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable

try:
    from scripts import pinned_sources
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import pinned_sources  # type: ignore[no-redef]


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


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1]


def _git_ls_files(root: Path, patterns: Iterable[str]) -> tuple[str, ...]:
    return pinned_sources.git_ls_files(root, tuple(patterns))


def tracked_shell_files(root: Path) -> tuple[str, ...]:
    files = set(_git_ls_files(root, ["*.sh"]))
    for hook in _git_ls_files(root, [".githooks"]):
        if "." not in Path(hook).name:
            files.add(hook)
    return tuple(sorted(files))


def receipt_pinned_shell_files(root: Path, tracked: Iterable[str] | None = None) -> tuple[str, ...]:
    tracked_set = set(tracked_shell_files(root) if tracked is None else tracked)
    return tuple(path for path in pinned_sources.protected_source_paths(root, tracked_set) if path in tracked_set)


def shellcheck_target_files(root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    tracked = tracked_shell_files(root)
    excluded = receipt_pinned_shell_files(root, tracked)
    return tuple(path for path in tracked if path not in set(excluded)), excluded


def _resolved_executable(path: str) -> str:
    executable = Path(path)
    if executable.is_absolute():
        return str(executable)
    return str((Path.cwd() / executable).resolve())


def run_shellcheck(shellcheck: str, root: Path) -> ShellCheckResult:
    root = root.resolve()
    tracked = tracked_shell_files(root)
    checked, excluded = shellcheck_target_files(root)
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
    print(f"receipt_pinned_shell={len(result.excluded_files)}")
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
    parser.add_argument("--list-excluded", action="store_true", help="print receipt-pinned shell files and exit")
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
