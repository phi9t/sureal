"""Record the actual bwrap command; never pretend an unwrapped argv executed."""
from pathlib import Path
from evidence.source_snapshot import is_regular_file
from insula.launch_plan import LaunchPlan, Mount, with_mounts

ARITY={'--unshare-all':0,'--die-with-parent':0,'--clearenv':0,
       '--proc':1,'--dev':1,'--tmpfs':1,'--chdir':1,
       '--ro-bind':2,'--bind':2,'--dev-bind':2,'--setenv':2,'--symlink':2}
ALIASES={'/tmp/resource-layer','/tmp/resource-output','/experiment/resources','/experiment/evidence'}


def inspect_legacy_receipt_command(command):
    """Parse old command receipts as values, never as isolation flags or mounts."""
    if (not isinstance(command,list) or not command or command[0]!='bwrap' or
        any(not isinstance(x,str) or not x for x in command) or command.count('--')!=1):
        raise ValueError('literal bwrap command required')
    separator=command.index('--');flags=set();options=[];index=1
    while index<separator:
        option=command[index];arity=ARITY.get(option)
        if arity is None or index+arity>=separator:
            raise ValueError('declared bwrap options required')
        values=tuple(command[index+1:index+1+arity])
        options.append((option,values));flags.add(option);index+=arity+1
    argv=command[separator+1:]
    if (not {'--unshare-all','--die-with-parent'}<=flags or len(argv)<2 or
        argv[0] not in {'python','/opt/waymo/bin/python'} or
        not Path(argv[1]).is_absolute() or not argv[1].endswith('.py')):
        raise ValueError('isolated namespace and declared original Python worker required')
    return separator,argv,options


inspect_command=inspect_legacy_receipt_command


def wrapped_command(command,code,output):
    """Construct the recorded wrapper without changing or executing anything."""
    separator,argv,options=inspect_legacy_receipt_command(command)
    if any(option in {'--ro-bind','--bind','--dev-bind','--proc','--dev','--tmpfs','--symlink'} and
           values[-1] in ALIASES for option,values in options):
        raise ValueError('resource mount aliases must be unused')
    bindings=['--ro-bind',str(code),'/tmp/resource-layer',
              '--ro-bind',str(code/'resources'),'/experiment/resources',
              '--ro-bind',str(code/'evidence'),'/experiment/evidence',
              '--bind',str(output),'/tmp/resource-output']
    return command[:separator]+bindings+['--',argv[0],'/tmp/resource-layer/resources/execute_worker.py','/tmp/resource-output',*argv[1:]],argv[1:]


def wrapped_rendered_plan_command(command,code,output):
    """Construct the resource wrapper in launch-plan render order."""
    separator,argv,options=inspect_legacy_receipt_command(command)
    if any(option in {'--ro-bind','--bind','--dev-bind','--proc','--dev','--tmpfs','--symlink'} and
           values[-1] in ALIASES for option,values in options):
        raise ValueError('resource mount aliases must be unused')
    devices_at=_plan_device_insertion_index(command,separator)
    tmp_at=_plan_tmp_mounts_index(command,devices_at)
    # render_plan order: other mounts, the /tmp tmpfs, then mounts under /tmp.
    experiment=['--ro-bind',str(code/'resources'),'/experiment/resources',
                '--ro-bind',str(code/'evidence'),'/experiment/evidence']
    under_tmp=['--ro-bind',str(code),'/tmp/resource-layer',
               '--bind',str(output),'/tmp/resource-output']
    return (command[:tmp_at]+experiment+command[tmp_at:devices_at]+under_tmp+command[devices_at:separator]+
            ['--',argv[0],'/tmp/resource-layer/resources/execute_worker.py','/tmp/resource-output',*argv[1:]]),argv[1:]


def _plan_tmp_mounts_index(command,devices_at):
    index=1
    while index<devices_at:
        option=command[index];arity=ARITY.get(option)
        if arity is None:raise ValueError('rendered launch plan option required')
        target=command[index+arity] if arity else None
        if option in {'--ro-bind','--bind','--dev-bind','--tmpfs','--symlink'} and (target=='/tmp' or target.startswith('/tmp/')):
            return index
        index+=1+arity
    return devices_at


def _plan_device_insertion_index(command,separator):
    for index in range(1,separator-1):
        if command[index:index+2]==['--proc','/proc']:
            return index
    raise ValueError('rendered launch plan device mounts required')


def wrapped_plan(plan,code,output):
    """Construct the resource wrapper as launch-plan data."""
    if not isinstance(plan,LaunchPlan):
        raise ValueError('launch plan required')
    argv=list(plan.command)
    if (len(argv)<2 or argv[0] not in {'python','/opt/waymo/bin/python'} or
        not Path(argv[1]).is_absolute() or not argv[1].endswith('.py')):
        raise ValueError('declared original Python worker required')
    if any(mount.kind in {'bind','dev-bind','tmpfs','symlink'} and mount.inside_path in ALIASES for mount in plan.mounts):
        raise ValueError('resource mount aliases must be unused')
    code=Path(code);output=Path(output)
    additions=[
        Mount('resource-layer','bind','/tmp/resource-layer','read_only',code),
        Mount('resource-experiment-resources','bind','/experiment/resources','read_only',code/'resources'),
        Mount('resource-experiment-evidence','bind','/experiment/evidence','read_only',code/'evidence'),
        Mount('resource-output','bind','/tmp/resource-output','writable',output),
    ]
    wrapped=with_mounts(
        plan,
        before_devices=additions,
        command=[argv[0],'/tmp/resource-layer/resources/execute_worker.py','/tmp/resource-output',*argv[1:]],
    )
    return wrapped,argv[1:]


def wrap_command(command,code,output):
    code=Path(code);output=Path(output)
    actual,worker_argv=wrapped_command(command,code,output)
    _validate_resource_wrapper_inputs(code,output)
    command[:]=actual
    return worker_argv


def wrap_plan(plan,code,output):
    code=Path(code);output=Path(output)
    wrapped,worker_argv=wrapped_plan(plan,code,output)
    _validate_resource_wrapper_inputs(code,output)
    return wrapped,worker_argv


def _validate_resource_wrapper_inputs(code,output):
    if (any(not p.is_absolute() or not p.is_dir() or any(q.is_symlink() for q in [p,*p.parents]) for p in [code,output]) or
        not (code/'resources').is_dir() or not (code/'evidence').is_dir() or
        not is_regular_file(code/'resources/execute_worker.py') or
        not is_regular_file(code/'evidence/source_snapshot.py') or
        any(output.iterdir())):
        raise ValueError('regular code and empty resource output required')
