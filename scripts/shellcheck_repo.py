#!/usr/bin/env python3
"""Run ShellCheck over unpinned tracked shell entry points."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable


RECEIPT_ROOTS = (
    Path("autonomy/research"),
    Path("docs/research"),
)

SOURCE_PIN_FIELDS = frozenset(
    {
        "candidate_hashes",
        "checkpoint_publisher_source_pins",
        "host_source_pins",
        "native_host_source_pins",
        "native_source_hashes",
        "original_verifier_source_pins",
        "resource_source_pins",
        "source_hashes",
        "source_pins",
        "verifier_source_pins",
    }
)


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
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    if root.resolve() == repository_root().resolve():
        apply_repo_gate_git_environment(env)
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", *patterns],
        env=env,
        check=True,
        stdout=subprocess.PIPE,
    )
    return tuple(
        path.decode("utf-8", errors="surrogateescape")
        for path in result.stdout.split(b"\0")
        if path
    )


def tracked_shell_files(root: Path) -> tuple[str, ...]:
    files = set(_git_ls_files(root, ["*.sh"]))
    for hook in _git_ls_files(root, [".githooks"]):
        if "." not in Path(hook).name:
            files.add(hook)
    return tuple(sorted(files))


def _json_paths(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix == ".json":
            yield root
        return
    if root.exists():
        yield from sorted(path for path in root.rglob("*.json") if path.is_file())


def _source_pin_keys(value) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in SOURCE_PIN_FIELDS and isinstance(child, dict):
                yield from (raw for raw in child if isinstance(raw, str))
            yield from _source_pin_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _source_pin_keys(child)


def _path_candidates(raw: str, root: Path) -> Iterable[str]:
    path = Path(raw)
    if path.is_absolute():
        try:
            yield path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
        for marker in (
            "/experiment/",
            "/source/experiment/",
            "/source/gpu/",
            "/source/",
            "/code/",
        ):
            if marker in raw:
                yield raw.split(marker, 1)[1]
    yield raw


def normalize_source_pin_path(raw: str, root: Path, tracked: set[str]) -> str | None:
    for candidate in _path_candidates(raw, root):
        candidate = candidate.lstrip("./")
        if candidate in tracked:
            return candidate
        autonomy_candidate = "autonomy/" + candidate
        if autonomy_candidate in tracked:
            return autonomy_candidate

    basename_matches = sorted(path for path in tracked if Path(path).name == Path(raw).name)
    if len(basename_matches) == 1:
        return basename_matches[0]
    return None


def receipt_pinned_shell_files(root: Path, tracked: Iterable[str] | None = None) -> tuple[str, ...]:
    tracked_set = set(tracked_shell_files(root) if tracked is None else tracked)
    pinned: set[str] = set()
    for receipt_root in RECEIPT_ROOTS:
        for path in _json_paths(root / receipt_root):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for raw in _source_pin_keys(value):
                normalized = normalize_source_pin_path(raw, root, tracked_set)
                if normalized is not None:
                    pinned.add(normalized)
    return tuple(sorted(pinned))


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
