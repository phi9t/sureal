"""Static boundary checks for Insula launch plans."""
from __future__ import annotations

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
    ("direct bwrap namespace argv", re.compile(r"""["']--(?:unshare-all|clearenv)["']""")),
)

RUNTIME_LOCK_PATTERNS = (
    ("direct runtime lock JSON path", re.compile(r"""Path\(\s*str\([^#\n]+\)\s*\+\s*["']\.lock\.json["']\s*\)\.read_text\(""")),
    ("direct runtime lock JSON load", re.compile(r"""json\.loads\([^#\n]*(?:Path\(\s*str\([^#\n]+\)\s*\+\s*["']\.lock\.json|lock_path|runtime_lock)[^#\n]*read_text\(""")),
    ("direct rootfs content verification", re.compile(r"(?<!def )\bverify_rootfs\(")),
)

ALLOWED_EXACT = {
    "insula/launch_plan.py",
    "insula/runtime_roots.py",
    "insula/runtime_identity.py",
    "insula/build_cpu_rootfs.sh",
    "insula/build_gpu_bazel_rootfs_v6.sh",
}

# The only active resource-specific old-receipt reconstruction outside the
# module lives in these named resources.command helpers. New launches must use
# launch-plan data and with_mounts; the allowlist is only for retained receipts.
RESOURCE_COMMAND_LEGACY_HELPERS = {
    "wrap_legacy_receipt_command",
    "wrap_rendered_plan_command",
    "rendered_command_matches_record",
    "_require_resource_aliases_unused",
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


def scan_launch_plan_boundary(root: Path = AUTONOMY_ROOT) -> list[Violation]:
    violations = []
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or not _is_scanned_file(path):
            continue
        relative = path.relative_to(root).as_posix()
        if not _is_active_path(relative):
            continue
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        function = None
        for line_number, line in enumerate(lines, start=1):
            match = re.match(r"def ([A-Za-z_][A-Za-z0-9_]*)\(", line)
            if match:
                function = match.group(1)
            for kind, pattern in (*BWRAP_ARGV_PATTERNS, *RUNTIME_LOCK_PATTERNS):
                if relative == "resources/command.py" and function in RESOURCE_COMMAND_LEGACY_HELPERS:
                    continue
                if pattern.search(line):
                    violations.append(Violation(relative, line_number, kind))
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

    def test_resource_wrapper_helpers_are_not_public_launch_plan_api(self):
        import insula.launch_plan as launch_plan

        resource_helpers = {
            "wrap_legacy_receipt_command",
            "wrap_rendered_plan_command",
            "wrap_resource_plan",
            "rendered_command_matches_record",
            "recorded_resource_mounts_match",
        }
        public = set(getattr(launch_plan, "__all__", ()))
        self.assertFalse(resource_helpers & public)
        for name in resource_helpers:
            self.assertFalse(hasattr(launch_plan, name), name)


if __name__ == "__main__":
    unittest.main()
