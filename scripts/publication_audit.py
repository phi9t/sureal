#!/usr/bin/env python3
"""Audit the repository's offline, publication-safe contract.

The audit deliberately derives its file set from Git's index. Untracked cache
and build output therefore cannot make a clean checkout fail, while a generated
artifact accidentally added with ``git add -f`` cannot escape detection.
"""

from __future__ import annotations

import argparse
import configparser
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Sequence

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


MAX_BLOB_BYTES = 26_214_400
TARGET_URL = "https://github.com/phi9t/sureal"
UPSTREAM_URL = "https://github.com/Anttwo/Surflo"
REQUIRED_PUBLIC_FILES = frozenset(
    {
        ".github/workflows/publication.yml",
        ".gitignore",
        ".gitmodules",
        "CONTRIBUTING.md",
        "LICENSE.md",
        "README.md",
        "RELEASING.md",
        "SECURITY.md",
        "THIRD_PARTY_NOTICES.md",
        "UPSTREAM.md",
        "pyproject.toml",
    }
)


@dataclass(frozen=True)
class IndexEntry:
    mode: str
    object_id: str
    path: str

    @property
    def is_gitlink(self) -> bool:
        return self.mode == "160000"

    @property
    def is_regular_file(self) -> bool:
        return self.mode.startswith("100")


class AuditInputError(RuntimeError):
    """An expected repository-input error suitable for public output."""


def _git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        raise AuditInputError("unable to execute Git") from error
    if result.returncode:
        raise AuditInputError(f"Git command failed: git {' '.join(args)}")
    return result.stdout


def _index_entries(root: Path) -> list[IndexEntry]:
    output = _git(root, "ls-files", "--stage", "-z")
    entries: list[IndexEntry] = []
    pattern = re.compile(rb"([0-9]{6}) ([0-9a-f]+) ([0-3])\t(.*)", re.DOTALL)
    for raw_entry in output.split(b"\0"):
        if not raw_entry:
            continue
        match = pattern.fullmatch(raw_entry)
        if match is None:
            raise AuditInputError("Git returned an unrecognized index entry")
        entries.append(
            IndexEntry(
                mode=match.group(1).decode("ascii"),
                object_id=match.group(2).decode("ascii"),
                path=match.group(4).decode("utf-8", errors="surrogateescape"),
            )
        )
    return sorted(entries, key=lambda entry: entry.path)


def _read_tracked_blob(root: Path, entry: IndexEntry) -> bytes:
    path = root / entry.path
    try:
        if path.is_file() and not path.is_symlink():
            return path.read_bytes()
    except OSError as error:
        raise AuditInputError(f"cannot read tracked file: {entry.path}") from error
    return _git(root, "cat-file", "blob", entry.object_id)


def _declared_submodule_paths(data: bytes) -> tuple[set[str], list[str]]:
    parser = configparser.ConfigParser(interpolation=None)
    errors: list[str] = []
    try:
        parser.read_string(data.decode("utf-8"))
    except (UnicodeDecodeError, configparser.Error):
        return set(), [".gitmodules: invalid Git configuration"]

    paths: set[str] = set()
    for section in parser.sections():
        if not section.startswith('submodule "'):
            continue
        path = parser.get(section, "path", fallback="").strip()
        if not path:
            errors.append(f".gitmodules: {section} has no path")
        elif path in paths:
            errors.append(f".gitmodules: duplicate path {path}")
        else:
            paths.add(path)
    return paths, errors


def _is_generated_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if not parts:
        return False
    if parts[0] in {"build", "dist"}:
        return True
    return any(
        part == "__pycache__"
        or part.endswith(".egg-info")
        or part.endswith((".pyc", ".pyo"))
        for part in parts
    )


