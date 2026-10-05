"""Isolated byte-pinned native shape consumer and independent source reread."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import resource
import time
from evidence.source_snapshot import file_sha256, require_regular_file
from .native_range_shape_file import read_native_range_shapes
from .native_range_shape_reference import verify_native_range_shapes


def run_shape_worker(source_path,job_path,*,expected_job_sha256,output):
    started=time.monotonic();job_path,output=Path(job_path),Path(output)
    if output.exists() or output.is_symlink():raise ValueError('new output required')
    try:
        job_path=require_regular_file(job_path)
    except ValueError as error:
        raise ValueError('bounded regular trusted job required') from error
    if job_path.stat().st_size>2*1024**2:
        raise ValueError('bounded regular trusted job required')
    data=job_path.read_bytes()
    if file_sha256(job_path)!=expected_job_sha256:
        raise ValueError('externally pinned job identity differs')
    job=json.loads(data)
    if not isinstance(job,dict) or set(job)!={'scene','membership','source','inventory'}:
        raise ValueError('complete native source job required')
    membership=job['membership']
    if (not isinstance(membership,dict) or set(membership)!={'official_split','research_splits'}
        or membership['official_split'] not in ('training','validation')
        or not isinstance(membership['research_splits'],list) or not membership['research_splits']
        or len(set(membership['research_splits']))!=len(membership['research_splits'])
        or any(not isinstance(g,str) or not g for g in membership['research_splits'])):
        raise ValueError('explicit source membership required')
    if importlib.util.find_spec('tensorflow') is not None:
        raise ValueError('TensorFlow-free runtime required')
    result=read_native_range_shapes(source_path,scene=job['scene'],source=job['source'],inventory=job['inventory'])
    reference=verify_native_range_shapes(source_path,result['shapes'],scene=job['scene'],source=job['source'],inventory=job['inventory'])
    report=dict(result,job_sha256=expected_job_sha256,membership=membership,independent=reference,
        worker_resources={'elapsed_seconds':time.monotonic()-started,
                          'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          'rss_scope':'worker_process_peak'},
        scope='one pinned source shape replay; caller admits membership/runtime/receipt and full cohort')
    content=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()
    try:descriptor=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    except OSError as error:raise ValueError('new regular output required') from error
    with os.fdopen(descriptor,'wb') as handle:handle.write(content)
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('job');parser.add_argument('output');parser.add_argument('--expected-job-sha256',required=True);args=parser.parse_args()
    report=run_shape_worker(args.source,args.job,expected_job_sha256=args.expected_job_sha256,output=args.output)
    print('PASS native shape source',report['shapes']['scene'],report['independent']['records_verified'])
if __name__=='__main__':main()
