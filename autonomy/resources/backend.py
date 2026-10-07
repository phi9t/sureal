"""Add resource admission without editing the source-frozen native backend."""
import json
from pathlib import Path
import re
from resources.sources import regular,sha,freeze_sources,validate_sources
from resources.stage import run_stage,validate_proof,write_new,require_separate

CAP_BYTES=16*1024**3
CURRENT=Path(__file__).resolve().parent
PACKAGE_ROOT=CURRENT.parent


def default_stage_timeout(metrics):
    if type(metrics) is not bool:raise ValueError('explicit metric stage flag required')
    return 14700 if metrics else 1800


def _stage_timeout(owner,metrics):
    timeout=getattr(owner,'resource_stage_timeout',default_stage_timeout)
    return timeout(metrics)


def _launcher(owner):
    module=getattr(owner,'resource_launcher_module',None)
    if module is None:
        raise ValueError('resource launcher module required')
    expected=getattr(owner,'resource_launcher_path',None)
    if expected is not None and Path(module.__file__).resolve()!=Path(expected):
        raise ValueError('original serialized native launcher required')
    return module


def prepare_identity(native,destination,*,source_directory=CURRENT,timeout_for_stage=default_stage_timeout,
                     source_snapshot_store=None,repo_root=None,bazel=None,runner=None):
    """Create a candidate attachment; execution needs its external digest."""
    native.guard();destination=Path(destination);source_directory=Path(source_directory)
    require_separate(native.output,destination,source_directory)
    if destination.parent!=native.R or not destination.is_absolute() or any(p.is_symlink() for p in [destination,*destination.parents]):
        raise ValueError('regular resource identity directory owned by native case required')
    destination.mkdir(exist_ok=False)
    pins=freeze_sources(source_directory,destination/'code',store=source_snapshot_store,repo_root=repo_root,bazel=bazel,runner=runner)
    (destination/'stages').mkdir()
    identity={'schema_version':1,'native_run_path':str(native.R/'run.json'),
              'native_run_sha256':sha(native.R/'run.json'),'native_case_directory':str(native.R),
              'manifest_sha256':native.manifest_sha,'anchor_templates_sha256':native.anchor_sha,
              'source_directory':str(source_directory),'source_pins':pins,'cap_bytes':CAP_BYTES,
              'timeout_seconds':{'ordinary':timeout_for_stage(False),'metrics':timeout_for_stage(True)},
              'scope':'additive source-frozen resource layer; legacy stages and HDFS closure require separate admission'}
    path=destination/'identity.json';write_new(path,identity)
    return path,sha(path)


