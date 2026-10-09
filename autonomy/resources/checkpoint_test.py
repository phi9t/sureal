"""The native final must have an immutable resource companion before resume."""
import copy,json,tempfile,unittest
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
        b.resource_work_root=root/'scientific';b.resource_reservations=[]
        b.resource_reserve_write=lambda path,maximum_new_bytes:b.resource_reservations.append((Path(path),maximum_new_bytes)) or {'used_bytes_before':0,'maximum_new_bytes':maximum_new_bytes}
        b.native=root/'scientific/balanced16-native-v2';native=b.native/'scene/100/producer';native.mkdir(parents=True)
        for name in ['observations.npz','targets.npz','report.json']:(native/name).write_text(name)
        physical=b.native.parent/'balanced16-physical-v2/scene/producer/100.npz';physical.parent.mkdir(parents=True);physical.write_text('physical')
        boxes=b.native.parent/'balanced16-labels-v2/scene/producer/targets.json';boxes.parent.mkdir(parents=True);boxes.write_text('full native GT fixture')
        b.manifest={'frames':[{'identity':'scene:100','relative_directory':'scene/100/producer','sha256':{name:sha(native/name) for name in ['observations.npz','targets.npz','report.json']},'physical_sha256':sha(physical),'boxes_sha256':sha(boxes)}]};(b.source/'manifest.json').write_text(json.dumps(b.manifest));b.manifest_sha=sha(b.source/'manifest.json')
        driver=root/'libcuda.fixture.so';driver.write_text('driver bytes');b.old={'driver_hashes':{str(driver):sha(driver)}}
        b.runtime_path=b.R/'runtime-lock.json';b.runtime_path.write_text('{"rootfs_sha256":"runtime fixture"}')
        from evidence.source_snapshot import LocalSnapshotStore,copy_source_snapshot,source_snapshot_receipt
        b.package=b.R/'code';b.package.mkdir();worker=b.package/'resources/sustained_scoring_budget.py';worker.parent.mkdir(parents=True);worker.write_text('def stage_timeout(metrics): return 14700 if metrics else 1800\n');b.pins={'resources/sustained_scoring_budget.py':sha(worker)}
        b.pins=source_snapshot_receipt(b.package,sorted(b.pins),LocalSnapshotStore(b.R/'source-snapshots'),target='fixture:sustained-run-package',materialized_root=b.package)
        host=root/'checkout';host.mkdir();(host/'host.py').write_text('host');b.host_pins=copy_source_snapshot(host,['host.py'],b.R/'host-source',LocalSnapshotStore(b.R/'host-source-snapshots'),target='fixture:sustained-controller-host')
        repo,runner=backend_test.ResourceBackendTests().resource_source_query()
        path,digest=prepare_identity(b,b.R/'resource-layer',source_snapshot_store=LocalSnapshotStore(b.R/'resource-source-snapshots'),repo_root=repo,bazel=repo/'bazelw',runner=runner);b.attach_resources(path,digest)
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
                self.assertIn('resource-sources/snapshot-object.tar',files);self.assertIn('resource-sources/materialized/autonomy/resources/sources.py',files)
                self.assertIn('resource-sources/materialized/autonomy/evidence/source_snapshot.py',files)
                self.assertIn('native-package/snapshot-object.tar',files);self.assertIn('native-package/materialized/resources/sustained_scoring_budget.py',files)
                self.assertIn('native-host/snapshot-object.tar',files);self.assertIn('native-host/materialized/host.py',files);self.assertNotIn('native-current/resources/sustained_scoring_budget.py',files)
                for stage in ['train','audit','literal-loss','export','proposals','score','metrics-audit']:
                    for name in ['proof.json','binding.json','worker.json','execution.log','native-receipt.json']:self.assertIn('stages/'+stage+'/'+name,files)
                for name,entry in files.items():self.assertEqual(sha(entry['path']),entry['sha256'])
                log=Path(files['stages/train/execution.log']['path']);log.write_text('changed archived evidence')
                with self.assertRaises(ValueError):inventory(b,record)

    def test_inventory_restores_source_snapshots_but_not_missing_stage_proofs(self):
        seal,_,inventory=self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                seal(b,record)
                roots=[
                    Path(b.resource_identity['source_pins']['source_snapshot_root']),
                    Path(b.pins['source_snapshot_root']),
                    Path(b.host_pins['source_snapshot_root']),
                ]
                missing_proof=b.resource_root/'stages/train-1000/resource-admitted.json'
                missing_proof.unlink()
                for root in roots:
                    import shutil
                    shutil.rmtree(root)
                with self.assertRaises(ValueError):
                    inventory(b,record)
                self.assertTrue(all(root.is_dir() for root in roots))
                self.assertFalse(missing_proof.exists())

    def test_inventory_refuses_corrupt_snapshot_archive_sidecar_without_overwrite(self):
        seal,_,inventory=self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                seal(b,record);files=inventory(b,record)
                archive=Path(files['resource-sources/snapshot-object.tar']['path'])
                archive.chmod(0o644);archive.write_text('corrupt sidecar')
                with self.assertRaises(ValueError):inventory(b,record)
                self.assertEqual(archive.read_text(),'corrupt sidecar')

    def test_snapshot_archive_staging_reserves_shared_root_and_keeps_retry_temps(self):
        seal,_,inventory=self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                seal(b,record)
                archive_cache=b.resource_work_root/'source-snapshot-archives';archive_cache.mkdir(parents=True)
                digest=b.resource_identity['source_pins']['source_snapshot_sha256']
                archive=archive_cache/('resource-sources-'+digest+'.tar')
                deterministic_tmp=archive.with_suffix(archive.suffix+'.tmp')
                deterministic_tmp.write_text('preexisting retry state')
                inventory(b,record)
                self.assertEqual(deterministic_tmp.read_text(),'preexisting retry state')
                self.assertTrue(b.resource_reservations)
                self.assertTrue(all(path==b.resource_work_root for path,_ in b.resource_reservations))

    def test_snapshot_archive_staging_does_not_follow_dangling_retry_symlink(self):
        seal,_,inventory=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);b,record=self.fixture(root)
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                seal(b,record)
                archive_cache=b.resource_work_root/'source-snapshot-archives';archive_cache.mkdir(parents=True)
                digest=b.resource_identity['source_pins']['source_snapshot_sha256']
                archive=archive_cache/('resource-sources-'+digest+'.tar')
                deterministic_tmp=archive.with_suffix(archive.suffix+'.tmp')
                escaped=root/'escaped-snapshot.tar'
                deterministic_tmp.symlink_to(escaped)
                inventory(b,record)
                self.assertTrue(deterministic_tmp.is_symlink())
                self.assertFalse(escaped.exists())

    def test_snapshot_archive_staging_requires_reservation_before_write(self):
        seal,_,inventory=self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            def refuse(path,maximum_new_bytes):
                self.assertEqual(Path(path),b.resource_work_root)
                raise ValueError('cap')
            b.resource_reserve_write=refuse
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                seal(b,record)
                digest=b.resource_identity['source_pins']['source_snapshot_sha256']
                archive=b.resource_work_root/'source-snapshot-archives'/('resource-sources-'+digest+'.tar')
                with self.assertRaisesRegex(ValueError,'cap'):
                    inventory(b,record)
                self.assertFalse(archive.exists())

    def test_snapshot_archive_staging_requires_accounting_hook(self):
        seal,_,inventory=self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp));del b.resource_reserve_write
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                seal(b,record)
                with self.assertRaisesRegex(ValueError,'resource accounting reservation required'):
                    inventory(b,record)

    def test_snapshot_archive_staging_counts_cumulative_work_root_bytes(self):
        seal,_,inventory=self.api()
        from evidence.source_snapshot import receipt_snapshot_digest,store_from_receipt
        from resources.scientific_budget import reserve_write
        from resources.scientific_payload import unique_payload_bytes
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            receipts=[b.resource_identity['source_pins'],b.pins]
            sizes=[len(store_from_receipt(receipt).fetch(receipt_snapshot_digest(receipt))) for receipt in receipts]
            self.assertNotEqual(receipts[0]['source_snapshot_sha256'],receipts[1]['source_snapshot_sha256'])
            initial=unique_payload_bytes(b.resource_work_root)
            limit=initial+max(sizes)+1
            reservations=[]
            def capped(path,maximum_new_bytes):
                self.assertEqual(Path(path),b.resource_work_root)
                reservations.append((unique_payload_bytes(path),maximum_new_bytes))
                return reserve_write(path,maximum_new_bytes,limit=limit)
            b.resource_reserve_write=capped
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                seal(b,record)
                with self.assertRaisesRegex(ValueError,'Scientific write refused before allocation'):
                    inventory(b,record)
            self.assertGreater(unique_payload_bytes(b.resource_work_root),initial)
            self.assertEqual(len(list(b.resource_work_root.rglob('*.tar'))),1)
            self.assertEqual(len(reservations),2)

    def test_existing_snapshot_archive_retry_reuses_verified_object_without_reservation(self):
        seal,_,inventory=self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,record=self.fixture(Path(temp))
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                seal(b,record);files=inventory(b,record)
                archive=Path(files['resource-sources/snapshot-object.tar']['path'])
                first_reservations=list(b.resource_reservations)
                def fail_if_called(path,maximum_new_bytes):
                    raise AssertionError('published content-addressed archive should be reused')
                b.resource_reserve_write=fail_if_called
                files=inventory(b,record)
                self.assertEqual(Path(files['resource-sources/snapshot-object.tar']['path']),archive)
                self.assertEqual(sha(archive),b.resource_identity['source_pins']['source_snapshot_sha256'])
                self.assertEqual(b.resource_reservations,first_reservations)

    def test_schema2_publication_binding_requires_canonical_host_archive_helper(self):
        from resources.checkpoint import _validate_publication_external_bindings
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'host-source';(source/'autonomy/resources').mkdir(parents=True)
            archive=source/'autonomy/resources/resource_archive.py';archive.write_text('archive helper')
            backend=type('Backend',(),{})()
            backend.resource_identity={'source_pins':{'source':'identity'}}
            backend.host_pins={'schema_version':2,'source_snapshot_root':str(source),'source_pins':{
                'autonomy/resources/command.py':'a'*64,
            }}
            pub={'resource_source_pins':backend.resource_identity['source_pins'],
                 'archive_library':{'path':str(archive),'sha256':sha(archive)}}
            with self.assertRaises(ValueError):
                _validate_publication_external_bindings(backend,pub)
            backend.host_pins['source_pins']['autonomy/resources/resource_archive.py']=sha(archive)
            _validate_publication_external_bindings(backend,pub)

    def test_legacy_publication_union_rejects_foreign_root_with_matching_blob_key_suffix(self):
        from resources.checkpoint import _validate_legacy_union
        expected={'input.json':{'sha256':'1'*64,'bytes':4}}
        archive='a'*64
        checks=[]
        for stage in ['create-live','archive-put','archive-get','manifest-put','manifest-get','verify-live','rehydrate-live']:
            validation={'archive_sha256':archive,'exact_members_and_hashes':True,'members':1,'payload_bytes':4}
            if stage=='rehydrate-live':
                validation['verified_rehydration']=True
            checks.append({'stage':stage,'exit_code':0,'validation':validation})
        prefix='hdfs://harunava/user/tiger/waystone/sureal/runs/perception-resource-closures/balanced16-test'
        pub={'schema_version':1,'manifest_readback_exact':True,'source_inventory':expected,'hdfs_prefix':prefix,
             'publication_manifest_hdfs_uri':prefix+'/publication-manifest.json',
             'chunks':[{'manifest':{'members':[{'path':'input.json','sha256':'1'*64,'bytes':4}],
                                    'payload_bytes':4,'archive_sha256':archive},
                        'archive_hdfs_uri':prefix+'/'+archive+'/archive.tar.gz',
                        'manifest_hdfs_uri':prefix+'/'+archive+'/manifest.json',
                        'checks':checks}]}
        readback={key:value for key,value in pub.items() if key not in {'manifest_readback_exact','publication_manifest_hdfs_uri','publication_manifest_sha256','independent_admission'}}
        self.assertEqual(_validate_legacy_union(pub,expected,readback)['files'],1)

        foreign='hdfs://other-cluster/x/runs/perception-resource-closures/balanced16-test'
        bad=json.loads(json.dumps(pub))
        bad['hdfs_prefix']=foreign
        bad['publication_manifest_hdfs_uri']=foreign+'/publication-manifest.json'
        bad['chunks'][0]['archive_hdfs_uri']=foreign+'/'+archive+'/archive.tar.gz'
        bad['chunks'][0]['manifest_hdfs_uri']=foreign+'/'+archive+'/manifest.json'
        foreign_readback={key:value for key,value in bad.items() if key not in {'manifest_readback_exact','publication_manifest_hdfs_uri','publication_manifest_sha256','independent_admission'}}
        with self.assertRaises(ValueError):
            _validate_legacy_union(bad,expected,foreign_readback)

    def test_legacy_publication_requires_schema_ordered_checks_and_independent_audit(self):
        from resources.checkpoint import _validate_independent_admission,_validate_legacy_union
        expected={'input.json':{'sha256':'1'*64,'bytes':4}}
        archive='a'*64
        checks=[]
        for stage in ['create-live','archive-put','archive-get','manifest-put','manifest-get','verify-live','rehydrate-live']:
            validation={'archive_sha256':archive,'exact_members_and_hashes':True,'members':1,'payload_bytes':4}
            if stage=='rehydrate-live':
                validation['verified_rehydration']=True
            checks.append({'stage':stage,'exit_code':0,'validation':validation})
        prefix='hdfs://harunava/user/tiger/waystone/sureal/runs/perception-resource-closures/balanced16-test'
        pub={'schema_version':1,'kind':'checkpoint','manifest_readback_exact':True,'source_inventory':expected,'hdfs_prefix':prefix,
             'publication_manifest_hdfs_uri':prefix+'/publication-manifest.json',
             'chunks':[{'manifest':{'members':[{'path':'input.json','sha256':'1'*64,'bytes':4}],
                                    'payload_bytes':4,'archive_sha256':archive},
                        'archive_hdfs_uri':prefix+'/'+archive+'/archive.tar.gz',
                        'manifest_hdfs_uri':prefix+'/'+archive+'/manifest.json',
                        'checks':checks}]}
        readback={key:value for key,value in pub.items() if key not in {'manifest_readback_exact','publication_manifest_hdfs_uri','publication_manifest_sha256','independent_admission'}}
        self.assertEqual(_validate_legacy_union(pub,expected,readback)['files'],1)

        for fault in ['schema','checks']:
            bad=copy.deepcopy(pub)
            if fault=='schema':
                bad.pop('schema_version')
            else:
                bad['chunks'][0].pop('checks')
            bad_readback={key:value for key,value in bad.items() if key not in {'manifest_readback_exact','publication_manifest_hdfs_uri','publication_manifest_sha256','independent_admission'}}
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                _validate_legacy_union(bad,expected,bad_readback)
        bad=copy.deepcopy(pub);bad['independent_admission']={}
        with self.assertRaises(ValueError):
            _validate_independent_admission(bad,expected,readback)

    def test_retained_legacy_resource_publication_receipt_still_validates_read_only(self):
        from resources.checkpoint import validate_publication_receipt
        path=Path('/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/resource-retention-balanced16-sustained-baseline-controller20261003a-checkpoint-a570042b0bb346998d80d8c9e64e9eab/verified-publication.json')
        if not path.exists():
            self.skipTest('retained legacy resource receipt is not present on this host')
        pub=json.loads(path.read_text())
        inventory=pub['source_inventory']
        backend=type('Backend',(),{})()
        backend.resource_identity_sha256=pub['resource_identity_sha256']
        backend.manifest_sha=pub['native_manifest_sha256']
        backend.resource_identity={'source_pins':pub['resource_source_pins']}
        record={'resource_companion_sha256':inventory['checkpoint.json']['sha256'],
                'final_sha256':inventory['native-final.json']['sha256'],
                'report_sha256':inventory['producer-report.json']['sha256']}
        receipt={'path':str(path),'sha256':sha(path),'hdfs_manifest_uri':pub['publication_manifest_hdfs_uri'],'kind':'checkpoint'}

        validated=validate_publication_receipt(backend,record,receipt)

        self.assertEqual(validated['publication_manifest_hdfs_uri'],pub['publication_manifest_hdfs_uri'])

    def test_blob_publication_shape_requires_schema_version(self):
        from resources.checkpoint import _is_blob_publication
        value={'store_descriptor':{'kind':'local','root':'/tmp/blob-store'},
               'tool_sha256':{'waystone-cli':'1'*64},
               'verified_by_readback':True,
               'blobs':{'manifest':{'key':'runs/x/y/z/manifest.json','sha256':'2'*64,'bytes':1}}}
        self.assertFalse(_is_blob_publication(value))
        value['schema_version']=1
        self.assertTrue(_is_blob_publication(value))

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
