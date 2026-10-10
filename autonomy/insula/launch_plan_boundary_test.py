"""Static boundary checks for Insula launch plans."""
from __future__ import annotations

import ast
import os
import re
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path


AUTONOMY_ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".bzl", ".py", ".sh"}
TEXT_NAMES = {"BUILD", "BUILD.bazel"}


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    kind: str


BWRAP_ARGV_PATTERNS = (
    ("legacy launch_plan command-line face", re.compile(r"\binsula\.entry\.launch_plan\b|from insula\.entry import launch_plan|def launch_plan\(")),
    ("legacy live_gate_plan command-line face", re.compile(r"\blive_gate_plan\b|insula\.sandbox_plan|def compose_bwrap_plan\(")),
    ("direct bwrap argv construction", re.compile(r"""\[[^\n#]*["']bwrap["']""")),
    ("direct bwrap mount argv", re.compile(r"""["']--(?:ro-bind|bind|dev-bind)["']""")),
    ("direct bwrap environment argv", re.compile(r"""^\s*\w+(?:\[[^\]]+\])?\s*(?:=|\+=)\s*\[[^\n#]*["']--setenv["']""")),
    ("direct bwrap tmpfs argv", re.compile(r"""^\s*\w+(?:\[[^\]]+\])?\s*(?:=|\+=)\s*\[[^\n#]*["']--tmpfs["']""")),
    ("direct bwrap symlink argv", re.compile(r"""^\s*\w+(?:\[[^\]]+\])?\s*(?:=|\+=)\s*\[[^\n#]*["']--symlink["']""")),
    ("direct bwrap working-directory argv", re.compile(r"""^\s*\w+(?:\[[^\]]+\])?\s*(?:=|\+=)\s*\[[^\n#]*["']--chdir["']""")),
    ("direct bwrap namespace argv", re.compile(r"""["']--(?:unshare-all|clearenv)["']""")),
    ("direct shell bwrap execution", re.compile(r"""(^|[;&|]\s*)(exec\s+)?bwrap(\s|$)""")),
)

RUNTIME_LOCK_PATTERNS = (
    ("direct runtime lock JSON path", re.compile(r"""Path\(\s*str\([^#\n]+\)\s*\+\s*["']\.lock\.json["']\s*\)\.read_text\(""")),
    ("direct runtime lock JSON load", re.compile(r"""json\.loads\([^#\n]*(?:Path\(\s*str\([^#\n]+\)\s*\+\s*["']\.lock\.json|lock_path|runtime_lock)[^#\n]*read_text\(""")),
    ("direct rootfs content verification", re.compile(r"(?<!def )\bverify_rootfs\(")),
)

ALLOWED_EXACT = {
    "insula/launch_plan.py",
    "insula/tracer.sh",
    "insula/runtime_roots.py",
    "insula/runtime_identity.py",
    "insula/build_cpu_rootfs.sh",
    "insula/build_gpu_bazel_rootfs_v6.sh",
    "tracer.sh",
}

ALLOWED_PREFIXES = (
    "research/",
    "studies/architecture/harness/",
)


def _is_scanned_file(path: Path) -> bool:
    return path.name in TEXT_NAMES or path.suffix in TEXT_SUFFIXES


def _is_frozen_path(relative: str) -> bool:
    if relative.startswith(ALLOWED_PREFIXES):
        return True
    if "/testdata/" in f"/{relative}/":
        return True
    return bool(re.match(r"studies/[^/]+/procedure_records/", relative))


def _is_active_path(relative: str) -> bool:
    if relative.endswith("_test.py"):
        return False
    if relative in ALLOWED_EXACT:
        return False
    return not _is_frozen_path(relative)


def _active_python_sources(root: Path = AUTONOMY_ROOT) -> dict[str, str]:
    sources = {}
    for path in sorted(Path(root).rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if not _is_active_path(relative):
            continue
        try:
            sources[relative] = path.read_text(errors="replace")
        except OSError:
            continue
    return sources


def scan_launch_plan_boundary(root: Path = AUTONOMY_ROOT) -> list[Violation]:
    violations = []
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or not _is_scanned_file(path):
            continue
        relative = path.relative_to(root).as_posix()
        if not _is_active_path(relative):
            continue
        try:
            source = path.read_text(errors="replace")
        except OSError:
            continue
        violations.extend(_private_launch_plan_imports(relative, source) if path.suffix == ".py" else [])
        lines = source.splitlines()
        for line_number, line in enumerate(lines, start=1):
            for kind, pattern in (*BWRAP_ARGV_PATTERNS, *RUNTIME_LOCK_PATTERNS):
                if pattern.search(line):
                    violations.append(Violation(relative, line_number, kind))
    return violations


def _private_launch_plan_imports(relative: str, source: str) -> list[Violation]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    violations = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "insula.launch_plan"
            and any(alias.name.startswith("_") for alias in node.names)
        ):
            violations.append(
                Violation(
                    relative,
                    node.lineno,
                    "private launch_plan import outside insula",
                )
            )
    return violations