class ResourceBackend:
    """Mixin for native study backends that need resource-bounded stages.

    Study packages provide the native superclass and may override
    ``resource_package_root`` or ``resource_stage_timeout``. This lower-layer
    module never imports study code.
    """
    resource_package_root=PACKAGE_ROOT
    resource_stage_timeout=staticmethod(default_stage_timeout)

    def __init__(self,*args,resource_identity_path,resource_identity_sha256,**kwargs):
        self._resource_identity=None
        super().__init__(*args,**kwargs)
        self.attach_resources(resource_identity_path,resource_identity_sha256)

    def attach_resources(self,path,digest):
        if self._resource_identity is not None:raise ValueError('resource identity cannot be replaced')
        self.resource_identity_path=Path(path);self.resource_identity_sha256=digest
        self.resource_root=self.resource_identity_path.parent
        self._resource_identity=json.loads(self.resource_identity_path.read_text())
        self._launching_stage=None;self.guard()

    @property
    def resource_identity(self):return self._resource_identity

    def guard(self):
        super().guard()
        if self._resource_identity is None:return
        value=self._resource_identity;path=self.resource_identity_path
        if (not regular(path) or sha(path)!=self.resource_identity_sha256 or json.loads(path.read_text())!=value or
            path.name!='identity.json' or self.resource_root.parent!=self.R or
            type(value['schema_version']) is not int or value['schema_version']!=1 or value['native_case_directory']!=str(self.R) or
            value['native_run_path']!=str(self.R/'run.json') or sha(self.R/'run.json')!=value['native_run_sha256'] or
            value['manifest_sha256']!=self.manifest_sha or value['anchor_templates_sha256']!=self.anchor_sha or
            not isinstance(value.get('source_directory'),str) or type(value['cap_bytes']) is not int or value['cap_bytes']!=CAP_BYTES or
            value['timeout_seconds']!={'ordinary':_stage_timeout(self,False),'metrics':_stage_timeout(self,True)} or
            not any(value['source_pins'].get('source_pins',{}).get(name) for name in ['resources/backend.py','autonomy/resources/backend.py'])):
            raise ValueError('complete externally pinned native/resource identity required')
        require_separate(self.output,self.resource_root,CURRENT)
        validate_sources(CURRENT,value['source_pins'])

    def _evidence(self,name):
        if not isinstance(name,str) or re.fullmatch('[a-z0-9-]{1,96}',name) is None:
            raise ValueError('declared native stage name required')
        return self.resource_root/'stages'/name

    def _resource_stage(self,receipt,*,require_binding=True):
        self.guard();evidence=self._evidence(receipt['requested_stage']);proof_path=evidence/'resource-admitted.json'
        if not regular(proof_path):raise ValueError('missing live resource stage admission; legacy revalidation required')
        proof=json.loads(proof_path.read_text());native=Path(receipt['output_directory'])
        metric=receipt['stage'].rsplit('-',1)[0] in {'score','metrics-audit'}
        if (proof['artifacts']['worker_resource']['path']!=str(evidence/'worker/worker-resource.json') or
            proof['artifacts']['execution_log']['sha256']!=receipt['artifacts'].get(str(native/'live.log'))):
            raise ValueError('resource proof is not bound to this native stage log/output')
        validate_proof(proof,receipt['command'],CURRENT,self.resource_identity['source_pins'],native,CAP_BYTES,_stage_timeout(self,metric))
        native_path=self.R/(receipt['requested_stage']+'-verified.json')
        binding={'schema_version':1,'native_receipt_path':str(native_path),'native_receipt_sha256':sha(native_path) if regular(native_path) else None,
                 'resource_identity_sha256':self.resource_identity_sha256,'resource_proof_path':str(proof_path),
                 'resource_proof_sha256':sha(proof_path),'requested_stage':receipt['requested_stage'],'stage':receipt['stage']}
        if require_binding:
            path=evidence/'native-resource-binding.json'
            if not regular(native_path) or json.loads(native_path.read_text())!=receipt or not regular(path) or json.loads(path.read_text())!=binding:
                raise ValueError('exact native/resource receipt binding required')
        return binding

    def bind_completed_stage(self,path):
        path=Path(path);receipt=json.loads(path.read_text());super().check_stage(receipt);binding=self._resource_stage(receipt,require_binding=False)
        if binding['native_receipt_path']!=str(path) or binding['native_receipt_sha256'] is None:
            raise ValueError('actual completed native receipt required')
        write_new(self._evidence(receipt['requested_stage'])/'native-resource-binding.json',binding)

    def stage(self,name,worker,directory,extra,**kwargs):
        launcher=_launcher(self)
        self.guard()
        if self._launching_stage is not None:
            raise ValueError('original serialized native launcher required')
        existed=(self.R/(name+'-verified.json')).exists();original=launcher.run_stage
        frozen=validate_sources(CURRENT,self.resource_identity['source_pins'])
        def scoped(command,cwd,env,stream,timeout):
            return run_stage(command,cwd,env,stream,timeout,code=frozen,current_sources=CURRENT,
                             source_pins=self.resource_identity['source_pins'],evidence_directory=self._evidence(name),
                             native_output=directory,cap_bytes=CAP_BYTES)
        self._launching_stage=name;launcher.run_stage=scoped
        try:path=super().stage(name,worker,directory,extra,**kwargs)
        finally:launcher.run_stage=original;self._launching_stage=None
        if not existed:self.bind_completed_stage(path)
        self.check_stage(json.loads(Path(path).read_text()))
        return path

    def check_stage(self,receipt,**kwargs):
        super().check_stage(receipt,**kwargs)
        fresh=self._launching_stage==receipt['requested_stage'] and not (self.R/(receipt['requested_stage']+'-verified.json')).exists()
        self._resource_stage(receipt,require_binding=not fresh)

    def train_and_admit(self,previous,target):
        from resources.checkpoint import seal_checkpoint
        record=super().train_and_admit(previous,target)
        seal_checkpoint(self,record)
        return record

    def check_record(self,record,previous):
        from resources.checkpoint import validate_checkpoint
        super().check_record(record,previous)
        validate_checkpoint(self,record)

    def persist(self,records,decision=None,diagnostic=None):
        previous=None
        for record in records:
            self.check_record(record,previous);previous=record
        if diagnostic is not None:self.check_record(diagnostic,previous)
        return super().persist(records,decision,diagnostic)

    def publish_and_release(self,record):
        # The native publisher preserves only its exact19 producer members.
        # Never let that release retire payloads before their separately retained
        # resource/source/log closure has an independent HDFS recovery gate.
        raise ValueError('resource HDFS closure admission required before native payload release')
