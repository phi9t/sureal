#!/usr/bin/env python3
"""Fixed non-managed preflight orchestration; no queue, model or stop oracle."""
import importlib.util
import copy
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import time

spec = importlib.util.spec_from_file_location('sureal_root_preflight_guards',
    Path(__file__).with_name('preflight_guards.py'))
guards = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guards
spec.loader.exec_module(guards)


def reference(path):
    return {'path': str(Path(path)), 'sha256': guards.digest(path)}


def save(path, value):
    path = Path(path)
    data = (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return reference(path)


def actor_argv(authority, role, base, authorization, output, intent):
    if role not in {'static', 'observer', 'operator'}:
        raise ValueError('only fixed non-managed preflight roles admitted')
    identifier = authority['fixture_id']
    if not identifier or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in identifier):
        raise ValueError('invalid fixed fixture identifier')
    return [authority['tools']['systemd_run'], '--user', '--scope', '--unit',
            'sureal-sustained-collab-'+identifier+'-'+role,
            '--property', 'MemoryMax=268435456', '--property', 'MemorySwapMax=0',
            '--', authority['tools']['python'], '-I', '-B', authority['driver_source'],
            'actor', '--role', role, '--authorization', base['path'],
            '--authorization-sha256', base['sha256'], '--actual-authorization', str(authorization),
            '--output', str(output), '--intent', str(intent)]


def post_process(process):
    try:
        actual = guards.incarnation(process['pid'])
    except FileNotFoundError:
        actual = None
    same = actual is not None and all(actual[key] == process[key]
        for key in ('boot_id', 'pid', 'start_ticks'))
    return {'schema_version': 1, 'kind': 'RecorderPostProcess',
            'observed_ns': time.monotonic_ns(), 'expected_process': process,
            'actual_process': actual, 'same_birth_alive': same}


def actor_binding(base, role, clock):
    kinds = {'operator': 'NativeFixtureLaunchAdmission', 'observer': 'RuntimeProbeAdmission',
             'static': 'StaticRuntimeProbeAdmission'}
    if role not in kinds or base.get('kind') != kinds[role]:
        raise ValueError('fixed actual role/admission mismatch')
    if (type(clock.get('started_ns')) is not int or type(clock.get('started_ms')) is not int or
        clock.get('deadline_ms') != 120000 or
        not 0 <= time.monotonic_ns()-clock['started_ns'] < 120000000000):
        raise ValueError('actual original host command clock required')
    own = guards.process_scope(os.getpid())
    members = [int(row) for row in (Path(own['path'])/'cgroup.procs').read_text().splitlines()]
    if (own['memory_max'] != '268435456' or own['memory_swap_max'] != '0' or own['oom_kill'] != 0 or
        members != [os.getpid()] or not Path(own['path']).name.startswith('sureal-sustained-collab-')):
        raise ValueError('bounded exclusive preflight scope required')
    value = copy.deepcopy(base)
    pin = {key: own[key] for key in ('path', 'device', 'inode')}
    if role == 'operator':
        value['operator_scope'] = pin
    else:
        value['resources']['observer_scope'] = pin
    value['live_clock'] = copy.deepcopy(clock)
    return value


