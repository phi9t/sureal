"""Compatibility checks for old resource publication receipts."""
import errno,json,os,re,shutil
from pathlib import Path
from blob_store.core import legacy_project_uri_to_key
from evidence.source_snapshot import is_regular_file,safe_member_name
from resources.sources import package_member_path,sha

LIMIT=128*1024**2
EXTRA={'manifest_readback_exact','publication_manifest_hdfs_uri','publication_manifest_sha256','independent_admission'}
ORDER=['create-live','archive-put','archive-get','manifest-put','manifest-get','verify-live','rehydrate-live']
RESOURCE_CLOSURE_BLOB_PREFIX='runs/perception-resource-closures/'


def materialize_execution_package(code,execution,library,library_sha,pins):
    """Build the retained execution tree from already admitted source bytes."""
    code=Path(code);execution=Path(execution);library=Path(library)
    try:source_pins=pins['source_pins']
    except (KeyError,TypeError) as error:
        raise ValueError('complete admitted resource source pins required') from error
    required={'resources/execute_worker.py','evidence/source_snapshot.py'}
    if not isinstance(source_pins,dict) or not required<={package_member_name(name) for name in source_pins}:
        raise ValueError('complete admitted resource source pins required')
    if execution.exists() or execution.is_symlink():
        raise ValueError('fresh execution package required')
    if not is_regular_file(library) or sha(library)!=library_sha:
        raise ValueError('pinned archive library changed')
    execution.mkdir()
    try:
        for name,digest in sorted(source_pins.items()):
            safe_member_name(name)
            source=package_member_path(code,name)
            if not is_regular_file(source) or sha(source)!=digest:
                raise ValueError('admitted resource source changed')
            target=package_member_path(execution,name);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            if sha(target)!=digest:raise ValueError('executed resource package changed')
        resources=execution/'resources';resources.mkdir(exist_ok=True);shutil.copyfile(library,resources/'resource_archive.py')
        if sha(resources/'resource_archive.py')!=library_sha:raise ValueError('executed archive helper changed')
    except BaseException:
        shutil.rmtree(execution,ignore_errors=True)
        raise
    return execution


def partition(inventory,limit=LIMIT):
    if not inventory or type(limit) is not int or not 0<limit<=LIMIT:raise ValueError('nonempty bounded resource inventory required')
    chunks=[];current=[];size=0
    for name in sorted(inventory):
        length=inventory[name]['bytes']
        if type(length) is not int or not 0<=length<=limit:raise ValueError('resource member exceeds archive limit')
        if current and size+length>limit:chunks.append(current);current=[];size=0
        current.append(name);size+=length
    if current:chunks.append(current)
    return chunks


def stage_member(entry,target,budget_root,*,reserve=None):
    """Copy only EXDEV inputs, charging new bytes to scientific staging."""
    if reserve is None:reserve=_reserve_write
    source=Path(entry['path']);target=Path(target);budget_root=Path(budget_root)
    if (not is_regular_file(source) or sha(source)!=entry['sha256'] or source.stat().st_size!=entry['bytes'] or
        type(entry['bytes']) is not int or not 0<=entry['bytes']<=LIMIT or target.exists() or
        not target.is_relative_to(budget_root) or any(p.is_symlink() for p in [target,*target.parents])):
        raise ValueError('exact bounded source and fresh scientific staging destination required')
    storage='hardlinked'
    try:os.link(source,target)
    except OSError as error:
        if error.errno!=errno.EXDEV:raise
        reserve(budget_root,entry['bytes']);shutil.copyfile(source,target);target.chmod(0o444);storage='copied'
    if target.stat().st_size!=entry['bytes'] or sha(target)!=entry['sha256']:
        raise ValueError('staged resource member differs from original input')
    return {'storage':storage,'bytes':entry['bytes'],'sha256':entry['sha256']}


def package_member_name(name):
    name=str(name)
    return name[len('autonomy/'):] if name.startswith('autonomy/') else name


def _reserve_write(root,maximum_new_bytes):
    raise ValueError('resource retention requires a study write-reservation callback')


