"""Host ownership, immutable input admission and two isolated shape consumers.

Expectations come from the caller's admitted source/job inventory. This one-source
module does not authorize scientific membership or close the full cohort.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from insula.staging_lease import staging_lease
from dataset.staged_source import staged_source


def sha(path):
    with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()


def replay_shape_source(job_path,source_receipt,*,expected_job_sha256,
        expected_source_receipt_sha256,cache,code_root,output,runtime_root,
        expected_runtime_lock,retained_bytes,limit_bytes,transfer_command=None):
    cache,code_root,output,runtime_root,job_path,source_receipt=map(Path,
        (cache,code_root,output,runtime_root,job_path,source_receipt))
    with staging_lease(cache/'scientific-processing/cohort-queue.lock'):
        if (output.exists() or output.is_symlink()
            or (cache/'scientific-processing').resolve() not in output.resolve().parents):
            raise ValueError('new accounted shape output required')
        if (job_path.is_symlink() or source_receipt.is_symlink()
            or sha(job_path)!=expected_job_sha256
            or sha(source_receipt)!=expected_source_receipt_sha256):
            raise ValueError('external job/source receipt identity differs')
        job=json.loads(job_path.read_text());source=json.loads(source_receipt.read_text())
        declared={'size_bytes':int(source['source_metadata']['size']),
                  'sha256':source['sha256'],'md5_base64':source['source_metadata']['md5_hash']}
        membership={'official_split':source['official_split'],'research_splits':source['research_splits']}
        if (source['component']!='lidar' or source['scene']!=job['scene']
            or job['membership']!=membership or job['source']!=declared
            or job['inventory']['rows']!=source['inventory']['rows']
            or job['inventory']['key_sha256']!=source['inventory']['key_sha256']):
            raise ValueError('shape job and admitted source differ')
        lock=json.loads(Path(str(runtime_root)+'.lock.json').read_text())
        if lock!=expected_runtime_lock:raise ValueError('external runtime lock differs')
        verify_rootfs(runtime_root,lock['rootfs_sha256'])
        names=['native_shape_source_replay.py','geometry/native_shape_transfer.py',
               'geometry/native_range_shape_worker.py','geometry/native_range_shape_file.py',
               'geometry/native_range_shapes.py','geometry/native_range_shape_reference.py',
               'dataset/staged_source.py','dataset/source_integrity.py','insula/staging_lease.py',
               'insula/entry.py','insula/runtime_identity.py']
        pins={n:sha(code_root/n if '/' in n else code_root/'pipeline'/n) for n in names}
        transfer_prefix=transfer_command if transfer_command is not None else [
            sys.executable,str(code_root/'geometry/native_shape_transfer.py'),'--timeout-seconds','600']
        with staged_source(source,cache,retained_bytes=retained_bytes,
                limit_bytes=limit_bytes,transfer_command=transfer_prefix) as (staged,transfer):
            output.mkdir(parents=True,exist_ok=False);inputs=output/'input';inputs.mkdir()
            (inputs/'job.json').write_bytes(job_path.read_bytes())
            (inputs/'source-receipt.json').write_bytes(source_receipt.read_bytes())
            worker=output/'worker';worker.mkdir();audit=output/'audit';audit.mkdir();checks=[]
            command=launch_plan(runtime_root,code_root,staged.parent,worker,
                ['python','-m','geometry.native_range_shape_worker','/source/source.parquet',
                 '/tmp/job/job.json','/outputs/shapes.json','--expected-job-sha256',expected_job_sha256])
            at=command.index('--');command[at:at]=['--ro-bind',str(inputs),'/tmp/job']
            result=subprocess.run(command,capture_output=True,text=True,timeout=300)
            (output/'worker.log').write_text(result.stdout+result.stderr)
            if result.returncode:raise ValueError('shape producer failed; retain worker log')
            checks.append({'command':command,'exit_code':result.returncode})
            report_sha=sha(worker/'shapes.json')
            program="""import hashlib,json,math
from pathlib import Path
from geometry.native_range_shape_reference import verify_native_range_shapes
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha('/tmp/job/job.json')==JOBPIN
j=json.loads(Path('/tmp/job/job.json').read_text());assert sha('/tmp/replayed/shapes.json')==OUTPUTPIN
r=json.loads(Path('/tmp/replayed/shapes.json').read_text())
assert r['job_sha256']==JOBPIN and r['source']==j['source'] and r['membership']==j['membership']
checked=verify_native_range_shapes('/source/source.parquet',r['shapes'],scene=j['scene'],source=j['source'],inventory=j['inventory'])
assert checked==r['independent'] and checked['records_verified']==2*j['inventory']['rows']
usage=r['worker_resources'];assert usage['rss_scope']=='worker_process_peak' and type(usage['peak_rss_kib']) is int and usage['peak_rss_kib']>0 and math.isfinite(usage['elapsed_seconds']) and usage['elapsed_seconds']>=0
Path('/outputs/check.json').write_text(json.dumps(dict(checked,worker_resources=usage),indent=2));print('PASS independently admitted native shape source',j['scene'],checked['records_verified'])
""".replace('JOBPIN',repr(expected_job_sha256)).replace('OUTPUTPIN',repr(report_sha))
            command=launch_plan(runtime_root,code_root,staged.parent,audit,['python','-c',program])
            at=command.index('--');command[at:at]=['--ro-bind',str(inputs),'/tmp/job','--ro-bind',str(worker),'/tmp/replayed']
            result=subprocess.run(command,capture_output=True,text=True,timeout=300)
            (output/'audit.log').write_text(result.stdout+result.stderr)
            if result.returncode:raise ValueError('shape independent admission failed; retain audit log')
            checks.append({'command':command,'exit_code':result.returncode})
            if (sha(job_path)!=expected_job_sha256 or sha(source_receipt)!=expected_source_receipt_sha256
                or pins!={n:sha(code_root/n if '/' in n else code_root/'pipeline'/n) for n in names}
                or sha(staged)!=source['sha256']):
                raise ValueError('source/job/code changed during shape replay')
            evidence={'checks':checks,'runtime_lock':lock,'input_identity':job,
                'job_sha256':expected_job_sha256,'source_receipt_sha256':expected_source_receipt_sha256,
                'code_sha256':pins,'transfer':transfer,'report_sha256':report_sha,
                'validation':json.loads((audit/'check.json').read_text()),
                'artifacts':{str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file()},
                'scope':'one source shape replay under shared leases; full cohort/retained receipt admission external'}
            (output/'receipt.json').write_text(json.dumps(evidence,indent=2)+'\n')
        if staged.exists():raise ValueError('shape stage was not removed')
        return evidence
