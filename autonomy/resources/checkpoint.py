"""Immutable resource lineage for an already independently admitted checkpoint.

This companion never substitutes for native math, model-state or metric gates.
It preserves all seven stage proofs under one digest for progression/recovery.
"""
import hashlib,json
from pathlib import Path
from evidence.source_snapshot import safe_member_name
from evidence.source_snapshot import verify_materialized_sources
from resources.sources import regular,sha
from resources.stage import write_new,require_separate
from resources.retention_audit import EXTRA as PUBLICATION_EXTRA,validate_union

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


def _stable_digest(value):
    data=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(data).hexdigest()


def publication_record_path(backend,record):
    path=backend.resource_root/'checkpoints'/f'checkpoint-{record["target_step"]:02d}-resource-publication.json'
    require_separate(Path(record['root']),path)
    return path


def _publication_readback(pub):
    return {key:value for key,value in pub.items() if key not in PUBLICATION_EXTRA}


def _publication_identity(path):
    path=Path(path)
    value=json.loads(path.read_text())
    receipt=value['resource_receipt']
    return {'sidecar_path':str(path),'sidecar_sha256':sha(path),
            'receipt_path':receipt['path'],'receipt_sha256':receipt['sha256'],
            'hdfs_manifest_uri':receipt['hdfs_manifest_uri'],'kind':receipt['kind']}


def _receipt_from_identity(identity):
    return {'path':identity['receipt_path'],'sha256':identity['receipt_sha256'],
            'hdfs_manifest_uri':identity['hdfs_manifest_uri'],'kind':identity['kind']}


def validate_publication_receipt(backend,record,receipt,expected_inventory=None):
    """Validate resource publication from retained immutable admission evidence."""
    try:
        if receipt['kind']!='checkpoint':raise ValueError('checkpoint resource publication required')
        path=Path(receipt['path'])
        if not regular(path) or sha(path)!=receipt['sha256']:raise ValueError('resource publication receipt changed')
        pub=json.loads(path.read_text())
        if (pub['kind']!='checkpoint' or pub['resource_identity_sha256']!=backend.resource_identity_sha256 or
            pub['native_manifest_sha256']!=backend.manifest_sha or
            receipt['hdfs_manifest_uri']!=pub['publication_manifest_hdfs_uri']):
            raise ValueError('resource publication identity differs')
        root=path.parent;expected_path=root/'expected.json';readback_path=root/'publication-readback.json'
        if (not regular(expected_path) or sha(expected_path)!=pub['source_inventory_sha256'] or
            json.loads(expected_path.read_text())!=pub['source_inventory'] or
            not regular(readback_path) or sha(readback_path)!=pub['publication_manifest_sha256'] or
            json.loads(readback_path.read_text())!=_publication_readback(pub)):
            raise ValueError('resource publication exact readback evidence changed')
        result=validate_union(pub,pub['source_inventory'],json.loads(readback_path.read_text()))
        admission=pub['independent_admission']
        if (admission['exit_code']!=0 or admission['validation']['whole_member_union_exact'] is not True or
            result['whole_member_union_exact'] is not True):
            raise ValueError('independent resource recovery admission required')
        inventory=pub['source_inventory']
        required={'identity.json':backend.resource_identity_sha256,
                  'checkpoint.json':record['resource_companion_sha256'],
                  'native-final.json':record['final_sha256'],
                  'producer-report.json':record['report_sha256'],
                  'native-manifest.json':backend.manifest_sha}
        for name,digest in required.items():
            if inventory.get(name,{}).get('sha256')!=digest:
                raise ValueError('resource publication retained wrong checkpoint identity')
        if expected_inventory is not None and (inventory!=expected_inventory or _stable_digest(inventory)!=_stable_digest(expected_inventory)):
            raise ValueError('resource publication inventory differs from live companion closure')
    except (KeyError,TypeError,OSError,AttributeError) as error:
        raise ValueError('complete resource publication receipt required') from error
    return pub


