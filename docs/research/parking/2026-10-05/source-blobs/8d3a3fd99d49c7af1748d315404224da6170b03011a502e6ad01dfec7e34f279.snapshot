"""Kata integration assertions inspect actual issue/dependency/revision readbacks."""
import json
from pathlib import Path
import sqlite3
import subprocess
import unittest

from test_contracts import module
from kata_fixture import KataFixture
from test_admission import git


class KataTests(unittest.TestCase):
    def test_completed_external_write_with_result_lock_conflict_is_unknown_and_recoverable(self):
        from unittest.mock import patch
        api, wire, storage = module(self, 'kata'), module(self, 'contracts'), module(self, 'store')
        with KataFixture() as fixture:
            client = api.Kata(fixture.project)
            uid = client.import_tasks([fixture.definition('49')]).evidence['tasks']['49']['issue_uid']
            actor = 'sureal/result-conflict49'
            actual_record = storage.Store.record
            conflicts, writes = [], []
            actual_call = client._call
            def call(arguments, **kwargs):
                if arguments == ['claim', uid]:
                    writes.append(arguments)
                return actual_call(arguments, **kwargs)
            def record(store, effect, facts):
                if effect.kind == 'kata-claim' and not conflicts:
                    conflicts.append(True)
                    raise wire.Refusal('OWNER_CONFLICT', 'Another bounded state section owns the lock')
                return actual_record(store, effect, facts)
            with patch.object(client, '_call', side_effect=call), patch.object(storage.Store, 'record', record):
                with self.assertRaises(wire.Refusal) as caught:
                    client.claim(uid, actor)
                self.assertEqual(caught.exception.outcome, 'unknown')
                self.assertEqual(client.read_issue(uid)['issue']['owner'], actor)
                recovered = client.claim(uid, actor)
            self.assertEqual(recovered['issue']['owner'], actor)
            self.assertEqual(len(writes), 1, 'Result persistence retry repeated the completed native claim')

    def test_changed_definition_during_native_write_cannot_accept_import(self):
        from unittest.mock import patch
        api, wire = module(self, 'kata'), module(self, 'contracts')
        with KataFixture() as fixture:
            client = api.Kata(fixture.project)
            original = fixture.definition('49')
            actual_call = client._call
            changed = []
            def call(arguments, **kwargs):
                response = actual_call(arguments, **kwargs)
                if arguments[:2] == ['meta', 'set'] and arguments[3] == 'sureal_definition' and not changed:
                    (fixture.source/'docs/49.md').write_text('# New acceptance after native write\n')
                    git(fixture.source, 'add', 'docs/49.md')
                    git(fixture.source, 'commit', '-m', 'Superseding fixture definition')
                    changed.append(True)
                return response
            with patch.object(client, '_call', side_effect=call):
                with self.assertRaises(wire.Refusal) as caught:
                    client.import_tasks([original])
            self.assertTrue(changed)
            self.assertEqual(caught.exception.outcome, 'unknown')

    def test_lost_claim_ack_reconciles_unknown_with_actual_owner_without_reclaim(self):
        from unittest.mock import patch
        api, wire = module(self, 'kata'), module(self, 'contracts')
        with KataFixture() as fixture:
            client = api.Kata(fixture.project)
            uid = client.import_tasks([fixture.definition('49')]).evidence['tasks']['49']['issue_uid']
            actor = 'sureal/lost-ack49'
            actual_call = client._call
            writes = []
            def call(arguments, **kwargs):
                response = actual_call(arguments, **kwargs)
                if arguments == ['claim', uid]:
                    writes.append(arguments)
                    raise wire.Refusal('UNKNOWN_EFFECT', 'Actual claim succeeded but acknowledgement was lost')
                return response
            with patch.object(client, '_call', side_effect=call):
                with self.assertRaises(wire.Refusal) as uncertain:
                    client.claim(uid, actor)
                self.assertEqual(uncertain.exception.outcome, 'unknown')
                restored = client.claim(uid, actor)
            self.assertEqual(restored['issue']['owner'], actor)
            self.assertEqual(len(writes), 1, 'Matching retry replayed an external claim')
            events = [json.loads(line) for line in (fixture.project.state/'events.jsonl').read_text().splitlines()]
            self.assertTrue(any(row['record'].get('facts', {}).get('outcome') == 'unknown' for row in events),
                            'Reconciliation must retain the original unknown result')

    def test_native_database_schema_is_not_a_protocol_record_schema(self):
        wire = module(self, 'contracts')
        with KataFixture() as fixture:
            raw = wire.canonical({'schema_version': 1, 'kata': fixture.project.kata})
            self.assertEqual(wire.loads(raw)['kata']['database_schema_version'], fixture.health['schema_version'])

    def test_kata_import_idempotency_and_dependency_readback(self):
        api = module(self, "kata")
        with KataFixture() as fixture:
            client = api.Kata(fixture.project)
            definitions = [fixture.definition("49"), fixture.definition("50", ("49",))]
            first = client.import_tasks(definitions)
            second = client.import_tasks(definitions)
            self.assertEqual(first.outcome, "ok")
            self.assertEqual(first.evidence["tasks"], second.evidence["tasks"])
            issues = fixture.call("--project", "sureal-test49", "list")["issues"]
            self.assertEqual(len(issues), 2)
            dependency = first.evidence["tasks"]["49"]["issue_uid"]
            dependent = first.evidence["tasks"]["50"]["issue_uid"]
            ready = fixture.call("--project", "sureal-test49", "ready")["issues"]
            self.assertEqual([x["uid"] for x in ready], [dependency])
            with sqlite3.connect(fixture.home / "kata.db") as database:
                links = database.execute("select type, from_issue_id, to_issue_id from links").fetchall()
                ids = dict(database.execute("select uid,id from issues").fetchall())
            self.assertIn(("blocks", ids[dependency], ids[dependent]), links)
            before = client.read_issue(dependent)["issue"]["metadata"]["sureal_definition"]
            (fixture.source / "docs/50.md").write_text("#50\nReviewed replacement definition.\n")
            git(fixture.source, "add", "docs/50.md")
            git(fixture.source, "commit", "-m", "revision")
            revised = [fixture.definition("49"), fixture.definition("50", ("49",))]
            result = client.import_tasks(revised)
            self.assertEqual(result.evidence["tasks"]["50"]["issue_uid"], dependent)
            after = client.read_issue(dependent)["issue"]["metadata"]["sureal_definition"]
            self.assertNotEqual(before["spec"]["sha256"], after["spec"]["sha256"])
            self.assertEqual(definitions[1].spec["sha256"], before["spec"]["sha256"])

    def test_claim_and_metadata_require_exact_actor_and_revision(self):
        api = module(self, "kata")
        errors = module(self, "contracts")
        with KataFixture() as fixture:
            client = api.Kata(fixture.project)
            uid = client.import_tasks([fixture.definition("49")]).evidence["tasks"]["49"]["issue_uid"]
            claimed = client.claim(uid, "sureal/attempt1")
            self.assertEqual(claimed["issue"]["owner"], "sureal/attempt1")
            with self.assertRaises(errors.Refusal):
                client.claim(uid, "sureal/attempt2")
            assignment = {"schema_version": 1, "actor": "sureal/attempt1", "generation": "generation1"}
            revision = str(claimed["issue"]["revision"])
            written = client.assign(uid, revision, assignment)
            self.assertEqual(written["issue"]["metadata"]["sureal_assignment"], assignment)
            with self.assertRaises(errors.Refusal):
                client.assign(uid, revision, {**assignment, "generation": "obsolete"})
            self.assertEqual(client.read_issue(uid)["issue"]["owner"], "sureal/attempt1")
            with self.assertRaises(errors.Refusal):
                client.release(uid, "sureal/attempt2")

    def test_assignment_retry_reads_same_effect_without_second_metadata_write(self):
        api = module(self, "kata")
        with KataFixture() as fixture:
            client = api.Kata(fixture.project)
            uid = client.import_tasks([fixture.definition("49")]).evidence["tasks"]["49"]["issue_uid"]
            claimed = client.claim(uid, "sureal/retry")
            revision = str(claimed["issue"]["revision"])
            assignment = {"schema_version": 1, "actor": "sureal/retry", "generation": "g1"}
            first = client.assign(uid, revision, assignment)
            repeated = client.assign(uid, revision, assignment)
            self.assertEqual(first["issue"]["revision"], repeated["issue"]["revision"])
            self.assertEqual(client.read_issue(uid)["issue"]["revision"], repeated["issue"]["revision"])

    def test_release_retry_and_old_claim_do_not_reclaim_released_task(self):
        api = module(self, "kata")
        errors = module(self, "contracts")
        with KataFixture() as fixture:
            client = api.Kata(fixture.project)
            uid = client.import_tasks([fixture.definition("49")]).evidence["tasks"]["49"]["issue_uid"]
            client.claim(uid, "sureal/retry")
            first = client.release(uid, "sureal/retry")
            repeated = client.release(uid, "sureal/retry")
            self.assertEqual(first["issue"]["revision"], repeated["issue"]["revision"])
            with self.assertRaises(errors.Refusal):
                client.claim(uid, "sureal/retry")
            self.assertFalse(client.read_issue(uid)["issue"].get("owner"))

    def test_export_retry_retains_exact_bytes_and_refuses_changed_output(self):
        api = module(self, "kata")
        errors = module(self, "contracts")
        with KataFixture() as fixture:
            client = api.Kata(fixture.project)
            client.import_tasks([fixture.definition("49")])
            output = fixture.root / "export.jsonl"
            first = client.export(fixture.project.kata["project_id"], output)
            repeated = client.export(fixture.project.kata["project_id"], output)
            self.assertEqual(first["sha256"], repeated["sha256"])
            output.write_bytes(output.read_bytes() + b"changed")
            with self.assertRaises(errors.Refusal):
                client.export(fixture.project.kata["project_id"], output)

    def test_changed_daemon_incarnation_refuses_identity(self):
        from dataclasses import replace
        api = module(self, "kata")
        errors = module(self, "contracts")
        with KataFixture() as fixture:
            altered = replace(fixture.project, kata={**fixture.project.kata, "started_at": "wrong-incarnation"})
            with self.assertRaises(errors.Refusal):
                api.Kata(altered).identity()

    def test_project_only_export_restores_into_fresh_database(self):
        api = module(self, "kata")
        with KataFixture() as fixture:
            client = api.Kata(fixture.project)
            client.import_tasks([fixture.definition("49")])
            fixture.call("--project", "foreign-test49", "create", "Foreign fixture row")
            output = fixture.root / "project.jsonl"
            client.export(fixture.project.kata["project_id"], output)
            restored = fixture.root / "restored.db"
            fixture.call("import", "--input", str(output), "--target", str(restored), "--new-instance",
                         home=fixture.root / "restore-home")
            with sqlite3.connect(restored) as database:
                self.assertCountEqual(database.execute("select uid,name from projects").fetchall(),
                                 [("00000000000000000000000000", ".kata-system"),
                                  (fixture.project.kata["project_uid"], fixture.project.kata["name"])])
                self.assertEqual(database.execute("select count(*) from issues").fetchone()[0], 1)
                self.assertEqual(database.execute("select count(*) from issues i join projects p on p.id=i.project_id where p.uid=?",
                                 ("00000000000000000000000000",)).fetchone()[0], 0)
            self.assertFalse((fixture.project.canonical / "project.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
