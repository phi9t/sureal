"""Owned raw fixture execution, filesystem snapshots and durable fault injection.

These helpers exercise producer code. They never declare a milestone accepted;
that judgment belongs to the separately authored, immutable auditor.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HOST_OUTPUT = Path(os.environ['SUREAL_COLLAB_HOST_OUTPUT']) if os.environ.get('SUREAL_COLLAB_HOST_OUTPUT') else None
NAMESPACE_OUTPUT = Path(os.environ['SUREAL_COLLAB_NAMESPACE_OUTPUT']) if os.environ.get('SUREAL_COLLAB_NAMESPACE_OUTPUT') else None


def observed_path(path):
    path = Path(path).absolute()
    if NAMESPACE_OUTPUT is not None and path.is_relative_to(NAMESPACE_OUTPUT):
        return str(HOST_OUTPUT/path.relative_to(NAMESPACE_OUTPUT))
    return str(path)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def reference(path):
    return {'path': observed_path(path), 'sha256': sha(path)}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()+b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    return reference(path)


def snapshot(state, destination, manifest):
    state, destination = Path(state), Path(destination)
    shutil.copytree(state, destination, symlinks=True)
    files = {}
    for path in destination.rglob('*'):
        if path.is_symlink():
            raise ValueError('fixture snapshots require physical files')
        if path.is_file():
            files[path.relative_to(destination).as_posix()] = sha(path)
    return write_json(manifest, {'schema_version': 1, 'root': observed_path(destination),
                              'files': files, 'device': state.stat().st_dev})


def command(argv, cwd, directory, timeout=15):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    started = time.time_ns()//1_000_000
    result = subprocess.run(list(map(str, argv)), cwd=cwd, capture_output=True, timeout=timeout,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'LC_ALL': 'C'})
    ended = time.time_ns()//1_000_000
    (directory/'stdout').write_bytes(result.stdout)
    (directory/'stderr').write_bytes(result.stderr)
    return write_json(directory/'actual-command.json', {'schema_version': 1, 'argv': list(map(str, argv)),
        'cwd': str(cwd), 'started_ms': started, 'ended_ms': ended, 'exit_code': result.returncode,
        'timeout_ms': timeout*1000, 'stdout': reference(directory/'stdout'), 'stderr': reference(directory/'stderr')})


def emit(result):
    from scripts._collab.contracts import canonical
    print(canonical(result.wire()).decode(), flush=True)
    return {'ok': 0, 'refused': 2, 'unknown': 3}[result.outcome]


def probe(args):
    from scripts._collab import store as implementation
    from scripts._collab.contracts import Refusal, Result
    state = Path(args.state)
    store = implementation.Store(state)
    name = args.scenario
    if name == 'reconcile' or args.recover:
        try:
            return emit(store.reconcile_journal())
        except Refusal as error:
            return emit(Result(args.operation_id, 'refused', reason=error.reason, evidence={'detail': error.detail}))
    if name == 'prepare':
        effect = store.prepare('fixture-probe', {'schema_version': 1, 'identity': 'unresolved'}, args.operation_id)
        return emit(Result(args.operation_id, 'ok', record_id=effect.record_id, evidence={'state': 'prepared'}))
    if name == 'seed':
        effect = store.prepare('fixture-seed', {'schema_version': 1, 'identity': 'existing-history'}, args.operation_id)
        return emit(store.record(effect, {'schema_version': 1, 'outcome': 'ok', 'fixture_observation': 'seed-only'}))
    if name in ('lock-holder', 'lock-contender'):
        try:
            with store.locked():
                lock = state/'project.lock'
                identity = {'path': observed_path(lock), 'device': lock.stat().st_dev, 'inode': lock.stat().st_ino,
                            'pid': os.getpid()}
                acquired = {**identity, 'event': 'acquired', 'timestamp_ms': time.time_ns()//1_000_000}
                if name == 'lock-holder':
                    write_json(args.lock_ready, {'schema_version': 1, 'acquired': acquired})
                    time.sleep(args.hold_ms/1000)
                    write_json(args.lock_events, {'schema_version': 1, 'events': [acquired,
                        {**identity, 'event': 'released', 'timestamp_ms': time.time_ns()//1_000_000}]})
            return emit(Result(args.operation_id, 'ok'))
        except Refusal as error:
            return emit(Result(args.operation_id, 'refused', reason=error.reason))
    if name == 'input-digest-reuse':
        try:
            store.prepare('fixture-seed', {'schema_version': 1, 'identity': 'changed-input'}, 'seed')
        except Refusal as error:
            return emit(Result(args.operation_id, 'refused', reason=error.reason))
        raise AssertionError('input identity reuse was silently admitted')
    if name not in {'prepared-event', 'immutable-record', 'projection', 'event-fsync', 'record-fsync',
                    'parent-fsync', 'disk-full', 'fsync-failure', 'result-fsync'}:
        raise ValueError('unsupported owned fault probe')
    log = Path(args.fault_log)
    sequence = 0
    actual_fsync = os.fsync
    actual_open = os.open
    actual_write = implementation._write
    def trace(event, relative_path, errno=None):
        nonlocal sequence
        sequence += 1
        value = {'schema_version': 1, 'sequence': sequence, 'operation_id': args.operation_id,
                 'event': event, 'boundary': name, 'relative_path': relative_path}
        if errno is not None:
            value['errno'] = errno
        with log.open('ab') as stream:
            stream.write(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()+b'\n')
            stream.flush()
            actual_fsync(stream.fileno())
    def fsync(fd):
        path = Path(os.readlink('/proc/self/fd/'+str(fd)))
        event_file = path == state/'events.jsonl'
        temporary_record = path.parent == state/'records' and '.pending-' in path.name
        record_parent = path == state/'records'
        trigger = ((event_file and name in ('prepared-event', 'event-fsync', 'fsync-failure', 'result-fsync')) or
                   (temporary_record and name == 'record-fsync') or
                   (record_parent and name == 'parent-fsync'))
        if not trigger:
            return actual_fsync(fd)
        relative = path.relative_to(state).as_posix()
        trace('call', relative)
        if name == 'prepared-event':
            actual_fsync(fd)
            trace('returned', relative)
            trace('interrupted', relative)
            os._exit(86)
        trace('raised', relative, 5)
        raise OSError(5, 'owned injected fsync failure')
    def atomic(path, data, **kwargs):
        interrupted = ((name == 'immutable-record' and Path(path).parent == state/'records') or
                       (name == 'projection' and Path(path) == state/'current.json'))
        relative = Path(path).relative_to(state).as_posix()
        if interrupted:
            trace('call', relative)
        actual_write(path, data, **kwargs)
        if interrupted:
            trace('returned', relative)
            trace('interrupted', relative)
            os._exit(86)
    def open_file(path, flags, *extra):
        if name == 'disk-full' and Path(path) == state/'events.jsonl' and flags & os.O_APPEND:
            trace('call', 'events.jsonl')
            # Create/open the real append target before simulating ENOSPC.
            fd = actual_open(path, flags, *extra)
            os.close(fd)
            trace('raised', 'events.jsonl', 28)
            raise OSError(28, 'owned injected append ENOSPC')
        return actual_open(path, flags, *extra)
    result_effect = store.prepare('fixture-probe', {'schema_version': 1, 'identity': 'unresolved'}, args.operation_id) if name in ('fsync-failure', 'result-fsync') else None
    os.fsync = fsync
    os.open = open_file
    implementation._write = atomic
    try:
        if result_effect is not None:
            store.record(result_effect, {'schema_version': 1, 'outcome': 'ok', 'fixture_observation': 'unconfirmed'})
        else:
            store.prepare('fixture-probe', {'schema_version': 1, 'identity': 'unresolved'}, args.operation_id)
    except OSError as error:
        return emit(Result(args.operation_id, 'unknown', reason='UNKNOWN_EFFECT', evidence={'errno': error.errno}))
    finally:
        os.fsync = actual_fsync
        os.open = actual_open
        implementation._write = actual_write
    raise AssertionError('fault was not reached')



def git(root, *args):
    from scripts._collab.git_workspace import run_git
    return run_git(Path(root), *args)


def git_facts(root):
    def text(*args):
        return git(root, *args).decode().strip()
    index = Path(text('rev-parse', '--path-format=absolute', '--git-path', 'index'))
    refs = dict(line.split(' ', 1) for line in text('for-each-ref', '--format=%(refname) %(objectname)').splitlines())
    return {'schema_version': 1, 'root': observed_path(Path(root).resolve()),
        'common_git_dir': observed_path(text('rev-parse', '--path-format=absolute', '--git-common-dir')),
        'ref': text('symbolic-ref', '-q', 'HEAD'), 'head': text('rev-parse', 'HEAD'),
        'tree': text('rev-parse', 'HEAD^{tree}'), 'index_sha256': sha(index) if index.is_file() else None,
        'refs': refs, 'status_z_hex': git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all').hex(),
        'ignored_z_hex': git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--ignored').hex(),
        'submodule_status': text('submodule', 'status', '--recursive')}


def create_source(root):
    root.mkdir()
    (root/'docs').mkdir()
    git(root, 'init', '--initial-branch=phi9t/mainline')
    git(root, 'config', 'user.name', 'Owned admission fixture')
    git(root, 'config', 'user.email', 'fixture@example.invalid')
    (root/'docs/spec.md').write_text('# Fixture acceptance\nA durable source-pinned admission.\n')
    (root/'docs/plan.md').write_text('# Fixture plan\nIndependent source and result verification.\n')
    git(root, 'add', 'docs/spec.md', 'docs/plan.md')
    git(root, 'commit', '-m', 'Owned fixture definitions')
    return git(root, 'rev-parse', 'HEAD').decode().strip()


def definition(root, source):
    from scripts._collab.contracts import digest
    value = {'schema_version': 1, 'task_id': '49', 'source_commit': source,
             'goal': 'Durable source admission', 'dependencies': []}
    for key, path in (('spec', 'docs/spec.md'), ('plan', 'docs/plan.md')):
        value[key] = {'path': path, 'blob': git(root, 'rev-parse', source+':'+path).decode().strip(),
                      'sha256': hashlib.sha256(git(root, 'show', source+':'+path)).hexdigest()}
    value['revision'] = digest(value)
    return value


def fixture_admission(root, state, base):
    return {'schema_version': 1, 'kind': 'ProjectAdmission', 'project_id': 'owned-negative-fixture49',
        'canonical': str(root), 'state': str(state), 'common_git_dir': str(root/'.git'),
        'ref': 'refs/heads/phi9t/mainline', 'transition_base': base, 'capacity': 2,
        'publication': {'policy': 'local-only'}, 'authority': {'lead': 'sureal/negative-fixture49',
        'ref': 'refs/heads/phi9t/mainline', 'fixture_only': True}, 'tools': {}, 'runtime': {}, 'kata': {}}


def seed_fixture_project(data):
    from scripts._collab.contracts import canonical, digest
    from scripts._collab.store import Store, _write
    # Explicit negative-only fixture authority; never substitutes actual admit_project.
    state = Path(data['state'])
    store = Store(state)
    effect = store.prepare('project-init', {'schema_version': 1, 'admission_digest': digest(data),
                                         'fixture_only': True}, 'fixture-init')
    _write(state/'project.json', canonical(data)+b'\n', immutable=True)
    store.record(effect, {'schema_version': 1, 'outcome': 'ok', 'evidence': {'project_sha256': sha(state/'project.json')}})


def case_record(case, context, manifest, logs):
    write_json(case/'context.json', context)
    write_json(case/'candidate-role-context.json', context)
    ref = write_json(case/'manifest.json', manifest)
    write_json(case/'oracle-inputs.json', {'schema_version': 1, 'fixture_manifest': ref})
    write_json(case/'independent-oracle.json', {'schema_version': 1, 'raw_root': observed_path(case),
                                             'fixture_manifest': ref})
    write_json(case/'raw-state-readback.json', {'schema_version': 1, 'fixture_manifest': ref})
    if 'scenarios' in manifest:
        write_json(case/'fault-boundary-records.json', {'schema_version': 1, 'fixture_manifest': ref})
    if logs:
        # Retain one literal executed command as the case entry receipt. Other
        # actual commands stay in the manifest; no synthetic aggregate argv.
        path = Path(logs[-1]['path'])
        if HOST_OUTPUT is not None and path.is_relative_to(HOST_OUTPUT):
            path = NAMESPACE_OUTPUT/path.relative_to(HOST_OUTPUT)
        shutil.copyfile(path, case/'actual-command.json')
        command_data = json.loads(path.read_bytes())
        stdout = Path(command_data['stdout']['path'])
        if HOST_OUTPUT is not None and stdout.is_relative_to(HOST_OUTPUT):
            stdout = NAMESPACE_OUTPUT/stdout.relative_to(HOST_OUTPUT)
        shutil.copyfile(stdout, case/'execution.log')
    return ref


def publish_case_envelopes(native, destination):
    """Keep raw fixtures at their original identities; publish their envelopes."""
    native, destination = Path(native), Path(destination)
    if not native.is_dir() or native.is_symlink():
        raise ValueError('physical native case directory required')
    envelopes = [path for path in native.iterdir() if path.suffix == '.json' or path.name == 'execution.log']
    if any(path.is_symlink() or not path.is_file() for path in envelopes):
        raise ValueError('physical regular case envelopes required')
    destination.mkdir(exist_ok=False)
    for path in envelopes:
        shutil.copyfile(path, destination/path.name)


def clean_fixtures(case, context):
    scenarios, logs = {}, []
    for name in ('dirty-tracked', 'dirty-index', 'untracked', 'wrong-ref', 'wrong-root', 'alias',
                 'unpinned-task', 'branch-only-spec'):
        work = case/name
        work.mkdir(parents=True)
        root, state = work/'repository', work/'state'
        base = create_source(root)
        source = root
        data = fixture_admission(root, state, base)
        if name == 'dirty-tracked':
            (root/'docs/spec.md').write_text('unreviewed tracked bytes')
        elif name == 'dirty-index':
            (root/'docs/spec.md').write_text('unreviewed staged bytes')
            git(root, 'add', 'docs/spec.md')
        elif name == 'untracked':
            (root/'unique.py').write_text('unique source must be retained')
        elif name == 'wrong-ref':
            git(root, 'switch', '-c', 'not-mainline')
        elif name == 'wrong-root':
            source = root/'inner'
            source.mkdir()
        elif name == 'alias':
            source = work/'alias'
            source.symlink_to(root.name, target_is_directory=True)
        admission_ref = write_json(work/'admission.json', data)
        before = write_json(work/'pre-git.json', git_facts(source))
        argv = [sys.executable, str(ROOT/'scripts/collab.py'), 'init', '--canonical', str(source),
                '--state', str(state), '--admission', str(work/'admission.json'), '--operation-id', name]
        authority_ref = admission_ref
        if name in ('unpinned-task', 'branch-only-spec'):
            if name == 'branch-only-spec':
                git(root, 'switch', '-c', 'branch-only-definition')
                (root/'docs/spec.md').write_text('Unlanded branch-only acceptance')
                git(root, 'add', 'docs/spec.md')
                git(root, 'commit', '-m', 'Not landed')
                branch = git(root, 'rev-parse', 'HEAD').decode().strip()
                task = definition(root, branch)
                git(root, 'switch', 'phi9t/mainline')
            else:
                task = definition(root, base)
                del task['spec']['blob']
                del task['spec']['sha256']
            # Capture refs after preparing the authority, before refusal.
            (work/'pre-git.json').unlink()
            before = write_json(work/'pre-git.json', git_facts(root))
            seed_fixture_project(data)
            authority_ref = write_json(work/'definitions.json', {'schema_version': 1, 'tasks': [task]})
            argv = [sys.executable, str(ROOT/'scripts/collab.py'), 'task', 'import', '--project-state', str(state),
                    '--definitions', str(work/'definitions.json'), '--task-map-output', str(work/'metadata/docs/research/kata-task-map.json'),
                    '--operation-id', name]
        receipt = command(argv, ROOT, work/'command')
        after = write_json(work/'post-git.json', git_facts(source))
        scenarios[name] = {'fixture_root': observed_path(source.resolve()), 'pre_git_facts_path': before,
            'post_git_facts_path': after, 'actual_command_path': receipt,
            'admission_input': admission_ref, 'authority_input': authority_ref}
        logs.append(receipt)
    return case_record(case, context, {'schema_version': 1, 'scenarios': scenarios}, logs)


def fault_fixtures(case, context, corruption=False):
    scenarios, logs = {}, []
    names = ('torn-tail', 'earlier-corruption', 'input-digest-reuse', 'fsync-failure') if corruption else (
        'prepared-event', 'immutable-record', 'projection', 'event-fsync', 'record-fsync', 'parent-fsync', 'disk-full', 'result-fsync')
    for name in names:
        work = case/name
        work.mkdir(parents=True)
        state = work/'state'
        prefix = [sys.executable, str(ROOT/'scripts/collab_live.py'), 'probe']
        seed = command([*prefix, 'seed', '--state', str(state), '--operation-id', 'seed'], ROOT, work/'seed')
        operation_id = 'fault-'+name
        if name in ('fsync-failure', 'result-fsync'):
            command([*prefix, 'prepare', '--state', str(state), '--operation-id', operation_id], ROOT, work/'prepare')
        before = snapshot(state, work/'before', work/'before.json')
        fault_log = work/'fault.jsonl'
        argv = [*prefix, name, '--state', str(state), '--operation-id', operation_id, '--fault-log', str(fault_log)]
        if name == 'torn-tail':
            with (state/'events.jsonl').open('ab') as stream:
                stream.write(b'{"uncompleted":"original torn bytes')
            mutation = seed
        elif name == 'earlier-corruption':
            journal = state/'events.jsonl'
            journal.write_bytes(journal.read_bytes().replace(b'existing-history', b'corrupted-history'))
            mutation = seed
        elif name == 'input-digest-reuse':
            mutation = seed
        else:
            mutation = command(argv, ROOT, work/'operation')
        interrupted = snapshot(state, work/'interrupted', work/'interrupted.json')
        reconcile_argv = [*prefix, name if corruption else 'reconcile', '--state', str(state),
                          '--operation-id', operation_id, '--fault-log', str(fault_log)]
        if name in ('torn-tail', 'earlier-corruption', 'fsync-failure'):
            reconcile_argv.append('--recover')
        recovered = command(reconcile_argv, ROOT, work/'reconcile')
        after = snapshot(state, work/'after', work/'after.json')
        row = {'operation_id': operation_id, 'before_state': before, 'interrupted_state': interrupted,
               'after_state': after, 'actual_command_path': mutation, 'reconcile_command_path': recovered}
        if fault_log.exists():
            row['fault_log'] = reference(fault_log)
        if name == 'input-digest-reuse':
            row['requested_inputs'] = write_json(work/'requested-inputs.json', {'schema_version': 1, 'identity': 'changed-input'})
        scenarios[name] = row
        logs.extend([seed, mutation, recovered])
    manifest = {'schema_version': 1, 'scenarios': scenarios}
    if not corruption:
        work = case/'lock'
        work.mkdir()
        state = work/'state'
        ready, events = work/'ready.json', work/'events.json'
        stdout, stderr = work/'holder.stdout', work/'holder.stderr'
        argv = [sys.executable, str(ROOT/'scripts/collab_live.py'), 'probe', 'lock-holder', '--state', str(state),
                '--operation-id', 'lock-holder', '--lock-ready', str(ready), '--lock-events', str(events), '--hold-ms', '1000']
        started = time.time_ns()//1_000_000
        with stdout.open('xb') as out, stderr.open('xb') as err:
            process = subprocess.Popen(argv, cwd=ROOT, stdout=out, stderr=err, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            deadline = time.monotonic()+5
            while not ready.exists():
                if process.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError('lock holder failed before observed lock')
                time.sleep(.01)
            contender = command([sys.executable, str(ROOT/'scripts/collab_live.py'), 'probe', 'lock-contender',
                '--state', str(state), '--operation-id', 'lock-contender'], ROOT, work/'contender')
            code = process.wait(timeout=5)
        holder = write_json(work/'holder-command.json', {'schema_version': 1, 'argv': argv, 'cwd': str(ROOT),
            'started_ms': started, 'ended_ms': time.time_ns()//1_000_000, 'exit_code': code,
            'stdout': reference(stdout), 'stderr': reference(stderr)})
        manifest.update(lock_holder_command=holder, lock_contender_command=contender, lock_events=reference(events))
        logs.extend([holder, contender])
    return case_record(case, context, manifest, logs)


def offline49(args):
    global HOST_OUTPUT, NAMESPACE_OUTPUT
    output = Path(args.output)
    output.mkdir(exist_ok=False)
    HOST_OUTPUT, NAMESPACE_OUTPUT = Path(args.host_output), output
    os.environ['SUREAL_COLLAB_HOST_OUTPUT'] = str(HOST_OUTPUT)
    os.environ['SUREAL_COLLAB_NAMESPACE_OUTPUT'] = str(NAMESPACE_OUTPUT)
    context = json.loads(Path(args.context).read_bytes())
    admission = json.loads(Path(args.gate_admission).read_bytes())
    if output.stat().st_dev != admission['state_filesystem']['device']:
        raise ValueError('fault fixtures must run on admitted real state filesystem')
    clean_fixtures(output/'clean-ref-and-path-refusals', context)
    fault_fixtures(output/'real-state-fs-durability', context)
    fault_fixtures(output/'journal-corruption', context, corruption=True)
    commands = [command([program, '--version'], ROOT, output/('capability-'+program)) for program in ('git', 'python')]
    write_json(output/'capabilities.json', {'schema_version': 1, 'commands': commands})
    print(json.dumps({'schema_version': 1, 'outcome': 'ok', 'operation': 'offline49',
                      'evidence': observed_path(output), 'acceptance': 'NOT_AUDITED'}), flush=True)
    return 0


def checked_command(argv, cwd, directory, timeout=15):
    ref = command(argv, cwd, directory, timeout)
    record = json.loads(Path(ref['path']).read_bytes())
    if record['exit_code']:
        raise RuntimeError('actual command failed; retained '+ref['path'])
    return ref


def command_stdout(ref):
    record = json.loads(Path(ref['path']).read_bytes())
    return Path(record['stdout']['path']).read_text().strip()


def extract_export(archive, root):
    import tarfile
    from pathlib import PurePosixPath
    root.mkdir()
    with tarfile.open(archive, 'r:') as stream:
        members = []
        seen = set()
        for member in stream:
            name = member.name.removeprefix('./').rstrip('/')
            if name in ('', '.'):
                continue
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or name in seen:
                raise ValueError('unsafe or duplicate actual export member')
            seen.add(name)
            members.append((name, member))
        # Never write through an archive symlink; emit symlinks last.
        for name, member in members:
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                path.mkdir(exist_ok=True)
            elif member.isfile() or member.islnk():
                source = stream.extractfile(member)
                if source is None:
                    raise ValueError('actual export member bytes unavailable')
                with source, path.open('xb') as destination:
                    shutil.copyfileobj(source, destination)
                path.chmod(member.mode)
            elif not member.issym():
                raise ValueError('unadmitted actual export node type')
        for name, member in members:
            path = root/name
            if member.issym():
                path.symlink_to(member.linkname)
        for name, member in reversed(members):
            if member.isdir():
                (root/name).chmod(member.mode)
    return len({item.relative_to(root).as_posix() for item in root.rglob('*')})


def build_runtime(materialization, packages, output, tools):
    materialized = json.loads(Path(materialization).read_bytes())
    source = Path(materialized['source'])
    recipe = source/'experiments/collaboration/runtime'
    requirements = json.loads((recipe/'requirements.lock').read_bytes())
    pinned = requirements['debian_packages']
    actual = {path.name: path for path in Path(packages).glob('*.deb') if path.is_file() and not path.is_symlink()}
    if set(actual) != set(pinned) or any(sha(actual[name]) != pin['sha256'] for name, pin in pinned.items()):
        raise ValueError('offline package union/content differs from immutable candidate lock')
    docker = Path(tools['docker']['path'])
    if not docker.is_file() or docker.is_symlink() or sha(docker) != tools['docker']['sha256']:
        raise ValueError('actual Docker executable differs from pin')
    output = Path(output)
    if output.exists() or output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('fresh separate owned runtime output required')
    output.mkdir()
    context = output/'context'
    context.mkdir()
    (context/'packages').mkdir()
    for name in ('Dockerfile', 'requirements.lock'):
        shutil.copyfile(recipe/name, context/name)
    for name, path in actual.items():
        shutil.copyfile(path, context/'packages'/name)
    # Snapshot the actual build context rather than a list of intended inputs.
    context_ref = write_json(output/'context.json', {'schema_version': 1, 'root': str(context),
        'device': context.stat().st_dev, 'files': {path.relative_to(context).as_posix(): sha(path)
            for path in context.rglob('*') if path.is_file()}})
    base = requirements['base_image']
    base_inspect = checked_command([docker, 'image', 'inspect', '--format', '{{json .RepoDigests}}', base], source, output/'base-inspect')
    iid = output/'image-id'
    build_command = checked_command([docker, 'build', '--network=none', '--memory=536870912',
        '--memory-swap=536870912', '--iidfile', iid, '--file', context/'Dockerfile', context],
        source, output/'build-command', timeout=300)
    image_id = iid.read_text().strip()
    inspect = checked_command([docker, 'image', 'inspect', '--format', '{{.Id}}', image_id], source, output/'image-inspect')
    create = checked_command([docker, 'create', '--network=none', '--memory=536870912', '--memory-swap=536870912',
                             image_id, 'python', '--version'], source, output/'create')
    container_id = command_stdout(create)
    container_inspect = checked_command([docker, 'container', 'inspect', '--format', '{{.Image}}', container_id], source, output/'container-inspect')
    archive = output/'rootfs.tar'
    export = checked_command([docker, 'export', '--output', archive, container_id], source, output/'export', timeout=60)
    rootfs = output/'rootfs'
    members = extract_export(archive, rootfs)
    sys.path.insert(0, str(source/'autonomy'))
    from pipeline.runtime_identity import rootfs_identity
    rootfs_sha = rootfs_identity(rootfs)
    inventory = write_json(output/'rootfs-inventory.json', {'schema_version': 1, 'rootfs_sha256': rootfs_sha,
                                                          'member_count': members})
    manifest = {'schema_version': 1, 'candidate': materialized['candidate'], 'base_image': base,
        'dockerfile_sha256': sha(recipe/'Dockerfile'), 'requirements_sha256': sha(recipe/'requirements.lock'),
        'rootfs_sha256': rootfs_sha, 'image_id': image_id, 'image_id_file': reference(iid), 'container_id': container_id,
        'build_context': context_ref, 'package_artifacts': [reference(path) for name, path in sorted(actual.items())],
        'base_inspect_command': base_inspect, 'build_command': build_command, 'inspect_command': inspect,
        'create_command': create, 'container_inspect_command': container_inspect, 'export_command': export,
        'rootfs_archive': reference(archive), 'rootfs_inventory': inventory, 'capability_commands': []}
    return write_json(output/'build-manifest.json', manifest)



def sqlite_backup(source, destination):
    import sqlite3
    current, retained = sqlite3.connect(source), sqlite3.connect(destination)
    try:
        current.backup(retained)
    finally:
        retained.close()
        current.close()
    return reference(destination)



def selected_project_snapshot(database, project_uid, native_baseline, destination):
    """Retain selected public rows in the native empty schema; never read tokens."""
    import sqlite3
    database, destination = Path(database), Path(destination)
    if destination.exists():
        raise ValueError('fresh selected snapshot destination required')
    with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as source:
        source.row_factory = sqlite3.Row
        source.execute('BEGIN')
        projects = list(source.execute('SELECT * FROM projects WHERE uid=?', (project_uid,)))
        if len(projects) != 1 or projects[0]['uid'] == '00000000000000000000000000':
            raise ValueError('exact selected user project required')
        project_id = projects[0]['id']
        issues = list(source.execute('SELECT * FROM issues WHERE project_id=?', (project_id,)))
        links = list(source.execute('SELECT links.* FROM links JOIN issues a ON links.from_issue_id=a.id '
            'JOIN issues b ON links.to_issue_id=b.id WHERE a.project_id=? OR b.project_id=?', (project_id, project_id)))
        issue_ids = {row['id'] for row in issues}
        if any(row['from_issue_id'] not in issue_ids or row['to_issue_id'] not in issue_ids for row in links):
            raise ValueError('cross-project relation prevents scoped snapshot')
        metadata = list(source.execute("SELECT key,value FROM meta WHERE key IN ('schema_version','instance_uid','created_by_version')"))
    source.close()
    shutil.copyfile(native_baseline, destination)
    with sqlite3.connect(destination) as target:
        for table, rows in (('projects', projects), ('issues', issues), ('links', links)):
            for row in rows:
                columns = list(row.keys())
                if any(not column.replace('_', '').isalnum() for column in columns):
                    raise ValueError('native column identifier unavailable')
                query = 'INSERT INTO "'+table+'" ('+','.join('"'+column+'"' for column in columns)+') VALUES ('+','.join('?' for column in columns)+')'
                target.execute(query, tuple(row))
        for row in metadata:
            target.execute('INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)', tuple(row))
    target.close()
    return reference(destination)

def host_fixtures49(output, context, admission):
    from dataclasses import asdict
    from scripts._collab.contracts import Project, TaskDefinition, canonical, digest
    from scripts._collab.kata import Kata, definition_record
    from scripts._collab.cli import read_status
    binary = Path(admission['tools']['kata']['path'])
    if not binary.is_file() or binary.is_symlink() or sha(binary) != admission['tools']['kata']['sha256']:
        raise ValueError('actual pinned Kata executable required before fixture side effects')
    output = Path(output)
    work = output/'host-kata-fixture'
    home = work/'kata-home'
    scope = admission.get('fixture_authority', {}).get('kata49', {})
    if (not work.is_absolute() or work != work.resolve() or
        scope.get('root') != str(work) or scope.get('home') != str(home) or
        scope.get('restore_home') != str(work/'restore-home') or
        scope.get('project_name') != 'sureal-fixture49' or
        scope.get('foreign_project_name') != 'sureal-foreign49' or
        not isinstance(scope.get('actor'), str) or not scope['actor'].startswith('sureal/') or
        scope.get('database_schema_version') != 25 or scope.get('api_schema_version') != '0.10.0' or
        scope.get('version') != 'v0.14.3'):
        raise ValueError('exact fixture creation scope must be admitted before daemon writes')
    actor = scope['actor']
    work.mkdir(exist_ok=False)
    home.mkdir(mode=0o700)
    environment = {**os.environ, 'KATA_HOME': str(home), 'USER': 'sureal-owned-fixture'}
    commands, count = [], 0
    def call(*arguments, selected_home=home):
        nonlocal count
        count += 1
        selected_home.mkdir(mode=0o700, exist_ok=True)
        directory = work/('native-command-'+str(count))
        directory.mkdir()
        argv = [str(binary), '--json', '--as', actor, *arguments]
        started = time.time_ns()//1_000_000
        actual = subprocess.run(argv, cwd=work, env={**environment, 'KATA_HOME': str(selected_home)},
                                capture_output=True, timeout=15)
        (directory/'stdout').write_bytes(actual.stdout)
        (directory/'stderr').write_bytes(actual.stderr)
        ref = write_json(directory/'actual-command.json', {'schema_version': 1, 'argv': argv, 'cwd': str(work),
            'environment': {'KATA_HOME': str(selected_home)}, 'started_ms': started,
            'ended_ms': time.time_ns()//1_000_000, 'exit_code': actual.returncode,
            'stdout': reference(directory/'stdout'), 'stderr': reference(directory/'stderr')})
        commands.append(ref)
        if actual.returncode:
            raise RuntimeError('retained native Kata fixture failure: '+ref['path'])
        return json.loads(actual.stdout) if actual.stdout else {}, ref
    started, start_command = call('daemon', 'start')
    health, health_command = call('health')
    if (health['db_path'] != str(home/'kata.db') or health.get('schema_version') != scope['database_schema_version']
        or health.get('api_schema_version') != scope['api_schema_version'] or health.get('version') != scope['version']):
        raise RuntimeError('new owned fixture daemon identity unproven; stop withheld')
    baseline = sqlite_backup(home/'kata.db', work/'native-baseline.db')
    identity, _ = call('projects', 'create', scope['project_name'])
    foreign, _ = call('projects', 'create', scope['foreign_project_name'])
    identity = identity['project']
    source = work/'definitions'
    create_source(source)
    (source/'docs/dependent.md').write_text('# Dependent fixture\nBuild safe ownership handoff.\n')
    git(source, 'add', 'docs/dependent.md')
    git(source, 'commit', '-m', 'Dependent owned definition')
    base = git(source, 'rev-parse', 'HEAD').decode().strip()
    project = Project('owned-fixture49', source, work/'state', source/'.git', 'refs/heads/phi9t/mainline', base,
        {'policy': 'local-only'}, {'name': identity['name'], 'project_id': identity['id'], 'project_uid': identity['uid'],
        'db_path': health['db_path'], 'home': str(home), 'database_schema_version': 25, 'api_schema_version': '0.10.0',
        'version': 'v0.14.3', 'started_at': health['started_at']}, {'kata': admission['tools']['kata']}, {},
        {'lead': actor, 'ref': 'refs/heads/phi9t/mainline'}, 'explicit-gate-fixture')
    class CapturedKata(Kata):
        def _call(self, arguments, *, actor=None, log=None):
            nonlocal count
            count += 1
            directory = log or work/('adapter-command-'+str(count))
            response = super()._call(arguments, actor=actor, log=directory)
            commands.append(reference(directory/'actual-command.json'))
            return response
    client = CapturedKata(project)
    def task_definitions():
        initial = definition(source, git(source, 'rev-parse', 'HEAD').decode().strip())
        second = {**initial, 'task_id': '50', 'goal': 'Safe worker ownership handoff', 'dependencies': ['49'],
                  'spec': {'path': 'docs/dependent.md', 'blob': git(source, 'rev-parse', 'HEAD:docs/dependent.md').decode().strip(),
                           'sha256': sha(source/'docs/dependent.md')}}
        del second['revision']
        second['revision'] = digest(second)
        return [TaskDefinition(row['task_id'], row['source_commit'], row['spec'], row['plan'], row['goal'],
                tuple(row['dependencies']), row['revision']) for row in (initial, second)]
    try:
        before_git = write_json(work/'definition-pre-git.json', git_facts(source))
        tasks = task_definitions()
        definitions_ref = write_json(work/'definitions.json', {'schema_version': 1,
            'tasks': {task.task_id: definition_record(task) for task in tasks}})
        client.import_tasks(tasks)
        first = sqlite_backup(home/'kata.db', work/'first.db')
        client.import_tasks(tasks)
        second = sqlite_backup(home/'kata.db', work/'second.db')
        old_brief = {'schema_version': 1, 'fixture_only': True, 'task_id': '49',
                     'definition': definition_record(tasks[0]), 'state': 'immutable-prior-brief'}
        old_before = write_json(work/'old-brief-before.json', old_brief)
        (source/'docs/spec.md').write_text('# Revised fixture acceptance\nRetain exact live ownership and journal proof.\n')
        git(source, 'add', 'docs/spec.md')
        git(source, 'commit', '-m', 'Reviewed fixture revision control')
        revised = task_definitions()
        client.import_tasks(revised)
        revised_db = sqlite_backup(home/'kata.db', work/'revised.db')
        old_after = write_json(work/'old-brief-after.json', old_brief)
        status_before = sqlite_backup(home/'kata.db', work/'status-before.db')
        write_json(work/'status.json', {'schema_version': 1, 'snapshot': asdict(read_status(project))})
        status_after = sqlite_backup(home/'kata.db', work/'status-after.db')
        after_git = write_json(work/'definition-post-git.json', git_facts(source))
        fixture_candidate = git(source, 'rev-parse', 'HEAD').decode().strip()
        auditor_entry = Path(admission['auditor']['source'])/'tests/collab/audit_live.py'
        retention_command = checked_command([sys.executable, auditor_entry, 'retain', '--repository', source,
            '--candidate', fixture_candidate, '--output', work/'definition-pack', '--owner', admission['authors']['producer']],
            ROOT, work/'retain-definition', timeout=60)
        imported_manifest = {'schema_version': 1, 'selected_project_uid': identity['uid'], 'first_db': first,
            'second_db': second, 'revised_db': revised_db, 'definitions': definitions_ref,
            'old_brief_before': old_before, 'old_brief_after': old_after,
            'status_before_db': status_before, 'status_after_db': status_after,
            'definition_repository': str(source), 'definition_retention': reference(work/'definition-pack/retention.json'),
            'definition_pre_git_facts': before_git, 'definition_post_git_facts': after_git,
            'commands': list(commands), 'retention_command': retention_command}
        import_case = output/'fixture-import-revision-status'
        import_case.mkdir()
        case_record(import_case, context, imported_manifest, commands)
        call('--project', scope['foreign_project_name'], 'create', 'Foreign exclusion fixture row')
        source_db = sqlite_backup(home/'kata.db', work/'source.db')
        export_file = work/'project.jsonl'
        client.export(identity['id'], export_file)
        export_commands = [ref for ref in commands if 'export' in json.loads(Path(ref['path']).read_bytes())['argv']]
        target = work/'restored.db'
        _, actual_import = call('import', '--input', str(export_file), '--target', str(target), '--new-instance',
                                selected_home=work/'restore-home')
        restore_manifest = {'schema_version': 1, 'selected_project_uid': identity['uid'],
            'source_db': source_db, 'restored_db': reference(target), 'native_baseline_db': baseline,
            'export': reference(export_file), 'actual_export_command': export_commands[-1],
            'actual_import_command': actual_import}
        restore_case = output/'scoped-queue-restore'
        restore_case.mkdir()
        case_record(restore_case, context, restore_manifest, [export_commands[-1], actual_import])
        write_json(restore_case/'kata-readback.json', {'schema_version': 1, 'source_db': source_db,
            'restored_db': reference(target), 'native_baseline_db': baseline})
        write_json(restore_case/'git-objects-and-status.json', {'schema_version': 1,
            'definition_retention': reference(work/'definition-pack/retention.json'),
            'definition_git_facts': git_facts(source)})
    finally:
        actual_health, _ = call('health')
        if actual_health['db_path'] != str(home/'kata.db') or actual_health['started_at'] != health['started_at']:
            raise RuntimeError('owned daemon stop identity changed; retaining unresolved fixture')
        call('daemon', 'stop')
        stopped_pid = started['pid']
        deadline = time.monotonic()+5
        while Path('/proc/'+str(stopped_pid)).exists():
            try:
                waited, _ = os.waitpid(stopped_pid, os.WNOHANG)
            except ChildProcessError:
                waited = 0
            if waited == stopped_pid:
                break
            if time.monotonic() > deadline:
                raise RuntimeError('owned fixture daemon termination not proved; retaining state')
            time.sleep(.01)
        write_json(work/'daemon-stopped.json', {'schema_version': 1, 'pid': stopped_pid,
                   'home': str(home), 'db_path': health['db_path'], 'terminal_ms': time.time_ns()//1_000_000,
                   'proc_absent': not Path('/proc/'+str(stopped_pid)).exists()})
    return {'schema_version': 1, 'native_baseline_db': baseline, 'home': str(home),
            'db_path': health['db_path'], 'project_uid': identity['uid'], 'pid': started['pid']}

def gate(args):
    from scripts._collab.contracts import Refusal, Result, loads
    materialization = loads(args.materialization.read_bytes())
    admission = loads(args.gate_admission.read_bytes())
    if (args.ticket != '49' or args.candidate_role not in ('implementation', 'metadata') or
        admission.get('kind') != 'GateAdmission' or args.candidate != materialization.get('candidate') or
        admission.get('source', {}).get('candidate') != args.candidate or
        admission['source'].get('materialization_sha256') != sha(args.materialization)):
        return emit(Result('gate49', 'refused', reason='CANDIDATE_MISMATCH', evidence={'detail': 'Exact candidate admission required'}))
    source = Path(materialization['source'])
    if source != source.resolve() or ROOT != source:
        raise Refusal('CANDIDATE_MISMATCH', 'host gate driver must run from the exact materialized candidate')
    for name, loaded in tuple(sys.modules.items()):
        if name == 'scripts._collab' or name.startswith('scripts._collab.'):
            filename = getattr(loaded, '__file__', None)
            if not filename or not Path(filename).resolve().is_relative_to(source/'scripts/_collab'):
                raise Refusal('CANDIDATE_MISMATCH', 'host controller import is outside materialized candidate')
    # The immutable reviewer/admission is checked before any live effects.
    auditor = Path(admission['auditor']['source'])/'tests/collab/audit_live.py'
    reviewer = Path(admission['auditor']['review']['path'])
    review = loads(reviewer.read_bytes())
    if (sha(reviewer) != admission['auditor']['review']['sha256'] or review.get('verdict') != 'pass'
            or review.get('candidate') != admission['auditor']['candidate']):
        raise Refusal('VERIFICATION_INCOMPLETE', 'independent auditor admission required')
    output = Path(args.output)
    output.mkdir(exist_ok=False)
    cases = output/'cases'
    cases.mkdir()
    verified = checked_command([sys.executable, auditor, 'verify-materialization', '--receipt', args.materialization,
                                '--candidate', args.candidate], ROOT, output/'verify-source-before', timeout=60)
    runtime = admission['runtime']
    native = Path(runtime['native_output_directory'])
    native.mkdir(exist_ok=False)
    context = {'schema_version': 1, 'ticket': '49', 'phase': 'gate', 'candidate_role': args.candidate_role,
        'candidate': args.candidate, 'parent': materialization['parent'], 'tree': materialization['tree'],
        'materialization_sha256': sha(args.materialization), 'gate_admission_sha256': sha(args.gate_admission)}
    write_json(native/'input-context.json', context)
    (native/'input-gate-admission.json').write_bytes(args.gate_admission.read_bytes())
    source = Path(materialization['source'])
    reference_root = Path(runtime['reference_path'])
    freeze = runtime['resource_freeze']
    if sha(freeze['path']) != freeze['sha256']:
        raise Refusal('SOURCE_UNAVAILABLE', 'resource source freeze changed')
    freeze_data = json.loads(Path(freeze['path']).read_bytes())
    pins = freeze_data['source_pins']
    sys.path.insert(0, str(reference_root))
    from resources.stage import run_stage
    import importlib.util
    entry_path = source/'experiments/collaboration/runtime/entry.py'
    entry_spec = importlib.util.spec_from_file_location('admitted_collaboration_entry', entry_path)
    entry = importlib.util.module_from_spec(entry_spec)
    entry_spec.loader.exec_module(entry)
    worker = ['python', '/source/scripts/collab_live.py', 'offline49', '--output', '/outputs/offline',
              '--host-output', str(native/'offline'), '--context', '/outputs/input-context.json',
              '--gate-admission', '/outputs/input-gate-admission.json']
    argv = entry.make_plan(runtime['rootfs_path'], reference_root, source, native, worker, runtime['lock']['path'])
    original = list(argv)
    started = time.time_ns()//1_000_000
    with (native/'live.log').open('x') as stream:
        run_stage(argv, str(source), None, stream, runtime['timeout_seconds'],
                  code=Path(freeze_data['snapshot']), current_sources=reference_root/'resources', source_pins=pins,
                  evidence_directory=output/'resource', native_output=native, cap_bytes=runtime['cap_bytes'])
    ended = time.time_ns()//1_000_000
    for case in ('clean-ref-and-path-refusals', 'real-state-fs-durability', 'journal-corruption'):
        publish_case_envelopes(native/'offline'/case, cases/case)
    checked_command([sys.executable, auditor, 'verify-materialization', '--receipt', args.materialization,
                     '--candidate', args.candidate], ROOT, output/'verify-source-after', timeout=60)
    exact = cases/'exact-source-and-rootfs'
    exact.mkdir()
    write_json(exact/'context.json', context)
    write_json(exact/'actual-command.json', {'schema_version': 1, 'argv': argv, 'cwd': str(source),
        'started_ms': started, 'ended_ms': ended, 'exit_code': 0,
        'stdout': reference(output/'resource/execution.log'), 'stderr': reference(output/'resource/execution.log')})
    shutil.copyfile(output/'resource/execution.log', exact/'execution.log')
    source_view = {'schema_version': 1, 'candidate': args.candidate, 'tree': materialization['tree'],
                   'entries': materialization['entries']}
    before_ref = write_json(exact/'pre-source.json', source_view)
    after_ref = write_json(exact/'post-source.json', source_view)
    write_json(exact/'git-objects-and-status.json', {'schema_version': 1,
        'materialization': reference(args.materialization), 'retention': admission['source']['retention'],
        'canonical_git_facts': git_facts(Path(admission['integration']['canonical'])),
        'pre_source_manifest': before_ref, 'post_source_manifest': after_ref})
    build = json.loads(Path(runtime['build_manifest']['path']).read_bytes())
    capability_refs = json.loads((native/'offline/capabilities.json').read_bytes())['commands']
    final_build = {**build, 'capability_commands': capability_refs, 'prior_build_manifest': runtime['build_manifest']}
    build_ref = write_json(exact/'build-manifest.json', final_build)
    write_json(exact/'independent-oracle.json', {'schema_version': 1, 'raw_root': str(exact),
        'resource_proof': reference(output/'resource/resource-admitted.json'), 'pre_source_manifest': before_ref,
        'post_source_manifest': after_ref, 'build_manifest': build_ref})
    # Host Kata fixtures are actual transport effects, distinct from offline Insula.
    host_fixtures49(cases, context, admission)
    if args.candidate_role == 'metadata':
        mapping_case = cases/'map-M-gate'
        mapping_case.mkdir()
        snapshot_command = checked_command([sys.executable, ROOT/'scripts/collab_live.py', 'selected-snapshot',
            '--database', admission['kata']['db_path'], '--project-uid', admission['kata']['project_uid'],
            '--baseline', admission['kata']['native_baseline_db']['path'], '--output', mapping_case/'project.db'],
            ROOT, mapping_case/'snapshot-command')
        project_db = reference(mapping_case/'project.db')
        case_record(mapping_case, context, {'schema_version': 1, 'project_db': project_db}, [snapshot_command])
    from resources.kernel_scope import read_scope
    final_scope = read_scope(runtime['cap_bytes'])
    if final_scope['process_ids'] != [os.getpid()]:
        raise RuntimeError('host fixture lifecycle still has unretained scope members')
    write_json(output/'host-effects-kernel-scope.json', {'schema_version': 1, 'kernel_scope': final_scope})
    print(json.dumps({'schema_version': 1, 'operation': 'gate49', 'outcome': 'ok',
        'evidence': str(output), 'acceptance': 'NOT_AUDITED', 'actual_original_command': original}), flush=True)
    return 0

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    fault = commands.add_parser('probe')
    fault.add_argument('scenario')
    fault.add_argument('--state', type=Path, required=True)
    fault.add_argument('--operation-id', required=True)
    fault.add_argument('--fault-log', type=Path)
    fault.add_argument('--lock-ready', type=Path)
    fault.add_argument('--lock-events', type=Path)
    fault.add_argument('--hold-ms', type=int, default=1000)
    fault.add_argument('--recover', action='store_true')
    offline = commands.add_parser('offline49')
    for name in ('output', 'host-output', 'context', 'gate-admission'):
        offline.add_argument('--'+name, type=Path, required=True)
    build = commands.add_parser('build')
    for name in ('materialization', 'packages', 'output', 'tools'):
        build.add_argument('--'+name, type=Path, required=True)
    selected = commands.add_parser('selected-snapshot')
    for name in ('database', 'baseline', 'output'):
        selected.add_argument('--'+name, type=Path, required=True)
    selected.add_argument('--project-uid', required=True)
    gating = commands.add_parser('gate')
    gating.add_argument('--ticket', required=True)
    gating.add_argument('--candidate', required=True)
    gating.add_argument('--candidate-role', required=True)
    for name in ('materialization', 'gate-admission', 'output'):
        gating.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'gate':
        return gate(args)
    if args.command == 'probe':
        return probe(args)
    if args.command == 'offline49':
        return offline49(args)
    if args.command == 'selected-snapshot':
        result = selected_project_snapshot(args.database, args.project_uid, args.baseline, args.output)
        print(json.dumps({'schema_version': 1, 'snapshot': result, 'acceptance': 'NOT_AUDITED'}), flush=True)
        return 0
    result = build_runtime(args.materialization, args.packages, args.output, json.loads(args.tools.read_bytes())['tools'])
    print(json.dumps({'schema_version': 1, 'build_manifest': result, 'acceptance': 'NOT_AUDITED'}), flush=True)
    return 0