def write_publication_record(backend,record,receipt,expected_inventory):
    validate_publication_receipt(backend,record,receipt,expected_inventory)
    path=publication_record_path(backend,record)
    value={'schema_version':1,'record_final_path':record['final_path'],
           'record_final_sha256':record['final_sha256'],'target_step':record['target_step'],
           'resource_identity_sha256':backend.resource_identity_sha256,
           'resource_companion_path':record['resource_companion_path'],
           'resource_companion_sha256':record['resource_companion_sha256'],
           'source_inventory_digest':_stable_digest(expected_inventory),
           'resource_receipt':receipt,
           'scope':'durable resource publication identity required before native release'}
    if path.exists():
        if not regular(path) or json.loads(path.read_text())!=value:
            raise ValueError('resource publication sidecar identity changed')
    else:
        path.parent.mkdir(exist_ok=True);write_new(path,value)
    identity=_publication_identity(path);record['resource_publication']=identity
    return identity


def recover_publication_record(backend,record,expected_inventory=None):
    path=publication_record_path(backend,record)
    if not path.exists():return None
    if not regular(path):raise ValueError('resource publication sidecar changed')
    value=json.loads(path.read_text())
    if (value.get('schema_version')!=1 or value.get('record_final_path')!=record['final_path'] or
        value.get('record_final_sha256')!=record['final_sha256'] or
        value.get('target_step')!=record['target_step'] or
        value.get('resource_identity_sha256')!=backend.resource_identity_sha256 or
        value.get('resource_companion_sha256')!=record['resource_companion_sha256']):
        raise ValueError('resource publication sidecar identity differs')
    if expected_inventory is not None and value.get('source_inventory_digest')!=_stable_digest(expected_inventory):
        raise ValueError('resource publication sidecar inventory differs')
    identity=_publication_identity(path)
    validate_publication_receipt(backend,record,_receipt_from_identity(identity),expected_inventory)
    record['resource_publication']=identity
    return identity


def validate_publication_record(backend,record):
    identity=record.get('resource_publication')
    if identity is None:
        identity=recover_publication_record(backend,record)
        if identity is None:raise ValueError('resource publication identity required before native release')
    path=Path(identity['sidecar_path'])
    if path!=publication_record_path(backend,record) or not regular(path) or sha(path)!=identity['sidecar_sha256']:
        raise ValueError('resource publication sidecar changed')
    value=json.loads(path.read_text())
    if value['source_inventory_digest']!=_stable_digest(json.loads(Path(value['resource_receipt']['path']).read_text())['source_inventory']):
        raise ValueError('resource publication inventory digest changed')
    receipt=_receipt_from_identity(identity)
    if receipt!=value['resource_receipt']:raise ValueError('resource publication receipt identity changed')
    validate_publication_receipt(backend,record,receipt)
    return identity


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
        safe_member_name(name);entry=reference(path)
        if name in files or digest is not None and entry['sha256']!=digest:
            raise ValueError('unique safe resource member and unchanged digest required')
        entry['bytes']=Path(path).stat().st_size;files[name]=entry
    def add_snapshot(prefix,receipt):
        try:
            root=Path(receipt['source_snapshot_root']);pins=receipt['source_pins']
            verified=verify_materialized_sources(root,receipt)
            if verified['source_pins']!=pins:
                raise ValueError('source snapshot pins differ')
            add(prefix+'/snapshot-object.tar',Path(receipt['source_snapshot_store'])/receipt['source_snapshot_sha256'],receipt['source_snapshot_sha256'])
            for name,digest in pins.items():
                add(prefix+'/materialized/'+name,root/name,digest)
        except (KeyError,TypeError,OSError) as error:
            raise ValueError('complete source snapshot receipt required') from error
    add('identity.json',backend.resource_identity_path,backend.resource_identity_sha256)
    add('checkpoint.json',record['resource_companion_path'],record['resource_companion_sha256'])
    add('native-final.json',record['final_path'],record['final_sha256'])
    add('native-run.json',backend.R/'run.json',backend.resource_identity['native_run_sha256'])
    add('native-manifest.json',backend.source/'manifest.json',backend.manifest_sha)
    add('producer-report.json',record['report_snapshot'],record['report_sha256'])
    add('native-runtime-lock.json',backend.runtime_path)
    add_snapshot('resource-sources',backend.resource_identity['source_pins'])
    add_snapshot('native-package',backend.pins)
    add_snapshot('native-host',backend.host_pins)
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