class LaunchPlanBoundaryTests(unittest.TestCase):
    def test_active_code_uses_only_launch_plan_module_for_sandbox_and_lock_boundaries(self):
        violations = scan_launch_plan_boundary()
        if os.environ.get("SUREAL_LAUNCH_PLAN_PLANT_VIOLATION") == "1":
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                planted = root / "dataset" / "planted.py"
                planted.parent.mkdir(parents=True)
                planted.write_text(
                    "import json\n"
                    "from pathlib import Path\n"
                    "cmd = ['bwrap', '--unshare-all', '--ro-bind', '/rootfs', '/']\n"
                    "lock = json.loads(Path(str(root) + '.lock.json').read_text())\n"
                )
                violations = scan_launch_plan_boundary(root)
        self.assertEqual(
            violations,
            [],
            "active code outside insula.launch_plan must not render bwrap argv "
            "or parse runtime locks directly",
        )

    def test_scanner_reports_a_planted_active_violation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            planted = root / "dataset" / "planted.py"
            planted.parent.mkdir(parents=True)
            planted.write_text(
                "import json\n"
                "from pathlib import Path\n"
                "cmd = ['bwrap', '--unshare-all', '--ro-bind', '/rootfs', '/']\n"
                "lock = json.loads(Path(str(root) + '.lock.json').read_text())\n"
            )

            violations = scan_launch_plan_boundary(root)

        self.assertEqual(
            violations,
            [
                Violation("dataset/planted.py", 3, "direct bwrap argv construction"),
                Violation("dataset/planted.py", 3, "direct bwrap mount argv"),
                Violation("dataset/planted.py", 3, "direct bwrap namespace argv"),
                Violation("dataset/planted.py", 4, "direct runtime lock JSON path"),
                Violation("dataset/planted.py", 4, "direct runtime lock JSON load"),
            ],
        )

    def test_scanner_reports_planted_bwrap_option_splicing_and_private_imports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            planted = root / "dataset" / "planted.py"
            planted.parent.mkdir(parents=True)
            planted.write_text(
                "from insula.launch_plan import _assemble_plan\n"
                "cmd = []\n"
                "cmd[0:0] = ['--setenv', 'A', 'B', '--tmpfs', '/tmp/x', '--symlink', 'usr/lib', '/lib', '--chdir', '/experiment']\n"
            )

            violations = scan_launch_plan_boundary(root)

        self.assertEqual(
            violations,
            [
                Violation("dataset/planted.py", 1, "private launch_plan import outside insula"),
                Violation("dataset/planted.py", 3, "direct bwrap environment argv"),
                Violation("dataset/planted.py", 3, "direct bwrap tmpfs argv"),
                Violation("dataset/planted.py", 3, "direct bwrap symlink argv"),
                Violation("dataset/planted.py", 3, "direct bwrap working-directory argv"),
            ],
        )

    def test_scanner_reports_parenthesized_private_imports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            planted = root / "dataset" / "planted.py"
            planted.parent.mkdir(parents=True)
            planted.write_text(
                "from insula.launch_plan import (\n"
                "    build_plan,\n"
                "    _assemble_plan,\n"
                ")\n"
            )

            violations = scan_launch_plan_boundary(root)

        self.assertEqual(
            violations,
            [Violation("dataset/planted.py", 1, "private launch_plan import outside insula")],
        )

    def test_scanner_reports_multiline_private_imports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            planted = root / "dataset" / "planted.py"
            planted.parent.mkdir(parents=True)
            planted.write_text(
                "from insula.launch_plan import \\\n"
                "    _render_mount\n"
            )

            violations = scan_launch_plan_boundary(root)

        self.assertEqual(
            violations,
            [Violation("dataset/planted.py", 1, "private launch_plan import outside insula")],
        )

    def test_python_worker_check_and_default_gpu_device_list_have_one_active_home(self):
        sources = _active_python_sources()
        launch_plan = (AUTONOMY_ROOT / "insula/launch_plan.py").read_text()

        self.assertEqual(launch_plan.count("def python_worker_command("), 1)
        self.assertEqual(launch_plan.count("_DEFAULT_GPU_CONTROL_DEVICE_PATHS ="), 1)
        self.assertEqual(launch_plan.count('"/dev/nvidiactl"'), 1)
        self.assertEqual(launch_plan.count('"/dev/nvidia-uvm"'), 1)
        self.assertEqual(
            [
                relative
                for relative, source in sources.items()
                if (
                    "declared original Python worker" in source
                    or "launch plan record Python worker" in source
                    or "isolated namespace and declared original Python worker" in source
                )
            ],
            [],
        )
        self.assertEqual(
            [
                relative
                for relative, source in sources.items()
                if '"/dev/nvidiactl"' in source and '"/dev/nvidia-uvm"' in source
            ],
            [],
        )

    def test_scanner_reports_planted_unquoted_shell_bwrap_call(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            planted = root / "dataset" / "planted.sh"
            planted.parent.mkdir(parents=True)
            planted.write_text("#!/usr/bin/env bash\nexec bwrap \"$@\"\n")

            violations = scan_launch_plan_boundary(root)

        self.assertEqual(
            violations,
            [Violation("dataset/planted.sh", 2, "direct shell bwrap execution")],
        )


if __name__ == "__main__":
    unittest.main()
