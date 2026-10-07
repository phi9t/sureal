"""Concept-boundary checks for resource-bounded execution."""
import ast
import importlib.util
from pathlib import Path
import unittest


RESOURCE_ROOT = Path(__file__).resolve().parent
FORBIDDEN_AREAS = {"advanced", "architecture", "cohort", "tier1"}


class ResourceConceptBoundaryTests(unittest.TestCase):
    def test_continuation_apis_are_owned_by_resources_package(self):
        for name in [
            "resources.compare_state",
            "resources.legacy_binding",
            "resources.legacy_values",
        ]:
            with self.subTest(name=name):
                self.assertIsNotNone(importlib.util.find_spec(name))

    def test_production_resources_do_not_import_study_areas(self):
        offenders = []
        for path in sorted(RESOURCE_ROOT.glob("*.py")):
            if path.name.endswith("_test.py"):
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    modules = [node.module]
                else:
                    continue
                for module in modules:
                    area = module.split(".", 1)[0]
                    if area in FORBIDDEN_AREAS:
                        offenders.append(f"{path.name}:{node.lineno}: {module}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
