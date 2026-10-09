"""Immutable resource lineage for an already independently admitted checkpoint.

This companion never substitutes for native math, model-state or metric gates.
It preserves all seven stage proofs under one digest for progression/recovery.
"""
import hashlib,json,os,re,tempfile
from pathlib import Path,PurePosixPath
from evidence.source_snapshot import is_regular_file
from evidence.source_snapshot import safe_member_name
from evidence.source_snapshot import receipt_snapshot_digest,store_from_receipt,verify_or_materialize_receipt_sources
from blob_store.core import BlobStoreError
from retention.publication import audit as audit_publication
from resources.backend import resource_cpu_root_for
from resources.sources import sha
from resources.stage import write_new,require_separate

STAGES=('train','audit','literal-loss','export','proposals','score','metrics-audit')
LEGACY_PUBLICATION_EXTRA={'manifest_readback_exact','publication_manifest_hdfs_uri','publication_manifest_sha256','independent_admission'}
LEGACY_RESOURCE_LIMIT=128*1024**2
LEGACY_RESOURCE_CHECK_ORDER=('create-live','archive-put','archive-get','manifest-put','manifest-get','verify-live','rehydrate-live')


def reference(path):
    path=Path(path)
    if not is_regular_file(path):raise ValueError('regular immutable resource parent required')
    return {'path':str(path),'sha256':sha(path)}


def _expected(backend,record):
    backend.guard()
    try:
        step=record['step'];target=record['target_step'];path=Path(record['final_path'])
        if (type(step) is not int or type(target) is not int or not 0<=step<=target<=32000 or
            not is_regular_file(path) or sha(path)!=record['final_sha256']):
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
    return {key:value for key,value in pub.items() if key not in LEGACY_PUBLICATION_EXTRA}


def _publication_identity(path):
    path=Path(path)
    value=json.loads(path.read_text())
    receipt=value['resource_receipt']
    identity={'sidecar_path':str(path),'sidecar_sha256':sha(path),
              'receipt_path':receipt['path'],'receipt_sha256':receipt['sha256'],
              'kind':receipt['kind']}
    if 'manifest_key' in receipt:
        identity['manifest_key']=receipt['manifest_key']
    else:
        identity['hdfs_manifest_uri']=receipt['hdfs_manifest_uri']
    return identity


def _receipt_from_identity(identity):
    receipt={'path':identity['receipt_path'],'sha256':identity['receipt_sha256'],'kind':identity['kind']}
    if 'manifest_key' in identity:
        receipt['manifest_key']=identity['manifest_key']
    else:
        receipt['hdfs_manifest_uri']=identity['hdfs_manifest_uri']
    return receipt


def _without_independent(pub):
    return {key:value for key,value in pub.items() if key!='independent_admission'}


def _validate_publication_external_bindings(backend,pub):
    try:
        identity=getattr(backend,'resource_identity',{})
        if pub['resource_source_pins']!=identity['source_pins']:
            raise ValueError('resource publication source identity differs from backend')
        cpu_runtime=getattr(backend,'cpu_runtime',None)
        if cpu_runtime is not None and pub['runtime_lock']!=cpu_runtime:
            raise ValueError('resource publication runtime identity differs from backend')
        cpu_root=None
        if getattr(backend,'resource_cpu_root',None) is not None or getattr(backend,'resource_cache_root',None) is not None:
            cpu_root=resource_cpu_root_for(backend)
        if cpu_root is not None and Path(pub['rootfs_path'])!=cpu_root:
            raise ValueError('resource publication rootfs identity differs from backend')
        host=getattr(backend,'host_pins',None)
        if host is not None:
            source_pins=host.get('source_pins',{})
            if host.get('schema_version')==2:
                key='autonomy/resources/resource_archive.py'
                if key not in source_pins:
                    raise ValueError('resource publication archive helper differs from admitted host source')
            elif 'resources/resource_archive.py' in source_pins:
                key='resources/resource_archive.py'
            elif 'autonomy/resources/resource_archive.py' in source_pins:
                key='autonomy/resources/resource_archive.py'
            else:
                key=None
            if key is not None:
                archive=Path(host['source_snapshot_root'])/key
                if pub['archive_library']!={'path':str(archive),'sha256':source_pins[key]}:
                    raise ValueError('resource publication archive helper differs from admitted host source')
    except (KeyError,TypeError,AttributeError) as error:
        raise ValueError('complete backend-bound resource publication identity required') from error


def _is_blob_publication(pub):
    return isinstance(pub,dict) and {'store_descriptor','tool_sha256','verified_by_readback','blobs'}<=set(pub)


