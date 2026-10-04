"""Relabeled commands and empty fault fixtures cannot supply independent proof."""
import json
import hashlib
import shutil
from pathlib import Path
import tempfile
import unittest

try:
    from audit_support.conditions import check_source_command, check_boundary
except ImportError:
    check_source_command=check_boundary=None
from audit_support.conditions import check_ignore_change


class CauseTests(unittest.TestCase):
    def test_actual_failed_result_fsync_retains_unknown_effect(self):
        def digest(value):
            return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            before=Path(temp)/"before";before.mkdir();(before/"records").mkdir()
            effect={"schema_version":1,"record_type":"Effect","operation_id":"op","step_name":"write",
                    "kind":"fixture","inputs":{"schema_version":1},"input_digest":digest({"schema_version":1}),
                    "state":"prepared"}
            effect_id=digest(effect)
            first={"schema_version":1,"sequence":1,"previous":None,"event":"prepared","operation_id":"op",
                   "record_id":effect_id,"record":effect};first["sha256"]=digest(first)
            (before/"events.jsonl").write_text(json.dumps(first)+"\n")
            (before/"records"/(effect_id+".json")).write_text(json.dumps(effect))
            (before/"current.json").write_text(json.dumps({"schema_version":1,"sequence":1,"head":first["sha256"],
                "effects":{"op\0write":effect_id},"results":{}}))
            interrupted=Path(temp)/"interrupted";shutil.copytree(before,interrupted)
            result={"schema_version":1,"record_type":"EffectResult","operation_id":"op",
                    "effect_id":effect_id,"facts":{"schema_version":1,"outcome":"ok"}}
            result_id=digest(result)
            second={"schema_version":1,"sequence":2,"previous":first["sha256"],"event":"result",
                    "operation_id":"op","record_id":result_id,"record":result};second["sha256"]=digest(second)
            with (interrupted/"events.jsonl").open("a") as stream:
                stream.write(json.dumps(second)+"\n")
            trace=[{"schema_version":1,"sequence":1,"operation_id":"op","event":"call",
                    "boundary":"result-fsync","relative_path":"events.jsonl"},
                   {"schema_version":1,"sequence":2,"operation_id":"op","event":"raised",
                    "boundary":"result-fsync","relative_path":"events.jsonl","errno":5}]
            partial=check_boundary(before,interrupted,"result-fsync","op",trace)
            self.assertEqual(partial["unresolved_effects"],[effect_id])
            with self.assertRaises(ValueError):
                check_boundary(before,interrupted,"result-fsync","other-operation",trace)
            (interrupted/"records"/(result_id+".json")).write_text(json.dumps(result))
            with self.assertRaises(ValueError):
                check_boundary(before,interrupted,"result-fsync","op",trace)
    def test_ignore_rule_order_cannot_be_changed_by_binding_commit(self):
        check_ignore_change(b"*\n!keep\n",b"*\n!keep\n.kata.local.toml\n")
        check_ignore_change(b"*\n!keep",b"*\n!keep\n.kata.local.toml\n")
        for changed in (b"!keep\n*\n.kata.local.toml\n",b"*\n.kata.local.toml\n",
                        b"*\n!keep\n.kata.local.toml\n.kata.local.toml\n"):
            with self.assertRaises(ValueError):
                check_ignore_change(b"*\n!keep\n",changed)
    def test_printer_cannot_be_relabelled_as_candidate_cli(self):
        self.assertIsNotNone(check_source_command,"Source-bound command oracle absent")
        materialization={"source":"/retained/X"}
        admission={"runtime":{"reference_path":"/reference","native_output_directory":"/outputs-host"}}
        command={"argv":["printf",'{"outcome":"refused"}'],"cwd":"/fixture"}
        with self.assertRaises(ValueError):
            check_source_command(command,materialization,admission)

    def test_empty_states_and_labelled_fault_do_not_credit_prepared_boundary(self):
        self.assertIsNotNone(check_boundary,"Boundary-specific raw consequence oracle absent")
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ("before","interrupted"):
                state=root/name;state.mkdir();(state/"records").mkdir()
                (state/"events.jsonl").write_bytes(b"")
                (state/"current.json").write_text(json.dumps({"schema_version":1,"sequence":0,
                    "head":None,"effects":{},"results":{}}))
            trace=[{"schema_version":1,"sequence":1,"operation_id":"op","event":"call",
                    "boundary":"prepared-event","relative_path":"events.jsonl"},
                   {"schema_version":1,"sequence":2,"operation_id":"op","event":"interrupted",
                    "boundary":"prepared-event","relative_path":"events.jsonl"}]
            with self.assertRaises(ValueError):
                check_boundary(root/"before",root/"interrupted","prepared-event","op",trace)


if __name__=="__main__":
    unittest.main()
