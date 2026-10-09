import copy,json,tempfile,unittest
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore
from insula.launch_plan import BAZEL_LINUX_X86_64_SHA256, BAZEL_VERSION, build_plan, load_runtime_lock, plan_data
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import CURRENT_CPU_ROOTFS_NAME
from resources.sources import freeze_sources,sha


AUTONOMY = Path(__file__).resolve().parents[1]


def write_rootfs(root):
    root.mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/python").write_text("#!/bin/sh\n")
    (root / "bin/python").chmod(0o755)


def write_cpu_lock(lock_path, rootfs):
    lock_path.write_text(json.dumps({
        'schema_version': 1,
        'rootfs_sha256': rootfs_identity(rootfs),
        'dockerfile_sha256': sha(AUTONOMY / 'insula/Dockerfile'),
        'requirements_sha256': sha(AUTONOMY / 'requirements-tracer.lock'),
        'test_tools_requirements_sha256': sha(AUTONOMY / 'insula/cpu-test-tools-requirements.lock'),
        'bazel_version': BAZEL_VERSION,
        'bazel_linux_x86_64_sha256': BAZEL_LINUX_X86_64_SHA256,
    }, sort_keys=True) + '\n')


class ResourceStageTests(unittest.TestCase):
    def api(self):
        try:
            from resources.stage import run_stage,validate_proof
        except ImportError:
            self.fail('stage resource proofs must gate successful controller execution')
        return run_stage,validate_proof
    def query_runner(self,names):
        def run(command,**kwargs):
            self.assertIn('query',command)
            class Result:pass
            result=Result()
            result.stdout=''.join('//'+name.rsplit('/',1)[0]+':'+name.rsplit('/',1)[1]+'\n' for name in sorted(names))
            return result
        return run

    def sources(self,root):
        repo=root/'source-repo';current=repo/'autonomy/resources';current.mkdir(parents=True)
        evidence=repo/'autonomy/evidence';evidence.mkdir()
        for name in ['sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py','stage_accounting.py','execute_worker.py','process_lifecycle.py']:
            (current/name).write_text('frozen '+name)
        (evidence/'source_snapshot.py').write_text('frozen helper')
        names=['autonomy/evidence/source_snapshot.py']+[f'autonomy/resources/{name}' for name in ['sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py','stage_accounting.py','execute_worker.py','process_lifecycle.py']]
        return current,freeze_sources(current,root/'code',store=LocalSnapshotStore(root/'source-snapshots'),repo_root=repo,bazel=repo/'bazelw',runner=self.query_runner(names))

    def test_uncapped_attempt_is_durable_and_cannot_start_worker(self):
        run,_=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current,pins=self.sources(root);native=root/'native';native.mkdir();marker=native/'must-not-exist';command=['bwrap','--unshare-all','--die-with-parent','--bind',str(native),'/outputs','--','python','/experiment/worker.py'];attempt=root/'attempt'
            with (native/'live.log').open('w') as stream,self.assertRaises(ValueError):
                run(command,root,{},stream,10,code=root/'code/autonomy',current_sources=current,source_pins=pins,evidence_directory=attempt,native_output=native,cap_bytes=1024**3)
            proof=json.loads((attempt/'attempt.json').read_text());self.assertIs(proof['admitted'],False);self.assertTrue(proof['error']);self.assertFalse(marker.exists());self.assertFalse((attempt/'resource-admitted.json').exists())

    def fixture(self,root,evidence_name='attempt'):
        current,pins=self.sources(root);native=root/'native';native.mkdir();log=native/'live.log';log.write_text('literal execution log');evidence=root/evidence_name;evidence.mkdir();worker_dir=evidence/'worker';worker_dir.mkdir();worker_path=worker_dir/'worker-resource.json'
        worker={'worker_argv':['/experiment/worker.py'],'worker_pid':123,'measurement':'in-runtime getrusage SELF and waited CHILDREN KiB','self_peak_rss_kib':150,'waited_child_peak_rss_kib':100,'peak_rss_kib':150,'elapsed_seconds':.8,'exit_code':0,'child_lifecycle':{'subreaper_verified':True,'remaining_children':[]}};worker_path.write_text(json.dumps(worker));retained_log=evidence/'execution.log';retained_log.write_bytes(log.read_bytes())
        code=root/'code/autonomy'
        original=['bwrap','--unshare-all','--die-with-parent','--bind',str(native),'/outputs','--','python','/experiment/worker.py'];command=original[:original.index('--')]+['--ro-bind',str(code),'/tmp/resource-layer','--ro-bind',str(code/'resources'),'/experiment/resources','--ro-bind',str(code/'evidence'),'/experiment/evidence','--bind',str(worker_dir),'/tmp/resource-output','--','python','/tmp/resource-layer/resources/execute_worker.py','/tmp/resource-output','/experiment/worker.py']
        host={'command':command.copy(),'exit_code':0,'timed_out':False,'peak_rss_kib':100,'elapsed_seconds':1.,'measurement':'wait4.ru_maxrss_KiB_largest_waited_child','kernel_scope':{'path':'/user.slice/sureal-sustained-fixture.scope','memory_max_bytes':1024**3,'memory_swap_max_bytes':0,'oom':0,'oom_kill':0,'members_verified':True,'process_ids':[111]},'stage_lifecycle':{'caller_pid':111,'scope_members_before':[111],'scope_members_after':[111],'subreaper_verified':True,'remaining_children':[]}}
        proof={'schema_version':1,'admitted':True,'command':command,'original_command':original,'worker_argv':worker['worker_argv'],'source_pins':pins,'native_output_directory':str(native),'cap_bytes':1024**3,'timeout_seconds':10,'host_measurement':host,'worker_measurement':worker,'resource_admission':{'peak_rss_bytes':153600,'aggregate_cap_bytes':1073741824,'scope':'separate launcher and in-runtime worker/waited-child peaks under aggregate kernel cap; not summed tree RSS'},'artifacts':{'worker_resource':{'path':str(worker_path),'sha256':sha(worker_path)},'execution_log':{'path':str(retained_log),'native_path':str(log),'sha256':sha(retained_log)}}}
        return current,pins,native,proof

    def test_consistently_forged_launch_records_cannot_bypass_command_grammar(self):
        _,validate=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current,pins,native,proof=self.fixture(root)
            for fault in ['missing-namespace','foreign-executable','fake-output-mount','namespace-as-env-value']:
                bad=copy.deepcopy(proof)
                for command in [bad['original_command'],bad['command']]:
                    if fault=='missing-namespace':command.remove('--unshare-all')
                    elif fault=='foreign-executable':command[0]='bash'
                    elif fault=='fake-output-mount':command[command.index(str(native))-1]='--setenv'
                    else:
                        command.remove('--unshare-all');command[1:1]=['--setenv','FAKE','--unshare-all']
                bad['host_measurement']['command']=bad['command'].copy()
                with self.subTest(fault=fault),self.assertRaises(ValueError):
                    validate(bad,bad['command'],current,pins,native,1024**3,10)

    def test_resource_closure_cannot_be_nested_in_native_payload(self):
        _,validate=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current,pins,native,proof=self.fixture(root,'native/resources')
            with self.assertRaises(ValueError):
                validate(proof,proof['command'],current,pins,native,1024**3,10)

    def test_overlapping_resource_directory_refused_before_creation_or_launch(self):
        run,_=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current,pins=self.sources(root);native=root/'native';native.mkdir();evidence=native/'resources'
            command=['bwrap','--unshare-all','--die-with-parent','--bind',str(native),'/outputs','--','python','/experiment/worker.py'];before=command.copy()
            with (native/'live.log').open('w') as stream,self.assertRaises(ValueError):
                run(command,root,{},stream,10,code=root/'code/autonomy',current_sources=current,source_pins=pins,evidence_directory=evidence,native_output=native,cap_bytes=1024**3)
            self.assertFalse(evidence.exists());self.assertEqual(command,before)

    def test_launch_plan_stage_wraps_resource_layer_as_plan_data(self):
        run,validate=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current,pins=self.sources(root);native=root/'native';native.mkdir()
            rootfs=root/CURRENT_CPU_ROOTFS_NAME;write_rootfs(rootfs);lock=rootfs.with_name(rootfs.name+'.lock.json');write_cpu_lock(lock,rootfs)
            runtime=load_runtime_lock(rootfs,lock)
            native_code=root/'native-code';native_source=root/'native-source'
            native_code.mkdir();native_source.mkdir()
            plan=build_plan(runtime,code=native_code,source=native_source,output=native,command=['python','/experiment/worker.py'])
            evidence=root/'attempt';observed={}
            def fake_scoped(command,*,cwd,stream,timeout,cap_bytes,env=None):
                observed['command']=command.copy()
                worker_path=evidence/'worker/worker-resource.json'
                worker={'worker_argv':['/experiment/worker.py'],'worker_pid':123,
                        'measurement':'in-runtime getrusage SELF and waited CHILDREN KiB',
                        'self_peak_rss_kib':150,'waited_child_peak_rss_kib':100,
                        'peak_rss_kib':150,'elapsed_seconds':.8,'exit_code':0,
                        'child_lifecycle':{'subreaper_verified':True,'remaining_children':[]}}
                worker_path.write_text(json.dumps(worker))
                return {'command':command.copy(),'exit_code':0,'timed_out':False,
                        'peak_rss_kib':100,'elapsed_seconds':1.,
                        'measurement':'wait4.ru_maxrss_KiB_largest_waited_child',
                        'kernel_scope':{'path':'/user.slice/sureal-sustained-fixture.scope',
                                        'memory_max_bytes':1024**3,'memory_swap_max_bytes':0,
                                        'oom':0,'oom_kill':0,'members_verified':True,
                                        'process_ids':[111]},
                        'stage_lifecycle':{'caller_pid':111,'scope_members_before':[111],
                                           'scope_members_after':[111],
                                           'subreaper_verified':True,'remaining_children':[]},
                        'resource_admission':{'peak_rss_bytes':102400,
                                              'aggregate_cap_bytes':1024**3,
                                              'scope':'fixture'}}
            import resources.stage as stage_module
            original=stage_module.run_scoped;stage_module.run_scoped=fake_scoped
            try:
                with (native/'live.log').open('w') as stream:
                    run(plan,root,{},stream,10,code=root/'code/autonomy',current_sources=current,
                        source_pins=pins,evidence_directory=evidence,native_output=native,
                        cap_bytes=1024**3)
            finally:
                stage_module.run_scoped=original
            proof=json.loads((evidence/'resource-admitted.json').read_text())
            mounts={mount['role']:mount for mount in proof['launch_plan']['mounts']}
            self.assertEqual(proof['host_measurement']['command'],observed['command'])
            self.assertEqual(proof['launch_plan']['command'],['python','/tmp/resource-layer/resources/execute_worker.py','/tmp/resource-output','/experiment/worker.py'])
            self.assertEqual(mounts['resource-layer']['inside_path'],'/tmp/resource-layer')
            self.assertEqual(mounts['resource-output']['inside_path'],'/tmp/resource-output')
            self.assertEqual(plan_data(plan)['command'],['python','/experiment/worker.py'])
            bad=copy.deepcopy(proof)
            bad['launch_plan']['mounts']=[mount for mount in bad['launch_plan']['mounts'] if mount['role']!='resource-layer']
            with self.assertRaises(ValueError):
                validate(bad,bad['command'],current,pins,native,1024**3,10)
            for fault in ['extra-mount','reordered-mount','changed-mount-mode']:
                bad=copy.deepcopy(proof)
                if fault=='extra-mount':
                    separator=bad['command'].index('--')
                    bad['command'][separator:separator]=['--bind',str(root),'/host']
                elif fault=='reordered-mount':
                    resource_output=str(evidence/'worker')
                    output_index=bad['command'].index(resource_output)-1
                    output_mount=bad['command'][output_index:output_index+3]
                    del bad['command'][output_index:output_index+3]
                    layer_index=bad['command'].index('/tmp/resource-layer')-2
                    bad['command'][layer_index:layer_index]=output_mount
                else:
                    bad['command'][bad['command'].index('/tmp/resource-layer')-2]='--bind'
                bad['host_measurement']['command']=bad['command'].copy()
                with self.subTest(fault=fault),self.assertRaises(ValueError):
                    validate(bad,bad['command'],current,pins,native,1024**3,10)
            bad=copy.deepcopy(proof)
            original_insert=bad['original_command'].index('--proc')
            wrapped_insert=bad['command'].index('/tmp/resource-layer')-2
            bad['original_command'][original_insert:original_insert]=['--bind',str(root),'/host']
            bad['command'][wrapped_insert:wrapped_insert]=['--bind',str(root),'/host']
            bad['host_measurement']['command']=bad['command'].copy()
            with self.assertRaises(ValueError):
                validate(bad,bad['command'],current,pins,native,1024**3,10)

    def test_exact_command_source_output_and_measured_worker_proof_required(self):
        _,validate=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current,pins,native,proof=self.fixture(root)
            admitted=validate(proof,proof['command'],current,pins,native,1024**3,10);self.assertEqual(admitted['peak_rss_bytes'],153600)
            for fault in ['failed','command','argv','output','sources','elapsed','cap','worker-alias','changed-log','admission-alias']:
                bad=copy.deepcopy(proof)
                if fault=='failed':bad['admitted']=False
                elif fault=='command':bad['command'][-1]='/experiment/foreign.py'
                elif fault=='argv':bad['worker_argv']=['/experiment/foreign.py']
                elif fault=='output':bad['native_output_directory']=str(root/'other')
                elif fault=='sources':bad['source_pins']={}
                elif fault=='elapsed':bad['host_measurement']['elapsed_seconds']=11.
                elif fault=='cap':bad['cap_bytes']=2*1024**3
                elif fault=='worker-alias':bad['worker_measurement']['peak_rss_kib']=100
                elif fault=='changed-log':bad['artifacts']['execution_log']['sha256']='0'*64
                else:bad['resource_admission']['peak_rss_bytes']=102400
                with self.subTest(fault=fault),self.assertRaises(ValueError):validate(bad,proof['command'],current,pins,native,1024**3,10)

    def test_resource_log_snapshot_survives_native_payload_retirement(self):
        _,validate=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current,pins,native,proof=self.fixture(root);copy_path=root/'attempt/execution.log';copy_path.write_bytes((native/'live.log').read_bytes())
            proof['artifacts']['execution_log']={'path':str(copy_path),'native_path':str(native/'live.log'),'sha256':sha(copy_path)}
            (native/'live.log').unlink()
            try:admitted=validate(proof,proof['command'],current,pins,native,1024**3,10)
            except ValueError:self.fail('resource closure must retain its own exact execution log when native payload is retired separately')
            self.assertEqual(admitted['peak_rss_bytes'],153600)
            copy_path.write_text('changed log snapshot')
            with self.assertRaises(ValueError):validate(proof,proof['command'],current,pins,native,1024**3,10)

if __name__=='__main__':unittest.main()
