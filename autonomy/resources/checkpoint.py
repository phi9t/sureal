"""Immutable resource lineage for an already independently admitted checkpoint.

This companion never substitutes for native math, model-state or metric gates.
It preserves all seven stage proofs under one digest for progression/recovery.
"""
import json
from pathlib import Path
from advanced.archive import safe_name
from cohort.sustained_controller_backend import P
from resources.sources import regular,sha
from resources.stage import write_new,require_separate

STAGES=('train','audit','literal-loss','export','proposals','score','metrics-audit')


def reference(path):
    path=Path(path)
    if not regular(path):raise ValueError('regular immutable resource parent required')
    return {'path':str(path),'sha256':sha(path)}


def _expected(backend,record):
    backend.guard()
    try:
        step=record['step'];target=record['target_step'];path=Path(record['final_path'])
        if (type(step) is not int or type(target) is not int or not 0<=step<=target<=32000 or
            not regular(path) or sha(path)!=record['final_sha256']):
            raise ValueError('bounded checkpoint and exact native final required')
        final=json.loads(path.read_text());refs=final['stage_receipts']
        if final['step']!=step or final['manifest_sha256']!=backend.manifest_sha or set(refs)!=set(STAGES):
            raise ValueError('all seven unchanged native stage parents required')
        stages={};seen=set()
        for stage in STAGES:
            ref=refs[stage];native=Path(ref['path'])
            if native in seen or reference(native)['sha256']!=ref['sha256']:
                raise ValueError('unique unchanged native stage parents required')
            seen.add(native);receipt=json.loads(native.read_text())
            if receipt['stage']!=f'{stage}-{step}' or receipt['requested_stage']!=f'{stage}-{target}':
                raise ValueError('native stage actual/requested checkpoint differs')
            backend.check_stage(receipt,released_root=Path(record['root']) if record.get('released') else None)
            evidence=backend._evidence(receipt['requested_stage'])
            if native!=backend.R/(receipt['requested_stage']+'-verified.json'):
                raise ValueError('native receipt belongs to a different case')
            stages[stage]={'native_receipt':reference(native),
                           'resource_binding':reference(evidence/'native-resource-binding.json'),
                           'resource_proof':reference(evidence/'resource-admitted.json')}
        return {'schema_version':1,'step':step,'target_step':target,'manifest_sha256':backend.manifest_sha,
                'checkpoint_sha256':record['checkpoint_sha256'],'native_final':reference(path),
                'resource_identity':reference(backend.resource_identity_path),'stages':stages,
                'scope':'resource integrity for an independently admitted seven-stage native checkpoint; no scientific promotion'}
    except (KeyError,TypeError,OSError) as error:
        raise ValueError('complete checkpoint resource lineage required') from error


def _path(backend,record):
    path=backend.resource_root/'checkpoints'/f'checkpoint-{record["target_step"]:02d}.json'
    require_separate(Path(record['root']),path)
    return path


def seal_checkpoint(backend,record):
    value=_expected(backend,record);path=_path(backend,record)
    path.parent.mkdir(exist_ok=True);write_new(path,value)
    record.update({'resource_companion_path':str(path),'resource_companion_sha256':sha(path),
                   'resource_identity_sha256':backend.resource_identity_sha256})
    return value


def validate_checkpoint(backend,record):
    try:
        path=Path(record['resource_companion_path'])
        if (path!=_path(backend,record) or not regular(path) or sha(path)!=record['resource_companion_sha256'] or
            record['resource_identity_sha256']!=backend.resource_identity_sha256 or
            json.loads(path.read_text())!=_expected(backend,record)):
            raise ValueError('immutable checkpoint resource companion changed')
    except (KeyError,TypeError,OSError) as error:
        raise ValueError('checkpoint resource companion required before progression') from error
    return json.loads(path.read_text())


def resource_inventory(backend,record):
    """Exact raw closure to archive separately from the nineteen producer files."""
    companion=validate_checkpoint(backend,record);files={}
    def add(name,path,digest=None):
        safe_name(name);entry=reference(path)
        if name in files or digest is not None and entry['sha256']!=digest:
            raise ValueError('unique safe resource member and unchanged digest required')
        entry['bytes']=Path(path).stat().st_size;files[name]=entry
    add('identity.json',backend.resource_identity_path,backend.resource_identity_sha256)
    add('checkpoint.json',record['resource_companion_path'],record['resource_companion_sha256'])
    add('native-final.json',record['final_path'],record['final_sha256'])
    add('native-run.json',backend.R/'run.json',backend.resource_identity['native_run_sha256'])
    add('native-manifest.json',backend.source/'manifest.json',backend.manifest_sha)
    add('producer-report.json',record['report_snapshot'],record['report_sha256'])
    add('native-runtime-lock.json',backend.runtime_path)
    for name,pin in backend.resource_identity['source_pins'].items():
        for kind in ['original','snapshot']:add('resource-'+kind+'/'+name,pin[kind],pin['sha256'])
    for name,digest in backend.pins.items():
        add('native-package/'+name,backend.package/name,digest);add('native-current/'+name,P/name,digest)
    for name,pin in backend.host_pins.items():
        for kind in ['original','snapshot']:add('native-host-'+kind+'/'+name,pin[kind],pin['sha256'])
    for stage,refs in companion['stages'].items():
        for label,key in [('proof.json','resource_proof'),('binding.json','resource_binding'),('native-receipt.json','native_receipt')]:
            add('stages/'+stage+'/'+label,refs[key]['path'],refs[key]['sha256'])
        proof=json.loads(Path(refs['resource_proof']['path']).read_text())
        for label,key in [('worker.json','worker_resource'),('execution.log','execution_log')]:
            add('stages/'+stage+'/'+label,proof['artifacts'][key]['path'],proof['artifacts'][key]['sha256'])
        receipt=json.loads(Path(refs['native_receipt']['path']).read_text())
        inputs=backend.R/(receipt['requested_stage']+'-input')
        if not receipt['input_hashes']:raise ValueError('native stage frozen input snapshots required')
        for path,digest in receipt['input_hashes'].items():
            relative=Path(path).relative_to(inputs).as_posix()
            add('stages/'+stage+'/inputs/'+relative,path,digest)
        for path,digest in receipt['verifier_source_pins'].items():
            relative=Path(path).relative_to(backend.R/'verifier').as_posix()
            add('stages/'+stage+'/verifiers/'+relative,path,digest)
        output=Path(receipt['output_directory'])
        for path,digest in receipt['artifacts'].items():
            # The unchanged native publisher separately recovers all19 producer
            # members. Retain every other stage output needed by native resume.
            if not Path(path).is_relative_to(Path(record['root'])):
                relative=Path(path).relative_to(output).as_posix()
                add('stages/'+stage+'/outputs/'+relative,path,digest)
    return files
