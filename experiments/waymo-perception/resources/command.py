"""Record the actual bwrap command; never pretend an unwrapped argv executed."""
from pathlib import Path

ARITY={'--unshare-all':0,'--die-with-parent':0,'--clearenv':0,
       '--proc':1,'--dev':1,'--tmpfs':1,'--chdir':1,
       '--ro-bind':2,'--bind':2,'--dev-bind':2,'--setenv':2}
ALIASES={'/tmp/resource-layer','/tmp/resource-output'}


def inspect_command(command):
    """Parse option values as values, never as isolation flags or mounts."""
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


def wrapped_command(command,code,output):
    """Construct the recorded wrapper without changing or executing anything."""
    separator,argv,options=inspect_command(command)
    if any(option in {'--ro-bind','--bind','--dev-bind','--proc','--dev','--tmpfs'} and
           values[-1] in ALIASES for option,values in options):
        raise ValueError('resource mount aliases must be unused')
    bindings=['--ro-bind',str(code),'/tmp/resource-layer','--bind',str(output),'/tmp/resource-output']
    return command[:separator]+bindings+['--',argv[0],'/tmp/resource-layer/execute_worker.py','/tmp/resource-output',*argv[1:]],argv[1:]


def wrap_command(command,code,output):
    code=Path(code);output=Path(output)
    actual,worker_argv=wrapped_command(command,code,output)
    if (any(not p.is_absolute() or not p.is_dir() or any(q.is_symlink() for q in [p,*p.parents]) for p in [code,output]) or
        not (code/'execute_worker.py').is_file() or (code/'execute_worker.py').is_symlink() or
        any(output.iterdir())):
        raise ValueError('regular code and empty resource output required')
    command[:]=actual
    return worker_argv
