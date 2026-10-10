#!/usr/bin/env python3
"""Discover source files protected by retained receipts and candidate audits."""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


IMPORT_ROOTS = ("autonomy", "parallax")
RECEIPT_ROOTS = ("autonomy", "parallax")
PIN_FIELD_CONSTANT = "RETAINED_SOURCE_PIN_FIELDS"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA256_BYTES = re.compile(rb"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")

SOURCE_DECLARATIONS = {
    "autonomy/resources/sources.py": {
        "REQUIRED": "autonomy/resources",
        "EVIDENCE_REQUIRED": "autonomy",
    },
    "autonomy/training_execution/sustained_sources.py": {
        "REQUIRED": "autonomy",
    },
    "autonomy/training_execution/sustained_controller_sources.py": {
        "REQUIRED": "autonomy",
        "HISTORICAL_REQUIRED": "autonomy",
    },
    "autonomy/retention/publication_sources.py": {
        "CHECKPOINT_REQUIRED": "autonomy",
        "NATIVE_CACHE_REQUIRED": "autonomy",
        "PILOT_REQUIRED": "autonomy",
        "HISTORICAL_CHECKPOINT_REQUIRED": "autonomy",
        "HISTORICAL_NATIVE_CACHE_REQUIRED": "autonomy",
        "HISTORICAL_PILOT_REQUIRED": "autonomy",
    },
    "autonomy/retention/publish_scientific_directory.py": {
        "HOST_SOURCE_REQUIRED": "autonomy",
    },
    "autonomy/retention/publish_symlink_audit.py": {
        "HOST_SOURCE_REQUIRED": "autonomy",
    },
}

FROZEN_PREFIXES = (
    "autonomy/research/",
    "parallax/research/",
)
FROZEN_PARTS = (
    ("autonomy", "studies", "*", "procedure_records"),
    ("parallax", "studies", "*", "procedure_records"),
)
FROZEN_EXACT_PREFIXES = (
    ("autonomy", "studies", "architecture", "harness"),
    ("parallax", "studies", "architecture", "harness"),
)


@dataclass(frozen=True)
class SourceTargets:
    tracked_files: tuple[str, ...]
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


def retained_source_pin_fields(root: Path) -> tuple[str, ...]:
    source = Path(root) / "autonomy" / "retained_receipt_sweep.py"
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    except OSError:
        return ()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == PIN_FIELD_CONSTANT for target in node.targets):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{PIN_FIELD_CONSTANT} must be a tuple of field names")
        return value
    return ()


def _json_paths(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix == ".json":
            yield root
        return
    if root.exists():
        yield from sorted(path for path in root.rglob("*.json") if path.is_file())


def _iter_receipt_values(value: object) -> Iterable[object]:
    yield value
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _iter_receipt_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_receipt_values(child)


def _iter_pin_mapping_paths(value: object) -> Iterable[str]:
    if not isinstance(value, Mapping):
        return
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str) and SHA256.fullmatch(item):
            yield key
        elif isinstance(item, Mapping):
            yield from _iter_pin_mapping_paths(item)
        elif isinstance(item, list):
            for child in item:
                yield from _iter_pin_mapping_paths(child)


def _path_candidates(raw: str, root: Path) -> Iterable[str]:
    raw = raw.strip().replace("\\", "/")
    if not raw:
        return
    path = Path(raw)
    if path.is_absolute():
        try:
            yield path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
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
    basename_counts = Counter(Path(path).name for path in tracked)
    basename_index = {Path(path).name: path for path in tracked if basename_counts[Path(path).name] == 1}
    return _normalize_source_pin_path(
        raw,
        root,
        tracked,
        basename_index,
        allow_marker_paths=True,
        allow_basename=True,
    )


def _normalize_source_pin_path(
    raw: str,
    root: Path,
    tracked: set[str],
    basename_index: Mapping[str, str],
    *,
    allow_marker_paths: bool,
    allow_basename: bool,
) -> str | None:
    for candidate in _path_candidates(raw, root):
        if Path(raw).is_absolute() and not allow_marker_paths and candidate != raw:
            continue
        candidate = candidate.lstrip("./")
        parts = PurePosixPath(candidate).parts
        if not parts or any(part in ("", ".", "..") for part in parts):
            continue
        normalized = PurePosixPath(*parts).as_posix()
        if normalized in tracked:
            return normalized
        for import_root in IMPORT_ROOTS:
            rooted = PurePosixPath(import_root, normalized).as_posix()
            if rooted in tracked:
                return rooted

    if allow_basename:
        return basename_index.get(Path(raw).name)
    return None


def _tracked_source_paths(root: Path) -> tuple[str, ...]:
    return git_ls_files(
        root,
        (
            "autonomy",
            "parallax",
            "scripts",
            "*.py",
            "*.sh",
            ".githooks",
            "BUILD",
            "BUILD.bazel",
            "*.bzl",
        ),
    )


def receipt_pinned_source_paths(
    root: Path,
    tracked: Iterable[str] | None = None,
    *,
    allow_marker_paths: bool = True,
    allow_basename: bool = True,
) -> tuple[str, ...]:
    root = Path(root)
    tracked_set = set(_tracked_source_paths(root) if tracked is None else tracked)
    fields = set(retained_source_pin_fields(root))
    if not fields:
        return ()
    basename_counts = Counter(Path(path).name for path in tracked_set)
    basename_index = {Path(path).name: path for path in tracked_set if basename_counts[Path(path).name] == 1}
    pinned: set[str] = set()
    for receipt_root in RECEIPT_ROOTS:
        for path in _json_paths(root / receipt_root):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            for value in _iter_receipt_values(data):
                if not isinstance(value, Mapping):
                    continue
                for field in fields:
                    if field not in value:
                        continue
                    for raw in _iter_pin_mapping_paths(value[field]):
                        normalized = _normalize_source_pin_path(
                            raw,
                            root,
                            tracked_set,
                            basename_index,
                            allow_marker_paths=allow_marker_paths,
                            allow_basename=allow_basename,
                        )
                        if normalized is not None:
                            pinned.add(normalized)
    return tuple(sorted(pinned))


