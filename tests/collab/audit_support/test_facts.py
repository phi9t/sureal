"""Hand-derived corrupt/good facts, independent of the producer's implementation."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    from audit_support.facts import check_journal, select_cases, content_digest
except ImportError:
    check_journal = select_cases = content_digest = None


def literal_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class JournalFactsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "records").mkdir()
        self.effect = {"schema_version":1,"record_type":"Effect","operation_id":"op",
            "step_name":"write","kind":"fixture","inputs":{"schema_version":1,"x":7},
            "input_digest": literal_digest({"schema_version":1,"x":7}),"state":"prepared"}
        self.effect_id = literal_digest(self.effect)
        self.event = {"schema_version":1,"sequence":1,"previous":None,"event":"prepared",
            "operation_id":"op","record_id":self.effect_id,"record":self.effect}
        self.event["sha256"] = literal_digest(self.event)
        (self.root / "events.jsonl").write_text(json.dumps(self.event)+"\n")
        (self.root / "records" / (self.effect_id+".json")).write_text(json.dumps(self.effect))
        self.projection = {"schema_version":1,"head":self.event["sha256"],"sequence":1,
            "effects":{"op\0write":self.effect_id},"results":{}}
        (self.root / "current.json").write_text(json.dumps(self.projection))

    def require_implemented(self):
        self.assertIsNotNone(check_journal, "Independent raw journal oracle absent")

    def test_surviving_prepared_intent_does_not_become_success(self):
        # Treating a pending intent as success is an actual unsafe recovery bug.
        self.require_implemented()
        facts = check_journal(self.root)
        self.assertEqual(facts["unresolved_effects"], [self.effect_id])
        self.assertEqual(facts["results"], {})

    def test_result_event_without_immutable_record_never_resolves_effect(self):
        result={"schema_version":1,"record_type":"EffectResult","operation_id":"op",
                "effect_id":self.effect_id,"facts":{"schema_version":1,"outcome":"ok"}}
        result_id=literal_digest(result)
        event={"schema_version":1,"sequence":2,"previous":self.event["sha256"],
               "event":"result","operation_id":"op","record_id":result_id,"record":result}
        event["sha256"]=literal_digest(event)
        with (self.root/"events.jsonl").open("a") as stream:
            stream.write(json.dumps(event)+"\n")
        partial=check_journal(self.root,allow_incomplete=True)
        self.assertEqual(partial["results"],{})
        self.assertEqual(partial["unresolved_effects"],[self.effect_id])
        self.assertEqual(partial["uncommitted_results"],{self.effect_id:result_id})
        with self.assertRaises(ValueError):
            check_journal(self.root)

    def test_earlier_event_corruption_cannot_be_hidden_by_valid_projection(self):
        self.require_implemented()
        self.event["record"]["inputs"]["x"] = 8
        (self.root / "events.jsonl").write_text(json.dumps(self.event)+"\n")
        with self.assertRaises(ValueError):
            check_journal(self.root)

    def test_projection_cannot_add_a_result_without_a_valid_journal_record(self):
        self.require_implemented()
        self.projection["results"][self.effect_id] = "f"*64
        (self.root / "current.json").write_text(json.dumps(self.projection))
        with self.assertRaises(ValueError):
            check_journal(self.root)

    def test_torn_tail_is_distinct_from_earlier_corruption(self):
        self.require_implemented()
        with (self.root / "events.jsonl").open("ab") as stream:
            stream.write(b'{"unfinished":')
        with self.assertRaises(ValueError):
            check_journal(self.root)
        facts = check_journal(self.root, allow_incomplete=True)
        self.assertEqual(facts["torn_tail_sha256"], hashlib.sha256(b'{"unfinished":').hexdigest())
        self.assertEqual(facts["sequence"], 1)

    def test_floats_and_duplicate_keys_are_rejected_in_digest_records(self):
        self.require_implemented()
        with self.assertRaises(ValueError):
            content_digest({"schema_version":1,"x":0.5})
        (self.root / "events.jsonl").write_text('{"schema_version":1,"schema_version":1}\n')
        with self.assertRaises(ValueError):
            check_journal(self.root)


class CoverageFactsTests(unittest.TestCase):
    def test_role_selection_requires_every_matching_authoritative_case(self):
        self.assertIsNotNone(select_cases, "Independent phase/role coverage oracle absent")
        coverage = {"schema_version":1,"ticket_roles":{"49":["implementation","metadata"]},
            "cases":{"49":[{"id":"shared","phase":"gate","candidate_roles":["all"]},
                              {"id":"map","phase":"gate","candidate_roles":["metadata"]},
                              {"id":"code","phase":"gate","candidate_roles":["implementation"]}]}}
        self.assertEqual([x["id"] for x in select_cases(coverage,"49","gate","metadata")],
                         ["shared","map"])
        with self.assertRaises(ValueError):
            select_cases(coverage,"49","gate","pilot-state")
        with self.assertRaises(ValueError):
            select_cases(coverage,"49","closure","implementation")


if __name__ == "__main__":
    unittest.main()