def _store_for_blob_publication(backend,pub):
    store=getattr(backend,'resource_blob_store',None)
    if store is not None:return store
    return None


def _inventory_public_facts(value):
    return {name:{'sha256':entry['sha256'],'bytes':entry['bytes']} for name,entry in sorted(value.items())}


def _audit_blob_publication(pub,store):
    try:
        result=audit_publication(pub,store=store)
    except BlobStoreError:
        raise
    except Exception as error:
        raise ValueError('complete blob publication receipt required') from error
    return {'manifest':result['manifest'],'inventory':result['inventory']}


def _validate_blob_publication_receipt(backend,record,receipt,pub,expected_inventory=None):
    if receipt['kind']!='checkpoint':raise ValueError('checkpoint resource publication required')
    result=_audit_blob_publication(pub,_store_for_blob_publication(backend,pub))
    inventory=result['inventory']
    if receipt.get('manifest_key')!=pub['blobs']['manifest']['key']:
        raise ValueError('resource publication identity differs')
    required={'identity.json':backend.resource_identity_sha256,
              'checkpoint.json':record['resource_companion_sha256'],
              'native-final.json':record['final_sha256'],
              'producer-report.json':record['report_sha256'],
              'native-manifest.json':backend.manifest_sha}
    for name,digest in required.items():
        if inventory.get(name,{}).get('sha256')!=digest:
            raise ValueError('resource publication retained wrong checkpoint identity')
    if expected_inventory is not None and inventory!=_inventory_public_facts(expected_inventory):
        raise ValueError('resource publication inventory differs from live companion closure')
    return {**pub,'source_inventory':inventory}


def _receipt_inventory_digest(pub,expected_inventory=None):
    if _is_blob_publication(pub):
        if expected_inventory is None:raise ValueError('publication expected inventory required')
        return _stable_digest(_inventory_public_facts(expected_inventory))
    return _stable_digest(expected_inventory)


def _validate_independent_admission(pub,inventory,readback):
    if not isinstance(pub.get('independent_admission'),dict):
        raise ValueError('complete independent resource admission evidence required')
    _verify_legacy_source_snapshot(pub)
    if pub.get('source_inventory')!=inventory or _publication_readback(pub)!=readback:
        raise ValueError('legacy resource publication readback evidence changed')


def _validate_legacy_union(pub,expected,readback):
    try:
        if (pub.get('manifest_readback_exact') is not True or _publication_readback(pub)!=readback or
            pub['source_inventory']!=expected or not expected):
            raise ValueError('exact external inventory and unchanged global readback required')
        prefix=pub['hdfs_prefix']
        if (not prefix.startswith('hdfs://harunava/user/tiger/waystone/sureal/runs/perception-resource-closures/balanced16-') or
            pub['publication_manifest_hdfs_uri']!=prefix+'/publication-manifest.json'):
            raise ValueError('declared resource closure namespace required')
        union={};payload=0
        for chunk in pub['chunks']:
            manifest=chunk['manifest'];members=manifest['members'];size=sum(m['bytes'] for m in members);digest=manifest['archive_sha256']
            if (not members or type(size) is not int or not 0<=size<=LEGACY_RESOURCE_LIMIT or
                size!=manifest['payload_bytes'] or re.fullmatch('[0-9a-f]{64}',digest) is None or
                chunk['archive_hdfs_uri']!=prefix+'/'+digest+'/archive.tar.gz' or
                chunk['manifest_hdfs_uri']!=prefix+'/'+digest+'/manifest.json'):
                raise ValueError('bounded exact resource archive identity required')
            checks=chunk.get('checks')
            if checks is not None:
                if ([check['stage'] for check in checks]!=list(LEGACY_RESOURCE_CHECK_ORDER) or
                    any(type(check['exit_code']) is not int or check['exit_code']!=0 for check in checks)):
                    raise ValueError('all measured live and exact transfer gates required')
                for index in (0,5,6):
                    value=checks[index]['validation']
                    if (value['exact_members_and_hashes'] is not True or value['archive_sha256']!=digest or
                        value['members']!=len(members) or value['payload_bytes']!=size or
                        index==6 and value.get('verified_rehydration') is not True):
                        raise ValueError('complete live archive recovery required')
            for member in members:
                name=safe_member_name(member['path'])
                if (name in union or name not in expected or type(member['bytes']) is not int or member['bytes']<0 or
                    member['sha256']!=expected[name]['sha256'] or member['bytes']!=expected[name]['bytes']):
                    raise ValueError('unique complete resource member bytes required')
                union[name]=member['sha256']
            payload+=size
        if union!={name:value['sha256'] for name,value in expected.items()}:
            raise ValueError('incomplete whole resource recovery union')
    except (KeyError,TypeError,OSError,AttributeError) as error:
        raise ValueError('complete independent resource recovery evidence required') from error
    return {'files':len(union),'chunks':len(pub['chunks']),'payload_bytes':payload,
            'whole_member_union_exact':True,'all_chunks_live_rehydrated':True}


