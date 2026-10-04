"""Git and source admission must leave refused source and refs untouched."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_contracts import module


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout


class AdmissionTests(unittest.TestCase):
    def test_init_result_conflict_is_unknown_and_retry_reopens_exact_project(self):
        from unittest.mock import patch
        import shutil
        api, records, wire, native = (module(self, name) for name in ('admission', 'store', 'contracts', 'kata'))
        data = self.admission()
        data['authority'] = {'lead': 'sureal/init49', 'ref': data['ref']}
        binaries = {'git': 'git', 'python': 'python3', 'kata': 'kata', 'codex': 'codex',
                    'bwrap': 'bwrap', 'systemd_run': 'systemd-run'}
        data['tools'] = {}
        for name, executable in binaries.items():
            binary = Path(shutil.which(executable)).resolve()
            data['tools'][name] = {'path': str(binary), 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
        actual_record, failed = records.Store.record, []
        def record(store, effect, facts):
            if effect.kind == 'project-init' and not failed:
                failed.append(True)
                raise wire.Refusal('OWNER_CONFLICT', 'Result section temporarily occupied')
            return actual_record(store, effect, facts)
        # This local boundary control bypasses the acceptance oracle and native
        # identity probe explicitly; it cannot supply an admission receipt.
        with patch.object(api, '_audit'), patch.object(native.Kata, 'identity', return_value={}), \
                patch.object(records.Store, 'record', record):
            with self.assertRaises(wire.Refusal) as caught:
                api.admit_project(self.root, self.state, data, operation_id='init-boundary')
            self.assertEqual(caught.exception.outcome, 'unknown')
            before = (self.state/'project.json').read_bytes()
            api.admit_project(self.root, self.state, data, operation_id='init-boundary')
        self.assertEqual((self.state/'project.json').read_bytes(), before)
        self.assertEqual(api.load_project(self.state).project_id, 'fixture49')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "canonical"
        self.root.mkdir()
        git(self.root, "init", "--initial-branch=phi9t/mainline")
        git(self.root, "config", "user.name", "Fixture")
        git(self.root, "config", "user.email", "fixture@example.invalid")
        (self.root / "spec.md").write_text("#49\nGoal and acceptance.\n")
        (self.root / "plan.md").write_text("# Plan\nDependent stages.\n")
        (self.root / "docs").mkdir()
        for name in ("spec.md", "plan.md"):
            (self.root / "docs" / name).write_bytes((self.root / name).read_bytes())
        (self.root / ".gitignore").write_text("declared-cache/\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "fixture")
        self.base = git(self.root, "rev-parse", "HEAD").decode().strip()
        self.state = Path(self.tmp.name) / "state"

    def admission(self):
        return {"schema_version": 1, "kind": "ProjectAdmission", "project_id": "fixture49",
                "canonical": str(self.root), "state": str(self.state),
                "common_git_dir": str(self.root / ".git"), "ref": "refs/heads/phi9t/mainline",
                "transition_base": self.base, "capacity": 2,
                "publication": {"policy": "local-only"}, "authority": {"lead": "fixture-lead"},
                "kata": {"project_id": 2, "project_uid": "fixture-project", "name": "fixture49"},
                "tools": {}, "runtime": {"fixture_only": True}}

    def test_inspection_is_read_only_and_records_ignored_disposition(self):
        api = module(self, "git_workspace")
        index = self.root / ".git/index"
        before = index.read_bytes()
        cache = self.root / "declared-cache"
        cache.mkdir()
        (cache / "result").write_text("not a verification input")
        facts = api.GitWorkspace.inspect(self.root)
        self.assertEqual(facts["head"], self.base)
        self.assertEqual(facts["ref"], "refs/heads/phi9t/mainline")
        self.assertEqual(facts["status_z_hex"], "")
        self.assertIn(b"declared-cache", bytes.fromhex(facts["ignored_z_hex"]))
        self.assertEqual(index.read_bytes(), before)
        self.assertEqual(facts["index_sha256"], hashlib.sha256(before).hexdigest())

    def test_git_inspection_does_not_execute_repository_fsmonitor(self):
        api = module(self, "git_workspace")
        marker = Path(self.tmp.name) / "unadmitted-effect"
        monitor = self.root / ".git/monitor"
        monitor.write_text("#!/bin/sh\nprintf invoked > '" + str(marker) + "'\nprintf '\\000'\n")
        monitor.chmod(0o755)
        git(self.root, "config", "core.fsmonitor", str(monitor))
        api.GitWorkspace.inspect(self.root)
        self.assertFalse(marker.exists(), "read-only Git inspection executed repository code")

    def test_git_uses_private_empty_hooks_directory_for_each_actual_read(self):
        from unittest.mock import patch
        api = module(self, 'git_workspace')
        actual = subprocess.run
        observed = []
        def run(argv, **kwargs):
            configured = [value.split('=', 1)[1] for value in argv if value.startswith('core.hooksPath=')]
            self.assertEqual(len(configured), 1)
            hooks = Path(configured[0])
            self.assertTrue(hooks.is_dir(), 'Controller must own a private empty hooks directory')
            self.assertEqual(list(hooks.iterdir()), [])
            self.assertEqual(hooks.stat().st_mode & 0o777, 0o700)
            observed.append(hooks)
            return actual(argv, **kwargs)
        with patch.object(api.subprocess, 'run', side_effect=run):
            api.GitWorkspace.inspect(self.root)
        self.assertTrue(observed)
        self.assertTrue(all(not path.exists() for path in observed))

    def test_admission_rejects_dirty_wrong_ref_unpinned_and_alias(self):
        api = module(self, "admission")
        errors = module(self, "contracts")
        changes = ("dirty-tracked", "dirty-index", "untracked", "wrong-ref", "wrong-root", "alias", "unpinned")
        for change in changes:
            with self.subTest(change=change):
                data = self.admission()
                source = self.root
                if change == "dirty-tracked":
                    (self.root / "spec.md").write_text("unreviewed edit")
                elif change == "dirty-index":
                    (self.root / "spec.md").write_text("staged edit")
                    git(self.root, "add", "spec.md")
                elif change == "untracked":
                    (self.root / "unowned.py").write_text("unique source")
                elif change == "wrong-ref":
                    git(self.root, "switch", "-c", "wrong")
                elif change == "wrong-root":
                    source = self.root / "inner"
                    source.mkdir()
                elif change == "alias":
                    source = Path(self.tmp.name) / "alias"
                    source.symlink_to(self.root, target_is_directory=True)
                else:
                    data["transition_base"] = "0" * 40
                before_head = git(self.root, "rev-parse", "HEAD")
                before_status = git(self.root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
                with self.assertRaises(errors.Refusal):
                    api.admit_project(source, self.state, data)
                self.assertEqual(git(self.root, "rev-parse", "HEAD"), before_head)
                self.assertEqual(git(self.root, "status", "--porcelain=v1", "-z", "--untracked-files=all"), before_status)
                self.assertFalse(self.state.exists())
                if change in {"dirty-tracked", "dirty-index"}:
                    git(self.root, "restore", "--source=HEAD", "--staged", "--worktree", "spec.md")
                elif change == "untracked":
                    (self.root / "unowned.py").unlink()
                elif change == "wrong-ref":
                    git(self.root, "switch", "phi9t/mainline")
                elif change == "wrong-root":
                    source.rmdir()

    def test_task_definition_is_exact_mainline_blob_not_branch_or_working_file(self):
        api = module(self, "admission")
        errors = module(self, "contracts")
        project_type = errors.Project
        project = project_type("fixture49", self.root, self.state, self.root / ".git",
                               "refs/heads/phi9t/mainline", self.base, {}, {}, {}, {}, {}, "fixture-admission")
        definition = {"schema_version": 1, "task_id": "49", "source_commit": self.base,
                      "goal": "Admit durable execution", "dependencies": [],
                      "spec": {"path": "docs/spec.md", "blob": git(self.root, "rev-parse", "HEAD:docs/spec.md").decode().strip(),
                               "sha256": hashlib.sha256((self.root / "docs/spec.md").read_bytes()).hexdigest()},
                      "plan": {"path": "docs/plan.md", "blob": git(self.root, "rev-parse", "HEAD:docs/plan.md").decode().strip(),
                               "sha256": hashlib.sha256((self.root / "docs/plan.md").read_bytes()).hexdigest()}}
        admitted = api.read_task_definition(project, "49", self.base, definition)
        self.assertEqual(admitted.spec["sha256"], definition["spec"]["sha256"])
        # The separately landed binding/map advances B without changing the
        # reviewed definition. Its historical revision remains a legitimate pin.
        (self.root / "binding.txt").write_text("fixture metadata")
        git(self.root, "add", "binding.txt")
        git(self.root, "commit", "-m", "binding metadata")
        advanced = api.read_task_definition(project, "49", self.base, definition)
        self.assertEqual(advanced.revision, admitted.revision)
        bad = json.loads(json.dumps(definition))
        bad["spec"]["sha256"] = "0" * 64
        with self.assertRaises(errors.Refusal):
            api.read_task_definition(project, "49", self.base, bad)
        git(self.root, "switch", "-c", "branch-only")
        (self.root / "spec.md").write_text("branch-only accepted? no")
        git(self.root, "add", "spec.md")
        git(self.root, "commit", "-m", "not landed")
        branch = git(self.root, "rev-parse", "HEAD").decode().strip()
        git(self.root, "switch", "phi9t/mainline")
        bad["source_commit"] = branch
        with self.assertRaises(errors.Refusal):
            api.read_task_definition(project, "49", branch, bad)

    def test_definition_rejects_non_document_authority_path(self):
        api = module(self, 'admission')
        errors = module(self, 'contracts')
        project = errors.Project('fixture49', self.root, self.state, self.root/'.git',
                               'refs/heads/phi9t/mainline', self.base, {}, {}, {}, {}, {}, 'fixture')
        definition = {'schema_version': 1, 'task_id': '49', 'source_commit': self.base,
                      'goal': 'Admit durable execution', 'dependencies': []}
        for key, path in (('spec', 'spec.md'), ('plan', 'plan.md')):
            definition[key] = {'path': path, 'blob': git(self.root, 'rev-parse', self.base+':'+path).decode().strip(),
                              'sha256': hashlib.sha256((self.root/path).read_bytes()).hexdigest()}
        with self.assertRaises(errors.Refusal) as caught:
            api.read_task_definition(project, '49', self.base, definition)
        self.assertEqual(caught.exception.reason, 'UNADMITTED_SPEC')

    def test_wrong_ref_and_changed_mainline_have_distinct_refusals(self):
        api = module(self, 'git_workspace')
        errors = module(self, 'contracts')
        git(self.root, 'switch', '-c', 'wrong-source-ref')
        with self.assertRaises(errors.Refusal) as wrong:
            api.admitted_source(self.root, 'refs/heads/phi9t/mainline', self.base)
        self.assertEqual(wrong.exception.reason, 'UNADMITTED_SPEC')
        git(self.root, 'switch', 'phi9t/mainline')
        with self.assertRaises(errors.Refusal) as stale:
            api.admitted_source(self.root, 'refs/heads/phi9t/mainline', '0'*40)
        self.assertEqual(stale.exception.reason, 'STALE_BASE')

    def test_loaded_project_is_bound_to_its_exact_completed_init(self):
        api = module(self, "admission")
        records = module(self, "store")
        wire = module(self, "contracts")
        data = self.admission()
        store = records.Store(self.state)
        effect = store.prepare("project-init", {"schema_version": 1, "admission_digest": wire.digest(data)}, "fixture-init")
        project_file = self.state / "project.json"
        project_file.write_bytes(wire.canonical(data) + b"\n")
        store.record(effect, {"schema_version": 1, "outcome": "ok", "evidence": {
            "project_sha256": hashlib.sha256(project_file.read_bytes()).hexdigest()}})
        self.assertEqual(api.load_project(self.state).project_id, "fixture49")
        data["project_id"] = "other-project"
        project_file.write_bytes(wire.canonical(data) + b"\n")
        with self.assertRaises(wire.Refusal):
            api.load_project(self.state)

    def task_brief(self, *, foreign_map=False):
        wire = module(self, 'contracts')
        definition = {'schema_version': 1, 'task_id': '50', 'source_commit': self.base,
                      'goal': 'Safe worker handoff', 'dependencies': ['49']}
        for key, path in (('spec', 'docs/spec.md'), ('plan', 'docs/plan.md')):
            definition[key] = {'path': path, 'blob': git(self.root, 'rev-parse', self.base+':'+path).decode().strip(),
                              'sha256': hashlib.sha256((self.root/path).read_bytes()).hexdigest()}
        definition['revision'] = wire.digest(definition)
        binding = self.root/'.kata.toml'
        binding.write_text('version = 1\n[project]\nname = "fixture49"\n')
        mapping = {'schema_version': 1, 'project': {'id': 2, 'uid': 'foreign' if foreign_map else 'fixture-project',
                   'name': 'fixture49'}, 'binding': {'path': '.kata.toml', 'sha256': hashlib.sha256(binding.read_bytes()).hexdigest()},
                   'source_commit': self.base, 'tasks': {'50': {'issue_uid': 'issue50', 'definition_revision': definition['revision'],
                   'spec': definition['spec'], 'plan': definition['plan'], 'dependencies': ['49']}}}
        (self.root/'docs/research').mkdir()
        (self.root/'docs/research/kata-task-map.json').write_bytes(wire.canonical(mapping))
        git(self.root, 'add', '.kata.toml', 'docs/research/kata-task-map.json')
        git(self.root, 'commit', '-m', 'Fixture map')
        fake_closure = Path(self.tmp.name)/'not-a-closure.json'
        fake_closure.write_bytes(wire.canonical({'schema_version': 1, 'outcome': 'ok'}))
        project = wire.Project('fixture49', self.root, self.state, self.root/'.git', 'refs/heads/phi9t/mainline',
                               self.base, {}, self.admission()['kata'], {}, {}, {}, 'fixture')
        brief = {'schema_version': 1, 'base': git(self.root, 'rev-parse', 'HEAD').decode().strip(),
                 'definition': definition, 'issue_uid': 'issue50', 'allowed_writes': ['scripts/_collab'], 'exclusions': [],
                 'resources': {}, 'checks': {}, 'retention': {}, 'dependency_closures': {'49': {'path': str(fake_closure),
                 'sha256': hashlib.sha256(fake_closure.read_bytes()).hexdigest()}}}
        return project, brief

    def test_task_admission_refuses_foreign_committed_project_map(self):
        api, errors = module(self, 'admission'), module(self, 'contracts')
        project, brief = self.task_brief(foreign_map=True)
        with self.assertRaises(errors.Refusal) as caught:
            api.admit_task(project, '50', brief)
        self.assertEqual(caught.exception.reason, 'UNADMITTED_SPEC')

    def test_dependency_hash_alone_cannot_accept_a_task(self):
        api, errors = module(self, 'admission'), module(self, 'contracts')
        project, brief = self.task_brief()
        with self.assertRaises(errors.Refusal) as caught:
            api.admit_task(project, '50', brief)
        self.assertEqual(caught.exception.reason, 'DEPENDENCY_OPEN')

    def test_definition_reads_use_project_git_pin_instead_of_path_shadow(self):
        from dataclasses import replace
        import os
        import shlex
        import shutil
        from unittest.mock import patch
        api = module(self, 'admission')
        project, brief = self.task_brief()
        binary = Path(shutil.which('git')).resolve()
        project = replace(project, tools={'git': {'path': str(binary), 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}})
        folder = Path(self.tmp.name)/'shadow-bin'
        folder.mkdir()
        marker = folder/'unadmitted-execution'
        shadow = folder/'git'
        shadow.write_text('#!/bin/sh\nprintf executed > '+shlex.quote(str(marker))+'\nexec '+shlex.quote(str(binary))+' "$@"\n')
        shadow.chmod(0o700)
        with patch.dict(os.environ, {'PATH': str(folder)+os.pathsep+os.environ['PATH']}):
            actual = api.read_task_definition(project, '50', self.base, brief['definition'])
        self.assertEqual(actual.task_id, '50')
        self.assertFalse(marker.exists(), 'Pinned project used an unadmitted PATH executable')


if __name__ == "__main__":
    unittest.main()
