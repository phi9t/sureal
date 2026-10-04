"""Live fixtures must exercise candidate code and retain actual interrupted bytes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class LiveTests(unittest.TestCase):
    def test_case_handoff_copies_envelopes_without_following_raw_aliases(self):
        spec = importlib.util.spec_from_file_location('handoff_test_support', ROOT/'tests/collab/live_support.py')
        support = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(support)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native = root/'native'
            native.mkdir()
            raw = native/'raw-fixture'
            raw.mkdir()
            payload = raw/'payload'
            payload.write_bytes(b'original evidence bytes')
            inode = payload.stat().st_ino
            alias = native/'namespace-alias'
            alias.symlink_to('/outputs/unavailable-on-host', target_is_directory=True)
            expected = {'manifest.json': b'{"schema_version":1}\n',
                        'actual-command.json': b'{"schema_version":1}\n',
                        'execution.log': b'actual retained stdout\n'}
            for name, data in expected.items():
                (native/name).write_bytes(data)
            destination = root/'case-envelopes'
            support.publish_case_envelopes(native, destination)
            self.assertEqual({p.name: p.read_bytes() for p in destination.iterdir()}, expected)
            self.assertEqual(payload.read_bytes(), b'original evidence bytes')
            self.assertEqual(payload.stat().st_ino, inode)
            self.assertTrue(alias.is_symlink())
            self.assertEqual(alias.readlink().as_posix(), '/outputs/unavailable-on-host')

    def test_case_handoff_refuses_symlinked_envelope_before_publication(self):
        spec = importlib.util.spec_from_file_location('unsafe_handoff_test_support', ROOT/'tests/collab/live_support.py')
        support = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(support)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native = root/'native'
            native.mkdir()
            (root/'foreign.json').write_bytes(b'{"schema_version":1}\n')
            (native/'manifest.json').symlink_to(root/'foreign.json')
            destination = root/'unstarted-publication'
            with self.assertRaises(ValueError):
                support.publish_case_envelopes(native, destination)
            self.assertFalse(destination.exists())

    def test_successful_live_entry_returns_to_frozen_resource_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resource_output = root/'resource'
            resource_output.mkdir()
            state = root/'state'
            worker = ROOT/'scripts/collab_live.py'
            wrapper = ROOT/'experiments/waymo-perception/resources/execute_worker.py'
            argv = [str(worker), 'probe', 'prepare', '--state', str(state),
                    '--operation-id', 'accounted-success']
            result = subprocess.run([sys.executable, '-B', str(wrapper), str(resource_output), *argv],
                                    cwd=ROOT, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['outcome'], 'ok')
            receipt = resource_output/'worker-resource.json'
            self.assertTrue(receipt.is_file(), 'Successful live CLI bypassed frozen worker accounting')
            measurement = json.loads(receipt.read_bytes())
            self.assertEqual(measurement['worker_argv'], argv)
            self.assertEqual(measurement['exit_code'], 0)
            self.assertGreater(measurement['self_peak_rss_kib'], 0)

    def test_nonzero_live_entry_cannot_emit_successful_resource_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resource_output = root/'resource'
            resource_output.mkdir()
            state = root/'state'
            worker = ROOT/'scripts/collab_live.py'
            wrapper = ROOT/'experiments/waymo-perception/resources/execute_worker.py'
            result = subprocess.run([sys.executable, '-B', str(wrapper), str(resource_output),
                str(worker), 'probe', 'disk-full', '--state', str(state), '--operation-id', 'accounted-failure',
                '--fault-log', str(root/'fault.jsonl')], cwd=ROOT, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertEqual(json.loads(result.stdout)['outcome'], 'unknown')
            self.assertFalse((resource_output/'worker-resource.json').exists())

    def test_gate_refuses_host_driver_outside_admitted_materialized_source_before_effects(self):
        from argparse import Namespace
        from unittest.mock import patch
        from test_contracts import module
        errors = module(self, 'contracts')
        spec = importlib.util.spec_from_file_location('wrong_source_live_support', ROOT/'tests/collab/live_support.py')
        support = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(support)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            other = root/'other-source'
            other.mkdir()
            materialization = root/'materialization.json'
            materialization.write_text(json.dumps({'schema_version': 1, 'candidate': 'a'*40, 'source': str(other)}))
            admission = root/'admission.json'
            review = root/'review.json'
            review.write_text(json.dumps({'schema_version': 1, 'verdict': 'pass', 'candidate': 'b'*40}))
            admission.write_text(json.dumps({'schema_version': 1, 'kind': 'GateAdmission', 'source': {'candidate': 'a'*40,
                'materialization_sha256': support.sha(materialization)}, 'auditor': {'source': str(other),
                'candidate': 'b'*40, 'review': {'path': str(review), 'sha256': support.sha(review)}}}))
            output = root/'unstarted-evidence'
            args = Namespace(materialization=materialization, gate_admission=admission, ticket='49',
                             candidate='a'*40, candidate_role='implementation', output=output)
            with patch.object(support, 'host_fixtures49') as host, patch.object(support, 'checked_command',
                    side_effect=AssertionError('Wrong-source driver reached an external command')) as command:
                with self.assertRaises(errors.Refusal) as caught:
                    support.gate(args)
                self.assertEqual(caught.exception.reason, 'CANDIDATE_MISMATCH')
                host.assert_not_called()
                command.assert_not_called()
            self.assertFalse(output.exists(), 'Wrong-source driver wrote gate artifacts before refusal')

    def test_prepare_boundary_probe_exits_at_actual_durable_event(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'state'
            log = Path(directory) / 'fault.jsonl'
            result = subprocess.run([sys.executable, str(ROOT/'scripts/collab_live.py'),
                'probe', 'prepared-event', '--state', str(state), '--operation-id', 'fault-op',
                '--fault-log', str(log)], cwd=ROOT, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 86, result.stderr)
            events = [json.loads(line) for line in (state/'events.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1]['operation_id'], 'fault-op')
            self.assertEqual(events[-1]['event'], 'prepared')
            self.assertFalse((state/'records'/(events[-1]['record_id']+'.json')).exists())
            trace = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(trace[-1]['event'], 'interrupted')
            self.assertEqual(trace[-1]['relative_path'], 'events.jsonl')

    def test_fsync_and_atomic_publication_probes_retain_named_boundary_bytes(self):
        for name in ('immutable-record', 'projection', 'event-fsync', 'record-fsync', 'parent-fsync', 'disk-full'):
            with self.subTest(boundary=name), tempfile.TemporaryDirectory() as directory:
                state = Path(directory)/'state'
                log = Path(directory)/'fault.jsonl'
                result = subprocess.run([sys.executable, str(ROOT/'scripts/collab_live.py'),
                    'probe', name, '--state', str(state), '--operation-id', 'fault-op',
                    '--fault-log', str(log)], cwd=ROOT, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 86 if name in ('immutable-record', 'projection') else 3, result.stderr)
                trace = [json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual(trace[-1]['boundary'], name)
                self.assertEqual(trace[-1]['operation_id'], 'fault-op')
                events = [json.loads(line) for line in (state/'events.jsonl').read_text().splitlines()]
                if name == 'disk-full':
                    self.assertEqual(events, [])
                    self.assertEqual(trace[-1]['errno'], 28)
                else:
                    self.assertEqual(len(events), 1)
                    record = state/'records'/(events[-1]['record_id']+'.json')
                    self.assertEqual(record.exists(), name in ('immutable-record', 'projection', 'parent-fsync'))
                    self.assertEqual((state/'current.json').exists(), name == 'projection')

    def test_offline_fixture_run_retains_refusal_inputs_and_recovery_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = root/'context.json'
            context.write_text(json.dumps({'schema_version': 1, 'ticket': '49', 'phase': 'gate',
                                          'candidate_role': 'implementation', 'candidate': 'fixture'}))
            admission = root/'gate-admission.json'
            admission.write_text(json.dumps({'schema_version': 1, 'state_filesystem': {'path': str(root), 'device': root.stat().st_dev}}))
            output = root/'output'
            result = subprocess.run([sys.executable, str(ROOT/'scripts/collab_live.py'), 'offline49',
                '--output', str(output), '--host-output', str(output), '--context', str(context),
                '--gate-admission', str(admission)], cwd=ROOT, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            coverage = json.loads((ROOT/'docs/collaboration/coverage.json').read_bytes())['cases']['49']
            for case in coverage:
                if case['id'] in ('clean-ref-and-path-refusals', 'real-state-fs-durability', 'journal-corruption'):
                    for relative in case['required_raw_evidence']:
                        required = output/Path(relative).relative_to('cases')
                        self.assertTrue(required.is_file(), 'Missing declared raw contract artifact: '+str(required))
            for case in ('clean-ref-and-path-refusals', 'real-state-fs-durability', 'journal-corruption'):
                oracle = json.loads((output/case/'independent-oracle.json').read_bytes())
                manifest = json.loads(Path(oracle['fixture_manifest']['path']).read_bytes())
                self.assertTrue(manifest['scenarios'])
                self.assertNotIn('passed', manifest)
            clean = json.loads((output/'clean-ref-and-path-refusals'/'manifest.json').read_bytes())
            self.assertEqual(len(clean['scenarios']), 8)
            alias_repository = Path(clean['scenarios']['alias']['fixture_root'])
            alias = alias_repository.parent/'alias'
            self.assertTrue(alias.is_symlink())
            self.assertEqual(alias.readlink().as_posix(), 'repository', 'Alias must retain its identity across host/namespace roots')
            self.assertEqual(alias.resolve(), alias_repository)
            incomplete = json.loads(Path(clean['scenarios']['unpinned-task']['authority_input']['path']).read_bytes())
            self.assertNotIn('blob', incomplete['tasks'][0]['spec'])
            self.assertNotIn('sha256', incomplete['tasks'][0]['spec'], 'Missing-pin fixture must not masquerade as an artifact reference')
            for row in clean['scenarios'].values():
                receipt = json.loads(Path(row['actual_command_path']['path']).read_bytes())
                self.assertEqual(receipt['exit_code'], 2)
                envelope = json.loads(Path(receipt['stdout']['path']).read_bytes())
                self.assertEqual(envelope['outcome'], 'refused')
            durable = json.loads((output/'real-state-fs-durability'/'manifest.json').read_bytes())
            self.assertEqual(len(durable['scenarios']), 8)
            self.assertTrue(durable['lock_holder_command'])

    def test_result_fsync_probe_requires_actual_effect_reconciliation(self):
        from test_contracts import module
        api = module(self, 'store')
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)/'state'
            store = api.Store(state)
            store.prepare('fixture-probe', {'schema_version': 1, 'identity': 'unresolved'}, 'result-op')
            log = Path(directory)/'fault.jsonl'
            result = subprocess.run([sys.executable, str(ROOT/'scripts/collab_live.py'), 'probe', 'result-fsync',
                '--state', str(state), '--operation-id', 'result-op', '--fault-log', str(log)],
                cwd=ROOT, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 3, result.stderr)
            events = [json.loads(line) for line in (state/'events.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1]['event'], 'result')
            self.assertFalse((state/'records'/(events[-1]['record_id']+'.json')).exists())
            recovered = subprocess.run([sys.executable, str(ROOT/'scripts/collab_live.py'), 'probe', 'reconcile',
                '--state', str(state), '--operation-id', 'recover'], cwd=ROOT, capture_output=True, timeout=5)
            self.assertEqual(recovered.returncode, 2, recovered.stderr)

    def test_offline_build_refuses_changed_packages_before_output_or_docker(self):
        support_path = ROOT/'tests/collab/live_support.py'
        spec = importlib.util.spec_from_file_location('build_test_support', support_path)
        support = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(support)
        self.assertTrue(hasattr(support, 'build_runtime'), 'Pinned offline runtime build is missing')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages = root/'packages'
            packages.mkdir()
            destination = root/'build'
            receipt = root/'materialization.json'
            receipt.write_text(json.dumps({'schema_version': 1, 'source': str(ROOT), 'candidate': 'fixture'}))
            with self.assertRaises(ValueError):
                support.build_runtime(receipt, packages, destination, {'docker': {'path': '/unavailable', 'sha256': '0'*64}})
            self.assertFalse(destination.exists())

    def test_gate_refuses_wrong_candidate_before_creating_live_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'source'
            source.mkdir()
            materialization = root/'materialization.json'
            materialization.write_text(json.dumps({'schema_version': 1, 'candidate': 'a'*40, 'source': str(source)}))
            admission = root/'admission.json'
            admission.write_text(json.dumps({'schema_version': 1, 'kind': 'GateAdmission',
                'source': {'candidate': 'a'*40, 'materialization_sha256': hashlib.sha256(materialization.read_bytes()).hexdigest()}}))
            output = root/'evidence'
            result = subprocess.run([sys.executable, str(ROOT/'scripts/collab_live.py'), 'gate', '--ticket', '49',
                '--candidate', 'b'*40, '--candidate-role', 'implementation', '--materialization', str(materialization),
                '--gate-admission', str(admission), '--output', str(output)], cwd=ROOT, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertTrue(result.stdout.strip(), 'Exact-source gate rejection is not implemented')
            self.assertIn('candidate', result.stdout.decode().lower())
            self.assertFalse(output.exists())

    def test_host_fixture_refuses_unpinned_kata_before_daemon_side_effect(self):
        support_path = ROOT/'tests/collab/live_support.py'
        spec = importlib.util.spec_from_file_location('host_fixture_test_support', support_path)
        support = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(support)
        self.assertTrue(hasattr(support, 'host_fixtures49'), 'Real scoped Kata fixture helper is missing')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'host'
            with self.assertRaises(ValueError):
                support.host_fixtures49(output, {'schema_version': 1},
                    {'schema_version': 1, 'tools': {'kata': {'path': '/not-an-admitted-tool', 'sha256': '0'*64}}})
            self.assertFalse(output.exists())

    def test_host_fixture_requires_pinned_creation_scope_before_any_daemon_write(self):
        import hashlib
        import shutil
        spec = importlib.util.spec_from_file_location('host_fixture_scope_test', ROOT/'tests/collab/live_support.py')
        support = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(support)
        binary = Path(shutil.which('kata')).resolve()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'live'
            output.mkdir()
            with self.assertRaisesRegex(ValueError, 'fixture creation scope'):
                support.host_fixtures49(output, {'schema_version': 1}, {'schema_version': 1,
                    'tools': {'kata': {'path': str(binary), 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}}})
            self.assertFalse((output/'host-kata-fixture').exists())

    def test_selected_live_snapshot_preserves_native_ids_and_excludes_foreign_payload(self):
        import sqlite3
        from kata_fixture import KataFixture
        from test_contracts import module
        support_path = ROOT/'tests/collab/live_support.py'
        spec = importlib.util.spec_from_file_location('snapshot_test_support', support_path)
        support = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(support)
        self.assertTrue(hasattr(support, 'selected_project_snapshot'), 'Scoped live snapshot helper is missing')
        with KataFixture() as fixture:
            client = module(self, 'kata').Kata(fixture.project)
            uid = client.import_tasks([fixture.definition('49')]).evidence['tasks']['49']['issue_uid']
            fixture.call('--project', 'foreign-test49', 'create', 'Private unrelated payload')
            result = support.selected_project_snapshot(fixture.home/'kata.db', fixture.project.kata['project_uid'],
                                                      fixture.baseline, fixture.root/'selected.db')
            with sqlite3.connect(Path(result['path']).as_uri()+'?mode=ro&immutable=1', uri=True) as database:
                rows = database.execute('select id,uid from projects where uid=?', (fixture.project.kata['project_uid'],)).fetchall()
                self.assertEqual(rows, [(fixture.project.kata['project_id'], fixture.project.kata['project_uid'])])
                self.assertEqual(database.execute('select uid,project_id from issues').fetchall(), [(uid, fixture.project.kata['project_id'])])
                self.assertEqual(database.execute('select count(*) from api_tokens').fetchone()[0], 0)
                self.assertEqual(database.execute('select count(*) from projects').fetchone()[0], 2)

    def test_snapshot_reopens_exact_file_union_on_real_state_filesystem(self):
        support_path = ROOT/'tests/collab/live_support.py'
        self.assertTrue(support_path.is_file(), 'Raw live snapshot helper is missing')
        spec = importlib.util.spec_from_file_location('live_test_support', support_path)
        support = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(support)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root/'state'
            state.mkdir()
            (state/'actual').write_bytes(b'actual bytes')
            ref = support.snapshot(state, root/'snapshot', root/'snapshot.json')
            data = json.loads(Path(ref['path']).read_bytes())
            self.assertEqual(data['files'], {'actual': hashlib.sha256(b'actual bytes').hexdigest()})
            self.assertEqual(data['device'], state.stat().st_dev)
            self.assertEqual((Path(data['root'])/'actual').read_bytes(), b'actual bytes')


if __name__ == '__main__':
    unittest.main()