def _verify_legacy_source_snapshot(pub):
    for receipt_key in ('resource_source_pins','host_source_pins'):
        receipt=pub.get(receipt_key)
        if isinstance(receipt,dict) and 'source_snapshot_sha256' in receipt:
            verify_or_materialize_receipt_sources(receipt,receipt.get('source_snapshot_root'))


def validate_publication_receipt(backend,record,receipt,expected_inventory=None):
    """Validate resource publication from retained immutable admission evidence."""
    try:
        if receipt['kind']!='checkpoint':raise ValueError('checkpoint resource publication required')
        path=Path(receipt['path'])
        if not is_regular_file(path) or sha(path)!=receipt['sha256']:raise ValueError('resource publication receipt changed')
        pub=json.loads(path.read_text())
        if _is_blob_publication(pub):
            return _validate_blob_publication_receipt(backend,record,receipt,pub,expected_inventory)
        if (pub['kind']!='checkpoint' or pub['resource_identity_sha256']!=backend.resource_identity_sha256 or
            pub['native_manifest_sha256']!=backend.manifest_sha or
            receipt['hdfs_manifest_uri']!=pub['publication_manifest_hdfs_uri']):
            raise ValueError('resource publication identity differs')
        _validate_publication_external_bindings(backend,pub)
        root=path.parent;expected_path=root/'expected.json';readback_path=root/'publication-readback.json'
        if (not is_regular_file(expected_path) or sha(expected_path)!=pub['source_inventory_sha256'] or
            json.loads(expected_path.read_text())!=pub['source_inventory'] or
            not is_regular_file(readback_path) or sha(readback_path)!=pub['publication_manifest_sha256'] or
            json.loads(readback_path.read_text())!=_publication_readback(pub)):
            raise ValueError('resource publication exact readback evidence changed')
        readback=json.loads(readback_path.read_text())
        result=_validate_legacy_union(pub,pub['source_inventory'],readback)
        admission=pub['independent_admission']
        _validate_independent_admission(pub,pub['source_inventory'],readback)
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
    receipt_value=json.loads(Path(receipt['path']).read_text())
    path=publication_record_path(backend,record)
    value={'schema_version':1,'record_final_path':record['final_path'],
           'record_final_sha256':record['final_sha256'],'target_step':record['target_step'],
           'resource_identity_sha256':backend.resource_identity_sha256,
           'resource_companion_path':record['resource_companion_path'],
           'resource_companion_sha256':record['resource_companion_sha256'],
           'source_inventory_digest':_receipt_inventory_digest(receipt_value,expected_inventory),
           'resource_receipt':receipt,
           'scope':'durable resource publication identity required before native release'}
    if path.exists():
        if not is_regular_file(path) or json.loads(path.read_text())!=value:
            raise ValueError('resource publication sidecar identity changed')
    else:
        path.parent.mkdir(exist_ok=True);write_new(path,value)
    identity=_publication_identity(path);record['resource_publication']=identity
    return identity


def recover_publication_record(backend,record,expected_inventory=None):
    path=publication_record_path(backend,record)
    if not path.exists():return None
    if not is_regular_file(path):raise ValueError('resource publication sidecar changed')
    value=json.loads(path.read_text())
    if (value.get('schema_version')!=1 or value.get('record_final_path')!=record['final_path'] or
        value.get('record_final_sha256')!=record['final_sha256'] or
        value.get('target_step')!=record['target_step'] or
        value.get('resource_identity_sha256')!=backend.resource_identity_sha256 or
        value.get('resource_companion_sha256')!=record['resource_companion_sha256']):
        raise ValueError('resource publication sidecar identity differs')
    identity=_publication_identity(path)
    pub=validate_publication_receipt(backend,record,_receipt_from_identity(identity),expected_inventory)
    if expected_inventory is not None and value.get('source_inventory_digest') not in {
        _stable_digest(expected_inventory),
        _receipt_inventory_digest(pub,expected_inventory),
    }:
        raise ValueError('resource publication sidecar inventory differs')
    record['resource_publication']=identity
    return identity


