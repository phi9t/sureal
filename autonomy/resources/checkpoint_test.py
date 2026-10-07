"""The native final must have an immutable resource companion before resume."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from resources.sources import sha
from resources import backend_test


class ResourceCheckpointTests(unittest.TestCase):
    def api(self):
        try:
            from resources.checkpoint import seal_checkpoint,validate_checkpoint,resource_inventory
        except ImportError:self.fail('checkpoint progression requires an immutable seven-stage resource companion')
        return seal_checkpoint,validate_checkpoint,resource_inventory

    def fixture(self,root):
        from resources.backend import ResourceBackend,prepare_identity
        class NativeBackend:
            def guard(self): pass
            def check_stage(self,*args,**kwargs): pass
            def check_record(self,*args,**kwargs): pass
            def persist(self,*args,**kwargs): return 'persisted'
            def train_and_admit(self,*args,**kwargs): raise NotImplementedError
        class BoundBackend(ResourceBackend,NativeBackend): pass
        b=BoundBackend.__new__(BoundBackend);b.R=root/'run';b.R.mkdir();b.output=root/'payload';b.output.mkdir();b.source=b.R/'input';b.source.mkdir();b.anchor_sha='b'*64;b._resource_identity=None;(b.R/'run.json').write_text('{"fixture":"native"}')
        b.native=root/'scientific/balanced16-native-v2';native=b.native/'scene/100/producer';native.mkdir(parents=True)
        for name in ['observations.npz','targets.npz','report.json']:(native/name).write_text(name)
        physical=b.native.parent/'balanced16-physical-v2/scene/producer/100.npz';physical.parent.mkdir(parents=True);physical.write_text('physical')
        boxes=b.native.parent/'balanced16-labels-v2/scene/producer/targets.json';boxes.parent.mkdir(parents=True);boxes.write_text('full native GT fixture')
        b.manifest={'frames':[{'identity':'scene:100','relative_directory':'scene/100/producer','sha256':{name:sha(native/name) for name in ['observations.npz','targets.npz','report.json']},'physical_sha256':sha(physical),'boxes_sha256':sha(boxes)}]};(b.source/'manifest.json').write_text(json.dumps(b.manifest));b.manifest_sha=sha(b.source/'manifest.json')
        driver=root/'libcuda.fixture.so';driver.write_text('driver bytes');b.old={'driver_hashes':{str(driver):sha(driver)}}
        b.runtime_path=b.R/'runtime-lock.json';b.runtime_path.write_text('{"rootfs_sha256":"runtime fixture"}')
        from evidence.source_snapshot import LocalSnapshotStore,copy_source_snapshot,source_snapshot_receipt
        b.package=b.R/'code';b.package.mkdir();worker=b.package/'sustained/sustained_scoring_budget.py';worker.parent.mkdir(parents=True);worker.write_text('def stage_timeout(metrics): return 14700 if metrics else 1800\n');b.pins={'sustained/sustained_scoring_budget.py':sha(worker)}
        b.pins=source_snapshot_receipt(b.package,sorted(b.pins),LocalSnapshotStore(b.R/'source-snapshots'),target='fixture:sustained-run-package',materialized_root=b.package)
        host=root/'checkout';host.mkdir();(host/'host.py').write_text('host');b.host_pins=copy_source_snapshot(host,['host.py'],b.R/'host-source',LocalSnapshotStore(b.R/'host-source-snapshots'),target='fixture:sustained-controller-host')
        path,digest=prepare_identity(b,b.R/'resource-layer');b.attach_resources(path,digest)
        refs={}
        for stage in ['train','audit','literal-loss','export','proposals','score','metrics-audit']:
            child=root/stage;child.mkdir();receipt,path,evidence=backend_test.ResourceBackendTests().stage_fixture(child,b,stage+'-1000')
            inputs=b.R/(stage+'-1000-input');inputs.mkdir();(inputs/'job.json').write_text(json.dumps({'stage':stage}));receipt['input_hashes']={str(inputs/'job.json'):sha(inputs/'job.json')};receipt['driver_hashes']=b.old['driver_hashes'] if stage in {'train','audit'} else {};receipt['verifier_source_pins']={}
            output=Path(receipt['output_directory']);(output/'check.json').write_text(json.dumps({'stage':stage}));receipt['artifacts'][str(output/'check.json')]=sha(output/'check.json')
            if stage=='audit':
                verifier=b.R/'verifier/audit_sustained_transition.py';verifier.parent.mkdir();verifier.write_text('verifier fixture');receipt['verifier_source_pins']={str(verifier):sha(verifier)}
            path.write_text(json.dumps(receipt))
            if stage in {'score','metrics-audit'}:
                proof_path=evidence/'resource-admitted.json';proof=json.loads(proof_path.read_text());proof['timeout_seconds']=14700;proof_path.write_text(json.dumps(proof))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):b.bind_completed_stage(path)
            refs[stage]={'path':str(path),'sha256':sha(path)}
        final=b.R/'checkpoint-1000-admitted.json';final.write_text(json.dumps({'step':1000,'manifest_sha256':b.manifest_sha,'stage_receipts':refs}))
        report=b.R/'producer-report-1000.json';report.write_text('{}')
        return b,{'step':1000,'target_step':1000,'root':str(b.output),'checkpoint_sha256':'c'*64,'final_path':str(final),'final_sha256':sha(final),'report_snapshot':str(report),'report_sha256':sha(report)}

    def test_all_seven_stages_bound_and_consistently_repinned_leaf_still_refused(self):
        seal,validate,_=self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                companion=seal(b,record);self.assertEqual(len(companion['stages']),7);validate(b,record)
                evidence=b.resource_root/'stages/literal-loss-1000';proof_path=evidence/'resource-admitted.json';proof=json.loads(proof_path.read_text());proof['host_measurement']['elapsed_seconds']+=.125;proof_path.write_text(json.dumps(proof));binding_path=evidence/'native-resource-binding.json';binding=json.loads(binding_path.read_text());binding['resource_proof_sha256']=sha(proof_path);binding_path.write_text(json.dumps(binding))
                receipt=json.loads((b.R/'literal-loss-1000-verified.json').read_text());b.check_stage(receipt)
                with self.assertRaises(ValueError):validate(b,record)

    def test_incomplete_native_parent_or_changed_companion_refused(self):
        seal,validate,_=self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                final=Path(record['final_path']);original=final.read_bytes();bad=json.loads(original);bad['stage_receipts'].pop('score');final.write_text(json.dumps(bad));record['final_sha256']=sha(final)
                with self.assertRaises(ValueError):seal(b,record)
                final.write_bytes(original);record['final_sha256']=sha(final);seal(b,record);companion=Path(record['resource_companion_path']);value=json.loads(companion.read_text());value['checkpoint_sha256']='d'*64;companion.write_text(json.dumps(value))
                with self.assertRaises(ValueError):validate(b,record)

    def test_inventory_retains_resource_sources_proofs_logs_and_native_dependencies(self):
        seal,_,inventory=self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                seal(b,record);files=inventory(b,record)
                self.assertIn('resource-sources/snapshot-object.tar',files);self.assertIn('resource-sources/materialized/resources/sources.py',files)
                self.assertIn('resource-sources/materialized/evidence/source_snapshot.py',files)
                self.assertIn('native-package/snapshot-object.tar',files);self.assertIn('native-package/materialized/sustained/sustained_scoring_budget.py',files)
                self.assertIn('native-host/snapshot-object.tar',files);self.assertIn('native-host/materialized/host.py',files);self.assertNotIn('native-current/sustained/sustained_scoring_budget.py',files)
                for stage in ['train','audit','literal-loss','export','proposals','score','metrics-audit']:
                    for name in ['proof.json','binding.json','worker.json','execution.log','native-receipt.json']:self.assertIn('stages/'+stage+'/'+name,files)
                for name,entry in files.items():self.assertEqual(sha(entry['path']),entry['sha256'])
                log=Path(files['stages/train/execution.log']['path']);log.write_text('changed archived evidence')
                with self.assertRaises(ValueError):inventory(b,record)

    def test_inventory_covers_raw_stage_inputs_nonproducer_outputs_and_verifiers(self):
        seal,_,inventory=self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                seal(b,record);files=inventory(b,record)
                for stage in ['train','audit','literal-loss','export','proposals','score','metrics-audit']:
                    self.assertIn('stages/'+stage+'/inputs/job.json',files)
                    self.assertIn('stages/'+stage+'/outputs/check.json',files)
                self.assertIn('stages/audit/verifiers/audit_sustained_transition.py',files)
                self.assertIn('producer-report.json',files);self.assertIn('native-runtime-lock.json',files)

    def shared(self,b):
        try:from resources.dependencies import shared_inventory
        except ImportError:self.fail('checkpoint recovery needs the exact shared cohort and driver dependency bundle')
        return shared_inventory(b)

    def test_shared_input_union_and_duplicate_frame_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            b,_=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'):
                files=self.shared(b);self.assertEqual(len(files),6)
                self.assertIn('native/scene/100/producer/observations.npz',files);self.assertIn('physical/scene/producer/100.npz',files);self.assertIn('boxes/scene/producer/targets.json',files);self.assertIn('drivers/libcuda.fixture.so',files)
                self.assertTrue(all(sha(entry['path'])==entry['sha256'] for entry in files.values()))
                b.manifest['frames'].append(b.manifest['frames'][0])
                with self.assertRaises(ValueError):self.shared(b)

    def test_changed_physical_dependency_refuses_before_archival(self):
        with tempfile.TemporaryDirectory() as temp:
            b,_=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'):
                self.shared(b);(b.native.parent/'balanced16-physical-v2/scene/producer/100.npz').write_text('changed measurement')
                with self.assertRaises(ValueError):self.shared(b)

    def test_backend_seals_new_checkpoint_and_checks_companion_before_persist(self):
        self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'),patch.object(native_base,'check_record'),patch.object(native_base,'persist') as persist,patch.object(native_base,'train_and_admit',return_value=record):
                with self.assertRaises(ValueError):b.persist([record])
                persist.assert_not_called();sealed=b.train_and_admit(None,1000)
                self.assertIn('resource_companion_sha256',sealed);b.check_record(sealed,None);b.persist([sealed]);persist.assert_called_once()
                Path(sealed['resource_companion_path']).write_text('{}');persist.reset_mock()
                with self.assertRaises(ValueError):b.persist([sealed])
                persist.assert_not_called()


if __name__=='__main__':unittest.main()
