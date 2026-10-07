import hashlib,subprocess,tempfile,unittest
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore,archive_sources,copy_source_snapshot


class ResourceSourceTests(unittest.TestCase):
    def api(self):
        try:
            from resources.sources import freeze_sources, validate_sources
        except ImportError:
            self.fail('separate resource execution source closure must exist')
        return freeze_sources, validate_sources

    def write_current(self,current):
        for name in ['sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py','stage_accounting.py','execute_worker.py','process_lifecycle.py']:
            (current/name).write_text('original '+name)

    def write_package(self,repo,evidence='admitted helper'):
        resources=repo/'autonomy/resources';resources.mkdir(parents=True)
        evidence_root=repo/'autonomy/evidence';evidence_root.mkdir(parents=True)
        self.write_current(resources)
        (evidence_root/'source_snapshot.py').write_text(evidence)
        return resources

    def query_runner(self,names):
        def run(command,**kwargs):
            self.assertIn('query',command)
            class Result:pass
            result=Result()
            result.stdout=''.join('//'+name.rsplit('/',1)[0]+':'+name.rsplit('/',1)[1]+'\n' for name in sorted(names))
            return result
        return run

    def test_target_snapshot_materializes_repo_relative_package_and_descriptor(self):
        freeze, validate = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=root/'repo';current=self.write_package(repo)
            names=['autonomy/evidence/source_snapshot.py']+[f'autonomy/resources/{name}' for name in ['sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py','stage_accounting.py','execute_worker.py','process_lifecycle.py']]
            pins=freeze(current,root/'code',store=LocalSnapshotStore(root/'store'),repo_root=repo,bazel=repo/'bazelw',runner=self.query_runner(names))
            self.assertEqual(pins['schema_version'],2)
            self.assertEqual(pins['source_snapshot_store'],{'schema_version':1,'kind':'local','root':str(root/'store')})
            self.assertIn('autonomy/evidence/source_snapshot.py',pins['source_pins'])
            self.assertIn('autonomy/resources/execute_worker.py',pins['source_pins'])
            self.assertEqual((root/'code/autonomy/evidence/source_snapshot.py').read_text(),'admitted helper')
            self.assertEqual(validate(current,pins),root/'code/autonomy')
            (current/'execute_worker.py').write_text('changed checkout copy')
            (repo/'autonomy/evidence/source_snapshot.py').write_text('changed checkout helper')
            (current/'unbound.py').write_text('unrelated helper')
            self.assertEqual(validate(current,pins),root/'code/autonomy')
            moved=self.write_package(root/'moved-checkout')
            self.assertEqual(validate(moved,pins),root/'code/autonomy')

    def test_altered_or_missing_snapshot_refused(self):
        freeze, validate = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=root/'repo';current=self.write_package(repo)
            names=['autonomy/evidence/source_snapshot.py']+[f'autonomy/resources/{name}' for name in ['sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py','stage_accounting.py','execute_worker.py','process_lifecycle.py']]
            pins=freeze(current,root/'code',store=LocalSnapshotStore(root/'store'),repo_root=repo,bazel=repo/'bazelw',runner=self.query_runner(names))
            snapshot=root/'store'/pins['source_snapshot_sha256']
            snapshot.write_bytes(b'not the admitted snapshot')
            with self.assertRaises(ValueError):validate(current,pins)
            snapshot.unlink()
            with self.assertRaises(FileNotFoundError):validate(current,pins)

    def test_changed_materialized_code_refused(self):
        freeze, validate = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=root/'repo';current=self.write_package(repo)
            names=['autonomy/evidence/source_snapshot.py']+[f'autonomy/resources/{name}' for name in ['sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py','stage_accounting.py','execute_worker.py','process_lifecycle.py']]
            pins=freeze(current,root/'code',store=LocalSnapshotStore(root/'store'),repo_root=repo,bazel=repo/'bazelw',runner=self.query_runner(names))
            worker=root/'code/autonomy/resources/execute_worker.py';worker.chmod(0o644);worker.write_text('different worker')
            with self.assertRaises(ValueError):validate(current,pins)
            worker.write_text('original execute_worker.py')
            helper=root/'code/autonomy/evidence/source_snapshot.py';helper.chmod(0o644);helper.write_text('different helper')
            with self.assertRaises(ValueError):validate(current,pins)

    def test_missing_required_helper_or_symlink_refused_before_copy(self):
        freeze, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current=root/'repo/autonomy/resources';current.mkdir(parents=True);(current/'execute_worker.py').write_text('one file')
            with self.assertRaises(ValueError):freeze(current,root/'snapshot',store=LocalSnapshotStore(root/'store'),repo_root=root/'repo',bazel=root/'repo/bazelw',runner=self.query_runner(['autonomy/resources/execute_worker.py']))
            self.assertFalse((root/'snapshot').exists())

    def test_missing_evidence_helper_refused_before_copy(self):
        freeze, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=root/'repo';current=repo/'autonomy/resources';current.mkdir(parents=True);self.write_current(current)
            names=[f'autonomy/resources/{name}' for name in ['sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py','stage_accounting.py','execute_worker.py','process_lifecycle.py']]
            with self.assertRaises(ValueError):freeze(current,root/'snapshot',store=LocalSnapshotStore(root/'store'),repo_root=repo,bazel=repo/'bazelw',runner=self.query_runner(names))
            self.assertFalse((root/'snapshot').exists())

    def test_legacy_component_relative_receipts_remain_valid(self):
        _, validate = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=root/'legacy';resources=repo/'resources';evidence=repo/'evidence'
            resources.mkdir(parents=True);evidence.mkdir()
            self.write_current(resources);(evidence/'source_snapshot.py').write_text('legacy helper')
            names=['evidence/source_snapshot.py']+[f'resources/{name}' for name in ['sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py','stage_accounting.py','execute_worker.py','process_lifecycle.py']]
            receipt=copy_source_snapshot(repo,names,root/'legacy-code',LocalSnapshotStore(root/'legacy-store'),target='legacy:resource-source-layer')
            self.assertEqual(validate(resources,receipt),root/'legacy-code')

if __name__=='__main__':unittest.main()
