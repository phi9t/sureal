"""Host staging and offline recovery of one externally admitted point archive."""
import json
from pathlib import Path
import subprocess
import time
from evidence.source_snapshot import file_sha256 as sha, require_regular_file
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from insula.staging_lease import staging_lease
from segmentation.semantic_recovery_runtime import recovery_rootfs, validate_recovery_output
from segmentation.staged_derived_archive_aligned import staged_derived_archive


def artifact_hashes(root):
    root = Path(root)
    artifacts = {}
    for path in root.rglob('*'):
        if path.is_dir() and not path.is_symlink():
            continue
        file_path = require_regular_file(path)
        artifacts[str(file_path.relative_to(root))] = sha(file_path)
    return artifacts


def recover_semantic_archive(record,*,cache,code_root,output,transfer_command=None,staging_cache=None):
    cache,code_root,output=map(Path,(cache,code_root,output))
    staging_cache=Path(staging_cache) if staging_cache is not None else cache
    # Refuse the active queue before touching source metadata/output. The stage
    # later reacquires and holds exclusion through the actual offline consumer.
    # The shared cache's lock refuses a live cohort queue; the staging cache's
    # lock is the one the stage itself holds.
    with staging_lease(cache/'scientific-processing/cohort-queue.lock'),staging_lease(staging_cache/'scientific-processing/cohort-queue.lock'):pass
    validate_recovery_output(output)
    publication=Path(record['publication_manifest'])
    if sha(publication)!=record['publication_manifest_sha256']:
        raise ValueError('externally admitted publication changed')
    pub=json.loads(publication.read_text());membership=record['membership']
    if (pub['scene']!=record['scene'] or pub['role']!='scientific'
            or pub['official_split']!=membership['official_split']
            or pub['research_splits']!=membership['research_splits']
            or pub['archive']['sha256']!=record['archive_sha256']
            or pub['archive']['archive_bytes']!=record['archive_bytes']
            or pub['archive']['report_sha256']!=record['report_sha256']):
        raise ValueError('recovery publication source/membership differs')
    root=recovery_rootfs(cache);lock=json.loads(Path(str(root)+'.lock.json').read_text())
    verify_rootfs(root,lock['rootfs_sha256'])
    names=['segmentation/semantic_recovery_job_aligned.py','segmentation/semantic_archive_support.py',
           'dataset/scientific_dataset.py','dataset/scene_archive_validate.py',
           'segmentation/semantic_support.py','segmentation/staged_derived_archive_aligned.py',
           'segmentation/semantic_recovery_runtime.py',
           'insula/staging_lease.py','insula/entry.py','insula/runtime_identity.py']
    pins={n:sha(code_root/n) for n in names}
    with staged_derived_archive(record,staging_cache,working_limit_bytes=15*1024**3,
                                transfer_command=transfer_command) as (archive,transfer):
        output.mkdir(parents=True,exist_ok=False);inputs=output/'input';inputs.mkdir();worker_output=output/'output';worker_output.mkdir()
        (inputs/'publication.json').write_bytes(publication.read_bytes())
        (inputs/'trusted.json').write_text(json.dumps(record,indent=2)+'\n')
        program="""import json,resource,time,importlib.util
from pathlib import Path
from segmentation.semantic_archive_support import archive_semantic_support
assert importlib.util.find_spec('tensorflow') is None
d=json.loads(Path('/mnt/trusted.json').read_text());started=time.monotonic()
r=archive_semantic_support('/source/scene.tar','/mnt/publication.json',expected_publication_sha256=d['publication_manifest_sha256'],usage=d['membership']['research_splits'][0])
assert r['scene']==d['scene'] and r['archive_sha256']==d['archive_sha256']
assert r['independent_reference_records']==d['records']
r['membership']=d['membership'];r['source_report_sha256']=d['report_sha256']
r['worker_resources']={'elapsed_seconds':time.monotonic()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rss_scope':'worker_process_peak'}
Path('/outputs/support.json').write_text(json.dumps(r,indent=2)+'\\n')
print('PASS recovered native semantic support',d['scene'],r['eligible_point_elements'])
"""
        command=launch_plan(root,code_root,archive.parent,worker_output,['python','-c',program])
        index=command.index('--');command[index:index]=['--ro-bind',str(inputs),'/mnt']
        started=time.monotonic();result=subprocess.run(command,capture_output=True,text=True,timeout=3600)
        (output/'live.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise ValueError('offline semantic recovery failed; preserve logs')
        if sha(publication)!=record['publication_manifest_sha256'] or pins!={n:sha(code_root/n) for n in pins}:
            raise ValueError('recovery source/code changed')
        validation=json.loads((worker_output/'support.json').read_text())
        receipt={'checks':[{'command':command,'exit_code':0}],'runtime_lock':lock,
                 'elapsed_seconds':time.monotonic()-started,'candidate_hashes':pins,
                 'input_identity':record,'transfer':transfer,'validation':validation,
                 'artifacts':artifact_hashes(output),
                 'scope':'one immutable semantic archive recovered; caller independently admits receipt/full-cohort coverage'}
        (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert not archive.exists()
    return receipt
