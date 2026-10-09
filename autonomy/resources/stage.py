"""A successful native stage also needs a separately bound resource receipt."""
import json
import math
import os
from pathlib import Path
import subprocess
import shutil
from evidence.source_snapshot import is_regular_file
from insula.launch_plan import (
    LaunchPlan,
    legacy_receipt_command_argv,
    read_receipt_mounts,
    record_plan,
    recorded_resource_mounts_match,
    render_plan,
    rendered_command_matches_record,
)
from resources.command import wrapped_command,wrapped_rendered_plan_command,wrap_command,wrap_plan
from resources.scoped_stage import run_scoped
from resources.sources import sha,validate_sources
from resources.stage_accounting import admit_worker


def write_new(path,value):
    path=Path(path)
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
        stream.flush();os.fsync(stream.fileno())
    descriptor=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def require_separate(native_output,*resource_paths):
    """Payload retirement must never remove its resource evidence or code."""
    paths=[Path(native_output),*(Path(p) for p in resource_paths)]
    if any(not p.is_absolute() or any(q.is_symlink() for q in [p,*p.parents]) for p in paths):
        raise ValueError('absolute regular native and resource paths required')
    native,*resources=[p.resolve() for p in paths]
    if any(p==native or p.is_relative_to(native) or native.is_relative_to(p) for p in resources):
        raise ValueError('resource closure must be separate from native payload')


def validate_proof(proof,command,current_sources,source_pins,native_output,cap_bytes,timeout):
    code=validate_sources(current_sources,source_pins);native_output=Path(native_output)
    try:
        if (type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0 or
            type(cap_bytes) is not int or cap_bytes<=0 or
            type(proof['schema_version']) is not int or proof['schema_version']!=1 or
            proof['admitted'] is not True or proof['command']!=command or
            proof['source_pins']!=source_pins or proof['native_output_directory']!=str(native_output) or
            type(proof['cap_bytes']) is not int or proof['cap_bytes']!=cap_bytes or
            type(proof['timeout_seconds']) not in (int,float) or proof['timeout_seconds']!=timeout or
            set(proof['artifacts'])!={'worker_resource','execution_log'}):
            raise ValueError('complete exact resource stage identity required')
        worker_path=Path(proof['artifacts']['worker_resource']['path']);worker_output=worker_path.parent
        require_separate(native_output,worker_output.parent,code,current_sources)
        output_mount=read_receipt_mounts({'command':command},include_digests=False,require_python_worker=True).get('/outputs')
        if 'launch_plan' in proof:
            expected,worker_argv=_validate_plan_wrapped_proof(proof,code,worker_output)
            command_matches=command==expected
        else:
            expected,worker_argv=wrapped_command(proof['original_command'],code,worker_output)
            command_matches=command==expected
        if (proof['worker_argv']!=worker_argv or not command_matches or
            output_mount!={'inside_path':'/outputs','mode':'writable','kind':'bind',
                           'role':'output','host_path':str(native_output)} or
            worker_path.name!='worker-resource.json' or worker_output.name!='worker' or
            proof['artifacts']['execution_log']['native_path']!=str(native_output/'live.log') or
            proof['artifacts']['execution_log']['path']!=str(worker_output.parent/'execution.log')):
            raise ValueError('actual wrapper, original worker, native output and resource mounts required')
        for artifact in proof['artifacts'].values():
            path=Path(artifact['path'])
            if not is_regular_file(path) or sha(path)!=artifact['sha256']:
                raise ValueError('actual resource artifact changed')
        if json.loads(worker_path.read_text())!=proof['worker_measurement']:
            raise ValueError('worker measurement differs from executed output')
        native_log=native_output/'live.log'
        # Native checkpoint release is admitted by the backend/HDFS lifecycle.
        # This resource closure keeps its own bytes and remains independently
        # readable after that separately verified payload retirement.
        if native_log.exists() and (not is_regular_file(native_log) or sha(native_log)!=proof['artifacts']['execution_log']['sha256']):
            raise ValueError('native execution log differs from retained resource snapshot')
        admitted=admit_worker(proof['host_measurement'],proof['worker_measurement'],
                              command,proof['worker_argv'],cap_bytes)
        if proof['resource_admission']!=admitted:
            raise ValueError('stored resource admission differs from actual measurements')
        if (proof['host_measurement']['elapsed_seconds']>timeout or
            proof['worker_measurement']['elapsed_seconds']>timeout):
            raise ValueError('actual stage elapsed resource bound exceeded')
    except (KeyError,TypeError,IndexError,OSError,AttributeError) as error:
        raise ValueError('complete resource stage proof required') from error
    return admitted


