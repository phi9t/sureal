#!/usr/bin/env python3
"""Fail on imports that bypass the repository's Python import roots."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Iterable, Mapping, Sequence


IMPORT_ROOTS = ("autonomy", "parallax")
BASELINE_PATH = Path("scripts/import_rule_baseline.json")
PIN_FIELD_CONSTANT = "RETAINED_SOURCE_PIN_FIELDS"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
Problem = tuple[str, str, int, str]
ProblemKey = tuple[str, int, str]


def _git_environment(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    configured_work_tree = env.get("SUREAL_REPO_GATE_GIT_WORK_TREE")
    if configured_work_tree:
        try:
            if Path(configured_work_tree).resolve(strict=False) != root.resolve(strict=False):
                for name in (
                    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                    "GIT_COMMON_DIR",
                    "GIT_DIR",
                    "GIT_OBJECT_DIRECTORY",
                    "GIT_WORK_TREE",
                ):
                    env.pop(name, None)
                return env
        except OSError:
            return env
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
    return env


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            env=_git_environment(root),
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return b""


def _tracked_files(root: Path, patterns: Sequence[str]) -> list[Path]:
    output = _git(root, "ls-files", "-z", "--", *patterns)
    if output:
        return [
            root / raw.decode("utf-8", errors="surrogateescape")
            for raw in output.split(b"\0")
            if raw
        ]
    return sorted(path for pattern in patterns for path in root.glob(pattern))


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_frozen_path(relative: str) -> bool:
    parts = PurePosixPath(relative).parts
    if len(parts) >= 2 and parts[0] in IMPORT_ROOTS and parts[1] == "research":
        return True
    if (
        len(parts) >= 4
        and parts[0] in IMPORT_ROOTS
        and parts[1] == "studies"
        and parts[3] == "procedure_records"
    ):
        return True
    return (
        len(parts) >= 4
        and parts[0] in IMPORT_ROOTS
        and parts[1:4] == ("studies", "architecture", "harness")
    )


def _pin_field_names(root: Path) -> tuple[str, ...]:
    source = root / "autonomy" / "retained_receipt_sweep.py"
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


def _normalize_pin_path(root: Path, raw_path: str) -> str | None:
    raw_path = raw_path.strip().replace("\\", "/")
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        try:
            raw_path = path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
        except ValueError:
            return None
    parts = PurePosixPath(raw_path).parts
    while parts and parts[0] in ("", "."):
        parts = parts[1:]
    if not parts or any(part in ("", ".", "..") for part in parts):
        return None
    relative = PurePosixPath(*parts).as_posix()
    if parts[0] in IMPORT_ROOTS and (root / relative).is_file():
        return relative
    for import_root in IMPORT_ROOTS:
        candidate = PurePosixPath(import_root, relative).as_posix()
        if (root / candidate).is_file():
            return candidate
    return None


def pinned_source_paths(root: Path) -> set[str]:
    fields = set(_pin_field_names(root))
    if not fields:
        return set()
    pinned: set[str] = set()
    for path in _tracked_files(root, ["autonomy/**/*.json", "parallax/**/*.json"]):
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
                    normalized = _normalize_pin_path(root, raw)
                    if normalized is not None:
                        pinned.add(normalized)
    return pinned


def _top_level_local_modules(root: Path, import_root: str) -> set[str]:
    directory = root / import_root
    modules: set[str] = set()
    for child in directory.iterdir():
        if child.name.startswith(".") or child.name == "__pycache__":
            continue
        if child.is_file() and child.suffix == ".py":
            modules.add(child.stem)
        elif child.is_dir() and any(child.rglob("*.py")):
            modules.add(child.name)
    return modules


def _local_module_suffixes(root: Path, import_root: str) -> dict[str, list[str]]:
    directory = root / import_root
    suffixes: dict[str, list[str]] = {}
    for source in sorted(directory.rglob("*.py")):
        relative = source.relative_to(directory)
        if any(part == "__pycache__" for part in relative.parts):
            continue
        dotted = ".".join(relative.with_suffix("").parts)
        suffixes.setdefault(source.stem, []).append(dotted)
    return suffixes


def _local_module_file(directory: Path, module: str) -> bool:
    parts = module.split(".")
    if not parts or any(not part.isidentifier() for part in parts):
        return False
    stem = directory.joinpath(*parts)
    return (stem.with_suffix(".py")).is_file() or (stem / "__init__.py").is_file()


def _anchored_import_problem(
    root: Path,
    path: Path,
    import_root: str,
    root_modules: set[str],
    module: str,
) -> str | None:
    if not module:
        return None
    top_level = module.split(".", 1)[0]
    if top_level in root_modules:
        return None
    try:
        current = path.parent.resolve(strict=False)
        import_root_path = (root / import_root).resolve(strict=False)
        current.relative_to(import_root_path)
    except ValueError:
        return None
    if _local_module_file(current, module):
        package = current.relative_to(import_root_path).as_posix().replace("/", ".")
        anchored = f"{package}.{module}" if package != "." else module
        return f"local import is not anchored at {import_root}/: {module} (use {anchored})"
    return None


def _unrooted_local_import_problem(
    root_modules: set[str],
    local_suffixes: Mapping[str, list[str]],
    module: str,
) -> str | None:
    if not module:
        return None
    top_level = module.split(".", 1)[0]
    if top_level in root_modules:
        return None
    candidates = local_suffixes.get(top_level, [])
    if not candidates:
        return None
    rendered = ", ".join(candidates[:3])
    if len(candidates) > 3:
        rendered += ", ..."
    return f"local import is not anchored at import root: {module} (use {rendered})"


def _is_sys_path_expr(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "path"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _is_sys_path_target(node: ast.AST) -> bool:
    return _is_sys_path_expr(node) or (
        isinstance(node, ast.Subscript) and _is_sys_path_expr(node.value)
    )


def _sys_path_edit_line(node: ast.AST) -> int | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in {"append", "extend", "insert", "remove", "pop", "clear"} and _is_sys_path_expr(node.func.value):
            return node.lineno
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
        targets = getattr(node, "targets", None)
        if targets is None:
            targets = [node.target] if hasattr(node, "target") else []
        if any(_is_sys_path_target(target) for target in targets):
            return node.lineno
    return None


def problem_key(problem: Problem) -> ProblemKey:
    kind, path, line, _message = problem
    return (path, line, kind)


def _format_key(key: ProblemKey) -> str:
    path, line, kind = key
    return f"{path}:{line}: {kind}"


def read_baseline(path: Path) -> dict[ProblemKey, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping) or data.get("version") != 1:
        raise ValueError(f"{path}: import-rule baseline must have version 1")
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: import-rule baseline entries must be a list")
    baseline: dict[ProblemKey, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ValueError(f"{path}: baseline entry {index} must be an object")
        relative = entry.get("path")
        line = entry.get("line")
        lines = entry.get("lines")
        kind = entry.get("kind")
        reason = entry.get("reason")
        if (
            not isinstance(relative, str)
            or not isinstance(kind, str)
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            raise ValueError(f"{path}: invalid import-rule baseline entry {index}")
        if isinstance(line, int):
            expanded_lines = [line]
        elif isinstance(lines, list) and all(isinstance(item, int) for item in lines):
            expanded_lines = lines
        else:
            raise ValueError(f"{path}: baseline entry {index} must set line or lines")
        for expanded_line in expanded_lines:
            if expanded_line < 1:
                raise ValueError(f"{path}: invalid import-rule baseline line in entry {index}")
            key = (relative, expanded_line, kind)
            if key in baseline:
                raise ValueError(f"{path}: duplicate import-rule baseline entry {_format_key(key)}")
            baseline[key] = reason
    return baseline


def scan(root: Path) -> list[Problem]:
    root = Path(root)
    pinned = pinned_source_paths(root)
    root_modules = {
        import_root: _top_level_local_modules(root, import_root)
        for import_root in IMPORT_ROOTS
        if (root / import_root).is_dir()
    }
    local_suffixes = {
        import_root: _local_module_suffixes(root, import_root)
        for import_root in root_modules
    }
    problems: list[Problem] = []
    for path in _tracked_files(root, [f"{import_root}/**/*.py" for import_root in IMPORT_ROOTS]):
        relative = _relative_path(path, root)
        parts = PurePosixPath(relative).parts
        if not parts or parts[0] not in root_modules:
            continue
        if _is_frozen_path(relative) or relative in pinned:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except SyntaxError as error:
            problems.append(("parse", relative, error.lineno or 0, str(error)))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    problems.append(("relative-import", relative, node.lineno, "relative import"))
                    continue
                message = _anchored_import_problem(
                    root,
                    path,
                    parts[0],
                    root_modules[parts[0]],
                    node.module or "",
                )
                if message is None:
                    message = _unrooted_local_import_problem(
                        root_modules[parts[0]],
                        local_suffixes[parts[0]],
                        node.module or "",
                    )
                if message is not None:
                    problems.append(("unrooted-local-import", relative, node.lineno, message))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    message = _anchored_import_problem(
                        root,
                        path,
                        parts[0],
                        root_modules[parts[0]],
                        alias.name,
                    )
                    if message is None:
                        message = _unrooted_local_import_problem(
                            root_modules[parts[0]],
                            local_suffixes[parts[0]],
                            alias.name,
                        )
                    if message is not None:
                        problems.append(("unrooted-local-import", relative, node.lineno, message))
                        break
            line = _sys_path_edit_line(node)
            if line is not None:
                problems.append(("sys-path-edit", relative, line, "sys.path edit"))
    return sorted(problems, key=lambda problem: (problem[1], problem[2], problem[0], problem[3]))


def check(root: Path, baseline_path: Path | None = None) -> dict[str, object]:
    root = Path(root)
    problems = scan(root)
    baseline = read_baseline(root / BASELINE_PATH if baseline_path is None else baseline_path)
    problem_keys = {problem_key(problem) for problem in problems}
    unexpected = [problem for problem in problems if problem_key(problem) not in baseline]
    stale = sorted(set(baseline) - problem_keys)
    baseline_hits = sorted(problem_keys & set(baseline))
    return {
        "problems": problems,
        "unexpected": unexpected,
        "stale_baseline": stale,
        "baseline_hits": baseline_hits,
        "baseline": baseline,
        "pinned_source_count": len(pinned_source_paths(root)),
    }


def _summary_counts(problems: Sequence[Problem]) -> dict[str, dict[str, int]]:
    by_kind = Counter(problem[0] for problem in problems)
    by_directory = Counter(str(PurePosixPath(problem[1]).parent) for problem in problems)
    return {
        "by_kind": dict(sorted(by_kind.items())),
        "by_directory": dict(sorted(by_directory.items())),
    }


def summary(report: Mapping[str, object]) -> dict[str, object]:
    problems = report["problems"]
    unexpected = report["unexpected"]
    baseline_hits = report["baseline_hits"]
    stale = report["stale_baseline"]
    if not isinstance(problems, list) or not isinstance(unexpected, list):
        raise TypeError("invalid import-rule report")
    return {
        "status": "fail" if unexpected or stale else "pass",
        "problem_count": len(problems),
        "unexpected_count": len(unexpected),
        "baseline_count": len(baseline_hits) if isinstance(baseline_hits, list) else 0,
        "stale_baseline_count": len(stale) if isinstance(stale, list) else 0,
        "pinned_source_count": report["pinned_source_count"],
        "all": _summary_counts(problems),
        "unexpected": _summary_counts(unexpected),
    }


def format_problem(problem: Problem) -> str:
    kind, path, line, message = problem
    location = f"{path}:{line}" if line else path
    return f"{location}: {kind}: {message}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--summary-json", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.root, args.baseline)
    if args.summary_json:
        print(json.dumps(summary(report), indent=2, sort_keys=True))
    else:
        for problem in report["unexpected"]:
            print(format_problem(problem), file=sys.stderr)
        for key in report["stale_baseline"]:
            print(f"stale import-rule baseline entry: {_format_key(key)}", file=sys.stderr)
    return 1 if report["unexpected"] or report["stale_baseline"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
