"""Contracts at the additive resource/native controller seam."""
import copy,json,shutil,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from resources.sources import sha


class ResourceBackendTests(unittest.TestCase):
    def api(self):
        try:
            from resources.backend import ResourceBackend,prepare_identity
        except ImportError:
            self.fail('native controller needs a separately pinned resource backend')
        return ResourceBackend,prepare_identity

    def backend(self,root):
        Backend,prepare=self.api()
        class NativeBackend:
            def guard(self): pass
            def check_stage(self,*args,**kwargs): pass
            def stage(self,*args,**kwargs): raise NotImplementedError
            def publish_and_release(self,*args,**kwargs): raise NotImplementedError
            def train_and_admit(self,*args,**kwargs): raise NotImplementedError
            def check_record(self,*args,**kwargs): pass
            def persist(self,*args,**kwargs): return 'persisted'
        class BoundBackend(Backend,NativeBackend): pass
        b=BoundBackend.__new__(BoundBackend)
        b.R=root/'native-run';b.R.mkdir();(b.R/'run.json').write_text('{"fixture":"native identity"}')
        b.manifest_sha='a'*64;b.anchor_sha='b'*64;b._resource_identity=None;b.output=root/'payload';b.output.mkdir()
        path,digest=prepare(b,b.R/'resource-layer');b.attach_resources(path,digest)
        return b,path,digest

    def stage_fixture(self,root,b,name='literal-loss-1000'):
        from resources.stage_test import ResourceStageTests
        scratch=root/'fixture';scratch.mkdir();_,_,native,proof=ResourceStageTests().fixture(scratch)
        evidence=b.resource_root/'stages'/name;shutil.move(str(scratch/'attempt'),evidence)
        worker=evidence/'worker/worker-resource.json';log=evidence/'execution.log'
        code=Path(b.resource_identity['source_pins']['source_snapshot_root'])
        command=proof['original_command'][:proof['original_command'].index('--')]+['--ro-bind',str(code),'/tmp/resource-layer','--ro-bind',str(code/'resources'),'/experiment/resources','--ro-bind',str(code/'evidence'),'/experiment/evidence','--bind',str(worker.parent),'/tmp/resource-output','--','python','/tmp/resource-layer/resources/execute_worker.py','/tmp/resource-output','/experiment/worker.py']
        proof['command']=command;proof['host_measurement']['command']=command.copy();proof['source_pins']=b.resource_identity['source_pins'];proof['cap_bytes']=16*1024**3;proof['timeout_seconds']=1800
        proof['host_measurement']['kernel_scope']['memory_max_bytes']=16*1024**3;proof['resource_admission']['aggregate_cap_bytes']=16*1024**3
        proof['artifacts']['worker_resource']['path']=str(worker);proof['artifacts']['execution_log']['path']=str(log)
        (evidence/'resource-admitted.json').write_text(json.dumps(proof))
        receipt={'stage':name,'requested_stage':name,'command':command,'output_directory':str(native),'artifacts':{str(native/'live.log'):sha(native/'live.log')}}
        path=b.R/(name+'-verified.json');path.write_text(json.dumps(receipt))
        return receipt,path,evidence

    def test_identity_and_native_run_edits_cannot_be_rebaselined(self):
        self.api()
        with tempfile.TemporaryDirectory() as temp:
            b,path,digest=self.backend(Path(temp))
            b.guard();original=path.read_bytes();value=json.loads(original);value['cap_bytes']=8*1024**3;path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):b.guard()
            path.write_bytes(original);(b.R/'run.json').write_text('changed original run')
            with self.assertRaises(ValueError):b.guard()

    def test_native_stage_requires_exact_separate_proof_and_receipt_binding(self):
        self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);b,_,_=self.backend(root);receipt,path,evidence=self.stage_fixture(root,b)
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'check_stage'):
                with self.assertRaises(ValueError):b.check_stage(receipt)
                b.bind_completed_stage(path);b.check_stage(receipt)
                binding=evidence/'native-resource-binding.json';before=binding.read_bytes();bad=json.loads(before);bad['resource_proof_sha256']='0'*64;binding.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):b.check_stage(receipt)
                binding.write_bytes(before);(evidence/'execution.log').write_text('changed retained log')
                with self.assertRaises(ValueError):b.check_stage(receipt)

    def test_failed_stage_restores_original_launcher_and_release_fails_closed(self):
        self.api()
        experiment_runner=types.SimpleNamespace(
            __file__=str(Path(__file__).resolve().parents[1]/'architecture/experiment_runner.py'),
            run_stage=object(),
        )
        with tempfile.TemporaryDirectory() as temp:
            b,_,_=self.backend(Path(temp));original=experiment_runner.run_stage
            b.resource_launcher_module=experiment_runner
            b.resource_launcher_path=experiment_runner.__file__
            def fail(*args,**kwargs):
                self.assertIsNot(experiment_runner.run_stage,original)
                raise RuntimeError('controlled inherited stage failure')
            native_base=type(b).__mro__[2]
            with patch.object(native_base,'guard'),patch.object(native_base,'stage',side_effect=fail):
                with self.assertRaises(RuntimeError):b.stage('train-2000','train_sustained.py',Path(temp)/'payload',[])
            self.assertIs(experiment_runner.run_stage,original)
            with patch.object(native_base,'publish_and_release') as publisher:
                with self.assertRaises(ValueError):b.publish_and_release({'step':1000})
                publisher.assert_not_called()


if __name__=='__main__':unittest.main()