def _tracked_autonomy_digests(root: Path, tracked: set[str]) -> dict[str, list[str]]:
    cited: dict[str, list[str]] = defaultdict(list)
    for name in git_ls_files(root / "autonomy", ("research",)):
        path = root / "autonomy" / name
        if path.is_file():
            for digest in set(SHA256_BYTES.findall(path.read_bytes())):
                cited[digest.decode("ascii")].append(name)
    pinned: dict[str, list[str]] = {}
    for relative in tracked:
        if not relative.startswith("autonomy/"):
            continue
        path = root / relative
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            receipts = cited.get(digest)
            if receipts:
                pinned[relative] = sorted(receipts)
    return pinned


def digest_pinned_source_paths(root: Path, tracked: Iterable[str] | None = None) -> tuple[str, ...]:
    root = Path(root)
    tracked_set = set(_tracked_source_paths(root) if tracked is None else tracked)
    return tuple(sorted(_tracked_autonomy_digests(root, tracked_set)))


def _literal_strings(node: ast.AST) -> Iterable[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    for child in ast.iter_child_nodes(node):
        yield from _literal_strings(child)


def _assigned_name(node: ast.Assign) -> str | None:
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return None
    return node.targets[0].id


def _normalize_declared_source(raw: str, base: str, root: Path, tracked: set[str]) -> str | None:
    if raw.startswith("//") or raw.startswith(":"):
        return None
    if "*" in raw:
        candidates = sorted(path.relative_to(root).as_posix() for path in (root / base).glob(raw) if path.is_file())
        for candidate in candidates:
            if candidate in tracked:
                return candidate
        return None
    return normalize_source_pin_path(PurePosixPath(base, raw).as_posix(), root, tracked)


def current_candidate_source_paths(root: Path, tracked: Iterable[str] | None = None) -> tuple[str, ...]:
    root = Path(root)
    tracked_set = set(_tracked_source_paths(root) if tracked is None else tracked)
    protected: set[str] = set()
    for relative, constants in SOURCE_DECLARATIONS.items():
        source = root / relative
        if not source.is_file():
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=relative)
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            name = _assigned_name(node)
            if name not in constants:
                continue
            base = constants[name]
            for raw in _literal_strings(node.value):
                normalized = _normalize_declared_source(raw, base, root, tracked_set)
                if normalized is not None:
                    protected.add(normalized)
    return tuple(sorted(protected))


def pinned_source_paths(root: Path, tracked: Iterable[str] | None = None) -> tuple[str, ...]:
    """Return the retained-receipt path pins used by the import checker."""

    return receipt_pinned_source_paths(
        root,
        _tracked_source_paths(root) if tracked is None else tracked,
        allow_marker_paths=False,
        allow_basename=False,
    )


def protected_source_paths(root: Path, tracked: Iterable[str] | None = None) -> tuple[str, ...]:
    root = Path(root)
    tracked_set = set(_tracked_source_paths(root) if tracked is None else tracked)
    return tuple(
        sorted(
            set(receipt_pinned_source_paths(root, tracked_set))
            | set(digest_pinned_source_paths(root, tracked_set))
            | set(current_candidate_source_paths(root, tracked_set))
        )
    )


def is_frozen_path(relative: str) -> bool:
    if any(relative.startswith(prefix) for prefix in FROZEN_PREFIXES):
        return True
    parts = PurePosixPath(relative).parts
    for prefix in FROZEN_EXACT_PREFIXES:
        if parts[: len(prefix)] == prefix:
            return True
    for pattern in FROZEN_PARTS:
        if len(parts) >= len(pattern) and all(
            expected == "*" or actual == expected for actual, expected in zip(parts, pattern)
        ):
            return True
    return False


def source_targets(
    root: Path,
    patterns: Sequence[str],
    *,
    protected: Iterable[str] | None = None,
    include_frozen: bool = False,
) -> SourceTargets:
    root = Path(root)
    tracked = git_ls_files(root, patterns)
    tracked_set = set(tracked)
    receipt_pinned = tuple(
        path
        for path in receipt_pinned_source_paths(root, tracked_set, allow_marker_paths=True, allow_basename=False)
        if path in tracked_set
    )
    digest_pinned = tuple(path for path in digest_pinned_source_paths(root, tracked_set) if path in tracked_set)
    candidate_pinned = tuple(path for path in current_candidate_source_paths(root, tracked_set) if path in tracked_set)
    protected_set = (
        set(protected) if protected is not None else set(receipt_pinned) | set(digest_pinned) | set(candidate_pinned)
    )
    frozen = tuple(path for path in tracked if is_frozen_path(path))
    excluded = protected_set | (set() if include_frozen else set(frozen))
    checked = tuple(path for path in tracked if path not in excluded)
    return SourceTargets(
        tracked_files=tracked,
        receipt_pinned_files=tuple(sorted(receipt_pinned)),
        digest_pinned_files=tuple(sorted(digest_pinned)),
        current_candidate_files=tuple(sorted(candidate_pinned)),
        frozen_files=tuple(sorted(frozen)),
        checked_files=checked,
    )


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=repository_root())
    parser.add_argument("--protected", action="store_true")
    args = parser.parse_args(argv)

    paths = protected_source_paths(args.root) if args.protected else pinned_source_paths(args.root)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
