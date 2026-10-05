"""Exercise real locks, writes and recovery, including abrupt process exit."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_contracts import module

ROOT = Path(__file__).resolve().parents[2]


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"

    def test_intent_result_order_and_idempotent_retry(self):
        api = module(self, "store")
        errors = module(self, "contracts")
        store = api.Store(self.state)
        inputs = {"schema_version": 1, "target": "fixture"}
        effect = store.prepare("fixture-create", inputs, "op-1")
        self.assertEqual(store.prepare("fixture-create", inputs, "op-1"), effect)
        result = store.record(effect, {"schema_version": 1, "outcome": "ok", "observed_id": "actual-1"})
        self.assertEqual(result.outcome, "ok")
        self.assertEqual(store.read(result.record_id)["facts"]["observed_id"], "actual-1")
        events = [json.loads(x) for x in (self.state / "events.jsonl").read_text().splitlines()]
        self.assertEqual([x["event"] for x in events], ["prepared", "result"])
        self.assertEqual([x["sequence"] for x in events], [1, 2])
        with self.assertRaises(errors.Refusal) as caught:
            store.prepare("fixture-create", {"schema_version": 1, "target": "other"}, "op-1")
        self.assertEqual(caught.exception.reason, "CANDIDATE_MISMATCH")
        self.assertEqual(len((self.state / "events.jsonl").read_text().splitlines()), 2)

    def test_created_state_directory_is_parent_fsynced_before_first_intent(self):
        api = module(self, "store")
        actual = os.fsync
        visited = []
        def observe(fd):
            visited.append(Path(os.readlink("/proc/self/fd/" + str(fd))))
            actual(fd)
        with patch.object(os, "fsync", side_effect=observe):
            api.Store(self.state).prepare("probe", {"schema_version": 1}, "op-1")
        self.assertIn(self.state.parent, visited)
        self.assertLess(visited.index(self.state.parent), visited.index(self.state / "events.jsonl"))

    def test_lock_excludes_second_controller(self):
        api = module(self, "store")
        store = api.Store(self.state)
        script = """from pathlib import Path
from scripts._collab.store import Store
from scripts._collab.contracts import Refusal
import sys
try:
    with Store(Path(sys.argv[1])).locked(): print('unexpected lock')
except Refusal as error:
    print(error.reason); raise SystemExit(2)
"""
        with store.locked():
            result = subprocess.run([sys.executable, "-c", script, str(self.state)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout.strip(), "OWNER_CONFLICT")
        with api.Store(self.state).locked():
            pass

    def test_durable_boundary_recovery(self):
        api = module(self, "store")
        script = """from pathlib import Path
from scripts._collab.store import Store
import os, sys
original=os.fsync; count=0
def crash(fd):
    global count
    original(fd); count+=1
    if count==int(sys.argv[2]): os._exit(99)
os.fsync=crash
Store(Path(sys.argv[1])).prepare('probe', {'schema_version':1,'target':'owned'}, 'crash-op')
"""
        for boundary in range(1, 10):
            with self.subTest(boundary=boundary):
                state = self.state / str(boundary)
                result = subprocess.run([sys.executable, "-c", script, str(state), str(boundary)],
                                        cwd=ROOT, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 99, result.stderr)
                reopened = api.Store(state)
                recovered = reopened.reconcile_journal()
                self.assertEqual(recovered.outcome, "ok")
                # A surviving intent never becomes evidence of an external result.
                projection = json.loads((state / "current.json").read_text())
                self.assertEqual(projection["results"], {})
                for effect_id in projection["effects"].values():
                    self.assertEqual(reopened.read(effect_id)["state"], "prepared")

    def test_torn_tail_retained_and_earlier_corruption_refuses(self):
        api = module(self, "store")
        errors = module(self, "contracts")
        store = api.Store(self.state)
        effect = store.prepare("probe", {"schema_version": 1}, "op-1")
        with (self.state / "events.jsonl").open("ab") as stream:
            stream.write(b'{"sequence":2,"partial":')
        result = api.Store(self.state).reconcile_journal()
        self.assertEqual(result.outcome, "ok")
        self.assertTrue(any(p.read_bytes() == b'{"sequence":2,"partial":'
                            for p in (self.state / "incidents").glob("*.tail")))
        self.assertEqual(store.read(effect.record_id)["operation_id"], "op-1")
        history = self.state / "events.jsonl"
        history.write_bytes(history.read_bytes().replace(b'"op-1"', b'"op-9"'))
        original = history.read_bytes()
        with self.assertRaises(errors.Refusal) as caught:
            api.Store(self.state).prepare("probe", {"schema_version": 1}, "op-2")
        self.assertEqual(caught.exception.reason, "UNKNOWN_EFFECT")
        self.assertEqual(history.read_bytes(), original)

    def test_fsync_failure_does_not_project_success(self):
        api = module(self, "store")
        store = api.Store(self.state)
        effect = store.prepare("probe", {"schema_version": 1}, "op-1")
        before = (self.state / "current.json").read_bytes()
        with patch.object(os, "fsync", side_effect=OSError("injected fsync failure")):
            with self.assertRaises(OSError):
                store.record(effect, {"schema_version": 1, "outcome": "ok"})
        self.assertEqual((self.state / "current.json").read_bytes(), before)
        errors = module(self, "contracts")
        with self.assertRaises(errors.Refusal) as caught:
            api.Store(self.state).prepare("probe", {"schema_version": 1}, "op-2")
        self.assertEqual(caught.exception.reason, "UNKNOWN_EFFECT")

    def test_recovery_does_not_promote_unfsynced_result_event_to_success(self):
        api = module(self, "store")
        errors = module(self, "contracts")
        store = api.Store(self.state)
        effect = store.prepare("probe", {"schema_version": 1}, "op-1")
        before = (self.state / "current.json").read_bytes()
        with patch.object(os, "fsync", side_effect=OSError(5, "injected result event fsync failure")):
            with self.assertRaises(OSError):
                store.record(effect, {"schema_version": 1, "outcome": "ok", "observed_id": "unconfirmed"})
        with self.assertRaises(errors.Refusal) as caught:
            api.Store(self.state).reconcile_journal()
        self.assertEqual(caught.exception.reason, "UNKNOWN_EFFECT")
        self.assertEqual((self.state / "current.json").read_bytes(), before)

    def test_immutable_record_corruption_and_symlink_refused(self):
        api = module(self, "store")
        errors = module(self, "contracts")
        store = api.Store(self.state)
        effect = store.prepare("probe", {"schema_version": 1}, "op-1")
        record = self.state / "records" / (effect.record_id + ".json")
        record.write_text('{"schema_version":1,"changed":true}\n')
        with self.assertRaises(errors.Refusal):
            api.Store(self.state).reconcile_journal()
        alias = Path(self.tmp.name) / "alias"
        alias.symlink_to(self.state, target_is_directory=True)
        with self.assertRaises(errors.Refusal):
            api.Store(alias).prepare("probe", {"schema_version": 1}, "op-2")


if __name__ == "__main__":
    unittest.main()