def _legacy_resource_blob_key(value):
    try:key=legacy_project_uri_to_key(value)
    except ValueError as error:
        raise ValueError('resource publication URI required') from error
    if not key.startswith(RESOURCE_CLOSURE_BLOB_PREFIX):
        raise ValueError('declared resource closure namespace required')
    return key

def validate_archive_snapshot(pub,chunk,check,mode):
    """Reconcile retained worker inputs/results with its exact chunk contract."""
    from resources.command import inspect_command
    try:
        inputs=Path(check['input_directory']);job=inputs/'job.json'
        if not is_regular_file(job) or check['input_hashes']!={str(job):sha(job)}:
            raise ValueError('exact retained archive job required')
        required={'source_sha256':{m['path']:m['sha256'] for m in chunk['manifest']['members']},
                  'max_bytes':LIMIT,'archive_module_path':'/tmp/resource-archive.py',
                  'archive_module_sha256':pub['archive_library']['sha256']}
        if mode!='create':required['manifest_sha256']=chunk['manifest_sha256']
        if json.loads(job.read_text())!=required:raise ValueError('archive job differs from exact chunk contract')
        _,_,options=inspect_command(check['command'])
        for alias,source in [('/',pub['rootfs_path']),('/experiment',pub['execution_directory']),
                             ('/tmp/inputs',str(inputs)),('/tmp/resource-archive.py',pub['archive_library']['path'])]:
            mounts=[(option,values[0]) for option,values in options
                    if option in {'--ro-bind','--bind','--dev-bind','--proc','--dev','--tmpfs'} and values[-1]==alias]
            if mounts!=[('--ro-bind',source)]:raise ValueError('actual archive input/library/runtime/code mount differs')
        library=Path(pub['archive_library']['path'])
        if not is_regular_file(library) or sha(library)!=pub['archive_library']['sha256']:raise ValueError('archive library bytes changed')
        for name in ['manifest_path','readback_path']:
            path=Path(chunk[name])
            if not is_regular_file(path) or sha(path)!=chunk['manifest_sha256'] or json.loads(path.read_text())!=chunk['manifest']:
                raise ValueError('retained/downloaded manifest differs from admitted chunk')
        artifacts=check['artifacts'];names={Path(p).name:p for p in artifacts}
        if set(names)!={'check.json','live.log'} or len(artifacts)!=2:raise ValueError('exact retained live archive outputs required')
        for path,digest in artifacts.items():
            if not is_regular_file(Path(path)) or sha(path)!=digest:raise ValueError('retained archive live output changed')
        if json.loads(Path(names['check.json']).read_text())!=check['validation']:
            raise ValueError('declared archive result differs from actual live output')
    except (KeyError,TypeError,OSError,AttributeError) as error:
        raise ValueError('complete live archive input/output binding required') from error