def _validate_plan_wrapped_proof(proof,code,worker_output):
    try:
        original_argv=legacy_receipt_command_argv(proof['original_command'])
        expected,worker_argv=wrapped_rendered_plan_command(proof['original_command'],code,worker_output)
        wrapped_argv=legacy_receipt_command_argv(expected)
        if (proof['original_launch_plan']['command']!=original_argv or
            not rendered_command_matches_record(proof['original_command'],proof['original_launch_plan']) or
            proof['launch_plan']['command']!=wrapped_argv or
            not rendered_command_matches_record(expected,proof['launch_plan']) or
            not recorded_resource_mounts_match(proof['launch_plan']['mounts'])):
            raise ValueError('actual wrapper, original worker, native output and resource mounts required')
        return expected,worker_argv
    except (KeyError,TypeError,ValueError) as error:
        raise ValueError('actual wrapper, original worker, native output and resource mounts required') from error


def run_stage(command,cwd,env,stream,timeout,*,code,current_sources,source_pins,
              evidence_directory,native_output,cap_bytes):
    """Launcher hook: mutate the argv actually stored by the native backend.

    Failure evidence is durable before the exception reaches the controller.
    Existing evidence directories are refused, preserving failed attempts.
    """
    evidence=Path(evidence_directory);native_output=Path(native_output)
    require_separate(native_output,evidence,code,current_sources)
    if (not evidence.is_absolute() or any(p.is_symlink() for p in [evidence,*evidence.parents]) or
        not evidence.parent.is_dir()):
        raise ValueError('regular owned evidence parent required')
    evidence.mkdir(exist_ok=False)
    original_plan=command if isinstance(command,LaunchPlan) else None
    original_command=render_plan(command) if original_plan is not None else command.copy()
    proof={'schema_version':1,'admitted':False,'original_command':original_command.copy(),
           'command':original_command.copy(),'source_pins':source_pins,
           'native_output_directory':str(native_output),'cap_bytes':cap_bytes,
           'timeout_seconds':timeout}
    if original_plan is not None:
        proof['original_launch_plan']=record_plan(original_plan)
    try:
        if (type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0 or
            type(cap_bytes) is not int or cap_bytes<=0 or
            str(stream.name)!=str(native_output/'live.log')):
            raise ValueError('declared finite timeout, cap and exact native execution log required')
        frozen=validate_sources(current_sources,source_pins)
        if frozen!=Path(code):raise ValueError('actual resource code differs from frozen closure')
        worker_output=evidence/'worker';worker_output.mkdir()
        if original_plan is None:
            execution_command=command
            proof['worker_argv']=wrap_command(execution_command,frozen,worker_output)
        else:
            wrapped,proof['worker_argv']=wrap_plan(original_plan,frozen,worker_output)
            proof['launch_plan']=record_plan(wrapped)
            execution_command=render_plan(wrapped)
        proof['command']=execution_command.copy()
        host=run_scoped(execution_command,cwd=cwd,stream=stream,timeout=timeout,cap_bytes=cap_bytes,env=env)
        proof['host_measurement']=host
        if 'resource_admission' not in host:raise ValueError('failed or incomplete scoped stage cannot be admitted')
        worker_path=worker_output/'worker-resource.json'
        proof['worker_measurement']=json.loads(worker_path.read_text())
        native_log=native_output/'live.log';retained_log=evidence/'execution.log'
        if not is_regular_file(native_log):raise ValueError('regular native execution log required')
        shutil.copyfile(native_log,retained_log)
        proof['artifacts']={name:{'path':str(path),'sha256':sha(path)} for name,path in
                            [('worker_resource',worker_path),('execution_log',retained_log)]}
        proof['artifacts']['execution_log']['native_path']=str(native_log)
        proof['resource_admission']=admit_worker(host,proof['worker_measurement'],execution_command,proof['worker_argv'],cap_bytes)
        proof['admitted']=True
        admitted=validate_proof(proof,execution_command,current_sources,source_pins,native_output,cap_bytes,timeout)
        proof['resource_admission']=admitted
        write_new(evidence/'resource-admitted.json',proof)
    except BaseException as error:
        proof['admitted']=False;proof['error']={'type':type(error).__name__,'message':str(error)}
        native_log=native_output/'live.log';retained_log=evidence/'execution.log'
        if is_regular_file(native_log):
            if not retained_log.exists():shutil.copyfile(native_log,retained_log)
            proof['retained_failure_log']={'path':str(retained_log),'sha256':sha(retained_log),'native_path':str(native_log)}
        for field in ['timeout_seconds','cap_bytes']:
            if type(proof[field]) not in (int,float) or not math.isfinite(proof[field]):proof[field]=repr(proof[field])
        write_new(evidence/'attempt.json',proof)
        raise
    return subprocess.CompletedProcess(execution_command,0)