SECRET_PATTERNS = (
    ("GitHub token", re.compile(rb"github_pat_[A-Za-z0-9_]{20,}")),
    ("GitHub token", re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("AWS access key", re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}")),
    ("private key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)


def _identity_errors(root: Path, entries: dict[str, IndexEntry]) -> list[str]:
    errors: list[str] = []
    readme_entry = entries.get("README.md")
    if readme_entry is not None:
        readme = _read_tracked_blob(root, readme_entry).decode("utf-8", errors="replace")
        for required_text in (
            "Sureal",
            "surflo",
            "non-commercial research and evaluation",
            TARGET_URL,
            UPSTREAM_URL,
        ):
            if required_text not in readme:
                errors.append(f"README.md: missing required identity text: {required_text}")
        if not any(
            disclosure in readme
            for disclosure in ("fork of Surflo", "fork of [Surflo]")
        ):
            errors.append("README.md: missing required identity text: fork of Surflo")

    metadata_entry = entries.get("pyproject.toml")
    if metadata_entry is None:
        return errors
    try:
        metadata = tomllib.loads(
            _read_tracked_blob(root, metadata_entry).decode("utf-8")
        )
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        errors.append("pyproject.toml: invalid TOML")
        return errors

    project = metadata.get("project")
    if not isinstance(project, dict):
        errors.append("pyproject.toml: missing [project] table")
        return errors
    if project.get("name") != "surflo":
        errors.append('pyproject.toml: project.name must remain "surflo"')
    urls = project.get("urls")
    if not isinstance(urls, dict):
        errors.append("pyproject.toml: missing [project.urls] table")
        return errors
    for key, expected in (
        ("Homepage", TARGET_URL),
        ("Repository", TARGET_URL),
        ("Upstream", UPSTREAM_URL),
    ):
        if urls.get(key) != expected:
            errors.append(f"pyproject.toml: project.urls.{key} must be {expected}")
    return errors


def static_errors(
    root: Path, *, max_blob_bytes: int = MAX_BLOB_BYTES
) -> list[str]:
    """Return deterministic publication errors that need no external tools."""

    root = Path(root)
    try:
        index_entries = _index_entries(root)
    except AuditInputError as error:
        return [f"repository: {error}"]

    entries = {entry.path: entry for entry in index_entries}
    errors = [
        f"required file is not tracked: {path}"
        for path in sorted(REQUIRED_PUBLIC_FILES - entries.keys())
    ]

    gitlinks = {entry.path for entry in index_entries if entry.is_gitlink}
    modules_entry = entries.get(".gitmodules")
    if modules_entry is not None:
        declared, module_errors = _declared_submodule_paths(
            _read_tracked_blob(root, modules_entry)
        )
        errors.extend(module_errors)
        for path in sorted(gitlinks - declared):
            errors.append(f"gitlink is not declared in .gitmodules: {path}")
        for path in sorted(declared - gitlinks):
            errors.append(f".gitmodules path has no matching gitlink: {path}")

    errors.extend(_identity_errors(root, entries))

    for entry in index_entries:
        if not entry.is_regular_file:
            continue
        if _is_generated_path(entry.path):
            errors.append(f"tracked generated path: {entry.path}")
        blob = _read_tracked_blob(root, entry)
        if len(blob) > max_blob_bytes:
            errors.append(
                f"tracked blob exceeds {max_blob_bytes} bytes: {entry.path} "
                f"({len(blob)} bytes)"
            )
        for rule_name, pattern in SECRET_PATTERNS:
            if pattern.search(blob):
                errors.append(f"suspected {rule_name} in tracked file: {entry.path}")

    return sorted(set(errors))


def portable_command_errors(root: Path) -> list[str]:
    """Run CPU-only checks that need only Git, Bash, and the active Python."""

    root = Path(root)
    try:
        entries = _index_entries(root)
    except AuditInputError as error:
        return [f"portable checks: {error}"]

    regular_paths = sorted(
        entry.path for entry in entries if entry.is_regular_file
    )
    python_paths = [path for path in regular_paths if path.endswith(".py")]
    shell_paths = [path for path in regular_paths if path.endswith(".sh")]

    commands: list[list[str]] = []
    if python_paths:
        commands.append([sys.executable, "-m", "compileall", "-q", *python_paths])
    commands.extend(["bash", "-n", path] for path in shell_paths)
    commands.append(["git", "diff", "--check", "HEAD"])
    pathway_audit = "experiments/3d-pathway/pipeline/audit.py"
    if pathway_audit in regular_paths:
        commands.append([sys.executable, pathway_audit, "--offline"])

    errors: list[str] = []
    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=root,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError:
            errors.append(f"portable command could not start: {' '.join(command)}")
            continue
        if result.returncode:
            errors.append(
                f"portable command failed (exit {result.returncode}): "
                f"{' '.join(command)}"
            )
    return errors


def audit_repository(root: Path) -> dict[str, object]:
    """Build the machine-readable publication report."""

    errors = static_errors(root) + portable_command_errors(root)
    try:
        entries = _index_entries(Path(root))
    except AuditInputError:
        entries = []
    return {
        "schema_version": 1,
        "status": "pass" if not errors else "fail",
        "tracked_files": sum(not entry.is_gitlink for entry in entries),
        "gitlinks": sum(entry.is_gitlink for entry in entries),
        "max_blob_bytes": MAX_BLOB_BYTES,
        "errors": sorted(set(errors)),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    report = audit_repository(args.root)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