def validate_union(pub,expected,readback,source=None):
    try:
        if (pub.get('manifest_readback_exact') is not True or
            {k:v for k,v in pub.items() if k not in EXTRA}!=readback or
            type(pub['schema_version']) is not int or pub['schema_version']!=1 or
            pub['kind'] not in {'shared','checkpoint'} or pub['source_inventory']!=expected or not expected):
            raise ValueError('exact external inventory and unchanged global readback required')
        prefix_key=_legacy_resource_blob_key(pub['hdfs_prefix'])
        if (not prefix_key.startswith(RESOURCE_CLOSURE_BLOB_PREFIX+'balanced16-') or
            _legacy_resource_blob_key(pub['publication_manifest_hdfs_uri'])!=prefix_key+'/publication-manifest.json'):
            raise ValueError('declared resource closure namespace required')
        union={};payload=0
        for chunk in pub['chunks']:
            manifest=chunk['manifest'];members=manifest['members'];size=sum(m['bytes'] for m in members);digest=manifest['archive_sha256']
            if (not members or type(size) is not int or not 0<=size<=LIMIT or size!=manifest['payload_bytes'] or
                re.fullmatch('[0-9a-f]{64}',digest) is None or
                _legacy_resource_blob_key(chunk['archive_hdfs_uri'])!=prefix_key+'/'+digest+'/archive.tar.gz' or
                _legacy_resource_blob_key(chunk['manifest_hdfs_uri'])!=prefix_key+'/'+digest+'/manifest.json'):
                raise ValueError('bounded exact resource archive identity required')
            checks=chunk['checks']
            if [c['stage'] for c in checks]!=ORDER or any(type(c['exit_code']) is not int or c['exit_code']!=0 for c in checks):
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
                if source is not None:
                    local=Path(source)/name
                    if (not is_regular_file(local) or
                        local.stat().st_size!=member['bytes'] or sha(local)!=member['sha256']):
                        raise ValueError('original resource source bytes differ')
                union[name]=member['sha256']
            payload+=size
        if union!={name:v['sha256'] for name,v in expected.items()}:
            raise ValueError('incomplete whole resource recovery union')
    except (KeyError,TypeError,OSError,AttributeError) as error:
        raise ValueError('complete independent resource recovery evidence required') from error
    return {'files':len(union),'chunks':len(pub['chunks']),'payload_bytes':payload,
            'whole_member_union_exact':True,'all_chunks_live_rehydrated':True}


def validate_live_references(pub):
    from resources.stage import validate_proof
    pins=pub['resource_source_pins'];current=Path(pub['resource_source_directory'])
    execution=Path(pub['execution_directory'])
    archive=execution/'resources/resource_archive.py'
    if not is_regular_file(archive) or sha(archive)!=pub['archive_library']['sha256']:
        raise ValueError('executed archive helper differs from native pinned library')
    for name,digest in pins['source_pins'].items():
        path=package_member_path(execution,name)
        if not is_regular_file(path) or sha(path)!=digest:raise ValueError('executed resource helper source changed')
    for chunk in pub['chunks']:
        for index,mode in [(0,'create'),(5,'verify'),(6,'rehydrate')]:
            check=chunk['checks'][index];path=Path(check['resource_proof_path'])
            if not is_regular_file(path) or sha(path)!=check['resource_proof_sha256']:raise ValueError('live archive resource proof changed')
            proof=json.loads(path.read_text())
            if proof['worker_argv']!=['/experiment/resources/archive_worker.py',mode]:raise ValueError('wrong live archive worker')
            validate_proof(proof,check['command'],current,pins,Path(proof['native_output_directory']),16*1024**3,300)
            validate_archive_snapshot(pub,chunk,check,mode)
        for check in chunk['checks'][1:5]:
            if sha(check['log_path'])!=check['log_sha256']:raise ValueError('HDFS transfer log changed')


if __name__=='__main__':
    import copy
    inputs=Path('/tmp/inputs');pub=json.loads((inputs/'publication.json').read_text());expected=json.loads((inputs/'expected.json').read_text());readback=json.loads((inputs/'readback.json').read_text())
    if sha(inputs/'readback.json')!=pub['publication_manifest_sha256'] or sha(inputs/'expected.json')!=pub['source_inventory_sha256']:
        raise ValueError('externally pinned inventory/global readback required')
    validate_live_references(pub);result=validate_union(pub,expected,readback,Path('/source'));refused=0
    for fault in ['missing','digest','recovery','namespace','readback']:
        bad=copy.deepcopy(pub)
        if fault=='missing':bad['chunks'].pop()
        elif fault=='digest':bad['chunks'][0]['manifest']['members'][0]['sha256']='0'*64
        elif fault=='recovery':bad['chunks'][0]['checks'].pop()
        elif fault=='namespace':bad['hdfs_prefix']='hdfs://foreign/unknown'
        else:bad['manifest_readback_exact']=False
        try:validate_union(bad,expected,readback)
        except ValueError:refused+=1
        else:raise AssertionError('corrupt resource closure admitted')
    result['corrupt_resource_copies_refused']=refused
    Path('/outputs/check.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS independent whole resource recovery',result['files'],flush=True)
