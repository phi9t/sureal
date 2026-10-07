"""Separate exact-inventory admission for resource HDFS readback/recovery."""
import json,re
from pathlib import Path
from evidence.source_snapshot import safe_member_name
from resources.sources import regular,sha

LIMIT=128*1024**2
EXTRA={'manifest_readback_exact','publication_manifest_hdfs_uri','publication_manifest_sha256','independent_admission'}
ORDER=['create-live','archive-put','archive-get','manifest-put','manifest-get','verify-live','rehydrate-live']

def validate_archive_snapshot(pub,chunk,check,mode):
    """Reconcile retained worker inputs/results with its exact chunk contract."""
    from resources.command import inspect_command
    try:
        inputs=Path(check['input_directory']);job=inputs/'job.json'
        if not regular(job) or check['input_hashes']!={str(job):sha(job)}:
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
        if not regular(library) or sha(library)!=pub['archive_library']['sha256']:raise ValueError('archive library bytes changed')
        for name in ['manifest_path','readback_path']:
            path=Path(chunk[name])
            if not regular(path) or sha(path)!=chunk['manifest_sha256'] or json.loads(path.read_text())!=chunk['manifest']:
                raise ValueError('retained/downloaded manifest differs from admitted chunk')
        artifacts=check['artifacts'];names={Path(p).name:p for p in artifacts}
        if set(names)!={'check.json','live.log'} or len(artifacts)!=2:raise ValueError('exact retained live archive outputs required')
        for path,digest in artifacts.items():
            if not regular(Path(path)) or sha(path)!=digest:raise ValueError('retained archive live output changed')
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
        prefix=pub['hdfs_prefix']
        if (not prefix.startswith('hdfs://harunava/user/tiger/waystone/sureal/runs/perception-resource-closures/balanced16-') or
            pub['publication_manifest_hdfs_uri']!=prefix+'/publication-manifest.json'):
            raise ValueError('declared resource closure namespace required')
        union={};payload=0
        for chunk in pub['chunks']:
            manifest=chunk['manifest'];members=manifest['members'];size=sum(m['bytes'] for m in members);digest=manifest['archive_sha256']
            if (not members or type(size) is not int or not 0<=size<=LIMIT or size!=manifest['payload_bytes'] or
                re.fullmatch('[0-9a-f]{64}',digest) is None or
                chunk['archive_hdfs_uri']!=prefix+'/'+digest+'/archive.tar.gz' or
                chunk['manifest_hdfs_uri']!=prefix+'/'+digest+'/manifest.json'):
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
                    if (not regular(local) or
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
    archive=execution/'advanced/archive.py'
    if not regular(archive) or sha(archive)!=pub['archive_library']['sha256']:
        raise ValueError('executed archive helper differs from native pinned library')
    for name,digest in pins['source_pins'].items():
        path=execution/name
        if not regular(path) or sha(path)!=digest:raise ValueError('executed resource helper source changed')
    for chunk in pub['chunks']:
        for index,mode in [(0,'create'),(5,'verify'),(6,'rehydrate')]:
            check=chunk['checks'][index];path=Path(check['resource_proof_path'])
            if not regular(path) or sha(path)!=check['resource_proof_sha256']:raise ValueError('live archive resource proof changed')
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
