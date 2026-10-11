#!/usr/bin/env python3
"""Run clang-format over tracked active C++ sources."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
from collections.abc import Sequence

try:
    from scripts import pinned_sources
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import pinned_sources  # type: ignore[no-redef]


CPP_FORMAT_PATTERNS = (
    "autonomy/**/*.cc",
    "autonomy/**/*.hh",
    "autonomy/**/*.cu",
    "autonomy/**/*.cuh",
    "parallax/**/*.cc",
    "parallax/**/*.hh",
    "parallax/**/*.cu",
    "parallax/**/*.cuh",
)
CLANG_FORMAT_BATCH_PREFIXES = (
    "autonomy/insula/",
    "parallax/insulas/orb-slam/",
)

@dataclass(frozen=True)
class ClangFormatTargets:
    tracked_cpp_files: tuple[str, ...]
    archive_files: tuple[str, ...]
    submodule_files: tuple[str, ...]
    checked_files: tuple[str, ...]

    @property
    def excluded_files(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.archive_files) | set(self.submodule_files)))


@dataclass(frozen=True)
class ClangFormatResult:
    returncode: int
    stdout: str
    stderr: str
    targets: ClangFormatTargets

    @property
    def tracked_cpp_files(self) -> tuple[str, ...]:
        return self.targets.tracked_cpp_files

    @property
    def excluded_files(self) -> tuple[str, ...]:
        return self.targets.excluded_files

    @property
    def checked_files(self) -> tuple[str, ...]:
        return self.targets.checked_files

    @property
    def format_violation_count(self) -> int:
        output = self.stdout + self.stderr
        paths = re.findall(r"(?m)^([^:\n]+):[0-9]+:[0-9]+: error: code should be clang-formatted", output)
        return len(set(paths))

    @property
    def diagnostic_counts(self) -> Counter[str]:
        output = self.stdout + self.stderr
        return Counter(re.findall(r"\[-W[^\]]+\]", output))


def repository_root() -> Path:
    return pinned_sources.repository_root()


def _resolved_executable(path: str) -> str:
    executable = Path(path)
    if executable.is_absolute():
        return str(executable)
    return str((Path.cwd() / executable).resolve())


def clang_format_targets(root: Path) -> ClangFormatTargets:
    registry_targets = pinned_sources.source_targets(root, CPP_FORMAT_PATTERNS)
    excluded = set(registry_targets.excluded_files)
    checked = tuple(
        path
        for path in registry_targets.tracked_files
        if path not in excluded and any(path.startswith(prefix) for prefix in CLANG_FORMAT_BATCH_PREFIXES)
    )
    return ClangFormatTargets(
        tracked_cpp_files=registry_targets.tracked_files,
        archive_files=registry_targets.archive_files,
        submodule_files=registry_targets.submodule_files,
        checked_files=checked,
    )


def _clang_format_command(clang_format: str, files: Sequence[str], *, fix: bool) -> list[str]:
    command = [_resolved_executable(clang_format), "--style=file"]
    if fix:
        command.append("-i")
    else:
        command.extend(["--dry-run", "--Werror"])
    command.extend(files)
    return command


def run_clang_format(
    clang_format: str,
    root: Path,
    *,
    fix: bool = False,
) -> ClangFormatResult:
    root = Path(root).resolve()
    targets = clang_format_targets(root)
    if not targets.checked_files:
        return ClangFormatResult(0, "", "", targets)
    result = subprocess.run(
        _clang_format_command(clang_format, targets.checked_files, fix=fix),
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return ClangFormatResult(result.returncode, result.stdout, result.stderr, targets)


def _print_summary(result: ClangFormatResult) -> None:
    targets = result.targets
    print(f"tracked_cpp={len(targets.tracked_cpp_files)}")
    print(f"archive_cpp={len(targets.archive_files)}")
    print(f"submodule_cpp={len(targets.submodule_files)}")
    print(f"clang_format_scope={len(targets.checked_files)}")
    if targets.excluded_files:
        print("excluded:")
        for path in targets.excluded_files:
            print(f"  {path}")
    counts = result.diagnostic_counts
    if counts:
        print("diagnostic_counts:", file=sys.stderr)
        for diagnostic, count in sorted(counts.items()):
            print(f"  {diagnostic} {count}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    parser.add_argument("--clang-format", required=True)
    parser.add_argument("--fix", action="store_true", help="rewrite checked C++ files in place")
    parser.add_argument("--list", action="store_true", help="print checked C++ files and exit")
    parser.add_argument("--list-excluded", action="store_true", help="print C++ files excluded by archive policy")
    args = parser.parse_args(argv)

    targets = clang_format_targets(args.root)
    if args.list:
        print("\n".join(targets.checked_files))
        return 0
    if args.list_excluded:
        print("\n".join(targets.excluded_files))
        return 0

    result = run_clang_format(args.clang_format, args.root, fix=args.fix)
    _print_summary(result)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
