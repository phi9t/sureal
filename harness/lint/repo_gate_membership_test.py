"""Tests that the repo gate keeps covering static policy checks."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import unittest


EXPECTED_HARNESS_REPO_GATE_TESTS = {
    "//harness/lint:clang_format_repo_test",
    "//harness/lint:check_cxx_test",
    "//harness/lint:check_identifiers_test",
    "//harness/lint:check_storage_boundary_test",
    "//harness/lint:githooks_test",
    "//harness/lint:import_rule_behavior_test",
    "//harness/lint:pinned_sources_test",
    "//harness/lint:publication_audit_behavior_test",
    "//harness/lint:repo_gate_clang_format_test",
    "//harness/lint:repo_gate_cxx_test",
    "//harness/lint:repo_gate_import_rule_test",
    "//harness/lint:repo_gate_membership_test",
    "//harness/lint:repo_gate_publication_audit_test",
    "//harness/lint:repo_gate_ruff_test",
    "//harness/lint:repo_gate_shell_style_test",
    "//harness/lint:repo_gate_shellcheck_test",
    "//harness/lint:repo_gate_shfmt_test",
    "//harness/lint:repo_gate_whitespace_test",
    "//harness/lint:ruff_repo_test",
    "//harness/lint:check_shell_style_test",
    "//harness/lint:shellcheck_repo_test",
    "//harness/lint:shfmt_repo_test",
}


def repository_root() -> Path:
    configured = os.environ.get("SUREAL_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2]


def repo_gate_tests(root: Path) -> set[str]:
    build = (root / "BUILD.bazel").read_text(encoding="utf-8")
    match = re.search(r"(?ms)^REPO_GATE_TESTS = \[(?P<body>.*?)^\]", build)
    if match is None:
        raise AssertionError("BUILD.bazel does not define REPO_GATE_TESTS")
    return set(re.findall(r'"([^"]+)"', match.group("body")))


def tracked_boundary_test_labels(root: Path) -> set[str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    apply_repo_gate_git_environment(env)
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", "autonomy/*_boundary_test.py", "autonomy/**/*_boundary_test.py"],
        env=env,
        check=True,
        stdout=subprocess.PIPE,
    )
    labels = set()
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        package, filename = path.rsplit("/", 1)
        labels.add(f"//{package}:{filename[:-3]}")
    return labels


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


class RepoGateMembershipTests(unittest.TestCase):
    def test_repo_gate_keeps_expected_lint_and_boundary_tests(self) -> None:
        root = repository_root()
        gate_tests = repo_gate_tests(root)
        expected = EXPECTED_HARNESS_REPO_GATE_TESTS | tracked_boundary_test_labels(root)

        self.assertEqual(gate_tests, expected)
        self.assertEqual(len(gate_tests), 25)


if __name__ == "__main__":
    unittest.main()
