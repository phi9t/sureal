"""The public command emits bounded-operation outcomes, never task acceptance."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CliTests(unittest.TestCase):
    def test_outer_import_result_conflict_is_unknown_and_retry_preserves_map(self):
        from argparse import Namespace
        from unittest.mock import patch
        from kata_fixture import KataFixture
        from test_admission import git
        from test_contracts import module
        cli, api, errors, storage = (module(self, name) for name in ('cli', 'kata', 'contracts', 'store'))
        with KataFixture() as fixture:
            metadata = fixture.root/'metadata'
            git(fixture.source, 'worktree', 'add', '-b', 'codex/metadata49/fixture', str(metadata))
            fixture.call('--workspace', str(metadata), '--project', 'sureal-test49', 'init')
            definitions = fixture.root/'definitions.json'
            definitions.write_text(json.dumps({'schema_version': 1, 'tasks': [api.definition_record(fixture.definition('49'))]}))
            output = metadata/'docs/research/kata-task-map.json'
            args = Namespace(definitions=definitions, task_map_output=output, operation_id='outer-map-import')
            actual_record, failed = storage.Store.record, []
            def record(store, effect, facts):
                if effect.kind == 'task-import' and not failed:
                    failed.append(True)
                    raise errors.Refusal('OWNER_CONFLICT', 'Result section temporarily occupied')
                return actual_record(store, effect, facts)
            with patch.object(storage.Store, 'record', record):
                with self.assertRaises(errors.Refusal) as caught:
                    cli._import(args, fixture.project)
                self.assertEqual(caught.exception.outcome, 'unknown')
                before = output.read_bytes()
                recovered = cli._import(args, fixture.project)
            self.assertEqual(recovered.outcome, 'ok')
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(len(fixture.call('--project', 'sureal-test49', 'list')['issues']), 1)

    def test_preparation_input_snapshot_refuses_parse_hash_races_before_native_writes(self):
        from argparse import Namespace
        from unittest.mock import patch
        from kata_fixture import KataFixture
        from test_admission import git
        from test_contracts import module
        cli, api, errors = (module(self, name) for name in ('cli', 'kata', 'contracts'))
        for changed in ('binding', 'definitions'):
            with self.subTest(changed=changed), KataFixture() as fixture:
                metadata = fixture.root/'metadata'
                git(fixture.source, 'worktree', 'add', '-b', 'codex/metadata49/fixture', str(metadata))
                fixture.call('--workspace', str(metadata), '--project', 'sureal-test49', 'init')
                binding = metadata/'.kata.toml'
                definitions = fixture.root/'definitions.json'
                definitions.write_text(json.dumps({'schema_version': 1, 'tasks': [api.definition_record(fixture.definition('49'))]}))
                args = Namespace(definitions=definitions, task_map_output=metadata/'docs/research/kata-task-map.json', operation_id='input-race')
                if changed == 'binding':
                    actual = cli.tomllib.loads
                    def parse(raw):
                        value = actual(raw)
                        binding.write_text('version = 1\n[project]\nname = "foreign-test49"\n')
                        return value
                    hook = patch.object(cli.tomllib, 'loads', side_effect=parse)
                else:
                    actual = cli.loads
                    def parse(raw):
                        value = actual(raw)
                        altered = json.loads(definitions.read_bytes())
                        altered['tasks'][0]['goal'] = 'Different goal after parse'
                        definitions.write_text(json.dumps(altered))
                        return value
                    hook = patch.object(cli, 'loads', side_effect=parse)
                with hook, self.assertRaises(errors.Refusal) as caught:
                    cli._import(args, fixture.project)
                self.assertEqual(caught.exception.outcome, 'refused')
                self.assertFalse(fixture.project.state.exists(), 'Changed parsed inputs created a durable operation')
                self.assertFalse(args.task_map_output.exists())
                self.assertEqual(fixture.call('--project', 'sureal-test49', 'list')['issues'], [])

    def test_mainline_advance_during_import_retains_unknown_intent_without_writing_map(self):
        from argparse import Namespace
        from unittest.mock import patch
        from kata_fixture import KataFixture
        from test_admission import git
        from test_contracts import module
        cli, api, errors = module(self, 'cli'), module(self, 'kata'), module(self, 'contracts')
        with KataFixture() as fixture:
            metadata = fixture.root/'metadata'
            git(fixture.source, 'worktree', 'add', '-b', 'codex/metadata49/fixture', str(metadata))
            fixture.call('--workspace', str(metadata), '--project', 'sureal-test49', 'init')
            definitions = fixture.root/'definitions.json'
            definitions.write_text(json.dumps({'schema_version': 1, 'tasks': [api.definition_record(fixture.definition('49'))]}))
            output = metadata/'docs/research/kata-task-map.json'
            args = Namespace(definitions=definitions, task_map_output=output, operation_id='map-import')
            actual_import = api.Kata.import_tasks
            def importing(client, tasks):
                result = actual_import(client, tasks)
                (fixture.source/'docs/new.md').write_text('# Concurrent mainline advance\n')
                git(fixture.source, 'add', 'docs/new.md')
                git(fixture.source, 'commit', '-m', 'Concurrent fixture integration')
                return result
            with patch.object(api.Kata, 'import_tasks', importing):
                with self.assertRaises(errors.Refusal) as caught:
                    cli._import(args, fixture.project)
            self.assertEqual(caught.exception.outcome, 'unknown')
            self.assertFalse(output.exists(), 'Old-base map was published after canonical advance')
            events = [json.loads(line) for line in (fixture.project.state/'events.jsonl').read_text().splitlines()]
            self.assertTrue(any(row.get('record', {}).get('kind') == 'task-import' for row in events))

    def test_read_only_command_does_not_add_source_bytecode(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'controller'
            scripts = root/'scripts'
            shutil.copytree(ROOT/'scripts/_collab', scripts/'_collab',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            shutil.copyfile(ROOT/'scripts/collab.py', scripts/'collab.py')
            before = {path.relative_to(root) for path in root.rglob('*')}
            environment = dict(__import__('os').environ)
            environment.pop('PYTHONDONTWRITEBYTECODE', None)
            actual = subprocess.run([sys.executable, str(scripts/'collab.py'), 'status',
                '--project-state', str(Path(directory)/'absent')], cwd=root, env=environment,
                capture_output=True, timeout=5)
            self.assertEqual(actual.returncode, 2, actual.stderr)
            self.assertEqual({path.relative_to(root) for path in root.rglob('*')}, before,
                             'Read-only controller command dirtied immutable source')

    def test_usage_has_machine_readable_64_envelope_and_no_state_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/collab.py"), "task", "start",
                                     "--project-state", str(state)], cwd=ROOT,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 64, result.stderr)
            envelope = json.loads(result.stdout)
            self.assertEqual(envelope["outcome"], "refused")
            self.assertEqual(envelope["reason"], "USAGE_ERROR")
            self.assertFalse(state.exists())

    def test_status_of_missing_project_refuses_without_creating_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/collab.py"), "status",
                                     "--project-state", str(state), "--format", "json"], cwd=ROOT,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertTrue(result.stdout.strip(), "planned status envelope is not implemented")
            self.assertEqual(json.loads(result.stdout)["reason"], "SOURCE_UNAVAILABLE")
            self.assertFalse(state.exists())

    def test_new_unknown_effect_has_distinct_exit3_envelope(self):
        from contextlib import redirect_stdout
        import io
        from unittest.mock import patch
        from test_contracts import module
        records = module(self, 'contracts')
        cli = module(self, 'cli')
        self.assertIn('outcome', __import__('inspect').signature(records.Refusal).parameters,
                      'Newly uncertain external effects cannot be distinguished from precondition refusals')
        output = io.StringIO()
        with patch.object(cli, 'admit_project', side_effect=records.Refusal('UNKNOWN_EFFECT', 'actual write is uncertain', outcome='unknown')):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'admission.json'
                path.write_text('{"schema_version":1}')
                with redirect_stdout(output):
                    code = cli.main(['init', '--canonical', directory, '--state', str(Path(directory)/'state'),
                                     '--admission', str(path), '--operation-id', 'unknown-op'])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(output.getvalue())['outcome'], 'unknown')

    def test_foreign_metadata_binding_refuses_before_issue_or_state_creation(self):
        from argparse import Namespace
        from kata_fixture import KataFixture
        from test_admission import git
        from test_contracts import module
        cli = module(self, 'cli')
        api = module(self, 'kata')
        errors = module(self, 'contracts')
        with KataFixture() as fixture:
            metadata = fixture.root/'metadata'
            git(fixture.source, 'worktree', 'add', '-b', 'codex/metadata49/fixture', str(metadata))
            (metadata/'.kata.toml').write_text('version = 1\n[project]\nname = "foreign-test49"\n')
            definitions = fixture.root/'definitions.json'
            definitions.write_text(json.dumps({'schema_version': 1, 'tasks': [api.definition_record(fixture.definition('49'))]}))
            args = Namespace(definitions=definitions, task_map_output=metadata/'docs/research/kata-task-map.json', operation_id='map-import')
            with self.assertRaises(errors.Refusal) as caught:
                cli._import(args, fixture.project)
            self.assertEqual(caught.exception.reason, 'UNADMITTED_SPEC')
            self.assertFalse(fixture.project.state.exists())
            self.assertEqual(fixture.call('--project', 'sureal-test49', 'list')['issues'], [])

    def test_task_map_output_cannot_write_an_arbitrary_metadata_file(self):
        from argparse import Namespace
        from kata_fixture import KataFixture
        from test_admission import git
        from test_contracts import module
        cli, api, errors = module(self, 'cli'), module(self, 'kata'), module(self, 'contracts')
        with KataFixture() as fixture:
            metadata = fixture.root/'metadata'
            git(fixture.source, 'worktree', 'add', '-b', 'codex/metadata49/fixture', str(metadata))
            (metadata/'.kata.toml').write_text('version = 1\n[project]\nname = "sureal-test49"\n')
            definitions = fixture.root/'definitions.json'
            definitions.write_text(json.dumps({'schema_version': 1, 'tasks': [api.definition_record(fixture.definition('49'))]}))
            with self.assertRaises(errors.Refusal) as caught:
                cli._import(Namespace(definitions=definitions, task_map_output=metadata/'unowned.py', operation_id='bad-output'), fixture.project)
            self.assertEqual(caught.exception.reason, 'SCOPE_CONFLICT')
            self.assertFalse(fixture.project.state.exists())
            self.assertEqual(fixture.call('--project', 'sureal-test49', 'list')['issues'], [])

    def test_stale_metadata_base_refuses_before_issue_or_state_creation(self):
        from argparse import Namespace
        from kata_fixture import KataFixture
        from test_admission import git
        from test_contracts import module
        cli, api, errors = module(self, 'cli'), module(self, 'kata'), module(self, 'contracts')
        with KataFixture() as fixture:
            metadata = fixture.root/'metadata'
            git(fixture.source, 'worktree', 'add', '-b', 'codex/metadata49/fixture', str(metadata))
            (metadata/'.kata.toml').write_text('version = 1\n[project]\nname = "sureal-test49"\n')
            git(metadata, 'add', '.kata.toml')
            git(metadata, 'commit', '-m', 'Different metadata base')
            definitions = fixture.root/'definitions.json'
            definitions.write_text(json.dumps({'schema_version': 1, 'tasks': [api.definition_record(fixture.definition('49'))]}))
            with self.assertRaises(errors.Refusal) as caught:
                cli._import(Namespace(definitions=definitions, task_map_output=metadata/'docs/research/kata-task-map.json', operation_id='stale-map'), fixture.project)
            self.assertEqual(caught.exception.reason, 'STALE_BASE')
            self.assertFalse(fixture.project.state.exists())
            self.assertEqual(fixture.call('--project', 'sureal-test49', 'list')['issues'], [])

    def test_admitted_metadata_import_retry_preserves_map_record_and_issue_uid(self):
        from argparse import Namespace
        from kata_fixture import KataFixture
        from test_admission import git
        from test_contracts import module
        cli, api = module(self, 'cli'), module(self, 'kata')
        with KataFixture() as fixture:
            metadata = fixture.root/'metadata'
            git(fixture.source, 'worktree', 'add', '-b', 'codex/metadata49/fixture', str(metadata))
            fixture.call('--workspace', str(metadata), '--project', 'sureal-test49', 'init')
            definitions = fixture.root/'definitions.json'
            definitions.write_text(json.dumps({'schema_version': 1, 'tasks': [api.definition_record(fixture.definition('49'))]}))
            output = metadata/'docs/research/kata-task-map.json'
            args = Namespace(definitions=definitions, task_map_output=output, operation_id='map-import')
            first = cli._import(args, fixture.project)
            original = output.read_bytes()
            repeated = cli._import(args, fixture.project)
            self.assertEqual(first.record_id, repeated.record_id)
            self.assertEqual(original, output.read_bytes())
            self.assertEqual(len(fixture.call('--project', 'sureal-test49', 'list')['issues']), 1)


if __name__ == "__main__":
    unittest.main()