class HostCommand:
    """Actual one-shot subprocess recording; timeout never kills or retries."""
    def __init__(self, root, argv, role, cwd):
        self.root, self.argv, self.cwd, self.role = Path(root), list(argv), cwd, role
        self.root.mkdir(mode=0o700, exist_ok=True)
        if self.root.resolve() != self.root or any(self.root.iterdir()):
            raise ValueError('fresh literal command-record directory required')
        self.started_ns, self.started_ms = time.monotonic_ns(), time.time_ns()//1000000
        self.intent = save(self.root/'intent.json', {'schema_version': 1,
            'kind': 'PreflightHostCommandIntent', 'role': role, 'argv': argv, 'cwd': cwd,
            'started_ms': self.started_ms, 'started_ns': self.started_ns, 'deadline_ms': 120000})
        self.stdout, self.stderr = (self.root/'stdout').open('xb'), (self.root/'stderr').open('xb')
        self.process = subprocess.Popen(argv, cwd=cwd, stdout=self.stdout, stderr=self.stderr,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        save(self.root/'spawn.json', {'schema_version': 1, 'kind': 'PreflightHostSpawn', 'intent': self.intent,
            'pid': self.process.pid, 'spawned_ns': time.monotonic_ns()})

    def finish(self):
        remaining = self.started_ns+120000000000-time.monotonic_ns()
        if remaining <= 0:
            raise TimeoutError('original host120s deadline')
        code = self.process.wait(timeout=remaining/1000000000)
        ended_ns, ended_ms = time.monotonic_ns(), time.time_ns()//1000000
        for stream in (self.stdout, self.stderr):
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
        if sum((self.root/key).stat().st_size for key in ('stdout', 'stderr')) > 33554432:
            raise ValueError('host stdout/stderr output cap')
        return save(self.root/'actual-command.json', {'schema_version': 1,
            'argv': self.argv, 'cwd': self.cwd, 'started_ms': self.started_ms,
            'ended_ms': ended_ms, 'started_ns': self.started_ns, 'ended_ns': ended_ns,
            'exit_code': code, 'stdout': reference(self.root/'stdout'),
            'stderr': reference(self.root/'stderr'), 'intent': self.intent,
            'environment': {'PYTHONDONTWRITEBYTECODE': '1'}})


def validate_driver(value, stage):
    if (stage not in {'static', 'live'} or value.get('kind') != 'NativeFixtureDriverAdmission' or
        value.get('schema_version') != 1 or value.get('stage') != stage):
        raise ValueError('explicit independently reviewed fixed driver admission required')
    source = guards.reopen(value['driver_source'])
    operator = value['operator']
    materialization = json.loads(guards.reopen(operator['materialization']).read_text())
    review = json.loads(guards.reopen(operator['review']).read_text())
    retention = json.loads(guards.reopen(operator['retention']).read_text())
    if (source != Path(__file__).resolve() or
        source != Path(materialization['source'])/'tests/collab/fixture_support/preflight_driver.py' or
        operator['candidate'] != materialization['candidate'] or
        operator['candidate'] != retention['candidate'] or review.get('candidate') != operator['candidate'] or
        review.get('source') != materialization['source'] or review.get('verdict') != 'pass' or
        not review.get('reviewer_native_thread_id')):
        raise ValueError('exact reviewed driver source/raw context required')
    guards.full_manifest(materialization)
    guards.reopen({'path': retention['pack_path'], 'sha256': retention['pack_sha256']})
    for ref in value['tools'].values():
        guards.reopen(ref)
    guards.reopen(value['user_authority'])
    helper = reference(Path(materialization['source'])/'tests/collab/fixture_support/python_import_profile.py')
    bootstrap = guards.profile_bootstrap(value['source_profile'], value['tools']['python'], helper)
    guards.module_closure([Path(materialization['source'])], Path(value['python_stdlib_root']), bootstrap)
    return {'fixture_id': value['fixture_id'], 'driver_source': str(source),
            'tools': {key: ref['path'] for key, ref in value['tools'].items()}}


def actor_program(value, role, authorization, output):
    if role not in {'static', 'observer', 'operator'}:
        raise ValueError('no arbitrary actor program')
    python = (value['tools'] if role == 'operator' else value['fixture_plan']['tools'])['python']['path']
    if role == 'operator':
        return [python, '-I', '-B', value['operator_source']['path'], 'launch',
                '--authorization', str(authorization), '--authorization-sha256', guards.digest(authorization),
                '--output', str(output)]
    return [python, '-B', str(Path(value['auditor']['source'])/'tests/collab/audit_support/runtime_probe.py'),
            '--probe', 'static-preflight' if role == 'static' else 'stop-capability',
            '--authorization', str(authorization), '--output', str(output)]


def actor(args):
    base_ref = {'path': str(args.authorization), 'sha256': args.authorization_sha256}
    base = json.loads(guards.reopen(base_ref).read_text())
    driver = json.loads(guards.reopen(base['driver_admission']).read_text())
    normalized = validate_driver(driver, driver['stage'])
    if driver['stage'] != ('static' if args.role == 'static' else 'live'):
        raise ValueError('actor role cannot cross admitted stages')
    original = json.loads(guards.reopen(driver[args.role+'_admission']).read_text())
    allowed = copy.deepcopy(original)
    allowed['driver_admission'] = base['driver_admission']
    if args.role == 'operator':
        for key in ('observer_ready', 'observer_argv'):
            allowed[key] = base[key]
    if base != allowed:
        raise ValueError('actor base differs from admitted source recipe')
    intent = json.loads(guards.reopen(reference(args.intent)).read_text())
    expected = actor_argv(normalized, args.role, base_ref, args.actual_authorization, args.output, args.intent)
    if (intent.get('kind') != 'PreflightHostCommandIntent' or intent.get('argv') != expected or
        intent.get('role') != args.role or intent.get('cwd') != str(Path.cwd()) or
        guards.argv(os.getpid()) != expected[expected.index('--')+1:]):
        raise ValueError('actual host/actor argv differs from admitted fixed recipe')
    clock = {key: intent[key] for key in ('started_ms', 'started_ns', 'deadline_ms')}
    clock['command_intent'] = reference(args.intent)
    exec_path = args.actual_authorization.with_name(args.actual_authorization.name+'.exec.json')
    clock['actor_exec_path'] = str(exec_path)
    actual = actor_binding(base, args.role, clock)
    auth_ref = save(args.actual_authorization, actual)
    argv = actor_program(actual, args.role, args.actual_authorization, args.output)
    save(exec_path, {'schema_version': 1, 'kind': 'ActorExec', 'role': args.role,
         'command_intent': reference(args.intent), 'authorization': auth_ref,
         'process': guards.incarnation(os.getpid()), 'scope': guards.process_scope(os.getpid()),
         'argv': argv, 'cwd': actual['resources']['output_root'] if args.role != 'operator' else str(Path.cwd()),
         'observed_ns': time.monotonic_ns()})
    if args.role != 'operator':
        os.chdir(actual['resources']['output_root'])
    os.execv(argv[0], argv)


def wait_file(path, deadline, child=None):
    path = Path(path)
    while not path.exists():
        if time.monotonic_ns() >= deadline:
            raise TimeoutError('original driver deadline waiting for immutable handoff')
        if child is not None and child.process.poll() is not None:
            child.finish()
            raise ValueError('actor ended before required handoff; no retry')
        time.sleep(.01)
    if path.resolve() != path or not path.is_file():
        raise ValueError('literal immutable handoff file required')
    return reference(path)


def run_stage(value, stage, output, authority_ref):
    normalized = validate_driver(value, stage)
    output = Path(output)
    if (not output.is_absolute() or output.resolve() != output or output.exists() or
        str(output) != value['output'] or output.parent.stat().st_uid != os.getuid()):
        raise ValueError('fresh admitted driver output required')
    own = guards.process_scope(os.getpid())
    members = [int(pid) for pid in (Path(own['path'])/'cgroup.procs').read_text().splitlines()]
    if (own['memory_max'] != '268435456' or own['memory_swap_max'] != '0' or own['oom_kill'] != 0 or
        members != [os.getpid()]):
        raise ValueError('driver bounded exclusive scope required')
    process = guards.incarnation(os.getpid())
    # Kernel process birth charges startup/imports as well as source/ready work.
    started = process['start_ticks']*(1000000000//os.sysconf('SC_CLK_TCK'))
    deadline = started+120000000000
    def timeout(_signum, _frame):
        raise TimeoutError('original driver120s whole-process bound')
    signal.signal(signal.SIGALRM, timeout)
    remaining = deadline-time.monotonic_ns()
    if remaining <= 0:
        raise TimeoutError('driver process already exceeded120s')
    signal.setitimer(signal.ITIMER_REAL, remaining/1000000000)
    output.mkdir(mode=0o700)
    save(output/'driver-start.json', {'schema_version': 1, 'kind': 'PreflightDriverStart', 'process': process,
         'argv': guards.argv(os.getpid()), 'resources': own, 'started_ns': started,
         'authority': authority_ref, 'stage': stage})
    children = []
    def start(role, base_ref, role_output):
        base = json.loads(guards.reopen(base_ref).read_text())
        base['driver_admission'] = authority_ref
        base_file = output/(role+'-base.json')
        base_ref = save(base_file, base)
        authorization = output/(role+'-authority.json')
        root = output/('host-'+role)
        argv = actor_argv(normalized, role, base_ref, authorization, Path(role_output), root/'intent.json')
        child = HostCommand(root, argv, role, str(output))
        children.append(child)
        return child
    try:
        if stage == 'static':
            base = json.loads(guards.reopen(value['static_admission']).read_text())
            run_output = Path(base['resources']['output_root'])/'run'
            child = start('static', value['static_admission'], run_output)
            command = child.finish()
            if json.loads(guards.reopen(command).read_text())['exit_code'] != 0:
                raise ValueError('static preparation did not complete')
            report = reference(run_output/'static-report.json')
            save(output/'static-bind.json', {'schema_version': 1, 'kind': 'StaticPreflightBinding',
                                           'report': report, 'command': command})
            return {'static_report': report, 'static_command': command}
        # No full cold reconstruction in this live seam; full current equality
        # against the already independently reconstructed static contexts remains.
        proofs = guards.fresh_sources(value)
        for number, proof in enumerate(proofs, 1):
            save(output/f'driver-fresh-manifest-{number}.json', proof)
        base = json.loads(guards.reopen(value['observer_admission']).read_text())
        observer_output = Path(value['fixture_plan']['observer_output'])
        observer = start('observer', value['observer_admission'], observer_output)
        ready_ref = wait_file(observer_output/'observer-ready.json', deadline, observer)
        ready = json.loads(guards.reopen(ready_ref).read_text())
        expected = {'fixture_id': value['fixture_id'], 'static_preflight': value['static_preflight'],
                    'output': str(observer_output), 'source': value['auditor']}
        guards.check_ready(ready, expected, time.monotonic_ns())
        actual_observer_authority = output/'observer-authority.json'
        expected_argv = actor_program(base, 'observer', actual_observer_authority, observer_output)
        if ready['argv'] != expected_argv:
            raise ValueError('ready actual observer argv differs')
        operator_base = json.loads(guards.reopen(value['operator_admission']).read_text())
        operator_base.update(observer_ready=ready_ref, observer_argv=expected_argv)
        op_ref = save(output/'operator-ready-base.json', operator_base)
        # The actor validates this one permitted ready-binding addition to the
        # original immutable operator admission before any native effect.
        operator = start('operator', op_ref, Path(value['fixture_plan']['fixture_output']))
        fixture_output = Path(value['fixture_plan']['fixture_output'])
        launch_ref = wait_file(fixture_output/'fixture-launch.json', deadline, operator)
        launch = json.loads(guards.reopen(launch_ref).read_text())
        payload_ref = wait_file(fixture_output/'payload/payload-running.json', deadline, operator)
        wrapper = {'schema_version': 1, 'kind': 'NativeStopFixture',
            **{key: launch[key] for key in ('fixture_id', 'workspace', 'output', 'common_git', 'command_sha256')},
            'operator': value['operator'], 'fixture_launch': launch_ref,
            'initial_goal': launch['initial_goal'], 'payload_running': payload_ref,
            'notification_channel': launch['notification_channel']}
        wrapper_ref = save(observer_output/'fixture-provenance.json', wrapper)
        save(Path(base['handoff_path']), {'schema_version': 1, 'kind': 'FixtureBound',
            'fixture_id': value['fixture_id'], 'observer_ready': ready_ref,
            'channel': launch['notification_channel'], 'fixture_provenance': wrapper_ref,
            'creation': launch['creation'], 'invocation': launch['invocation'],
            'payload_running': payload_ref, 'bound_ns': time.monotonic_ns()})
        # Reap the exact recorder, never kill or retire it from a status flag.
        while operator.process.poll() is None:
            if time.monotonic_ns() >= deadline:
                raise TimeoutError('original driver120s waiting for recorder')
            if observer.process.poll() is not None:
                observer.finish()
                raise ValueError('observer ended before recorder closure; retained uncertainty')
            time.sleep(.01)
        reaped_ns = time.monotonic_ns()
        command = operator.finish()
        channel = json.loads(guards.reopen(launch['notification_channel']).read_text())
        final = reference(Path(channel['channel_root']['path'])/'channel-final.json')
        post = post_process(channel['operator_process'])
        post_ref = save(output/'recorder-post-process.json', post)
        exit_ref = save(Path(base['recorder_exit_path']), {'schema_version': 1, 'kind': 'RecorderHostExit',
            'fixture_id': value['fixture_id'], 'channel': launch['notification_channel'],
            'final': final, 'process': channel['operator_process'], 'command': command,
            'post_process': post_ref, 'reaped_ns': reaped_ns})
        observer_command = observer.finish()
        return {'recorder_exit': exit_ref, 'observer_command': observer_command}
    except Exception as error:
        save(output/'driver-unknown.json', {'schema_version': 1, 'kind': 'PreflightDriverUncertainty',
            'error_type': type(error).__name__, 'ownership_released': False, 'retry_permitted': False,
            'cleanup_permitted': False, 'children': [{'argv': child.argv, 'host_pid': child.process.pid,
                'returncode': child.process.poll(), 'intent': child.intent} for child in children]})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('static', 'live', 'actor'))
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--authorization-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--role', choices=('static', 'observer', 'operator'))
    parser.add_argument('--actual-authorization', type=Path)
    parser.add_argument('--intent', type=Path)
    args = parser.parse_args()
    if args.mode == 'actor':
        actor(args)
    else:
        ref = {'path': str(args.authorization), 'sha256': args.authorization_sha256}
        value = json.loads(guards.reopen(ref).read_text())
        result = run_stage(value, args.mode, args.output, ref)
        save(args.output/'driver-result.json', {'schema_version': 1, 'kind': 'PreflightDriverResult', **result,
             'task50_accepted': False, 'native_stop_accepted': False, 'cleanup_permitted': False})


if __name__ == '__main__':
    main()
