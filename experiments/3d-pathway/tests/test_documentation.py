from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent
DOC = REPO_ROOT / "docs" / "3d-reconstruction-pathway.md"
sys.path.insert(0, str(ROOT / "pipeline"))


class SurveyContractTest(unittest.TestCase):
    def test_every_module_has_reproduction_structure_sources_and_command(self) -> None:
        text = DOC.read_text()
        curriculum = json.loads((ROOT / "curriculum.json").read_text())
        source_map = {item["id"]: item for item in json.loads((ROOT / "sources.json").read_text())["sources"]}
        headings = [(text.index(f"## {int(module['id'])}. {module['title']}"), module) for module in curriculum["modules"]]
        self.assertEqual([module["id"] for _, module in headings], [f"{index:02d}" for index in range(1, 16)])
        required = (
            "### Evidence and observability",
            "### Representation and inference",
            "### Defining mathematics",
            "### Assumptions and failure modes",
            "### Primary-source reading sequence",
            "### Reproduction lab",
            "### Transition",
        )
        for index, (start, module) in enumerate(headings):
            end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
            section = text[start:end]
            with self.subTest(module=module["id"]):
                for label in required:
                    self.assertIn(label, section)
                for source_id in module["sources"]:
                    source = source_map[source_id]
                    self.assertIn(f"[{source_id}]({source['primary_url']})", section)
                self.assertIn(
                    f"experiments/3d-pathway/run.sh run --module {module['id']} --profile smoke",
                    section,
                )
                self.assertIn("`result.json`", section)
                self.assertIn("failure_sweep.csv`", section)

    def test_survey_has_scope_metric_and_surflo_guardrails(self) -> None:
        text = DOC.read_text()
        self.assertIn("Historical cutoff: **September 25, 2026**", text)
        self.assertIn("medical tomography", text.lower())
        self.assertIn("Novel-view synthesis", text)
        self.assertIn("surface reconstruction", text)
        self.assertIn("one persistent complete-scene state", text)
        self.assertIn(r"p(z^* \mid O)", text)
        self.assertIn("point stochasticity", text)
        self.assertIn("scene stochasticity", text)

    def test_mission_links_concisely_to_pathway(self) -> None:
        mission = (REPO_ROOT / "MISSION.md").read_text()
        marker = "docs/3d-reconstruction-pathway.md"
        self.assertEqual(mission.count(marker), 1)
        paragraph = next(block for block in mission.split("\n\n") if marker in block)
        self.assertLessEqual(len(paragraph.split()), 90)
        self.assertIn("persistent", paragraph.lower())
        self.assertIn("scene", paragraph.lower())


class AuditContractTest(unittest.TestCase):
    def test_offline_audit_validates_citations_assets_and_terminology(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "pipeline" / "audit.py"), "--offline"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["modules"], 15)
        self.assertGreaterEqual(summary["sources"], 45)
        self.assertEqual(summary["errors"], [])

    def test_audit_rejects_unknown_citation_and_task_conflation(self) -> None:
        from audit import audit_text

        known = {"known": "https://example.org/known"}
        errors = audit_text(
            "[missing](https://example.org/missing) and PSNR proves accurate geometry.",
            known,
            forbidden_patterns=["psnr proves accurate geometry"],
        )
        self.assertTrue(any("unknown citation" in error for error in errors))
        self.assertTrue(any("forbidden terminology" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
