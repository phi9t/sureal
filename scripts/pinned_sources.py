#!/usr/bin/env python3
"""Discover tracked source files excluded from active repo-gate lint."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import subprocess


ARCHIVE_PREFIXES = (
    "autonomy/research/",
    "parallax/research/",
)
PROCEDURE_RECORD_PARTS = (
    ("autonomy", "studies", "*", "procedure_records"),
    ("parallax", "studies", "*", "procedure_records"),
)
ARCHITECTURE_HARNESS_PREFIXES = (
    ("autonomy", "studies", "architecture", "harness"),
    ("parallax", "studies", "architecture", "harness"),
)


@dataclass(frozen=True)
class SourceTargets:
    tracked_files: tuple[str, ...]
    archive_files: tuple[str, ...]
    submodule_files: tuple[str, ...]
    checked_files: tuple[str, ...]

    @property
    def excluded_files(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.archive_files) | set(self.submodule_files)))


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


def git_environment(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    gate_work_tree = env.get("SUREAL_REPO_GATE_GIT_WORK_TREE") or env.get("SUREAL_REPO_ROOT")
    if gate_work_tree:
        try:
            if Path(gate_work_tree).resolve(strict=False) == Path(root).resolve(strict=False):
                apply_repo_gate_git_environment(env)
        except OSError:
            pass
    return env


def _fallback_paths(root: Path, patterns: Sequence[str]) -> tuple[str, ...]:
    if not patterns:
        patterns = ("**/*",)
    paths: set[str] = set()
    for pattern in patterns:
        candidate = root / pattern
        if candidate.is_file():
            paths.add(candidate.relative_to(root).as_posix())
        elif candidate.is_dir():
            paths.update(path.relative_to(root).as_posix() for path in candidate.rglob("*") if path.is_file())
        else:
            paths.update(path.relative_to(root).as_posix() for path in root.glob(pattern) if path.is_file())
    return tuple(sorted(paths))


def git_ls_files(root: Path, patterns: Sequence[str] = ()) -> tuple[str, ...]:
    command = ["git", "-C", str(root), "ls-files", "-z"]
    if patterns:
        command.extend(["--", *patterns])
    try:
        result = subprocess.run(
            command,
            env=git_environment(root),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _fallback_paths(root, patterns)
    return tuple(sorted(raw.decode("utf-8", errors="surrogateescape") for raw in result.stdout.split(b"\0") if raw))


def is_archive_path(relative: str) -> bool:
    if any(relative.startswith(prefix) for prefix in ARCHIVE_PREFIXES):
        return True
    parts = PurePosixPath(relative).parts
    for prefix in ARCHITECTURE_HARNESS_PREFIXES:
        if parts[: len(prefix)] == prefix:
            return True
    for pattern in PROCEDURE_RECORD_PARTS:
        if len(parts) >= len(pattern) and all(
            expected == "*" or actual == expected for actual, expected in zip(parts, pattern)
        ):
            return True
    return False


def is_submodule_path(relative: str) -> bool:
    return "submodules" in PurePosixPath(relative).parts


def is_excluded_path(relative: str) -> bool:
    return is_archive_path(relative) or is_submodule_path(relative)


def source_targets(root: Path, patterns: Sequence[str]) -> SourceTargets:
    root = Path(root)
    tracked = tuple(path for path in git_ls_files(root, patterns) if (root / path).is_file())
    archives = tuple(path for path in tracked if is_archive_path(path))
    submodules = tuple(path for path in tracked if is_submodule_path(path))
    excluded = set(archives) | set(submodules)
    checked = tuple(path for path in tracked if path not in excluded)
    return SourceTargets(
        tracked_files=tracked,
        archive_files=tuple(sorted(archives)),
        submodule_files=tuple(sorted(submodules)),
        checked_files=checked,
    )


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    parser.add_argument("patterns", nargs="*", default=())
    args = parser.parse_args(argv)

    for path in source_targets(args.root, args.patterns).excluded_files:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
