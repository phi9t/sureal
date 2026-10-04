"""Auditor failure output is retained; a case name or flag cannot confer proof."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import hashlib

from audit_support.cases import accepted_report

AUDITOR=Path(__file__).resolve().parents[1]/"audit_live.py"


class EntryTests(unittest.TestCase):
    def test_flag_only_prior_report_cannot_supply_phase_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"fake.json"
            path.write_text(json.dumps({"schema_version":1,"kind":"independent-collaboration-audit",
                "ticket":"49","phase":"gate","candidate_role":"implementation","candidate":"a"*40,
                "accepted":True,"status":"pass","phase_complete":True,"cases":{}}))
            ref={"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
            with self.assertRaises(ValueError):
                accepted_report(ref,candidate="a"*40,role="implementation",phase="gate")

    def test_project_admission_cannot_be_substituted_for_gate_authority(self):
        # Accepting the wrong admission kind permits circular project self-admission.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            admission=root/"admission.json"
            admission.write_text(json.dumps({"schema_version":1,"kind":"ProjectAdmission","passed":True}))
            materialization=root/"materialization.json"
            materialization.write_text(json.dumps({"schema_version":1,"passed":True}))
            evidence=root/"evidence";evidence.mkdir()
            report=root/"audit.json"
            result=subprocess.run(["python3",str(AUDITOR),"--ticket","49","--phase","gate",
                "--candidate","a"*40,"--candidate-role","implementation","--materialization",str(materialization),
                "--gate-admission",str(admission),"--evidence",str(evidence),"--output",str(report)],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(result.returncode,2)
            self.assertTrue(report.is_file(),result.stderr.decode())
            value=json.loads(report.read_text())
            self.assertEqual(value["status"],"fail")
            self.assertFalse(value["accepted"])
            self.assertIn("GateAdmission",value["reason"])


if __name__=="__main__":
    unittest.main()