def validate_publication_record(backend,record):
    identity=record.get('resource_publication')
    if identity is None:
        identity=recover_publication_record(backend,record)
        if identity is None:raise ValueError('resource publication identity required before native release')
    path=Path(identity['sidecar_path'])
    if path!=publication_record_path(backend,record) or not is_regular_file(path) or sha(path)!=identity['sidecar_sha256']:
        raise ValueError('resource publication sidecar changed')
    value=json.loads(path.read_text())
    receipt=_receipt_from_identity(identity)
    if receipt!=value['resource_receipt']:raise ValueError('resource publication receipt identity changed')
    pub=validate_publication_receipt(backend,record,receipt)
    if _is_blob_publication(pub):
        if value['source_inventory_digest']!=_stable_digest(pub['source_inventory']):
            raise ValueError('resource publication inventory digest changed')
    elif value['source_inventory_digest']!=_stable_digest(pub['source_inventory']):
        raise ValueError('resource publication inventory digest changed')
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
        if (path!=_path(backend,record) or not is_regular_file(path) or sha(path)!=record['resource_companion_sha256'] or
            record['resource_identity_sha256']!=backend.resource_identity_sha256 or
            json.loads(path.read_text())!=_expected(backend,record)):
            raise ValueError('immutable checkpoint resource companion changed')
    except (KeyError,TypeError,OSError) as error:
        raise ValueError('checkpoint resource companion required before progression') from error
    return json.loads(path.read_text())


def resource_inventory(backend,record):
    """Exact raw closure to archive separately from the nineteen producer files."""
    for receipt in [getattr(backend,'resource_identity',{}).get('source_pins'),getattr(backend,'pins',None),getattr(backend,'host_pins',None),getattr(backend,'checkpoint_publisher_pins',None)]:
        if isinstance(receipt,dict) and receipt.get('source_snapshot_root') is not None:
            verify_or_materialize_receipt_sources(receipt,receipt['source_snapshot_root'],env_var='SUREAL_SOURCE_SNAPSHOT_STORE')
    companion=validate_checkpoint(backend,record);files={}
    reserve=getattr(backend,'resource_reserve_write',None)
    accounting_root=getattr(backend,'resource_work_root',None)
    if accounting_root is not None:
        archive_cache=Path(accounting_root)/'source-snapshot-archives'
    else:
        archive_cache=None
    def add(name,path,digest=None):
        safe_member_name(name);entry=reference(path)
        if name in files or digest is not None and entry['sha256']!=digest:
            raise ValueError('unique safe resource member and unchanged digest required')
        entry['bytes']=Path(path).stat().st_size;files[name]=entry
    def stage_archive(prefix,receipt):
        if reserve is None or accounting_root is None or archive_cache is None:raise ValueError('resource accounting reservation required')
        digest=receipt_snapshot_digest(receipt);archive=archive_cache/(prefix.replace('/','-')+'-'+digest+'.tar')
        if archive.exists() or archive.is_symlink():
            if not is_regular_file(archive) or sha(archive)!=digest:raise ValueError('source snapshot archive sidecar changed')
            add(prefix+'/snapshot-object.tar',archive,digest);return
        archive_cache.mkdir(parents=True,exist_ok=True)
        if archive_cache.is_symlink():raise ValueError('regular source snapshot archive cache required')
        data=store_from_receipt(receipt,env_var='SUREAL_SOURCE_SNAPSHOT_STORE').fetch(digest)
        if hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError('snapshot digest differs from receipt')
        reserve(Path(accounting_root),len(data))
        fd,temporary_name=tempfile.mkstemp(prefix='.'+archive.name+'.',suffix='.tmp',dir=archive_cache)
        temporary=Path(temporary_name)
        try:
            with os.fdopen(fd,'wb') as output:
                output.write(data);output.flush();os.fsync(output.fileno())
            if temporary.is_symlink():raise ValueError('regular source snapshot archive temporary required')
            temporary.chmod(0o444)
            try:os.link(temporary,archive)
            except FileExistsError:
                if not is_regular_file(archive) or sha(archive)!=digest:raise ValueError('source snapshot archive sidecar changed')
        finally:
            if temporary.exists():temporary.unlink()
        add(prefix+'/snapshot-object.tar',archive,digest)
    def add_snapshot(prefix,receipt):
        try:
            root=Path(receipt['source_snapshot_root']);pins=receipt['source_pins']
            verified=verify_or_materialize_receipt_sources(receipt,root,env_var='SUREAL_SOURCE_SNAPSHOT_STORE')
            if verified['source_pins']!=pins:
                raise ValueError('source snapshot pins differ')
            stage_archive(prefix,receipt)
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
